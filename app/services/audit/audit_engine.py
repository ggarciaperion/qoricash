"""
Agente Contable IA — Motor Central de Auditoría
================================================
Ejecuta la auditoría diaria completa del sistema QoriCash.

Principio fundamental:
  Single Source of Truth = journal_entries + journal_entry_lines
  Todos los módulos se validan contra el Libro Diario, nunca al revés.

El agente:
  ✅ Lee para validar
  ✅ Genera asientos de depreciación (única acción activa permitida)
  ✅ Registra hallazgos en AuditReport
  ✅ Emite alertas vía sistema de notificaciones
  ❌ NUNCA modifica asientos existentes
  ❌ NUNCA elimina datos
  ❌ NUNCA corrige saldos silenciosamente

Módulos de validación:
  1. Operaciones completadas sin asiento contable
  2. Partida doble (DEBE ≠ HABER)
  3. Conciliación Tesorería vs Libro Diario (SSoT)
  4. Gastos sin comprobante
  5. Activos fijos — depreciación mensual automática
  6. Cierre diario — validación apertura/cierre
  7. Integridad del período contable
  8. Estado de Resultados del período
"""
import logging
import time
from datetime import date, datetime
from decimal import Decimal

from app.extensions import db

logger = logging.getLogger(__name__)

# ── Constantes ────────────────────────────────────────────────────────────────
DEMO_USERNAME = 'demo_trader'


