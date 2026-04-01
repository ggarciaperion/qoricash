"""
Factory de la aplicación Flask para QoriCash Trading V2

Este archivo crea y configura la aplicación Flask usando el patrón Factory.
"""
# IMPORTANTE: Monkey patch de eventlet DEBE ir PRIMERO, antes de cualquier otra importación
import eventlet

# CRITICAL: Desactivar DNS monkey patching para permitir Cloudinary/S3
# Parchear solo lo necesario para Socket.IO
eventlet.monkey_patch(
    os=True,
    select=True,
    socket=True,
    thread=True,
    time=True
)

import logging
import os
from flask import Flask
from app.config import get_config
from app.extensions import db, migrate, login_manager, csrf, socketio, limiter, mail, cors

# Scheduler global para expiración de operaciones
_scheduler_greenlet = None


def create_app(config_name=None):
    """
    Factory para crear la aplicación Flask
    
    Args:
        config_name: Nombre de la configuración ('development', 'production', 'testing')
    
    Returns:
        Flask app instance
    """
    app = Flask(__name__)
    
    # Cargar configuración
    if config_name:
        from app.config import config
        app.config.from_object(config[config_name])
    else:
        app.config.from_object(get_config())
    
    # Inicializar extensiones
    initialize_extensions(app)
    
    # Registrar blueprints
    register_blueprints(app)
    
    # Configurar logging
    configure_logging(app)
    
    # Registrar error handlers
    register_error_handlers(app)

    # Configurar Shell context (para flask shell)
    register_shell_context(app)

    # Inicializar scheduler de expiración de operaciones usando eventlet
    # IMPORTANTE: Usar eventlet en lugar de APScheduler para compatibilidad con SocketIO
    start_operation_expiry_scheduler(app)

    # Advertir si rate limiting usa memoria (no persiste entre workers ni reinicios)
    import os
    if not os.environ.get('REDIS_URL'):
        logging.warning(
            '[Security] REDIS_URL no configurada — rate limiting usa memoria volátil. '
            'Configura REDIS_URL en Render para rate limiting efectivo en producción.'
        )

    # Sembrar competidores FX (idempotente — solo inserta si no existen)
    try:
        with app.app_context():
            from app.services.fx_monitor.monitor_service import FXMonitorService
            FXMonitorService.seed_competitors()
    except Exception as e:
        logging.warning(f"[FX] seed_competitors falló (puede que las tablas no existan aún): {e}")

    # Inicializar schedulers del módulo Mercado
    start_market_schedulers(app)

    # Registrar CLI commands (aquí para que estén disponibles sin importar
    # cómo Flask CLI descubra la app — factory o instancia directa)
    register_cli_commands(app)

    return app


def initialize_extensions(flask_app):
    """Inicializar extensiones de Flask"""
    db.init_app(flask_app)
    migrate.init_app(flask_app, db)
    login_manager.init_app(flask_app)
    csrf.init_app(flask_app)
    socketio.init_app(flask_app)
    mail.init_app(flask_app)

    # CORS - Permitir solicitudes desde el frontend web
    # Incluye localhost para desarrollo y dominios de producción
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:3001",
        "https://qoricash.vercel.app",
        "https://www.qoricash.pe",
        "https://qoricash.pe",
        "https://qoricash-web.onrender.com"
    ]

    cors.init_app(
        flask_app,
        resources={r"/api/*": {"origins": allowed_origins}},
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    )

    if flask_app.config['RATELIMIT_ENABLED']:
        limiter.init_app(flask_app)

    # Configurar user_loader para Flask-Login
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Importar eventos de Socket.IO
    with flask_app.app_context():
        import app.socketio_events

    # Registrar filtros personalizados de Jinja2
    register_template_filters(flask_app)

    # Configurar headers de seguridad
    configure_security_headers(flask_app)


def register_blueprints(app):
    """Registrar blueprints de la aplicación"""
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.users import users_bp
    from app.routes.clients import clients_bp
    from app.routes.operations import operations_bp
    from app.routes.position import position_bp
    from app.routes.platform import platform_bp
    from app.routes.platform_api import platform_api_bp
    from app.routes.client_auth import client_auth_bp
    from app.routes.web_api import web_api_bp
    from app.routes.legal import legal_bp
    from app.routes.referrals import referrals_bp
    from app.routes.compliance import compliance_bp
    from app.routes.complaints import complaints_bp
    from app.routes.fx_monitor import fx_monitor_bp
    from app.routes.market import market_bp
    from app.routes.contabilidad import contabilidad_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(users_bp, url_prefix='/users')
    app.register_blueprint(clients_bp, url_prefix='/clients')
    app.register_blueprint(operations_bp, url_prefix='/operations')
    app.register_blueprint(position_bp, url_prefix='/position')
    app.register_blueprint(platform_bp)  # Sin prefijo, las rutas ya tienen /api/platform
    app.register_blueprint(platform_api_bp)  # API pública plataforma: /api/platform/*
    app.register_blueprint(client_auth_bp)  # Autenticación de clientes: /api/client/* (web + móvil)
    app.register_blueprint(web_api_bp)  # API Web QoriCash: /api/web/*
    app.register_blueprint(legal_bp)  # Rutas legales: /legal/terms, /legal/privacy
    app.register_blueprint(referrals_bp)  # Sistema de referidos
    app.register_blueprint(compliance_bp, url_prefix='/compliance')  # Módulo de compliance
    app.register_blueprint(complaints_bp, url_prefix='/complaints')  # Módulo de reclamos
    app.register_blueprint(fx_monitor_bp)  # Monitor de competencia
    app.register_blueprint(market_bp)      # Módulo Mercado
    app.register_blueprint(contabilidad_bp, url_prefix='/contabilidad')  # Módulo Contable


