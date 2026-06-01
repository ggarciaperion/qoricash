"""
Corrige AS-2026-0107 (ajuste FX abril) que tiene HABER > DEBE por 20,640.
El servicio ajuste_fx calculó la ganancia de 1012+1044 pero solo escribio
la linea DEBE para 1012. Este script agrega la linea faltante para 1044.
Ejecutar en Render shell: python3 fix_ajuste_fx_abril.py
"""
from app import create_app
from app.extensions import db
from decimal import Decimal

app = create_app()

ENTRY_NUMBER = 'AS-2026-0107'
MONTO        = Decimal('20640.00')

with app.app_context():
    from app.models.journal_entry import JournalEntry
    from app.models.journal_entry_line import JournalEntryLine

    entry = JournalEntry.query.filter_by(entry_number=ENTRY_NUMBER).first()
    if not entry:
        print('ERROR: No se encontro {}'.format(ENTRY_NUMBER))
        exit(1)

    print('Asiento encontrado: {} | DEBE={} HABER={}'.format(
        entry.entry_number, entry.total_debe, entry.total_haber
    ))

    diff = entry.total_haber - entry.total_debe
    print('Descuadre actual: {}'.format(diff))

    if abs(diff) < Decimal('0.01'):
        print('El asiento ya esta cuadrado. No se requiere correccion.')
        exit(0)

    if diff < 0:
        print('ERROR: el asiento tiene DEBE > HABER, revisar manualmente.')
        exit(1)

    # Verificar que no exista ya una linea DEBE en 1044
    existing = JournalEntryLine.query.filter_by(
        journal_entry_id=entry.id,
        account_code='1044'
    ).first()
    if existing:
        print('Ya existe linea para 1044: DEBE={} HABER={}'.format(
            existing.debe, existing.haber
        ))
        print('Revisar manualmente — no se modifica.')
        exit(1)

    # Agregar linea faltante: DEBE 1044
    nueva_linea = JournalEntryLine(
        journal_entry_id=entry.id,
        account_code='1044',
        description='Correccion ajuste FX — revaluacion BCP USD',
        debe=diff,
        haber=Decimal('0'),
        currency='PEN',
    )
    db.session.add(nueva_linea)

    # Actualizar total_debe del asiento
    entry.total_debe = entry.total_debe + diff

    db.session.commit()

    print('\nCorreccion aplicada:')
    print('  + Linea DEBE 1044 BCP USD: {}'.format(diff))
    print('  Nuevo total_debe: {}'.format(entry.total_debe))
    print('  Total haber:      {}'.format(entry.total_haber))
    print('  Diferencia:       {}'.format(abs(entry.total_debe - entry.total_haber)))

    if abs(entry.total_debe - entry.total_haber) <= Decimal('0.02'):
        print('\n{} CUADRADO CORRECTAMENTE.'.format(ENTRY_NUMBER))
    else:
        print('\nATENCION: sigue descuadrado.')
