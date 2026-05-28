"""
Live cache para notificaciones SSE del Trading Monitor.
El scraping loop llama a notify() después de cada ciclo.
Los clientes SSE suscritos reciben la señal y hacen fetch inmediato.
"""
import threading

_lock      = threading.Lock()
_version   = 0
_listeners = []   # lista de eventlet Queues, una por cliente SSE conectado


def notify():
    """Llamar después de cada ciclo de scraping exitoso."""
    global _version
    with _lock:
        _version += 1
        v = _version
        dead = []
        for q in _listeners:
            try:
                q.put_nowait(v)
            except Exception:
                dead.append(q)
        for q in dead:
            try:
                _listeners.remove(q)
            except ValueError:
                pass
    return v


def subscribe():
    """Crear una cola y suscribirla al feed. Retorna la cola."""
    import eventlet.queue
    q = eventlet.queue.LightQueue(maxsize=10)
    with _lock:
        _listeners.append(q)
    return q


def unsubscribe(q):
    """Eliminar la cola del feed cuando el cliente se desconecta."""
    with _lock:
        try:
            _listeners.remove(q)
        except ValueError:
            pass


def get_version():
    with _lock:
        return _version
