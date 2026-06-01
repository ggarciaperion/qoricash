"""
Script para cerrar el periodo contable mayo 2026.
Ejecutar en Render shell: python3 cerrar_mayo.py
"""
from app import create_app
from app.services.accounting.journal_service import JournalService

app = create_app()

with app.app_context():
    from app.models.user import User
    master = User.query.filter_by(role='Master').first()
    if not master:
        print('ERROR: No se encontro usuario Master.')
        exit(1)

    result = JournalService.close_period(year=2026, month=5, user_id=master.id)
    if result:
        print('Periodo mayo 2026 CERRADO correctamente.')
    else:
        print('ERROR al cerrar el periodo. Verificar logs.')
