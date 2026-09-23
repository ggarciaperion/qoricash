#!/usr/bin/env python3
"""
tests/test_eod_deposit_protection.py

Prueba la regla de cierre diario 22:00:
operaciones con transferencia reportada deben conservarse para revisión;
operaciones sin transferencia reportada deben cancelarse.

Ejecutar:
    cd /Users/gianpierre/Desktop/Qoricash/Sistema/qoricash
    python3 -m pytest tests/test_eod_deposit_protection.py -v
"""
import sys
import os
import types
import unittest
from unittest.mock import MagicMock, patch, call
from datetime import datetime


# ── Stubs mínimos ─────────────────────────────────────────────────────────────

def _build_stubs():
    app_pkg = types.ModuleType('app')
    sys.modules.setdefault('app', app_pkg)

    ext = types.ModuleType('app.extensions')
    db = MagicMock()
    ext.db = db
    sys.modules.setdefault('app.extensions', ext)

    fmt = types.ModuleType('app.utils.formatters')
    fmt.now_peru = lambda: datetime(2026, 9, 23, 22, 0, 30)
    sys.modules.setdefault('app.utils.formatters', fmt)
    sys.modules.setdefault('app.utils', types.ModuleType('app.utils'))

    op_mod = types.ModuleType('app.models.operation')
    op_mod.Operation = MagicMock()
    sys.modules.setdefault('app.models.operation', op_mod)

    ns_mod = types.ModuleType('app.services.notification_service')
    ns_mod.NotificationService = MagicMock()
    sys.modules.setdefault('app.services.notification_service', ns_mod)

    return db, op_mod


_DB, _OP_MOD = _build_stubs()

# Importar el módulo bajo prueba directamente
SVC_PATH = os.path.join(os.path.dirname(__file__), '..', 'app', 'services',
                        'operation_expiry_service.py')
_svc = types.ModuleType('expiry_svc_test')
with open(SVC_PATH, encoding='utf-8') as _f:
    exec(compile(_f.read(), SVC_PATH, 'exec'), _svc.__dict__)  # noqa: S102


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_op(op_id, status='Pendiente', deposits=None):
    op = MagicMock()
    op.id = hash(op_id) % 10000
    op.operation_id = op_id
    op.status = status
    op.client_deposits = deposits if deposits is not None else []
    op.client = MagicMock()
    op.client.full_name = 'Cliente Prueba'
    op.updated_at = None
    op.cancellation_reason = None
    op.notes = ''
    return op


def _wire_query(ops_initial, ops_locked=None):
    """
    ops_initial: list returned by the initial bulk query (pending_ops)
    ops_locked:  dict {op_id: op} returned by filter_by(id=...).with_for_update().first()
                 defaults to same objects as ops_initial
    """
    if ops_locked is None:
        ops_locked = {op.id: op for op in ops_initial}

    _OP_MOD.Operation.query.filter.return_value.all.return_value = ops_initial

    def _filter_by(**kw):
        m = MagicMock()
        op_id = kw.get('id')
        locked = ops_locked.get(op_id)
        m.with_for_update.return_value.first.return_value = locked
        return m

    _OP_MOD.Operation.query.filter_by.side_effect = _filter_by


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestEodDepositProtection(unittest.TestCase):

    def setUp(self):
        _DB.session.reset_mock()
        _DB.session.commit.reset_mock()
        _OP_MOD.Operation.query.reset_mock()
        _OP_MOD.Operation.query.filter_by.side_effect = None

    def _run(self):
        with patch.object(_svc, 'NotificationService', MagicMock()), \
             patch('builtins.__import__', side_effect=lambda name, *a, **kw:
                   types.ModuleType(name) if name == 'app.services.wa_bot' else __import__(name, *a, **kw)):
            return _svc.OperationExpiryService.cancel_end_of_day_operations()

    def test_op_sin_deposito_se_cancela(self):
        op = _make_op('EXP-001', deposits=[])
        _wire_query([op])
        count = self._run()
        self.assertEqual(count, 1)
        self.assertEqual(op.status, 'Cancelado')

    def test_op_con_deposito_se_conserva(self):
        op = _make_op('EXP-002', deposits=[{'codigo_operacion': 'BCP123', 'importe': 500}])
        _wire_query([op])
        count = self._run()
        self.assertEqual(count, 0, 'Op con depósito no debe cancelarse')
        self.assertNotEqual(op.status, 'Cancelado',
                            f'Status fue modificado a: {op.status}')

    def test_mix_cancela_solo_sin_deposito(self):
        op_sin = _make_op('EXP-010', deposits=[])
        op_con = _make_op('EXP-011', deposits=[{'codigo_operacion': 'ITB456', 'importe': 200}])
        _wire_query([op_sin, op_con])
        count = self._run()
        self.assertEqual(count, 1)
        self.assertEqual(op_sin.status, 'Cancelado')
        self.assertNotEqual(op_con.status, 'Cancelado')

    def test_revalidacion_concurrente_estado_cambiado(self):
        """Simula que entre la consulta inicial y el lock, alguien completó la op."""
        op_initial = _make_op('EXP-020', status='Pendiente', deposits=[])
        op_locked = _make_op('EXP-020', status='Completada', deposits=[])
        _wire_query([op_initial], ops_locked={op_initial.id: op_locked})
        count = self._run()
        self.assertEqual(count, 0, 'Op ya completada no debe cancelarse')
        self.assertNotEqual(op_locked.status, 'Cancelado')

    def test_revalidacion_deposito_concurrente(self):
        """Simula que el depósito llegó entre la consulta y el lock."""
        op_initial = _make_op('EXP-030', status='Pendiente', deposits=[])
        op_locked = _make_op('EXP-030', status='Pendiente',
                             deposits=[{'codigo_operacion': 'RCP789', 'importe': 100}])
        _wire_query([op_initial], ops_locked={op_initial.id: op_locked})
        count = self._run()
        self.assertEqual(count, 0, 'Depósito concurrente debe proteger la op')
        self.assertNotEqual(op_locked.status, 'Cancelado')

    def test_fuera_de_ventana_horaria_devuelve_cero(self):
        """Fuera de 22:00–22:01 no debe ejecutar nada."""
        op = _make_op('EXP-040', deposits=[])
        _wire_query([op])
        # now_peru está importada por nombre en el módulo bajo prueba
        with patch.object(_svc, 'now_peru', return_value=datetime(2026, 9, 23, 21, 59, 0)):
            count = _svc.OperationExpiryService.cancel_end_of_day_operations()
        self.assertEqual(count, 0)
        self.assertNotEqual(op.status, 'Cancelado')


if __name__ == '__main__':
    unittest.main(verbosity=2)
