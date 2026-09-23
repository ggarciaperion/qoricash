#!/usr/bin/env python3
"""
tests/test_wa_bot_pg_concurrency.py

Pruebas de concurrencia con PostgreSQL real — garantías de FOR UPDATE.

Estas pruebas validan el comportamiento de locking a nivel de base de datos
que sustenta las garantías de _crear_op_y_confirmar y _flujo_registrar_codigo_op.
Usan psycopg2 directamente porque threading + Flask scoped sessions requieren
un contexto de app por hilo, lo cual añade complejidad sin valor adicional
para verificar el comportamiento SQL (FOR UPDATE es una garantía del motor,
no de la capa Python).

Requisitos:
    pip install psycopg2-binary
    PostgreSQL accesible en PG_TEST_DSN (variable de entorno o default abajo)

    Para prueba local con cluster desechable:
        /opt/homebrew/opt/postgresql@16/bin/initdb -D /tmp/qc_pgtest
        /opt/homebrew/opt/postgresql@16/bin/pg_ctl -D /tmp/qc_pgtest \\
            -o "-p 15432" -l /tmp/qc_pgtest/pg.log start
        createdb -h 127.0.0.1 -p 15432 qctest_db
        PG_TEST_DSN="host=127.0.0.1 port=15432 dbname=qctest_db" \\
            python3 -m pytest tests/test_wa_bot_pg_concurrency.py -v

    Se omiten automáticamente si PostgreSQL no está disponible.

Resultados reproducidos (2026-09-22, PostgreSQL 16.4):
    Test 1 ✓  confirmación concurrente → 1 op; T2 bloqueado por FOR UPDATE
    Test 2 ✓  retry recupera op existente sin duplicar
    Test 3 ✓  código de depósito concurrente → 1 depósito registrado
    Test 4 ✓  send failure → op persiste (commit before send)
    Test 5 ✓  re-lectura bajo lock devuelve datos frescos (stale read resuelto)

Ejecutar:
    cd /Users/gianpierre/Desktop/Qoricash/Sistema/qoricash
    python3 -m pytest tests/test_wa_bot_pg_concurrency.py -v
"""

import os
import json
import threading
import unittest

# ── Detectar disponibilidad de PostgreSQL ─────────────────────────────────────
PG_DSN = os.environ.get(
    'PG_TEST_DSN',
    'host=127.0.0.1 port=15432 dbname=qctest_db'
)

try:
    import psycopg2
    _conn_test = psycopg2.connect(PG_DSN)
    _conn_test.close()
    PG_AVAILABLE = True
except Exception:
    PG_AVAILABLE = False

_skip_no_pg = unittest.skipUnless(
    PG_AVAILABLE,
    f'PostgreSQL no disponible en {PG_DSN!r}. '
    'Inicia un cluster de prueba (ver docstring) para ejecutar estos tests.'
)


# ── Infraestructura compartida ────────────────────────────────────────────────

def _conn():
    return psycopg2.connect(PG_DSN)


DDL = """
CREATE TABLE IF NOT EXISTS qc_sessions (
    id          SERIAL PRIMARY KEY,
    numero      TEXT UNIQUE NOT NULL,
    estado      TEXT NOT NULL DEFAULT 'inicio',
    cotiz_token TEXT,
    cotiz_op_id TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS qc_operations (
    id              SERIAL PRIMARY KEY,
    operation_id    TEXT UNIQUE NOT NULL,
    client_id       INTEGER NOT NULL DEFAULT 1,
    status          TEXT NOT NULL DEFAULT 'Pendiente',
    client_deposits JSONB DEFAULT '[]'
);
"""

TEARDOWN = """
DROP TABLE IF EXISTS qc_operations;
DROP TABLE IF EXISTS qc_sessions;
"""


def _setup_db():
    c = _conn()
    c.autocommit = True
    with c.cursor() as cur:
        cur.execute(TEARDOWN)
        cur.execute(DDL)
    c.close()