class AuditEngine:
    """
    Motor de auditoría contable. Instanciar con año/mes del período a auditar.
    Llamar a run() para ejecutar la auditoría completa.
    """

    def __init__(self, year: int, month: int,
                 audit_date: date = None,
                 trigger: str = 'cron',
                 executed_by_id: int = None,
                 auto_depreciate: bool = True):
        self.year          = year
        self.month         = month
        self.audit_date    = audit_date or date.today()
        self.trigger       = trigger
        self.executed_by   = executed_by_id
        self.auto_depreciate = auto_depreciate

    # ─────────────────────────────────────────────────────────────────────────
    # Punto de entrada principal
    # ─────────────────────────────────────────────────────────────────────────

    def run(self):
        """
        Ejecuta la auditoría completa y persiste el AuditReport.
        Retorna la instancia de AuditReport guardada.
        """
        from app.models.audit_report import (
            AuditReport, ESTADO_APROBADO,
            SEVERIDAD_INFO, SEVERIDAD_ALERTA, SEVERIDAD_CRITICO,
        )
        from app.models.accounting_period import AccountingPeriod

        start = time.time()
        logger.info(
            f'[AuditEngine] 🔍 Iniciando auditoría {self.year}/{self.month:02d} '
            f'trigger={self.trigger}'
        )

        periodo = AccountingPeriod.query.filter_by(
            year=self.year, month=self.month
        ).first()
        period_label = f'{self.month:02d}/{self.year}'

        # Crear el reporte
        report = AuditReport(
            audit_date   = self.audit_date,
            period_label = period_label,
            estado       = ESTADO_APROBADO,
            trigger      = self.trigger,
            executed_by  = self.executed_by,
        )
        db.session.add(report)
        db.session.flush()

        # ── 1. Operaciones sin asiento ────────────────────────────────────────
        try:
            self._check_ops_sin_asiento(report)
        except Exception as e:
            logger.error(f'[AuditEngine] check_ops_sin_asiento: {e}')

        # ── 2. Partida doble ─────────────────────────────────────────────────
        try:
            self._check_partida_doble(report)
        except Exception as e:
            logger.error(f'[AuditEngine] check_partida_doble: {e}')

        # ── 3. Conciliación Tesorería vs Diario ───────────────────────────────
        try:
            self._check_conciliacion(report)
        except Exception as e:
            logger.error(f'[AuditEngine] check_conciliacion: {e}')

        # ── 4. Gastos sin comprobante ─────────────────────────────────────────
        try:
            self._check_gastos_sin_comprobante(report)
        except Exception as e:
            logger.error(f'[AuditEngine] check_gastos_sin_comprobante: {e}')

        # ── 5. Depreciación automática ────────────────────────────────────────
        try:
            self._check_y_depreciar(report)
        except Exception as e:
            logger.error(f'[AuditEngine] check_y_depreciar: {e}')

        # ── 6. Cierre diario ──────────────────────────────────────────────────
        try:
            self._check_cierre_diario(report)
        except Exception as e:
            logger.error(f'[AuditEngine] check_cierre_diario: {e}')

        # ── 7. Integridad del período ─────────────────────────────────────────
        try:
            self._check_integridad_periodo(report, periodo)
        except Exception as e:
            logger.error(f'[AuditEngine] check_integridad_periodo: {e}')

        # ── 8. Estado de Resultados ───────────────────────────────────────────
        try:
            self._calcular_estado_resultados(report)
        except Exception as e:
            logger.error(f'[AuditEngine] calcular_estado_resultados: {e}')

        # ── Finalizar ─────────────────────────────────────────────────────────
        elapsed = round(time.time() - start, 2)
        report.execution_seconds = elapsed

        try:
            db.session.commit()
            logger.info(
                f'[AuditEngine] ✅ Auditoría completada en {elapsed}s — '
                f'Estado: {report.estado} — Hallazgos: {report.total_hallazgos}'
            )
        except Exception as exc:
            db.session.rollback()
            logger.error(f'[AuditEngine] Error al guardar AuditReport: {exc}')
            report.error_message = str(exc)

        # ── Emitir alertas si hay críticos ────────────────────────────────────
        if report.hallazgos_criticos > 0:
            try:
                self._emitir_alerta_critica(report)
            except Exception as e:
                logger.warning(f'[AuditEngine] Error al emitir alerta: {e}')

        return report

    # ─────────────────────────────────────────────────────────────────────────
    # Módulos de validación
    # ─────────────────────────────────────────────────────────────────────────

    def _check_ops_sin_asiento(self, report):
        """
        Verifica que todas las operaciones Completadas del período
        tengan su asiento contable generado en el Libro Diario.
        """
        from app.models.audit_report import SEVERIDAD_CRITICO, SEVERIDAD_ALERTA
        from app.models.operation import Operation
        from app.models.journal_entry import JournalEntry
        from app.models.user import User
        from sqlalchemy import func, extract

        demo_id = User.get_demo_user_id()

        ids_con_asiento = {
            r[0] for r in db.session.query(JournalEntry.source_id).filter(
                JournalEntry.source_type == 'operation',
                JournalEntry.status == 'activo',
            ).all() if r[0]
        }

        q = Operation.query.filter(
            Operation.status == 'Completada',
            extract('year',  Operation.completed_at) == self.year,
            extract('month', Operation.completed_at) == self.month,
            ~Operation.id.in_(ids_con_asiento) if ids_con_asiento else True,
        )
        if demo_id:
            q = q.filter(Operation.user_id != demo_id)

        ops = q.all()
        report.ops_sin_asiento = len(ops)

        if ops:
            ids_str = ', '.join(op.operation_id for op in ops[:10])
            sev = SEVERIDAD_CRITICO if len(ops) > 5 else SEVERIDAD_ALERTA
            report.add_hallazgo(
                modulo='Libro Diario',
                severidad=sev,
                titulo=f'{len(ops)} operación(es) completada(s) sin asiento contable',
                detalle=(
                    f'Las siguientes operaciones no tienen asiento en el Libro Diario: '
                    f'{ids_str}{"..." if len(ops) > 10 else ""}. '
                    f'Período: {self.month:02d}/{self.year}.'
                ),
                accion=(
                    'Ir a Contabilidad → Períodos → "Generar Asientos Retroactivos" '
                    f'para {self.month:02d}/{self.year}.'
                ),
            )
        else:
            logger.info('[AuditEngine] ✅ Todas las operaciones tienen asiento')

    def _check_partida_doble(self, report):
        """
        Valida que DEBE == HABER en todos los asientos del período.
        Un asiento descuadrado es un error CRÍTICO.
        """
        from app.models.audit_report import SEVERIDAD_CRITICO
        from .reconciliation import run_partida_doble_check

        descuadrados = run_partida_doble_check(self.year, self.month)
        report.asientos_descuadrados = len(descuadrados)

        if descuadrados:
            detalle = '; '.join(
                f"{d['entry_number']} Δ S/{d['diferencia']:.2f}"
                for d in descuadrados[:5]
            )
            report.add_hallazgo(
                modulo='Partida Doble',
                severidad=SEVERIDAD_CRITICO,
                titulo=f'{len(descuadrados)} asiento(s) con DEBE ≠ HABER',
                detalle=(
                    f'Asientos descuadrados: {detalle}. '
                    'Violación del principio de partida doble. '
                    'El Libro Diario no puede cerrarse con esta diferencia.'
                ),
                accion=(
                    'Revisar cada asiento en Contabilidad → Libro Diario. '
                    'Anular y recrear el asiento con los valores correctos.'
                ),
            )

    def _check_conciliacion(self, report):
        """
        Concilia Tesorería (BankBalance) vs Libro Diario (SSoT).
        Detecta diferencias por banco y moneda.
        """
        from app.models.audit_report import SEVERIDAD_ALERTA, SEVERIDAD_CRITICO
        from .reconciliation import run_conciliacion

        resultado = run_conciliacion()

        diferencias = [
            (code, data) for code, data in resultado.items()
            if not data['ok'] and data['diferencia'] is not None
        ]

        report.diferencias_banco = len(diferencias)
        report.conciliacion = {
            code: {
                'label':           d['label'],
                'moneda':          d['moneda'],
                'saldo_journal':   float(d['saldo_journal']),
                'saldo_tesoreria': float(d['saldo_tesoreria']) if d['saldo_tesoreria'] is not None else None,
                'diferencia':      float(d['diferencia']) if d['diferencia'] is not None else None,
                'ok':              d['ok'],
                'observacion':     d['observacion'],
            }
            for code, d in resultado.items()
        }

        if diferencias:
            for code, data in diferencias:
                dif_abs = abs(float(data['diferencia']))
                sev = SEVERIDAD_CRITICO if dif_abs > 100 else SEVERIDAD_ALERTA
                report.add_hallazgo(
                    modulo='Conciliación Bancaria',
                    severidad=sev,
                    titulo=f'Diferencia {data["moneda"]} {dif_abs:,.2f} en {data["label"]} ({code})',
                    detalle=data['observacion'],
                    accion=(
                        f'Ir a Contabilidad → Caja y Bancos → cuenta {code} → '
                        '"Conciliar". Ingresar el saldo real del estado bancario '
                        'para generar el asiento de ajuste.'
                    ),
                )
        else:
            logger.info('[AuditEngine] ✅ Tesorería concilia con Libro Diario')

    def _check_gastos_sin_comprobante(self, report):
        """
        Detecta gastos registrados sin comprobante ni proveedor identificado.
        """
        from app.models.audit_report import SEVERIDAD_ALERTA
        from app.models.expense_record import ExpenseRecord
        from sqlalchemy import extract

        gastos = ExpenseRecord.query.filter(
            extract('year',  ExpenseRecord.expense_date) == self.year,
            extract('month', ExpenseRecord.expense_date) == self.month,
        ).all()

        sin_comprobante = [
            g for g in gastos
            if not g.voucher_number and not g.supplier_ruc
            and g.expense_type not in ('tributo',)
        ]

        report.gastos_sin_comprobante = len(sin_comprobante)

        if sin_comprobante:
            total = sum(float(g.amount_pen) for g in sin_comprobante)
            report.add_hallazgo(
                modulo='Gastos',
                severidad=SEVERIDAD_ALERTA,
                titulo=(
                    f'{len(sin_comprobante)} gasto(s) sin comprobante '
                    f'(S/ {total:,.2f} total)'
                ),
                detalle=(
                    f'{len(sin_comprobante)} gastos no tienen número de comprobante '
                    f'ni RUC de proveedor. Monto total: S/ {total:,.2f}. '
                    'SUNAT requiere sustento documental para deducir gastos.'
                ),
                accion=(
                    'Ir a Contabilidad → Gastos. Editar cada gasto e ingresar '
                    'el número de comprobante y RUC del proveedor.'
                ),
            )

    def _check_y_depreciar(self, report):
        """
        Verifica activos fijos con depreciación pendiente.
        Si auto_depreciate=True, genera los asientos automáticamente.
        """
        from app.models.audit_report import (
            SEVERIDAD_ALERTA, SEVERIDAD_INFO
        )
        from .depreciation import (
            check_activos_pendientes, run_depreciacion_mensual
        )

        pendientes = check_activos_pendientes(self.year, self.month)
        report.activos_sin_depreciar = len(pendientes)

        if not pendientes:
            logger.info('[AuditEngine] ✅ Depreciación al día')
            return

        if self.auto_depreciate:
            resultado = run_depreciacion_mensual(
                self.year, self.month,
                created_by_id=self.executed_by
            )
            report.activos_sin_depreciar = len(resultado.get('errores', []))

            if resultado['generados'] > 0:
                report.add_hallazgo(
                    modulo='Activos Fijos',
                    severidad=SEVERIDAD_INFO,
                    titulo=(
                        f'✅ Depreciación automática: {resultado["generados"]} '
                        f'asiento(s) generado(s) — S/ {resultado["total_depreciation"]:,.2f}'
                    ),
                    detalle=(
                        f'El agente generó automáticamente {resultado["generados"]} '
                        f'asiento(s) de depreciación para el período '
                        f'{self.month:02d}/{self.year}. '
                        f'Total depreciado: S/ {resultado["total_depreciation"]:,.2f}.'
                    ),
                    accion='Verificar en Contabilidad → Activos Fijos → columna Depreciación.',
                )

            if resultado.get('errores'):
                report.add_hallazgo(
                    modulo='Activos Fijos',
                    severidad=SEVERIDAD_ALERTA,
                    titulo=f'{len(resultado["errores"])} activo(s) con error en depreciación',
                    detalle='; '.join(resultado['errores'][:5]),
                    accion='Revisar el período contable y el estado del activo.',
                )
        else:
            total_mens = sum(p['monthly_depreciation'] for p in pendientes)
            report.add_hallazgo(
                modulo='Activos Fijos',
                severidad=SEVERIDAD_ALERTA,
                titulo=(
                    f'{len(pendientes)} activo(s) sin depreciación en '
                    f'{self.month:02d}/{self.year} '
                    f'(S/ {total_mens:,.2f}/mes)'
                ),
                detalle=(
                    f'Activos pendientes: '
                    f'{", ".join(p["asset_code"] for p in pendientes[:5])}.'
                ),
                accion=(
                    'Ir a Contabilidad → Activos Fijos → "Depreciar período" '
                    f'para {self.month:02d}/{self.year}.'
                ),
            )

    def _check_cierre_diario(self, report):
        """
        Verifica que el día auditado tenga cierre diario validado en Tesorería.
        """
        from app.models.audit_report import SEVERIDAD_ALERTA
        from app.models.daily_closure import DailyClosure

        cierre = DailyClosure.query.filter_by(
            closure_date=self.audit_date
        ).first()

        if not cierre:
            report.add_hallazgo(
                modulo='Cierre Diario',
                severidad=SEVERIDAD_ALERTA,
                titulo=f'Sin cierre diario registrado para {self.audit_date.strftime("%d/%m/%Y")}',
                detalle=(
                    f'No existe registro de cierre diario para '
                    f'{self.audit_date.strftime("%d/%m/%Y")}. '
                    'El cierre diario es obligatorio para validar saldos.'
                ),
                accion='Ir a Finanzas → Control → registrar cierre del día.',
            )
        elif cierre.status != DailyClosure.STATUS_VALIDADO:
            report.add_hallazgo(
                modulo='Cierre Diario',
                severidad=SEVERIDAD_ALERTA,
                titulo=f'Cierre diario {self.audit_date.strftime("%d/%m/%Y")} en estado: {cierre.status}',
                detalle=(
                    f'El cierre del día existe pero no ha sido validado por el responsable. '
                    f'Estado actual: {cierre.status}.'
                ),
                accion='Ir a Finanzas → Control → validar el cierre del día.',
            )
        elif cierre.has_discrepancies:
            report.add_hallazgo(
                modulo='Cierre Diario',
                severidad=SEVERIDAD_ALERTA,
                titulo=(
                    f'Cierre diario con discrepancias — '
                    f'USD {float(cierre.max_discrepancy_usd):,.2f} / '
                    f'PEN {float(cierre.max_discrepancy_pen):,.2f}'
                ),
                detalle=(
                    f'El cierre del {self.audit_date.strftime("%d/%m/%Y")} '
                    f'fue validado pero registra diferencias entre saldos '
                    f'del sistema y saldos reales. '
                    f'Razón declarada: {cierre.discrepancy_reason or "no indicada"}.'
                ),
                accion=(
                    'Verificar movimientos del día y registrar asiento de '
                    'ajuste/conciliación si corresponde.'
                ),
            )

    def _check_integridad_periodo(self, report, periodo):
        """
        Verifica la integridad del período contable:
        - Que el período exista
        - Que no haya asientos en períodos cerrados (excepto reversiones)
        """
        from app.models.audit_report import SEVERIDAD_CRITICO, SEVERIDAD_ALERTA
        from app.models.journal_entry import JournalEntry
        from app.models.accounting_period import AccountingPeriod
        from sqlalchemy import extract

        if not periodo:
            report.add_hallazgo(
                modulo='Período Contable',
                severidad=SEVERIDAD_ALERTA,
                titulo=f'Período {self.month:02d}/{self.year} no existe',
                detalle=(
                    f'El período contable {self.month:02d}/{self.year} '
                    f'no está registrado en la base de datos.'
                ),
                accion=(
                    'Ir a Contabilidad → Períodos → crear período '
                    f'{self.month:02d}/{self.year}.'
                ),
            )
            return

        # Verificar asientos huérfanos (source_id sin operación existente)
        # Solo para asientos de tipo operacion_completada
        from app.models.operation import Operation

        entry_ids_ops = db.session.query(JournalEntry.source_id).filter(
            JournalEntry.source_type == 'operation',
            JournalEntry.status == 'activo',
            extract('year',  JournalEntry.entry_date) == self.year,
            extract('month', JournalEntry.entry_date) == self.month,
        ).all()

        op_ids = {r[0] for r in entry_ids_ops if r[0]}
        existing_op_ids = {
            r[0] for r in db.session.query(Operation.id).filter(
                Operation.id.in_(op_ids)
            ).all()
        } if op_ids else set()

        huerfanos = op_ids - existing_op_ids
        if huerfanos:
            report.add_hallazgo(
                modulo='Integridad',
                severidad=SEVERIDAD_CRITICO,
                titulo=f'{len(huerfanos)} asiento(s) con operación origen eliminada',
                detalle=(
                    f'Existen asientos que referencian operaciones que ya no '
                    f'existen en la base de datos: IDs {list(huerfanos)[:10]}. '
                    'Posible eliminación de operaciones sin anular asientos.'
                ),
                accion='Revisar log de auditoría. Anular los asientos huérfanos manualmente.',
            )

    def _calcular_estado_resultados(self, report):
        """
        Calcula el Estado de Ganancias y Pérdidas del período
        desde el Libro Diario (SSoT) y lo almacena en las métricas del reporte.

        Separación de gastos por entry_type para evitar mezcla con
        depreciaciones automáticas (6814) y pérdidas FX de calce (6762):
          gastos_operativos → entry_type IN ('gasto','activo_fijo','manual')
                              Coincide con /contabilidad/gastos (ExpenseRecord)
          gastos_depreciacion → entry_type = 'depreciacion'
          perdidas_fx         → cuenta 6762, entry_type = 'calce_netting'
        """
        from app.models.journal_entry import JournalEntry
        from app.models.journal_entry_line import JournalEntryLine
        from sqlalchemy import func, extract

        base_f = [
            extract('year',  JournalEntry.entry_date) == self.year,
            extract('month', JournalEntry.entry_date) == self.month,
            JournalEntry.status == 'activo',
        ]

        def _sum_cuentas(prefix: str, campo: str,
                         entry_types=None, excluir: str = None) -> Decimal:
            filters = base_f + [JournalEntryLine.account_code.like(f'{prefix}%')]
            if entry_types:
                filters.append(JournalEntry.entry_type.in_(entry_types))
            if excluir:
                filters.append(JournalEntryLine.account_code != excluir)
            result = db.session.query(
                func.sum(getattr(JournalEntryLine, campo))
            ).join(
                JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id
            ).filter(*filters).scalar()
            return Decimal(str(result or 0))

        # Ingresos (7xxx) — naturaleza acreedora: HABER − DEBE
        ingresos_h = _sum_cuentas('7', 'haber')
        ingresos_d = _sum_cuentas('7', 'debe')
        ingresos   = max(ingresos_h - ingresos_d, Decimal('0'))

        # Gastos operativos — solo los registrados manualmente en el módulo de Gastos
        # entry_type: 'gasto', 'activo_fijo', 'manual' → vienen de ExpenseRecord
        _OP = ('gasto', 'activo_fijo', 'manual')
        gop_d = _sum_cuentas('6', 'debe',  entry_types=_OP)
        gop_h = _sum_cuentas('6', 'haber', entry_types=_OP)
        gastos_operativos = max(gop_d - gop_h, Decimal('0'))

        # Depreciación automática (6814) — creada por el agente
        dep_d = _sum_cuentas('6', 'debe',  entry_types=('depreciacion',))
        dep_h = _sum_cuentas('6', 'haber', entry_types=('depreciacion',))
        depreciacion = max(dep_d - dep_h, Decimal('0'))

        # Pérdidas FX (6762) — de operaciones de calce/netting
        pfx_d = _sum_cuentas('6762', 'debe',  entry_types=('calce_netting',))
        pfx_h = _sum_cuentas('6762', 'haber', entry_types=('calce_netting',))
        perdidas_fx = max(pfx_d - pfx_h, Decimal('0'))

        # Gastos totales para P&L contable
        gastos = gastos_operativos + depreciacion + perdidas_fx

        utilidad = ingresos - gastos
        ir_pago  = (utilidad * Decimal('0.01')).quantize(Decimal('0.01')) if utilidad > 0 else Decimal('0')

        # gastos_pen = gastos_operativos (lo que muestra /contabilidad/gastos)
        # utilidad usa el total contable (incluye depreciación + pérdidas FX)
        report.ingresos_pen       = ingresos
        report.gastos_pen         = gastos_operativos
        report.utilidad_neta_pen  = utilidad
        report.ir_pago_cuenta_pen = ir_pago

        # Desglose por cuenta para metricas_json
        rows_ing = db.session.query(
            JournalEntryLine.account_code,
            func.sum(JournalEntryLine.haber).label('th'),
            func.sum(JournalEntryLine.debe).label('td'),
        ).join(
            JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id
        ).filter(
            JournalEntryLine.account_code.like('7%'),
            extract('year',  JournalEntry.entry_date) == self.year,
            extract('month', JournalEntry.entry_date) == self.month,
            JournalEntry.status == 'activo',
        ).group_by(JournalEntryLine.account_code).all()

        rows_gas = db.session.query(
            JournalEntryLine.account_code,
            JournalEntry.entry_type,
            func.sum(JournalEntryLine.debe).label('td'),
            func.sum(JournalEntryLine.haber).label('th'),
        ).join(
            JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id
        ).filter(
            JournalEntryLine.account_code.like('6%'),
            extract('year',  JournalEntry.entry_date) == self.year,
            extract('month', JournalEntry.entry_date) == self.month,
            JournalEntry.status == 'activo',
        ).group_by(JournalEntryLine.account_code, JournalEntry.entry_type).all()

        report.metricas = {
            'year':                  self.year,
            'month':                 self.month,
            'ingresos_pen':          float(ingresos),
            'gastos_pen':            float(gastos),            # total contable
            'gastos_operativos':     float(gastos_operativos), # solo ExpenseRecord
            'gastos_depreciacion':   float(depreciacion),      # 6814 auto
            'perdidas_fx':           float(perdidas_fx),       # 6762 calce
            'utilidad_pen':          float(utilidad),
            'ir_1pct':               float(ir_pago),
            'ingresos_detalle': [
                {
                    'cuenta': r.account_code,
                    'monto': float(
                        max(Decimal(str(r.th or 0)) - Decimal(str(r.td or 0)), Decimal('0'))
                    ),
                }
                for r in rows_ing
                if (Decimal(str(r.th or 0)) - Decimal(str(r.td or 0))) > Decimal('0.01')
            ],
            'gastos_detalle': [
                {
                    'cuenta':      r.account_code,
                    'entry_type':  r.entry_type,
                    'monto': float(
                        max(Decimal(str(r.td or 0)) - Decimal(str(r.th or 0)), Decimal('0'))
                    ),
                }
                for r in rows_gas
                if (Decimal(str(r.td or 0)) - Decimal(str(r.th or 0))) > Decimal('0.01')
            ],
        }

        logger.info(
            f'[AuditEngine] G&P {self.month:02d}/{self.year}: '
            f'Ingresos S/{float(ingresos):,.2f} | '
            f'Gastos op. S/{float(gastos_operativos):,.2f} | '
            f'Deprec. S/{float(depreciacion):,.2f} | '
            f'PérdidasFX S/{float(perdidas_fx):,.2f} | '
            f'Utilidad S/{float(utilidad):,.2f} | '
            f'IR 1% S/{float(ir_pago):,.2f}'
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Alertas
    # ─────────────────────────────────────────────────────────────────────────

    def _emitir_alerta_critica(self, report):
        """
        Emite una notificación de alerta crítica usando el sistema
        de notificaciones existente.
        """
        try:
            from app.services.notification_service import NotificationService
            from app.models.user import User

            masters = User.query.filter(
                User.role == 'Master',
                User.is_active == True,
            ).all()

            mensaje = (
                f'🚨 Auditoría contable {report.audit_date.strftime("%d/%m/%Y")}: '
                f'{report.hallazgos_criticos} hallazgo(s) CRÍTICO(s) detectado(s). '
                f'Estado: {report.estado}. Revisar módulo Auditoría.'
            )

            for user in masters:
                NotificationService.create(
                    user_id=user.id,
                    title='⚠️ Auditoría Contable — Alerta Crítica',
                    message=mensaje,
                    notification_type='auditoria_critica',
                    link='/contabilidad/auditoria/',
                )
            logger.info(
                f'[AuditEngine] Alerta crítica enviada a {len(masters)} usuario(s) Master'
            )
        except Exception as exc:
            logger.warning(f'[AuditEngine] No se pudo emitir alerta: {exc}')
