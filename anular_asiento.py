"""
Anula un asiento contable por su entry_number.

Uso:
    python3 anular_asiento.py AS-2026-0132
"""
import sys
from app import create_app
from app.extensions import db
from app.utils.formatters import now_peru

app = create_app()

with app.app_context():
    from app.models.journal_entry import JournalEntry

    if len(sys.argv) < 2:
        print('Uso: python3 anular_asiento.py <entry_number>')
        sys.exit(1)

    entry_number = sys.argv[1].strip()
    entry = JournalEntry.query.filter_by(entry_number=entry_number).first()

    if not entry:
        print(f'Asiento {entry_number} no encontrado.')
        sys.exit(1)

    if entry.status == 'anulado':
        print(f'Asiento {entry_number} ya está anulado.')
        sys.exit(0)

    print(f'Asiento encontrado:')
    print(f'  ID          : {entry.id}')
    print(f'  Número      : {entry.entry_number}')
    print(f'  Fecha       : {entry.entry_date}')
    print(f'  Descripción : {entry.description}')
    print(f'  Estado      : {entry.status}')

    confirm = input(f'\n¿Anular este asiento? [s/N]: ')
    if confirm.strip().lower() != 's':
        print('Abortado.')
        sys.exit(0)

    entry.status          = 'anulado'
    entry.annulled_at     = now_peru()
    entry.annulled_reason = 'Anulado manualmente: asiento de ajuste basado en activo ficticio'
    db.session.commit()

    print(f'\n✓ Asiento {entry_number} anulado correctamente.')