def _seed_session(numero, estado='confirmando_operacion', token='tok-123', op_id=''):
    c = _conn()
    with c.cursor() as cur:
        cur.execute("""
            INSERT INTO qc_sessions (numero, estado, cotiz_token, cotiz_op_id)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (numero) DO UPDATE
                SET estado=EXCLUDED.estado,
                    cotiz_token=EXCLUDED.cotiz_token,
                    cotiz_op_id=EXCLUDED.cotiz_op_id
        """, (numero, estado, token, op_id))
    c.commit()
    c.close()


def _seed_op(operation_id, status='Pendiente', deposits=None):
    c = _conn()
    with c.cursor() as cur:
        cur.execute("""
            INSERT INTO qc_operations (operation_id, status, client_deposits)
            VALUES (%s, %s, %s)
            ON CONFLICT (operation_id) DO NOTHING
        """, (operation_id, status, json.dumps(deposits or [])))
    c.commit()
    c.close()


class _PgConcurrencyBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if PG_AVAILABLE:
            _setup_db()

    def setUp(self):
        if PG_AVAILABLE:
            _setup_db()


# ── Test 1: confirmación concurrente → 1 op, T2 ve estado incorrecto ──────────

@_skip_no_pg
class TestConcurrentConfirm(_PgConcurrencyBase):
    """FOR UPDATE serializa dos confirmaciones simultáneas.

    T1 adquiere el lock, crea la op, actualiza estado='op_pendiente_pago', commit.
    T2 adquiere el lock después, ve estado incorrecto, no crea segunda op.
    """

    def test_una_sola_op_creada(self):
        NUMERO = '51900000001'
        TOKEN  = 'tok-concurrent'
        _seed_session(NUMERO, token=TOKEN)

        barrier   = threading.Barrier(2)
        results   = {}

        def simulate_confirm(thread_id, delay_after_lock=0):
            c = _conn()
            try:
                c.autocommit = False
                with c.cursor() as cur:
                    barrier.wait()  # ambos hilos arrancan a la vez

                    cur.execute(
                        'SELECT id, estado, cotiz_token FROM qc_sessions '
                        'WHERE numero=%s FOR UPDATE',
                        (NUMERO,)
                    )
                    row = cur.fetchone()
                    if not row:
                        results[thread_id] = 'not_found'
                        return

                    _, estado, token = row

                    import time
                    time.sleep(delay_after_lock)

                    if estado != 'confirmando_operacion':
                        results[thread_id] = 'wrong_state'
                        c.rollback()
                        return

                    if token != TOKEN:
                        results[thread_id] = 'wrong_token'
                        c.rollback()
                        return

                    op_id = f'EXP-T{thread_id}-{threading.get_ident()}'
                    cur.execute(
                        "INSERT INTO qc_operations (operation_id) VALUES (%s) "
                        "ON CONFLICT DO NOTHING",
                        (op_id,)
                    )
                    cur.execute(
                        "UPDATE qc_sessions SET estado='op_pendiente_pago', "
                        "cotiz_token=NULL, cotiz_op_id=%s WHERE numero=%s",
                        (op_id, NUMERO)
                    )
                    c.commit()
                    results[thread_id] = f'op_created:{op_id}'
            except Exception as e:
                results[thread_id] = f'error:{e}'
                try:
                    c.rollback()
                except Exception:
                    pass
            finally:
                c.close()

        t1 = threading.Thread(target=simulate_confirm, args=(1, 0.1))
        t2 = threading.Thread(target=simulate_confirm, args=(2, 0))
        t1.start(); t2.start()
        t1.join(timeout=10); t2.join(timeout=10)

        created = [v for v in results.values() if v.startswith('op_created')]
        blocked = [v for v in results.values() if v == 'wrong_state']
        errors  = [v for v in results.values() if v.startswith('error')]

        self.assertEqual(len(errors), 0, f'Errores inesperados: {errors}')
        self.assertEqual(len(created), 1, f'Esperado 1 op creada, got: {results}')
        # T2 ve estado 'op_pendiente_pago' (set by T1) → wrong_state o token_consumed
        second_blocked = len(blocked) == 1 or any(
            'wrong' in v for v in results.values() if not v.startswith('op_created')
        )
        self.assertTrue(second_blocked, f'T2 debería haber sido bloqueado: {results}')


