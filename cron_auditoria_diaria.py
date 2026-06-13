"""
Cron Job — Auditoría Contable IA Diaria
=========================================
Ejecuta automáticamente el Agente Contable al cierre del día.

Configurar en Render como Cron Job:
  Comando : python3 cron_auditoria_diaria.py
  Schedule: 0 23 * * 1-5        ← 23:00 Lima (lunes a viernes)
  Env     : FLASK_ENV=production + DATABASE_URL (automático en Render)

Parámetros opcionales (variables de entorno):
  AUDIT_YEAR   — año a auditar (default: año actual Lima)
  AUDIT_MONTH  — mes a auditar (default: mes actual Lima)
  AUTO_DEPRECIATE — 'true'/'false' (default: 'true')

Salida:
  Imprime resumen en stdout (visible en logs de Render).
  Persiste AuditReport en la base de datos.
  Emite notificación si hay hallazgos críticos.
"""
import os
import sys
import logging
from datetime import datetime

# ── Configuración de logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger('cron_auditoria')

# ── Flask app context ─────────────────────────────────────────────────────────
os.environ.setdefault('FLASK_ENV', 'production')

try:
    from app import create_app
    from app.extensions import db
    app = create_app()
except ImportError as e:
    logger.critical(f'No se pudo importar la app Flask: {e}')
    sys.exit(1)


def _now_lima() -> datetime:
    try:
        import pytz
        lima = pytz.timezone('America/Lima')
        return datetime.now(lima)
    except ImportError:
        from datetime import timezone, timedelta
        return datetime.now(timezone(timedelta(hours=-5)))


def main():
    now = _now_lima()
    logger.info(f'{'='*60}')
    logger.info(f'AGENTE CONTABLE IA — AUDITORÍA DIARIA')
    logger.info(f'Inicio: {now.strftime("%Y-%m-%d %H:%M:%S")} (Lima)')
    logger.info(f'{'='*60}')

    year  = int(os.environ.get('AUDIT_YEAR',  now.year))
    month = int(os.environ.get('AUDIT_MONTH', now.month))
    auto_d = os.environ.get('AUTO_DEPRECIATE', 'true').lower() == 'true'

    logger.info(f'Período auditado: {month:02d}/{year}')
    logger.info(f'Depreciación automática: {auto_d}')

    with app.app_context():
        from app.services.audit.audit_engine import AuditEngine

        engine = AuditEngine(
            year=year,
            month=month,
            audit_date=now.date(),
            trigger='cron',
            executed_by_id=None,
            auto_depreciate=auto_d,
        )

        try:
            report = engine.run()
        except Exception as exc:
            logger.critical(f'Error fatal en AuditEngine: {exc}', exc_info=True)
            sys.exit(1)

        # ── Imprimir resumen ──────────────────────────────────────────────────
        logger.info(f'\n{"="*60}')
        logger.info(f'RESUMEN DE AUDITORÍA {month:02d}/{year}')
        logger.info(f'{"="*60}')
        logger.info(f'Estado global       : {report.estado}')
        logger.info(f'Total hallazgos     : {report.total_hallazgos}')
        logger.info(f'Hallazgos críticos  : {report.hallazgos_criticos}')
        logger.info(f'Ops sin asiento     : {report.ops_sin_asiento}')
        logger.info(f'Asientos descuadrad.: {report.asientos_descuadrados}')
        logger.info(f'Diferencias banco   : {report.diferencias_banco}')
        logger.info(f'Gastos s/comprobante: {report.gastos_sin_comprobante}')
        logger.info(f'Activos s/depreciar : {report.activos_sin_depreciar}')
        logger.info(f'─────────────────────────────────────────────────────')
        logger.info(f'Ingresos   : S/ {float(report.ingresos_pen or 0):>12,.2f}')
        logger.info(f'Gastos     : S/ {float(report.gastos_pen or 0):>12,.2f}')
        logger.info(f'Utilidad   : S/ {float(report.utilidad_neta_pen or 0):>12,.2f}')
        logger.info(f'IR 1% MYPE : S/ {float(report.ir_pago_cuenta_pen or 0):>12,.2f}')
        logger.info(f'─────────────────────────────────────────────────────')
        logger.info(f'Tiempo ejecución    : {float(report.execution_seconds or 0):.2f}s')
        logger.info(f'Reporte ID          : {report.id}')
        logger.info(f'{"="*60}\n')

        if report.hallazgos:
            logger.info('HALLAZGOS DETECTADOS:')
            for i, h in enumerate(report.hallazgos, 1):
                logger.info(
                    f'  {i}. [{h["severidad"]}] [{h["modulo"]}] {h["titulo"]}'
                )
                logger.info(f'     → {h["accion_sugerida"]}')

        # Código de salida según severidad (útil para alertas en CI/CD)
        if report.hallazgos_criticos > 0:
            logger.warning('⚠️  Auditoría con hallazgos CRÍTICOS — revisar sistema')
            sys.exit(2)  # exit code 2 = hallazgos críticos
        elif report.total_hallazgos > 0:
            logger.info('ℹ️  Auditoría con observaciones — revisar hallazgos')
            sys.exit(0)
        else:
            logger.info('✅ Contabilidad limpia — sin hallazgos')
            sys.exit(0)


if __name__ == '__main__':
    main()
