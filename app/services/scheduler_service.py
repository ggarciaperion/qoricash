"""
Schedulers del sistema QoriCash.

Todos los jobs periódicos corren como greenlets eventlet lanzados en app/__init__.py:
  - start_operation_expiry_scheduler(app)  → expira operaciones cada 60s
  - start_market_schedulers(app)           → precios, noticias, macro, fx_monitor, calendario

Este archivo se conserva como referencia histórica.
No hay jobs activos aquí.
"""
