"""
Limpia el LIG de mayo 2026 marcando como 'anulado' el asiento FX fantasma
AS-2026-0113 y su asiento de reversión.

Por qué: el LIG filtra account_code LIKE '7%' AND haber > 0 AND status='activo'.
AS-2026-0113 tiene 7761 HABER 9704.39 activo → aparece como ingreso.
Su reverso tiene 7761 DEBE 9704.39 (no HABER) → no lo cancela en el LIG.
Solución: marcar ambos 'anulado' — su efecto contable neto ya era cero.

Resultado esperado en LIG mayo:
  - Solo AS-2026-0130: S/1,518.04 (spread real)
  - Total ingresos: S/1,518.04

Ejecutar en Render shell: python3 limpiar_fx_mayo_lig.py
"""
from app import create_app
from app.extensions import db

app = create_app()

TARGET = 'AS-2026-0113'

with app.app_context():
    from app.models.journal_entry import JournalEntry
    from app.models.journal_entry_line import JournalEntryLine

    # ── 1. Localizar AS-2026-0113 ─────────────────────────────────────────────
    original = JournalEntry.query.filter_by(entry_number=TARGET).first()
    if not original:
        print(f'ERROR: No se encontró {TARGET}.')
        exit(1)

    print(f'Asiento original: {original.entry_number} | status={original.status}')
    print(f'  DEBE={original.total_debe}  HABER={original.total_haber}')
    for l in JournalEntryLine.query.filter_by(journal_entry_id=original.id).all():
        print(f'  {l.account_code} D={l.debe} H={l.haber} | {(l.description or "")[:60]}')

    # ── 2. Localizar el reverso de AS-2026-0113 ───────────────────────────────
    reverso = JournalEntry.query.filter(
        JournalEntry.description.like(f'Reversión {TARGET}%'),
        JournalEntry.status == 'activo',
    ).first()

    print()
    if reverso:
        print(f'Asiento reverso: {reverso.entry_number} | status={reverso.status}')
        print(f'  DEBE={reverso.total_debe}  HABER={reverso.total_haber}')
        for l in JournalEntryLine.query.filter_by(journal_entry_id=reverso.id).all():
            print(f'  {l.account_code} D={l.debe} H={l.haber} | {(l.description or "")[:60]}')
    else:
        print('AVISO: No se encontró reverso activo (puede estar ya anulado o no creado).')

    # ── 3. Confirmar acción ───────────────────────────────────────────────────
    print()
    to_annul = [e for e in [original, reverso] if e and e.status == 'activo']
    if not to_annul:
        print('Nada que hacer — ambos asientos ya están anulados.')
        exit(0)

    print(f'Se marcarán como "anulado": {[e.entry_number for e in to_annul]}')
    print('Efecto: desaparecen del LIG y del Balance sin crear nuevas entradas.')

    for entry in to_annul:
        entry.status = 'anulado'

    db.session.commit()
    print()
    print('✓ Asientos anulados correctamente.')
    print()
    print('LIG mayo ahora debería mostrar:')
    print('  AS-2026-0130 | 7591 | S/1,518.04  ← spread real operativo')
    print('  TOTAL INGRESOS: S/1,518.04')