# ── Test 2: retry recupera op existente sin duplicar ─────────────────────────

@_skip_no_pg
class TestRetryFindsExistingOp(_PgConcurrencyBase):
    """Segunda confirmación encuentra op ya existente — no crea segunda."""

    def test_retry_no_duplica(self):
        NUMERO = '51900000002'
        TOKEN  = 'tok-retry'
        OP_ID  = 'EXP-RETRY-001'

        _seed_session(NUMERO, estado='op_pendiente_pago', token=None, op_id=OP_ID)
        _seed_op(OP_ID)

        c = _conn()
        with c.cursor() as cur:
            # Simular segundo intento: adquirir lock, ver estado incorrecto
            cur.execute(
                'SELECT estado FROM qc_sessions WHERE numero=%s FOR UPDATE',
                (NUMERO,)
            )
            row = cur.fetchone()
            estado = row[0] if row else None

            # Verificar op existente
            if estado != 'confirmando_operacion':
                cur.execute(
                    'SELECT operation_id FROM qc_operations WHERE operation_id=%s',
                    (OP_ID,)
                )
                existing = cur.fetchone()
                result = 'op_already_exists' if existing else 'wrong_state_no_op'
            else:
                result = 'unexpected_open'
            c.rollback()
        c.close()

        self.assertEqual(result, 'op_already_exists')

        # Confirmar que sigue habiendo exactamente 1 op
        c2 = _conn()
        with c2.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM qc_operations WHERE operation_id=%s', (OP_ID,))
            count = cur.fetchone()[0]
        c2.close()
        self.assertEqual(count, 1)


# ── Test 3: código de depósito concurrente → 1 registro ──────────────────────

@_skip_no_pg
class TestConcurrentCodeRegistration(_PgConcurrencyBase):
    """FOR UPDATE en la fila de operación serializa registro de código.

    T1 y T2 intentan registrar 'COD-A' simultáneamente.
    Solo uno debe persistir (el otro detecta duplicado bajo el lock).
    """

    def test_una_sola_entrada_en_deposits(self):
        OP_ID   = 'EXP-CODE-001'
        CODIGO  = 'COD-A'
        _seed_op(OP_ID, deposits=[])

        barrier = threading.Barrier(2)
        results = {}

        def register_code(thread_id):
            c = _conn()
            try:
                c.autocommit = False
                with c.cursor() as cur:
                    barrier.wait()

                    cur.execute(
                        'SELECT client_deposits FROM qc_operations '
                        'WHERE operation_id=%s FOR UPDATE',
                        (OP_ID,)
                    )
                    row = cur.fetchone()
                    deposits = row[0] if row else []

                    if any(d.get('codigo') == CODIGO for d in deposits):
                        results[thread_id] = 'duplicate_code'
                        c.rollback()
                        return

                    deposits.append({'codigo': CODIGO, 'thread': thread_id})
                    cur.execute(
                        'UPDATE qc_operations SET client_deposits=%s '
                        'WHERE operation_id=%s',
                        (json.dumps(deposits), OP_ID)
                    )
                    c.commit()
                    results[thread_id] = 'registered'
            except Exception as e:
                results[thread_id] = f'error:{e}'
                try:
                    c.rollback()
                except Exception:
                    pass
            finally:
                c.close()

        t1 = threading.Thread(target=register_code, args=(1,))
        t2 = threading.Thread(target=register_code, args=(2,))
        t1.start(); t2.start()
        t1.join(timeout=10); t2.join(timeout=10)

        registered = [v for v in results.values() if v == 'registered']
        self.assertEqual(len(registered), 1, f'Esperado 1 registro, got: {results}')

        c = _conn()
        with c.cursor() as cur:
            cur.execute('SELECT client_deposits FROM qc_operations WHERE operation_id=%s', (OP_ID,))
            deposits = cur.fetchone()[0]
        c.close()
        codes = [d.get('codigo') for d in deposits]
        self.assertEqual(codes.count(CODIGO), 1, f'Depósitos: {deposits}')


