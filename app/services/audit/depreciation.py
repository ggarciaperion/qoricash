"""
Motor de Depreciación Automática
==================================
Genera el asiento de depreciación mensual para todos los activos fijos
activos que aún no han sido depreciados en el período indicado.

Cuenta PCGE:
  DEBE  6814  Depreciación de inmuebles, maquinaria y equipo
  HABER 39xx  Depreciación acumulada (3951/3961/3962/3921)

El motor es IDEMPOTENTE: si ya existe un asiento de depreciación para
el activo en el período, no genera uno nuevo.

Retorna:
  {
    'generados': int,         — asientos creados
    'omitidos': int,          — activos ya depreciados este período
    'errores': list[str],     — activos con error
    'total_depreciation': float  — monto total en PEN depreciado
  }
"""
import logging
from datetime import date
from decimal import Decimal

from app.extensions import db

logger = logging.getLogger(__name__)


def run_depreciacion_mensual(year: int, month: int,
                              created_by_id: int = None) -> dict:
    """
    Genera asientos de depreciación mensual para todos los activos activos
    del período year/month que aún no tienen asiento de depreciación.

    Solo crea asientos — NUNCA modifica asientos existentes.
    """
    from app.models.fixed_asset import FixedAsset
    from app.models.journal_entry import JournalEntry
    from app.services.accounting.journal_service import JournalService
    import calendar

    # Último día del período
    last_day = calendar.monthrange(year, month)[1]
    period_date = date(year, month, last_day)

    # Activos con asiento de depreciación ya registrado este período
    existing_source_ids = {
        r[0] for r in db.session.query(JournalEntry.source_id).filter(
            JournalEntry.entry_type == 'depreciacion',
            JournalEntry.source_type == 'fixed_asset',
            JournalEntry.status == 'activo',
        ).all() if r[0]
    }

    # IDs de asientos de depreciación por activo en este período exacto
    # (verificación más estricta: mismo período mes/año)
    from sqlalchemy import extract
    existing_this_period = {
        r[0] for r in db.session.query(JournalEntry.source_id).filter(
            JournalEntry.entry_type == 'depreciacion',
            JournalEntry.source_type == 'fixed_asset',
            extract('year',  JournalEntry.entry_date) == year,
            extract('month', JournalEntry.entry_date) == month,
            JournalEntry.status == 'activo',
        ).all() if r[0]
    }

    # Activos elegibles
    assets = FixedAsset.query.filter(
        FixedAsset.status == 'activo',
        FixedAsset.acquisition_date <= period_date,
    ).all()

    generados       = 0
    omitidos        = 0
    errores         = []
    total_deprec    = Decimal('0')

    for asset in assets:
        if asset.is_fully_depreciated:
            omitidos += 1
            continue

        if asset.id in existing_this_period:
            omitidos += 1
            continue

        # Monto a depreciar este mes
        monto = Decimal(str(asset.monthly_depreciation))

        # No depreciar más allá del valor neto en libros
        valor_neto = asset.net_book_value
        if valor_neto <= 0:
            asset.status = 'depreciado'
            db.session.add(asset)
            omitidos += 1
            continue

        monto = min(monto, valor_neto)

        try:
            entry = JournalService.create_entry(
                entry_type='depreciacion',
                description=(
                    f'Depreciación {asset.asset_code} — {asset.name[:40]} '
                    f'({year}/{month:02d})'
                ),
                lines=[
                    {
                        'account_code': '6814',
                        'description':  (
                            f'Gasto depreciación {asset.category} '
                            f'{asset.asset_code}'
                        ),
                        'debe':     monto,
                        'haber':    Decimal('0'),
                        'currency': 'PEN',
                    },
                    {
                        'account_code': asset.deprec_account,
                        'description':  (
                            f'Depreciación acumulada {asset.asset_code} '
                            f'mes {month:02d}/{year}'
                        ),
                        'debe':     Decimal('0'),
                        'haber':    monto,
                        'currency': 'PEN',
                    },
                ],
                source_type='fixed_asset',
                source_id=asset.id,
                entry_date=period_date,
                created_by=created_by_id,
            )

            if entry:
                # Actualizar el activo
                asset.months_depreciated = (asset.months_depreciated or 0) + 1
                asset.accumulated_depreciation = (
                    Decimal(str(asset.accumulated_depreciation or 0)) + monto
                ).quantize(Decimal('0.01'))
                if asset.is_fully_depreciated:
                    asset.status = 'depreciado'
                db.session.add(asset)
                db.session.commit()

                generados    += 1
                total_deprec += monto
                logger.info(
                    f'[Depreciation] ✅ {asset.asset_code} '
                    f'S/ {monto:.2f} → {entry.entry_number}'
                )
            else:
                errores.append(
                    f'{asset.asset_code}: período cerrado o error en JournalService'
                )

        except Exception as exc:
            db.session.rollback()
            msg = f'{asset.asset_code}: {exc}'
            errores.append(msg)
            logger.error(f'[Depreciation] ❌ {msg}')

    return {
        'generados':         generados,
        'omitidos':          omitidos,
        'errores':           errores,
        'total_depreciation': float(total_deprec),
        'period':            f'{year}/{month:02d}',
    }


def check_activos_pendientes(year: int, month: int) -> list:
    """
    Retorna lista de activos que necesitan depreciación en el período
    pero aún no la tienen registrada. Para uso del audit engine.
    """
    from app.models.fixed_asset import FixedAsset
    from app.models.journal_entry import JournalEntry
    from sqlalchemy import extract
    import calendar

    last_day    = calendar.monthrange(year, month)[1]
    period_date = date(year, month, last_day)

    existing_this_period = {
        r[0] for r in db.session.query(JournalEntry.source_id).filter(
            JournalEntry.entry_type == 'depreciacion',
            JournalEntry.source_type == 'fixed_asset',
            extract('year',  JournalEntry.entry_date) == year,
            extract('month', JournalEntry.entry_date) == month,
            JournalEntry.status == 'activo',
        ).all() if r[0]
    }

    pendientes = []
    assets = FixedAsset.query.filter(
        FixedAsset.status == 'activo',
        FixedAsset.acquisition_date <= period_date,
    ).all()

    for a in assets:
        if not a.is_fully_depreciated and a.id not in existing_this_period:
            pendientes.append({
                'asset_code':          a.asset_code,
                'name':                a.name,
                'monthly_depreciation': float(a.monthly_depreciation),
                'months_depreciated':  a.months_depreciated or 0,
                'remaining_months':    a.remaining_months,
            })

    return pendientes
