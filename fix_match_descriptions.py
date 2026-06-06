"""
Script one-time: corrige descripciones de asientos de amarres con pérdida
que quedaron con texto "Ganancia FX" siendo en realidad pérdidas.

Ejecutar en Render shell:
  python3 fix_match_descriptions.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.extensions import db
from app.models.journal_entry import JournalEntry
from app.models.accounting_match import AccountingMatch
from decimal import Decimal

app = create_app()

with app.app_context():
    # Buscar todos los asientos de tipo calce_match con descripción "Ganancia FX"
    # pero cuyo match tiene profit_pen negativo
    entries = JournalEntry.query.filter(
        JournalEntry.entry_type == 'calce_match',
        JournalEntry.description.like('Ganancia FX amarre%'),
        JournalEntry.status == 'activo',
    ).all()

    fixed = 0
    for entry in entries:
        match = AccountingMatch.query.get(entry.source_id)
        if match and Decimal(str(match.profit_pen)) < 0:
            old_desc = entry.description
            entry.description = entry.description.replace('Ganancia FX amarre', 'Pérdida FX amarre')
            print(f'  ✓ {entry.entry_number}: "{old_desc}" → "{entry.description}"')
            fixed += 1

    db.session.commit()
    print(f'\nTotal corregidos: {fixed} asientos')
