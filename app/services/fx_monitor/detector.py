"""
Lógica de detección de cambios en tipos de cambio
"""
from decimal import Decimal

# Cambio mínimo absoluto para considerar que hubo un cambio real (filtro de ruido)
MIN_CHANGE_ABS = Decimal("0.0005")


def detect_change(new_buy, new_sell, prev_buy, prev_sell):
    """
    Compara nuevos precios contra los anteriores.

    Returns:
        dict con información del cambio, o None si no hubo cambio significativo.
    """
    if prev_buy is None or prev_sell is None:
        return None

    nb = Decimal(str(new_buy))
    ns = Decimal(str(new_sell))
    pb = Decimal(str(prev_buy))
    ps = Decimal(str(prev_sell))

    buy_changed  = abs(nb - pb) >= MIN_CHANGE_ABS
    sell_changed = abs(ns - ps) >= MIN_CHANGE_ABS

    if not buy_changed and not sell_changed:
        return None

    buy_delta  = nb - pb
    sell_delta = ns - ps

    if pb != 0:
        buy_delta_pct = (buy_delta / pb * 100).quantize(Decimal("0.001"))
    else:
        buy_delta_pct = Decimal("0")

    if ps != 0:
        sell_delta_pct = (sell_delta / ps * 100).quantize(Decimal("0.001"))
    else:
        sell_delta_pct = Decimal("0")

    if buy_changed and sell_changed:
        field = "both"
    elif buy_changed:
        field = "buy"
    else:
        field = "sell"

    return {
        "field":          field,
        "old_buy":        float(pb),
        "new_buy":        float(nb),
        "old_sell":       float(ps),
        "new_sell":       float(ns),
        "buy_delta":      float(buy_delta),
        "sell_delta":     float(sell_delta),
        "buy_delta_pct":  float(buy_delta_pct),
        "sell_delta_pct": float(sell_delta_pct),
    }