def configure_logging(app):
    """Configurar logging de la aplicación"""
    if not app.debug and not app.testing:
        # Configurar logging para producción
        logging.basicConfig(
            level=getattr(logging, app.config['LOG_LEVEL']),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Logger de la app
        app.logger.setLevel(getattr(logging, app.config['LOG_LEVEL']))


def register_error_handlers(app):
    """Registrar manejadores de errores"""
    from flask import jsonify

    @app.errorhandler(404)
    def not_found_error(error):
        # Siempre retornar JSON para APIs
        return jsonify({'success': False, 'error': 'Recurso no encontrado'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        import traceback, logging as _log
        tb = traceback.format_exc()
        _log.error(f'[500] {request.path}\n{tb}')
        # JSON solo para peticiones AJAX / API
        if (request.is_json or
                request.path.startswith('/api/') or
                request.headers.get('X-Requested-With') == 'XMLHttpRequest'):
            return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500
        # Páginas HTML: mostrar el traceback para facilitar diagnóstico
        return (
            f'<h2 style="color:red">Error 500 — {request.path}</h2>'
            f'<pre style="background:#f8f8f8;padding:16px;border-radius:6px">'
            f'{tb}</pre>',
            500,
        )

    @app.errorhandler(403)
    def forbidden_error(error):
        # Siempre retornar JSON para APIs
        return jsonify({'success': False, 'error': 'Acceso denegado'}), 403


def configure_security_headers(flask_app):
    """
    Configurar headers de seguridad HTTP para proteger contra ataques comunes
    """
    @flask_app.after_request
    def add_security_headers(response):
        # Prevenir clickjacking
        response.headers['X-Frame-Options'] = 'DENY'

        # Prevenir MIME type sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'

        # Habilitar protección XSS del navegador
        response.headers['X-XSS-Protection'] = '1; mode=block'

        # Forzar HTTPS en producción (HSTS)
        if not flask_app.debug:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

        # Content Security Policy - SOLO para rutas de API web/cliente
        # No aplicar CSP al sistema administrativo para no romper estilos de CDN
        from flask import request
        if request.path.startswith('/api/'):
            response.headers['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.socket.io https://vercel.live; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data: https: blob:; "
                "connect-src 'self' https://app.qoricash.pe wss://app.qoricash.pe https://qoricash.vercel.app https://vitals.vercel-insights.com; "
                "frame-ancestors 'none';"
            )

        # Referrer Policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Permissions Policy (antes Feature-Policy)
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'

        return response


def register_template_filters(flask_app):
    """Registrar filtros personalizados de Jinja2"""

    def format_currency_filter(value, decimals=2):
        """
        Formatea un número como moneda con separador de miles (coma)
        Ejemplo: 1000000.50 -> 1,000,000.50
        """
        try:
            num = float(value)
            formatted = f"{num:,.{decimals}f}"
            return formatted
        except (ValueError, TypeError):
            return "0.00"

    # Registrar el filtro en el entorno de Jinja2
    flask_app.jinja_env.filters['format_currency'] = format_currency_filter


def register_shell_context(app):
    """Registrar contexto para flask shell"""
    @app.shell_context_processor
    def make_shell_context():
        from app.models.user import User
        from app.models.client import Client
        from app.models.operation import Operation
        return {
            'db': db,
            'User': User,
            'Client': Client,
            'Operation': Operation
        }


def start_operation_expiry_scheduler(app):
    """
    Iniciar scheduler de expiración de operaciones usando eventlet
    Se ejecuta en un greenlet separado cada 60 segundos

    IMPORTANTE: Solo se inicia UNA vez globalmente, incluso si gunicorn
    tiene múltiples workers. Usamos una variable global para evitar duplicados.
    """
    global _scheduler_greenlet

    # Solo iniciar si no está ya corriendo
    if _scheduler_greenlet is not None:
        logging.info("[SCHEDULER] Ya existe un scheduler en ejecución, no se inicia otro")
        return

    def scheduler_loop():
        """Loop infinito que expira operaciones cada 60 segundos"""
        import time
        logging.info("[SCHEDULER] ✅ Scheduler de expiración de operaciones iniciado")

        while True:
            try:
                with app.app_context():
                    from app.services.operation_expiry_service import OperationExpiryService
                    expired_count = OperationExpiryService.expire_old_operations()
                    if expired_count > 0:
                        logging.info(f"[SCHEDULER] ⏱️ {expired_count} operaciones canceladas automáticamente")
            except Exception as e:
                logging.error(f"[SCHEDULER] ❌ Error en scheduler de expiración: {str(e)}")
                import traceback
                logging.error(traceback.format_exc())

            # Esperar 60 segundos antes de la próxima verificación
            eventlet.sleep(60)

    # Iniciar el scheduler en un greenlet separado
    _scheduler_greenlet = eventlet.spawn(scheduler_loop)
    logging.info("[SCHEDULER] 🚀 Greenlet de scheduler spawneado")


def start_market_schedulers(app):
    """Iniciar greenlets para jobs del módulo Mercado (precios, noticias, macro, fx_monitor)"""

    def _run_every(interval_sec, job_name, fn):
        def loop():
            logging.info(f"[MARKET] ✅ {job_name} iniciado (cada {interval_sec//60} min)")
            eventlet.sleep(30)  # pequeño delay al arrancar para no saturar el inicio
            while True:
                try:
                    with app.app_context():
                        fn()
                except Exception as e:
                    import traceback
                    logging.error(f"[MARKET] ❌ {job_name}: {e}\n{traceback.format_exc()}")
                eventlet.sleep(interval_sec)
        eventlet.spawn(loop)

    def _prices():
        from app.services.market.market_service import MarketService
        r = MarketService.run_price_cycle()
        logging.info(f"[MARKET] Precios: {r}")

    def _news():
        from app.services.market.market_service import MarketService
        r = MarketService.run_news_cycle()
        logging.info(f"[MARKET] Noticias: {r}")

    def _macro():
        from app.services.market.market_service import MarketService
        r = MarketService.run_macro_cycle()
        logging.info(f"[MARKET] Macro: {r}")

    def _fx_monitor():
        from app.services.fx_monitor.monitor_service import FXMonitorService
        r = FXMonitorService.run_scrape_cycle()
        logging.info(f"[MARKET] FX Monitor: {r}")

    def _calendar():
        from app.services.market.market_service import MarketService
        r = MarketService.run_calendar_cycle()
        logging.info(f"[MARKET] Calendario: {r}")

    _run_every(5  * 60, 'Precios de mercado',   _prices)
    _run_every(15 * 60, 'Noticias RSS',          _news)
    _run_every(6  * 3600, 'Indicadores macro',   _macro)
    _run_every(5  * 60, 'FX Monitor scraping',   _fx_monitor)
    _run_every(24 * 3600, 'Calendario económico', _calendar)

    # Análisis diario a las 8:30 AM Lima, lunes a viernes
    def _daily_analysis_at_time():
        from datetime import datetime, timezone, timedelta
        _LIMA = timezone(timedelta(hours=-5))

        def _next_830(now_lima):
            """Próximo 8:30 AM Lima en día hábil (lun-vie)."""
            target = now_lima.replace(hour=8, minute=30, second=0, microsecond=0)
            if now_lima >= target:
                target += timedelta(days=1)
            while target.weekday() >= 5:  # saltar sábado (5) y domingo (6)
                target += timedelta(days=1)
            return target

        def loop():
            logging.info("[MARKET] ✅ Scheduler análisis diario 8:30 AM Lima iniciado")
            while True:
                now  = datetime.now(_LIMA)
                next_run = _next_830(now)
                wait_secs = (next_run - now).total_seconds()
                logging.info(
                    f"[MARKET] Próximo análisis diario en "
                    f"{int(wait_secs//3600)}h {int((wait_secs%3600)//60)}m "
                    f"({next_run.strftime('%Y-%m-%d %H:%M')} Lima)"
                )
                eventlet.sleep(wait_secs)
                try:
                    with app.app_context():
                        from app.services.market.market_service import MarketService
                        r = MarketService.run_daily_analysis_cycle()
                        logging.info(f"[MARKET] Análisis base 8:30 AM: {r}")
                except Exception as e:
                    import traceback
                    logging.error(f"[MARKET] ❌ Análisis diario: {e}\n{traceback.format_exc()}")

        eventlet.spawn(loop)

    _daily_analysis_at_time()


def register_cli_commands(app):
    """Registra CLI commands dentro del factory para que siempre estén disponibles."""

    @app.cli.command("create-tables")
    def create_tables():
        """Crea todas las tablas faltantes usando db.create_all() (seguro, idempotente)."""
        from app.extensions import db
        from app.models.system_config import SystemConfig
        import traceback
        try:
            db.create_all()
            # Seed parámetros fiscales por defecto (idempotente)
            defaults = [
                ('UIT',  '5350', 'Unidad Impositiva Tributaria vigente (S/)'),
                ('RUC',  '20000000001', 'RUC de la empresa (para exportaciones SUNAT)'),
                ('RAZON_SOCIAL', 'QORICASH TRADING S.A.C.', 'Razón social de la empresa'),
            ]
            for key, value, desc in defaults:
                if not SystemConfig.query.get(key):
                    db.session.add(SystemConfig(key=key, value=value, description=desc))
            db.session.commit()
            print("✓ Tablas creadas / verificadas correctamente")
        except Exception as e:
            print(f"✗ Error: {e}")
            traceback.print_exc()

    @app.cli.command("refresh-market")
    def refresh_market():
        """Ejecuta manualmente todos los ciclos de mercado: precios, noticias, macro, calendario."""
        from app.services.market.market_service import MarketService
        import traceback

        print("=== CICLO DE PRECIOS ===")
        try:
            r = MarketService.run_price_cycle()
            print(f"  Resultado: {r}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            traceback.print_exc()

        print("\n=== CICLO DE NOTICIAS ===")
        try:
            r = MarketService.run_news_cycle()
            print(f"  Resultado: {r}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            traceback.print_exc()

        print("\n=== CICLO MACRO ===")
        try:
            r = MarketService.run_macro_cycle()
            print(f"  Resultado: {r}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            traceback.print_exc()

        print("\n=== CICLO CALENDARIO ===")
        try:
            r = MarketService.run_calendar_cycle()
            print(f"  Resultado: {r}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            traceback.print_exc()

        print("\n✓ refresh-market completado")

    @app.cli.command("refresh-fx")
    def refresh_fx():
        """Siembra competidores y ejecuta ciclo de scraping FX Monitor."""
        from app.services.fx_monitor.monitor_service import FXMonitorService
        import traceback

        print("=== SEEDING COMPETIDORES ===")
        try:
            FXMonitorService.seed_competitors()
            print("  ✓ Competidores sembrados")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            traceback.print_exc()

        print("\n=== CICLO FX SCRAPING ===")
        try:
            r = FXMonitorService.run_scrape_cycle()
            print(f"  Resultado: {r}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            traceback.print_exc()

        print("\n✓ refresh-fx completado")

    @app.cli.command("seed-accounts")
    def seed_accounts():
        """Carga el catálogo de cuentas PCGE para QoriCash (idempotente)."""
        from app.extensions import db
        from app.models.accounting_account import AccountingAccount
        import traceback

        ACCOUNTS = [
            # ── ACTIVO ──────────────────────────────────────────────────────
            ('1011', 'Caja MN',                        'activo',    'deudora',   'PEN'),
            ('1012', 'Caja ME',                        'activo',    'deudora',   'USD'),
            ('1041', 'BCP – Cuenta Corriente PEN',        'activo',    'deudora',   'PEN'),
            ('1044', 'BCP – Cuenta Corriente USD',        'activo',    'deudora',   'USD'),
            ('1047', 'Interbank – Cuenta Corriente USD',  'activo',    'deudora',   'USD'),
            ('1048', 'Interbank – Cuenta Corriente PEN',  'activo',    'deudora',   'PEN'),
            ('1049', 'BanBif – Cuenta Corriente PEN',     'activo',    'deudora',   'PEN'),
            ('1050', 'BanBif – Cuenta Corriente USD',     'activo',    'deudora',   'USD'),
            ('1051', 'Pichincha – Cuenta Corriente PEN',  'activo',    'deudora',   'PEN'),
            ('1052', 'Pichincha – Cuenta Corriente USD',  'activo',    'deudora',   'USD'),
            ('1211', 'Clientes por liquidar',          'activo',    'deudora',   'PEN'),
            # ── PASIVO ──────────────────────────────────────────────────────
            ('4011', 'IR – Pago a cuenta mensual',     'pasivo',    'acreedora', 'PEN'),
            ('4031', 'EsSalud por pagar',              'pasivo',    'acreedora', 'PEN'),
            ('4032', 'AFP / ONP por pagar',            'pasivo',    'acreedora', 'PEN'),
            ('4111', 'Sueldos por pagar',              'pasivo',    'acreedora', 'PEN'),
            ('4699', 'Anticipos de clientes',          'pasivo',    'acreedora', 'PEN'),
            # ── PATRIMONIO ──────────────────────────────────────────────────
            ('501',  'Capital social',                 'patrimonio','acreedora', 'PEN'),
            ('591',  'Utilidades acumuladas',          'patrimonio','acreedora', 'PEN'),
            ('592',  'Pérdidas acumuladas',            'patrimonio','deudora',   'PEN'),
            # ── INGRESOS ────────────────────────────────────────────────────
            ('7711', 'Diferencial cambiario – Compra/Venta', 'ingreso', 'acreedora', 'PEN'),
            ('7712', 'Otros ingresos financieros',     'ingreso',   'acreedora', 'PEN'),
            # ── GASTOS ──────────────────────────────────────────────────────
            ('621',  'Remuneraciones al personal',     'gasto',     'deudora',   'PEN'),
            ('627',  'Seguridad social – EsSalud/AFP', 'gasto',     'deudora',   'PEN'),
            ('6311', 'Transporte y delivery',          'gasto',     'deudora',   'PEN'),
            ('6361', 'Energía / telecomunicaciones',   'gasto',     'deudora',   'PEN'),
            ('6381', 'Honorarios (contador, legal)',   'gasto',     'deudora',   'PEN'),
            ('6391', 'Comisiones bancarias / ITF',     'gasto',     'deudora',   'PEN'),
            ('6392', 'Servicios de tecnología',        'gasto',     'deudora',   'PEN'),
            ('6411', 'IR – Pago a cuenta (gasto)',     'gasto',     'deudora',   'PEN'),
            ('6511', 'Otros gastos de gestión',        'gasto',     'deudora',   'PEN'),
            ('6751', 'Pérdida por diferencia de cambio','gasto',    'deudora',   'PEN'),
        ]

        try:
            created = 0
            skipped = 0
            for code, name, type_, nature, currency in ACCOUNTS:
                existing = AccountingAccount.query.filter_by(code=code).first()
                if existing:
                    skipped += 1
                    continue
                acc = AccountingAccount(
                    code=code, name=name, type=type_,
                    nature=nature, currency=currency, is_active=True
                )
                db.session.add(acc)
                created += 1
            # Desactivar cuentas BBVA/Scotiabank si existen (QoriCash no opera en esos bancos)
            deactivated = 0
            for old_code in ('1042', '1043', '1045', '1046'):
                old_acc = AccountingAccount.query.filter_by(code=old_code).first()
                if old_acc and old_acc.is_active:
                    old_acc.is_active = False
                    deactivated += 1
            db.session.commit()
            print(f"✓ seed-accounts: {created} cuentas creadas, {skipped} ya existían, {deactivated} desactivadas")
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error en seed-accounts: {e}")
            traceback.print_exc()

    @app.cli.command("seed-demo-contabilidad")
    def seed_demo_contabilidad():
        """Carga datos demo de contabilidad para Enero-Marzo 2026 (visualización)."""
        from app.extensions import db
        from app.models.accounting_period import AccountingPeriod
        from app.models.expense_record import ExpenseRecord
        from app.models.operation import Operation
        from app.models.client import Client
        from app.services.accounting.journal_service import JournalService
        from datetime import date, datetime
        from decimal import Decimal
        from sqlalchemy import extract
        import traceback

        # ── Buscar un cliente existente para las Operaciones del LIG ────────
        demo_client = Client.query.first()
        if not demo_client:
            print("  · Sin clientes en BD — se crearán asientos pero NO operaciones (LIG vacío)")

        def _seed_month(year, month, month_tag, ops_data, spreads_data, gastos_data, op_prefix):
            """Siembra un mes completo. Idempotente: salta si ya hay datos demo."""
            # Período
            period = AccountingPeriod.query.filter_by(year=year, month=month).first()
            if not period:
                period = AccountingPeriod(year=year, month=month, status='abierto')
                db.session.add(period)
                db.session.flush()
                print(f"  ✓ Período {month_tag} {year} creado")
            else:
                print(f"  · Período {month_tag} {year} ya existe")

            # Chequeo de idempotencia: ¿ya existen asientos demo en este mes?
            existing = db.session.query(JournalService._model()).filter(
                JournalService._model().source_type == 'demo',
                extract('year',  JournalService._model().entry_date) == year,
                extract('month', JournalService._model().entry_date) == month,
            ).first() if hasattr(JournalService, '_model') else None

            # Usamos JournalEntry directamente para la verificación
            from app.models.journal_entry import JournalEntry
            existing = JournalEntry.query.filter(
                JournalEntry.source_type == 'demo',
                extract('year',  JournalEntry.entry_date) == year,
                extract('month', JournalEntry.entry_date) == month,
            ).first()
            if existing:
                print(f"  · Asientos demo {month_tag} ya existen — saltando")
                return

            # ── Asientos de operaciones ──────────────────────────────────
            op_counter = [0]
            for d, tipo, cliente, usd, tc, pen, acc_pen, acc_usd in ops_data:
                pen_d = Decimal(str(pen))
                usd_d = Decimal(str(usd))
                tc_d  = Decimal(str(tc))
                if tipo == 'Compra':
                    lines = [
                        {'account_code': acc_pen, 'description': f'Ingreso PEN – {cliente}',
                         'debe': pen_d, 'haber': Decimal('0'), 'currency': 'PEN'},
                        {'account_code': acc_usd, 'description': f'Egreso USD – {cliente}',
                         'debe': Decimal('0'), 'haber': pen_d,
                         'currency': 'USD', 'amount_usd': usd_d, 'exchange_rate': tc_d},
                    ]
                    glosa = f'DEMO Compra USD – {cliente}'
                else:
                    lines = [
                        {'account_code': acc_usd, 'description': f'Ingreso USD – {cliente}',
                         'debe': pen_d, 'haber': Decimal('0'),
                         'currency': 'USD', 'amount_usd': usd_d, 'exchange_rate': tc_d},
                        {'account_code': acc_pen, 'description': f'Egreso PEN – {cliente}',
                         'debe': Decimal('0'), 'haber': pen_d, 'currency': 'PEN'},
                    ]
                    glosa = f'DEMO Venta USD – {cliente}'

                e = JournalService.create_entry(
                    entry_type='operacion_completada',
                    description=glosa,
                    lines=lines,
                    source_type='demo',
                    source_id=None,
                    entry_date=d,
                    created_by=None,
                )
                print(f"  ✓ {e.entry_number}  {glosa[:55]}")

                # Crear Operation para el LIG si hay cliente disponible
                if demo_client:
                    op_counter[0] += 1
                    op_id = f'{op_prefix}-{op_counter[0]:03d}'
                    if not Operation.query.filter_by(operation_id=op_id).first():
                        op = Operation(
                            operation_id=op_id,
                            client_id=demo_client.id,
                            operation_type=tipo,
                            origen='sistema',
                            amount_usd=usd_d,
                            exchange_rate=tc_d,
                            amount_pen=pen_d,
                            status='Completada',
                            completed_at=datetime(d.year, d.month, d.day, 14, 0, 0),
                        )
                        db.session.add(op)

            # ── Asientos de spread ───────────────────────────────────────
            for d, glosa, lines in spreads_data:
                e = JournalService.create_entry('calce_netting', glosa, lines,
                                                source_type='demo', entry_date=d)
                print(f"  ✓ {e.entry_number}  {glosa}")

            # ── Gastos + ExpenseRecords ──────────────────────────────────
            for d, cat, desc, monto, vtype, vnum, ruc, proveedor in gastos_data:
                pen_d = Decimal(str(monto))
                e = JournalService.create_entry(
                    entry_type='gasto',
                    description=f'DEMO Gasto: {desc}',
                    lines=[
                        {'account_code': cat,  'description': desc,
                         'debe': pen_d, 'haber': Decimal('0'), 'currency': 'PEN'},
                        {'account_code': '4699','description': f'Por pagar: {desc}',
                         'debe': Decimal('0'), 'haber': pen_d, 'currency': 'PEN'},
                    ],
                    source_type='demo',
                    entry_date=d,
                    created_by=None,
                )
                er = ExpenseRecord(
                    period_id=period.id,
                    expense_date=d,
                    category=cat,
                    description=desc,
                    amount_pen=pen_d,
                    voucher_type=vtype,
                    voucher_number=vnum,
                    supplier_ruc=ruc,
                    supplier_name=proveedor,
                    journal_entry_id=e.id if e else None,
                    created_by=None,
                )
                db.session.add(er)
                print(f"  ✓ Gasto: {desc[:50]}  S/ {monto:.2f}")

            db.session.commit()
            print(f"  ✓ {month_tag} {year} completado\n")

        # ═══════════════════════════════════════════════════════════════════
        # DATOS ENERO 2026
        # ═══════════════════════════════════════════════════════════════════
        print("\n── Enero 2026 ─────────────────────────────────────────────")
        _seed_month(2026, 1, 'Ene',
            ops_data=[
                (date(2026,1, 5), 'Compra', 'Roberto Castillo',    4_000, 3.7100, 14_840.00, '1041','1044'),
                (date(2026,1, 8), 'Venta',  'Sonia Vargas',        2_800, 3.6900, 10_332.00, '1041','1044'),
                (date(2026,1,12), 'Compra', 'Inversiones Norte SAC',7_500, 3.7200, 27_900.00, '1048','1047'),
                (date(2026,1,15), 'Venta',  'Miguel Torres',        3_000, 3.6800, 11_040.00, '1048','1047'),
                (date(2026,1,19), 'Compra', 'Diana Quispe',         6_000, 3.7300, 22_380.00, '1041','1044'),
                (date(2026,1,22), 'Venta',  'Transporte Lima SAC', 10_000, 3.6700, 36_700.00, '1041','1044'),
                (date(2026,1,26), 'Compra', 'Arturo Mendoza',       5_500, 3.7100, 20_405.00, '1041','1044'),
                (date(2026,1,29), 'Venta',  'Cecilia Flores',       4_200, 3.6800, 15_456.00, '1041','1044'),
            ],
            spreads_data=[
                (date(2026,1,31), 'DEMO Spread compra USD Ene-2026',
                 [{'account_code':'1041','description':'Spread compra','debe':Decimal('1620.00'),'haber':Decimal('0'),'currency':'PEN'},
                  {'account_code':'7711','description':'Dif. cambiario compra','debe':Decimal('0'),'haber':Decimal('1620.00'),'currency':'PEN'}]),
                (date(2026,1,31), 'DEMO Spread venta USD Ene-2026',
                 [{'account_code':'1041','description':'Spread venta','debe':Decimal('980.00'),'haber':Decimal('0'),'currency':'PEN'},
                  {'account_code':'7711','description':'Dif. cambiario venta','debe':Decimal('0'),'haber':Decimal('980.00'),'currency':'PEN'}]),
            ],
            gastos_data=[
                (date(2026,1, 2),'6391','Alquiler local Ene-2026',         3_500.00,'Factura','F001-00198','20512345678','Inmobiliaria Central SAC'),
                (date(2026,1, 5),'6361','Energía eléctrica enero',           295.00,'Boleta', 'B003-08750','20331376783','Enel Distribución Perú SAC'),
                (date(2026,1, 5),'6361','Telefonía e internet enero',        450.00,'Boleta', 'B002-01423','20116544526','Claro Perú SAC'),
                (date(2026,1,10),'6381','Honorarios contador Ene-2026',      800.00,'Recibo', 'RH-001-0312','10412345678','Juan Pérez Quispe CPC'),
                (date(2026,1,15),'6391','Comisión bancaria BCP enero',       160.00, None,     None,         None,         None),
                (date(2026,1,20),'6391','Publicidad digital enero',          500.00,'Factura','F004-00701','20601234567','Digital Media SAC'),
                (date(2026,1,25),'6511','Útiles de escritorio',              210.00,'Boleta', 'B005-02201','10298765432','Librería San Juan EIRL'),
                (date(2026,1,31),'6361','Internet adicional enero',          250.00,'Boleta', 'B006-04321','20116544526','Movistar Perú SAC'),
            ],
            op_prefix='DEMO-ENE26',
        )

        # ═══════════════════════════════════════════════════════════════════
        # DATOS FEBRERO 2026
        # ═══════════════════════════════════════════════════════════════════
        print("── Febrero 2026 ───────────────────────────────────────────")
        _seed_month(2026, 2, 'Feb',
            ops_data=[
                (date(2026,2, 3), 'Compra', 'Carlos Mendoza',           5_000, 3.7200, 18_600.00, '1041','1044'),
                (date(2026,2, 5), 'Venta',  'Ana Torres',               3_200, 3.6800, 11_776.00, '1041','1044'),
                (date(2026,2, 7), 'Compra', 'Empresa XYZ SAC',         10_000, 3.7300, 37_300.00, '1048','1047'),
                (date(2026,2,10), 'Venta',  'Luis García',              2_500, 3.6700,  9_175.00, '1048','1047'),
                (date(2026,2,12), 'Compra', 'María López',              8_000, 3.7100, 29_680.00, '1041','1044'),
                (date(2026,2,14), 'Venta',  'Importaciones ABC SAC',   15_000, 3.6900, 55_350.00, '1041','1044'),
                (date(2026,2,17), 'Compra', 'Pedro Sánchez',            4_500, 3.7400, 16_830.00, '1041','1044'),
                (date(2026,2,19), 'Venta',  'Rosa Flores',              6_000, 3.6800, 22_080.00, '1041','1044'),
                (date(2026,2,21), 'Compra', 'Exportadores del Perú SAC',20_000, 3.7200, 74_400.00, '1041','1044'),
                (date(2026,2,24), 'Venta',  'Jorge Huanca',             3_800, 3.6600, 13_908.00, '1041','1044'),
                (date(2026,2,26), 'Compra', 'Patricia Quispe',          7_500, 3.7300, 27_975.00, '1048','1047'),
                (date(2026,2,28), 'Venta',  'Comercial Lima SAC',      12_000, 3.7000, 44_400.00, '1048','1047'),
            ],
            spreads_data=[
                (date(2026,2,28), 'DEMO Spread compra USD Feb-2026',
                 [{'account_code':'1041','description':'Spread compra','debe':Decimal('1850.50'),'haber':Decimal('0'),'currency':'PEN'},
                  {'account_code':'7711','description':'Dif. cambiario compra','debe':Decimal('0'),'haber':Decimal('1850.50'),'currency':'PEN'}]),
                (date(2026,2,28), 'DEMO Spread venta USD Feb-2026',
                 [{'account_code':'1041','description':'Spread venta','debe':Decimal('1240.00'),'haber':Decimal('0'),'currency':'PEN'},
                  {'account_code':'7711','description':'Dif. cambiario venta','debe':Decimal('0'),'haber':Decimal('1240.00'),'currency':'PEN'}]),
            ],
            gastos_data=[
                (date(2026,2, 1),'6391','Alquiler local Feb-2026',          3_500.00,'Factura','F001-00234','20512345678','Inmobiliaria Central SAC'),
                (date(2026,2, 3),'6361','Servicio de energía eléctrica',      320.00,'Boleta', 'B003-08921','20331376783','Enel Distribución Perú SAC'),
                (date(2026,2, 3),'6361','Telefonía e internet empresarial',   450.00,'Boleta', 'B002-01567','20116544526','Claro Perú SAC'),
                (date(2026,2, 8),'6381','Honorarios contador Feb-2026',       800.00,'Recibo', 'RH-001-0345','10412345678','Juan Pérez Quispe CPC'),
                (date(2026,2,10),'6391','Comisión bancaria BCP Feb-2026',     185.00, None,     None,         None,         None),
                (date(2026,2,15),'6391','Comisión bancaria Interbank Feb-2026',120.00, None,     None,         None,         None),
                (date(2026,2,17),'6391','Publicidad en redes sociales',       600.00,'Factura','F004-00789','20601234567','Digital Media SAC'),
                (date(2026,2,20),'6511','Material de oficina y útiles',       280.00,'Boleta', 'B005-02345','10298765432','Librería San Juan EIRL'),
                (date(2026,2,25),'6391','Servicio de limpieza de local',      350.00,'Recibo', 'RC-002-0123','20456789012','Limpiezas Rápidas SAC'),
                (date(2026,2,28),'6361','Internet y comunicaciones añadidas', 250.00,'Boleta', 'B006-04567','20116544526','Movistar Perú SAC'),
            ],
            op_prefix='DEMO-FEB26',
        )

        # ═══════════════════════════════════════════════════════════════════
        # DATOS MARZO 2026 (mes actual — el que se ve por defecto)
        # ═══════════════════════════════════════════════════════════════════
        print("── Marzo 2026 (mes actual) ────────────────────────────────")
        _seed_month(2026, 3, 'Mar',
            ops_data=[
                (date(2026,3, 2), 'Compra', 'Fernanda Villanueva',    6_000, 3.7150, 22_290.00, '1041','1044'),
                (date(2026,3, 4), 'Venta',  'Grupo Andino SAC',       4_500, 3.6950, 16_627.50, '1041','1044'),
                (date(2026,3, 6), 'Compra', 'Humberto Palomino',      3_200, 3.7200, 11_904.00, '1048','1047'),
                (date(2026,3,10), 'Venta',  'Exportaciones Sur EIRL', 8_000, 3.6800, 29_440.00, '1048','1047'),
                (date(2026,3,12), 'Compra', 'Luz Marina Rojas',       5_000, 3.7300, 18_650.00, '1041','1044'),
                (date(2026,3,14), 'Venta',  'Comercio Global SAC',   12_000, 3.6900, 44_280.00, '1041','1044'),
                (date(2026,3,17), 'Compra', 'Omar Salinas',            7_000, 3.7250, 26_075.00, '1041','1044'),
                (date(2026,3,19), 'Venta',  'Importex Perú SAC',      9_500, 3.6850, 35_007.50, '1041','1044'),
                (date(2026,3,21), 'Compra', 'Cristina Pacheco',        4_000, 3.7200, 14_880.00, '1041','1044'),
                (date(2026,3,24), 'Venta',  'Negocios Lima SAC',      15_000, 3.6750, 55_125.00, '1041','1044'),
                (date(2026,3,26), 'Compra', 'Raúl Contreras',          6_500, 3.7300, 24_245.00, '1048','1047'),
                (date(2026,3,28), 'Venta',  'Trading Norte SAC',      11_000, 3.6900, 40_590.00, '1048','1047'),
                (date(2026,3,31), 'Compra', 'Vanessa Herrera',         3_500, 3.7200, 13_020.00, '1041','1044'),
            ],
            spreads_data=[
                (date(2026,3,31), 'DEMO Spread compra USD Mar-2026',
                 [{'account_code':'1041','description':'Spread compra','debe':Decimal('2105.75'),'haber':Decimal('0'),'currency':'PEN'},
                  {'account_code':'7711','description':'Dif. cambiario compra','debe':Decimal('0'),'haber':Decimal('2105.75'),'currency':'PEN'}]),
                (date(2026,3,31), 'DEMO Spread venta USD Mar-2026',
                 [{'account_code':'1041','description':'Spread venta','debe':Decimal('1487.50'),'haber':Decimal('0'),'currency':'PEN'},
                  {'account_code':'7711','description':'Dif. cambiario venta','debe':Decimal('0'),'haber':Decimal('1487.50'),'currency':'PEN'}]),
            ],
            gastos_data=[
                (date(2026,3, 2),'6391','Alquiler local Mar-2026',          3_500.00,'Factura','F001-00271','20512345678','Inmobiliaria Central SAC'),
                (date(2026,3, 4),'6361','Energía eléctrica marzo',            308.00,'Boleta', 'B003-09104','20331376783','Enel Distribución Perú SAC'),
                (date(2026,3, 4),'6361','Telefonía e internet marzo',         450.00,'Boleta', 'B002-01689','20116544526','Claro Perú SAC'),
                (date(2026,3, 9),'6381','Honorarios contador Mar-2026',       800.00,'Recibo', 'RH-001-0378','10412345678','Juan Pérez Quispe CPC'),
                (date(2026,3,11),'6391','Comisión bancaria BCP marzo',        195.00, None,     None,         None,         None),
                (date(2026,3,15),'6391','Comisión bancaria Interbank marzo',   130.00, None,     None,         None,         None),
                (date(2026,3,18),'6391','Campaña publicidad marzo',           750.00,'Factura','F004-00832','20601234567','Digital Media SAC'),
                (date(2026,3,20),'6511','Material de oficina marzo',          195.00,'Boleta', 'B005-02489','10298765432','Librería San Juan EIRL'),
                (date(2026,3,25),'6391','Servicio de limpieza marzo',         350.00,'Recibo', 'RC-002-0145','20456789012','Limpiezas Rápidas SAC'),
                (date(2026,3,28),'6391','Renovación dominio web',             320.00,'Factura','F007-00112','20789012345','TechHost Perú SAC'),
                (date(2026,3,31),'6361','Internet adicional marzo',           250.00,'Boleta', 'B006-04789','20116544526','Movistar Perú SAC'),
            ],
            op_prefix='DEMO-MAR26',
        )

        print("✓ seed-demo-contabilidad completado — Ene, Feb, Mar 2026")
        print("  Para eliminar estos datos: flask drop-demo-contabilidad")

    @app.cli.command("drop-demo-contabilidad")
    def drop_demo_contabilidad():
        """Elimina TODOS los datos demo de contabilidad (Ene-Mar 2026)."""
        from app.extensions import db
        from app.models.accounting_period import AccountingPeriod
        from app.models.journal_entry import JournalEntry
        from app.models.journal_entry_line import JournalEntryLine
        from app.models.expense_record import ExpenseRecord
        from app.models.operation import Operation
        from sqlalchemy import extract
        import traceback

        YEAR = 2026
        try:
            # Operaciones demo (LIG)
            op_del = Operation.query.filter(
                Operation.operation_id.like('DEMO-%')
            ).delete(synchronize_session=False)
            print(f"  ✓ {op_del} operaciones demo eliminadas")

            for month in [1, 2, 3]:
                # Expense records
                er_del = ExpenseRecord.query.filter(
                    db.extract('year',  ExpenseRecord.expense_date) == YEAR,
                    db.extract('month', ExpenseRecord.expense_date) == month,
                ).delete(synchronize_session=False)

                # Journal entries (cascade a lines via source_type='demo')
                je_ids = [r[0] for r in db.session.query(JournalEntry.id).filter(
                    JournalEntry.source_type == 'demo',
                    extract('year',  JournalEntry.entry_date) == YEAR,
                    extract('month', JournalEntry.entry_date) == month,
                ).all()]
                if je_ids:
                    JournalEntryLine.query.filter(
                        JournalEntryLine.journal_entry_id.in_(je_ids)
                    ).delete(synchronize_session=False)
                    JournalEntry.query.filter(JournalEntry.id.in_(je_ids)).delete(
                        synchronize_session=False)

                period = AccountingPeriod.query.filter_by(year=YEAR, month=month).first()
                if period:
                    db.session.delete(period)

                month_names = {1:'Ene', 2:'Feb', 3:'Mar'}
                print(f"  ✓ {month_names[month]} {YEAR}: {er_del} gastos, {len(je_ids)} asientos eliminados")

            db.session.commit()
            print(f"\n✓ drop-demo-contabilidad completado")
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error: {e}")
            traceback.print_exc()

    @app.cli.command("seed-demo-multibanco")
    def seed_demo_multibanco():
        """
        Crea cliente demo con cuentas en 3 bancos y 2 operaciones con pagos múltiples.
        Diseñado para visualizar el Libro Caja y Bancos desagregado por banco.
        Idempotente: salta si ya existen los datos.
        """
        from app.extensions import db
        from app.models.client import Client
        from app.models.operation import Operation
        from app.models.accounting_period import AccountingPeriod
        from app.services.accounting.journal_service import JournalService
        from datetime import date, datetime
        from decimal import Decimal
        import json, traceback

        DEMO_DNI   = '72345678'
        DEMO_EMAIL = 'demo.multibanco@qoricash.pe'

        try:
            # ── 1. Cliente demo ─────────────────────────────────────────────
            client = Client.query.filter_by(dni=DEMO_DNI).first()
            if not client:
                client = Client(
                    document_type='DNI',
                    dni=DEMO_DNI,
                    email=DEMO_EMAIL,
                    nombres='María Gracia',
                    apellido_paterno='Villanueva',
                    apellido_materno='Torres',
                    phone='999888777',
                )
                # 5 cuentas en 3 bancos (PEN y USD)
                cuentas = [
                    {'bank_name': 'BCP',        'account_type': 'Ahorro',    'currency': 'S/',
                     'account_number': '19173537790119',        'origen': 'Lima'},
                    {'bank_name': 'BBVA',       'account_type': 'Ahorro',    'currency': 'S/',
                     'account_number': '00110123456789',        'origen': 'Lima'},
                    {'bank_name': 'INTERBANK',  'account_type': 'Ahorro',    'currency': 'S/',
                     'account_number': '09830123456789',        'origen': 'Lima'},
                    {'bank_name': 'BCP',        'account_type': 'Ahorro',    'currency': '$',
                     'account_number': '19174567890234',        'origen': 'Lima'},
                    {'bank_name': 'SCOTIABANK', 'account_type': 'Corriente', 'currency': '$',
                     'account_number': '00001234567890',        'origen': 'Lima'},
                ]
                client.bank_accounts_json = json.dumps(cuentas)
                db.session.add(client)
                db.session.flush()
                print(f"  ✓ Cliente creado: {client.nombres} {client.apellido_paterno} (DNI {DEMO_DNI})")
                print(f"       BCP PEN     19173537790119")
                print(f"       BBVA PEN    00110123456789")
                print(f"       INTERBANK PEN 09830123456789")
                print(f"       BCP USD     19174567890234")
                print(f"       SCOTIABANK USD 00001234567890")
            else:
                print(f"  · Cliente {DEMO_DNI} ya existe — reutilizando")

            # ── 2. Período contable Marzo 2026 ──────────────────────────────
            period = AccountingPeriod.query.filter_by(year=2026, month=3).first()
            if not period:
                period = AccountingPeriod(year=2026, month=3, status='abierto')
                db.session.add(period)
                db.session.flush()

            # ── Operación A: COMPRA $3,000 con 3 abonos PEN / 2 pagos USD ──
            OP_A_ID = 'DEMO-MB-COMPRA-001'
            if not Operation.query.filter_by(operation_id=OP_A_ID).first():
                # Cliente paga en 3 abonos PEN desde 3 bancos distintos
                deposits_a = [
                    {'importe': 4000.00, 'codigo_operacion': 'BCK-001',
                     'cuenta_cargo': '19173537790119',   # BCP PEN
                     'comprobante_url': ''},
                    {'importe': 4000.00, 'codigo_operacion': 'BCK-002',
                     'cuenta_cargo': '00110123456789',   # BBVA PEN
                     'comprobante_url': ''},
                    {'importe': 3160.00, 'codigo_operacion': 'BCK-003',
                     'cuenta_cargo': '09830123456789',   # INTERBANK PEN
                     'comprobante_url': ''},
                ]
                # QoriCash paga USD al cliente en 2 cuentas distintas
                payments_a = [
                    {'importe': 1500.00, 'cuenta_destino': '19174567890234'},   # BCP USD
                    {'importe': 1500.00, 'cuenta_destino': '00001234567890'},   # SCOTIABANK USD
                ]
                op_a = Operation(
                    operation_id=OP_A_ID,
                    client_id=client.id,
                    operation_type='Compra',
                    origen='sistema',
                    amount_usd=Decimal('3000.00'),
                    exchange_rate=Decimal('3.7200'),
                    amount_pen=Decimal('11160.00'),
                    status='Completada',
                    completed_at=datetime(2026, 3, 10, 14, 30, 0),
                    client_deposits_json=json.dumps(deposits_a),
                    client_payments_json=json.dumps(payments_a),
                )
                db.session.add(op_a)
                db.session.flush()

                entry_a = JournalService.create_entry_for_completed_operation(op_a)
                if entry_a:
                    print(f"\n  ✓ Operación A: {OP_A_ID}  COMPRA $3,000 @ 3.7200 = S/ 11,160")
                    print(f"    Abonos PEN:")
                    print(f"      BCP PEN   S/ 4,000.00  → cuenta 1041 DEBE")
                    print(f"      BCP PEN   S/ 4,000.00  → cuenta 1041 DEBE (cliente BBVA→fallback BCP)")
                    print(f"      INTERBANK S/ 3,160.00  → cuenta 1048 DEBE")
                    print(f"    Pagos USD:")
                    print(f"      BCP USD   $1,500 (S/ 5,580) → cuenta 1044 HABER")
                    print(f"      BCP USD   $1,500 (S/ 5,580) → cuenta 1044 HABER (cliente Scotia→fallback BCP)")
                    print(f"    Asiento: {entry_a.entry_number}  DEBE S/{entry_a.total_debe}  HABER S/{entry_a.total_haber}")
                else:
                    print(f"  ✗ Error al crear asiento para {OP_A_ID}")
            else:
                print(f"  · {OP_A_ID} ya existe — saltando")

            # ── Operación B: VENTA $2,000 con 2 abonos USD / 2 pagos PEN ───
            OP_B_ID = 'DEMO-MB-VENTA-001'
            if not Operation.query.filter_by(operation_id=OP_B_ID).first():
                # Cliente deposita USD desde 2 cuentas
                deposits_b = [
                    {'importe': 1200.00, 'codigo_operacion': 'BKV-001',
                     'cuenta_cargo': '19174567890234',   # BCP USD
                     'comprobante_url': ''},
                    {'importe':  800.00, 'codigo_operacion': 'BKV-002',
                     'cuenta_cargo': '00001234567890',   # SCOTIABANK USD
                     'comprobante_url': ''},
                ]
                # QoriCash paga PEN al cliente en 2 bancos
                payments_b = [
                    {'importe': 4000.00, 'cuenta_destino': '19173537790119'},   # BCP PEN
                    {'importe': 3380.00, 'cuenta_destino': '00110123456789'},   # BBVA PEN
                ]
                op_b = Operation(
                    operation_id=OP_B_ID,
                    client_id=client.id,
                    operation_type='Venta',
                    origen='sistema',
                    amount_usd=Decimal('2000.00'),
                    exchange_rate=Decimal('3.6900'),
                    amount_pen=Decimal('7380.00'),
                    status='Completada',
                    completed_at=datetime(2026, 3, 18, 10, 15, 0),
                    client_deposits_json=json.dumps(deposits_b),
                    client_payments_json=json.dumps(payments_b),
                )
                db.session.add(op_b)
                db.session.flush()

                entry_b = JournalService.create_entry_for_completed_operation(op_b)
                if entry_b:
                    print(f"\n  ✓ Operación B: {OP_B_ID}  VENTA $2,000 @ 3.6900 = S/ 7,380")
                    print(f"    Abonos USD:")
                    print(f"      BCP USD   $1,200 (S/ 4,428) → cuenta 1044 DEBE")
                    print(f"      BCP USD   $  800 (S/ 2,952) → cuenta 1044 DEBE (cliente Scotia→fallback BCP)")
                    print(f"    Pagos PEN:")
                    print(f"      BCP PEN   S/ 4,000.00 → cuenta 1041 HABER")
                    print(f"      BCP PEN   S/ 3,380.00 → cuenta 1041 HABER (cliente BBVA→fallback BCP)")
                    print(f"    Asiento: {entry_b.entry_number}  DEBE S/{entry_b.total_debe}  HABER S/{entry_b.total_haber}")
                else:
                    print(f"  ✗ Error al crear asiento para {OP_B_ID}")
            else:
                print(f"  · {OP_B_ID} ya existe — saltando")

            db.session.commit()
            print(f"\n✓ seed-demo-multibanco completado")
            print(f"  Para eliminar: flask drop-demo-multibanco")
            print(f"  Ver en: /contabilidad/caja?year=2026&month=3")

        except Exception as e:
            db.session.rollback()
            print(f"✗ Error: {e}")
            traceback.print_exc()

    @app.cli.command("drop-demo-multibanco")
    def drop_demo_multibanco():
        """Elimina el cliente y operaciones del seed-demo-multibanco."""
        from app.extensions import db
        from app.models.client import Client
        from app.models.operation import Operation
        from app.models.journal_entry import JournalEntry
        from app.models.journal_entry_line import JournalEntryLine
        import traceback

        try:
            # Asientos de las operaciones demo
            for op_id in ['DEMO-MB-COMPRA-001', 'DEMO-MB-VENTA-001']:
                op = Operation.query.filter_by(operation_id=op_id).first()
                if op:
                    je = JournalEntry.query.filter_by(
                        source_type='operation', source_id=op.id
                    ).first()
                    if je:
                        JournalEntryLine.query.filter_by(
                            journal_entry_id=je.id
                        ).delete(synchronize_session=False)
                        db.session.delete(je)
                    db.session.delete(op)
                    print(f"  ✓ Operación {op_id} + asiento eliminados")

            # Cliente demo
            client = Client.query.filter_by(dni='72345678').first()
            if client:
                db.session.delete(client)
                print(f"  ✓ Cliente demo DNI 72345678 eliminado")

            db.session.commit()
            print(f"✓ drop-demo-multibanco completado")
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error: {e}")
            traceback.print_exc()

    @app.cli.command("clear-complaints")
    def clear_complaints():
        """Elimina TODOS los reclamos de la tabla complaints (producción)."""
        from app.extensions import db
        from app.models.complaint import Complaint
        import traceback
        try:
            count = Complaint.query.count()
            if count == 0:
                print("✓ No hay reclamos que eliminar.")
                return
            print(f"  Se van a eliminar {count} reclamo(s)...")
            Complaint.query.delete()
            db.session.commit()
            print(f"✓ {count} reclamo(s) eliminado(s) correctamente.")
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error: {e}")
            traceback.print_exc()

    @app.cli.command("drop-all-demo")
    def drop_all_demo():
        """
        Limpieza completa de TODOS los datos demo:
        asientos, gastos, operaciones, períodos, cliente demo,
        compliance/KYC, matches y batches ligados a operaciones demo.
        """
        from app.extensions import db
        from app.models.journal_entry import JournalEntry
        from app.models.journal_entry_line import JournalEntryLine
        from app.models.expense_record import ExpenseRecord
        from app.models.operation import Operation
        from app.models.accounting_period import AccountingPeriod
        from app.models.accounting_batch import AccountingBatch
        from app.models.accounting_match import AccountingMatch
        from app.models.journal_sequence import JournalSequence
        from app.models.client import Client
        from app.models.compliance import (
            ClientRiskProfile, ComplianceAlert, RestrictiveListCheck,
            TransactionMonitoring, ComplianceDocument, ComplianceAudit,
        )
        from sqlalchemy import extract
        import traceback

        DEMO_DNI  = '72345678'
        DEMO_YEAR = 2026
        DEMO_MONTHS = [1, 2, 3]

        try:
            # ── 1. Recopilar IDs de operaciones demo ────────────────────────
            demo_ops = Operation.query.filter(
                Operation.operation_id.like('DEMO-%')
            ).all()
            demo_op_ids = [op.id for op in demo_ops]
            print(f"  · {len(demo_op_ids)} operaciones demo encontradas")

            # ── 2. Compliance ligado a operaciones y cliente demo ───────────
            demo_client = Client.query.filter_by(dni=DEMO_DNI).first()
            demo_client_id = demo_client.id if demo_client else None

            if demo_op_ids:
                tm_del = TransactionMonitoring.query.filter(
                    TransactionMonitoring.operation_id.in_(demo_op_ids)
                ).delete(synchronize_session=False)
                alert_op_del = ComplianceAlert.query.filter(
                    ComplianceAlert.operation_id.in_(demo_op_ids)
                ).delete(synchronize_session=False)
                print(f"  ✓ {tm_del} transaction_monitoring, {alert_op_del} alertas (ops) eliminadas")

            if demo_client_id:
                alert_cl_del = ComplianceAlert.query.filter_by(
                    client_id=demo_client_id
                ).delete(synchronize_session=False)
                rlc_del = RestrictiveListCheck.query.filter_by(
                    client_id=demo_client_id
                ).delete(synchronize_session=False)
                doc_del = ComplianceDocument.query.filter_by(
                    client_id=demo_client_id
                ).delete(synchronize_session=False)
                audit_del = ComplianceAudit.query.filter_by(
                    client_id=demo_client_id
                ).delete(synchronize_session=False) if hasattr(ComplianceAudit, 'client_id') else 0
                profile_del = ClientRiskProfile.query.filter_by(
                    client_id=demo_client_id
                ).delete(synchronize_session=False)
                print(f"  ✓ KYC/compliance del cliente demo: {alert_cl_del} alertas, "
                      f"{rlc_del} listas restrictivas, {doc_del} docs, {profile_del} perfil de riesgo")

            # ── 3. Accounting matches y batches de ops demo ─────────────────
            if demo_op_ids:
                match_del = AccountingMatch.query.filter(
                    (AccountingMatch.buy_operation_id.in_(demo_op_ids)) |
                    (AccountingMatch.sell_operation_id.in_(demo_op_ids))
                ).delete(synchronize_session=False)
                print(f"  ✓ {match_del} accounting_matches eliminados")

                # Batches sin matches restantes
                batch_ids_used = [
                    r[0] for r in db.session.query(AccountingMatch.batch_id)
                    .filter(AccountingMatch.batch_id.isnot(None)).all()
                ]
                orphan_batches = AccountingBatch.query.filter(
                    AccountingBatch.id.notin_(batch_ids_used) if batch_ids_used
                    else AccountingBatch.id.isnot(None)
                ).all()
                for b in orphan_batches:
                    db.session.delete(b)
                print(f"  ✓ {len(orphan_batches)} batches huérfanos eliminados")

            # ── 4. Journal entries de las operaciones demo ──────────────────
            if demo_op_ids:
                je_op_ids = [r[0] for r in db.session.query(JournalEntry.id).filter(
                    JournalEntry.source_id.in_(demo_op_ids),
                    JournalEntry.source_type == 'operation',
                ).all()]
                if je_op_ids:
                    JournalEntryLine.query.filter(
                        JournalEntryLine.journal_entry_id.in_(je_op_ids)
                    ).delete(synchronize_session=False)
                    JournalEntry.query.filter(
                        JournalEntry.id.in_(je_op_ids)
                    ).delete(synchronize_session=False)
                    print(f"  ✓ {len(je_op_ids)} asientos de operaciones eliminados")

            # ── 5. Operaciones demo ─────────────────────────────────────────
            op_del = Operation.query.filter(
                Operation.operation_id.like('DEMO-%')
            ).delete(synchronize_session=False)
            print(f"  ✓ {op_del} operaciones demo eliminadas")

            # ── 6. Asientos demo (source_type='demo') + gastos por mes ──────
            for month in DEMO_MONTHS:
                er_del = ExpenseRecord.query.filter(
                    extract('year',  ExpenseRecord.expense_date) == DEMO_YEAR,
                    extract('month', ExpenseRecord.expense_date) == month,
                ).delete(synchronize_session=False)

                je_ids = [r[0] for r in db.session.query(JournalEntry.id).filter(
                    JournalEntry.source_type == 'demo',
                    extract('year',  JournalEntry.entry_date) == DEMO_YEAR,
                    extract('month', JournalEntry.entry_date) == month,
                ).all()]
                if je_ids:
                    JournalEntryLine.query.filter(
                        JournalEntryLine.journal_entry_id.in_(je_ids)
                    ).delete(synchronize_session=False)
                    JournalEntry.query.filter(
                        JournalEntry.id.in_(je_ids)
                    ).delete(synchronize_session=False)

                period = AccountingPeriod.query.filter_by(year=DEMO_YEAR, month=month).first()
                if period:
                    db.session.delete(period)

                names = {1:'Ene', 2:'Feb', 3:'Mar'}
                print(f"  ✓ {names[month]} {DEMO_YEAR}: {er_del} gastos, {len(je_ids)} asientos demo")

            # ── 7. Asiento de apertura demo (si existe) ─────────────────────
            apertura_del = JournalEntry.query.filter(
                JournalEntry.entry_type == 'apertura',
                extract('year', JournalEntry.entry_date) == DEMO_YEAR,
            ).all()
            for ap in apertura_del:
                JournalEntryLine.query.filter_by(
                    journal_entry_id=ap.id
                ).delete(synchronize_session=False)
                db.session.delete(ap)
            if apertura_del:
                print(f"  ✓ {len(apertura_del)} asiento(s) de apertura eliminados")

            # ── 8. Secuencia de numeración 2026 (reset) ─────────────────────
            seq = JournalSequence.query.filter_by(year=DEMO_YEAR).first()
            if seq:
                db.session.delete(seq)
                print(f"  ✓ JournalSequence {DEMO_YEAR} eliminada (se reiniciará desde AS-2026-0001)")

            # ── 9. Cliente demo ─────────────────────────────────────────────
            if demo_client:
                db.session.delete(demo_client)
                print(f"  ✓ Cliente demo DNI {DEMO_DNI} eliminado")

            db.session.commit()
            print(f"\n✓ drop-all-demo completado — base de datos lista para producción")

        except Exception as e:
            db.session.rollback()
            print(f"✗ Error: {e}")
            traceback.print_exc()
