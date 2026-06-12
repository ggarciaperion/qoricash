"""
Reabre un cierre diario validado (lo vuelve a estado 'borrador').
Revierte exactamente lo que hace api_cierre_confirmar:
  - closure.status → 'borrador'
  - closure.validated_by / validated_at → None
  - BankMovement.is_validated → False  (para los movimientos de ese día)

Uso:
  python3 reabrir_cierre.py YYYY-MM-DD          -> DRY RUN
  python3 reabrir_cierre.py YYYY-MM-DD --apply  -> aplica
"""
import os
import sys
from datetime import date

if len(sys.argv) < 2 or sys.argv[1].startswith('--'):
    print("Uso: python3 reabrir_cierre.py YYYY-MM-DD [--apply]")
    sys.exit(1)

fecha_str = sys.argv[1]
DRY_RUN   = '--apply' not in sys.argv

try:
    fecha = date.fromisoformat(fecha_str)
except ValueError:
    print(f"Fecha inválida: {fecha_str}. Usa formato YYYY-MM-DD.")
    sys.exit(1)

os.environ.setdefault('FLASK_ENV', 'production')
from app import create_app
app = create_app()

with app.app_context():
    from app.extensions import db
    from app.models.daily_closure import DailyClosure
    from app.models.bank_movement import BankMovement

    closure = DailyClosure.query.filter_by(closure_date=fecha).first()
    if not closure:
        print(f"No existe cierre para {fecha_str}.")
        sys.exit(1)

    print(f"Cierre encontrado: {fecha_str}")
    print(f"  status:       {closure.status}")
    print(f"  is_validated: {closure.is_validated}")
    print(f"  validated_at: {closure.validated_at}")
    print(f"  validated_by: {closure.validated_by}")

    mv_count = BankMovement.query.filter_by(closure_date=fecha, is_validated=True).count()
    print(f"  BankMovements is_validated=True: {mv_count}")

    if not closure.is_validated:
        print("\nEste cierre ya está en borrador — no necesita reabrirse.")
        sys.exit(0)

    if DRY_RUN:
        print(f"\n[DRY RUN] Se revertiría: status→borrador, validated_at→None, "
              f"{mv_count} BankMovements→is_validated=False")
        print("Usa --apply para aplicar.")
        sys.exit(0)

    closure.status       = DailyClosure.STATUS_BORRADOR
    closure.validated_by = None
    closure.validated_at = None

    BankMovement.query.filter_by(closure_date=fecha, is_validated=True).update(
        {'is_validated': False}
    )

    db.session.commit()
    print(f"\n✓ Cierre {fecha_str} reabierto correctamente.")
    print(f"  {mv_count} BankMovements desmarcados de validado.")