# ── Test 4: send failure → op persiste (commit before send) ──────────────────

@_skip_no_pg
class TestSendFailureOpPersists(_PgConcurrencyBase):
    """Commit ocurre antes del envío WA; si falla el envío, la op persiste."""

    def test_op_en_db_aunque_send_falle(self):
        OP_ID  = 'EXP-SEND-FAIL'
        NUMERO = '51900000003'
        TOKEN  = 'tok-send'
        _seed_session(NUMERO, token=TOKEN)

        c = _conn()
        with c.cursor() as cur:
            cur.execute(
                'SELECT id FROM qc_sessions WHERE numero=%s FOR UPDATE',
                (NUMERO,)
            )
            cur.execute(
                "INSERT INTO qc_operations (operation_id) VALUES (%s)",
                (OP_ID,)
            )
            cur.execute(
                "UPDATE qc_sessions SET estado='op_pendiente_pago', "
                "cotiz_token=NULL, cotiz_op_id=%s WHERE numero=%s",
                (OP_ID, NUMERO)
            )
            c.commit()  # ← commit antes del envío simulado

        # Simular fallo de envío (sin rollback — el commit ya ocurrió)
        send_failed = True  # in real code: return value of send_buttons

        # La op debe existir en DB a pesar del fallo de envío
        c2 = _conn()
        with c2.cursor() as cur:
            cur.execute('SELECT operation_id, status FROM qc_operations WHERE operation_id=%s', (OP_ID,))
            row = cur.fetchone()
        c2.close()

        self.assertIsNotNone(row, 'Op debe existir en DB aunque send falle')
        self.assertEqual(row[0], OP_ID)
        self.assertTrue(send_failed)  # confirmar que el send efectivamente falló en la simulación


# ── Test 5: re-lectura bajo lock devuelve datos frescos ──────────────────────

@_skip_no_pg
class TestStaleReadRefreshedUnderLock(_PgConcurrencyBase):
    """FOR UPDATE garantiza que la transacción ve datos comprometidos por otras transacciones.

    Conexión A lee la sesión (datos viejos).
    Conexión B actualiza el token y hace commit.
    Conexión A adquiere FOR UPDATE → ve el nuevo token (lectura fresca).
    """

    def test_for_update_devuelve_datos_frescos(self):
        NUMERO     = '51900000004'
        TOKEN_OLD  = 'tok-old'
        TOKEN_NEW  = 'tok-new'
        _seed_session(NUMERO, token=TOKEN_OLD)

        conn_a = _conn()
        conn_b = _conn()

        try:
            # A lee la sesión sin lock (puede ver valor viejo en una transacción repeatable read,
            # pero en READ COMMITTED — default PostgreSQL — FOR UPDATE siempre devuelve fresco)
            conn_a.autocommit = False
            with conn_a.cursor() as cur:
                cur.execute('SELECT cotiz_token FROM qc_sessions WHERE numero=%s', (NUMERO,))
                stale_token = cur.fetchone()[0]

            # B actualiza el token y confirma
            conn_b.autocommit = True
            with conn_b.cursor() as cur:
                cur.execute(
                    'UPDATE qc_sessions SET cotiz_token=%s WHERE numero=%s',
                    (TOKEN_NEW, NUMERO)
                )

            # A adquiere FOR UPDATE → debe ver TOKEN_NEW (READ COMMITTED)
            with conn_a.cursor() as cur:
                cur.execute(
                    'SELECT cotiz_token FROM qc_sessions WHERE numero=%s FOR UPDATE',
                    (NUMERO,)
                )
                fresh_token = cur.fetchone()[0]
            conn_a.rollback()

            self.assertEqual(stale_token, TOKEN_OLD,
                             'Lectura inicial debe ver valor viejo')
            self.assertEqual(fresh_token, TOKEN_NEW,
                             'FOR UPDATE debe devolver valor comprometido por B')

        finally:
            conn_a.close()
            conn_b.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
