"""
Cliente Anthropic compartido para todos los agentes IA de QoriCash.

Compatibilidad eventlet/httpx:
  El SDK de Anthropic usa httpx/anyio internamente. Cuando eventlet ha
  aplicado monkey-patch, httpx falla con "Trio primitives monkey-patched out".
  Solución: ejecutar la llamada bloqueante en un OS thread real vía
  eventlet.tpool.execute(). Esto libera al greenlet actual sin romper httpx.
"""
import json
import os
import re
import logging

_log = logging.getLogger(__name__)

HAIKU  = 'claude-haiku-4-5-20251001'
SONNET = 'claude-sonnet-4-6'


# ── Llamada real (en OS thread, fuera del greenlet de eventlet) ──────────────

def _anthropic_blocking(api_key: str, model: str, messages: list,
                        system: str, max_tokens: int) -> tuple:
    """
    Se ejecuta en un OS thread real (via tpool) para evitar el conflicto
    entre eventlet monkey-patch y httpx/anyio del SDK de Anthropic.
    Retorna (text, input_tokens, output_tokens).
    """
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    kwargs = dict(model=model, max_tokens=max_tokens, messages=messages)
    if system:
        kwargs['system'] = system
    resp = client.messages.create(**kwargs)
    text = resp.content[0].text.strip() if resp.content else ''
    in_tok  = resp.usage.input_tokens  if resp.usage else 0
    out_tok = resp.usage.output_tokens if resp.usage else 0
    return text, in_tok, out_tok


def _anthropic_urllib(api_key: str, model: str, messages: list,
                      system: str, max_tokens: int) -> tuple:
    """
    Llamada directa a la API de Anthropic usando urllib (stdlib).
    No usa httpx/trio — seguro con eventlet monkey-patch activo pero sin hub.
    """
    import json as _json
    import urllib.request
    payload = {
        'model':      model,
        'max_tokens': max_tokens,
        'messages':   messages,
    }
    if system:
        payload['system'] = system
    body = _json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        'https://api.anthropic.com/v1/messages',
        data=body,
        method='POST',
        headers={
            'x-api-key':         api_key,
            'anthropic-version': '2023-06-01',
            'content-type':      'application/json',
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = _json.loads(resp.read())
    text    = data.get('content', [{}])[0].get('text', '').strip()
    usage   = data.get('usage', {})
    in_tok  = usage.get('input_tokens', 0)
    out_tok = usage.get('output_tokens', 0)
    return text, in_tok, out_tok


def _anthropic_subprocess(api_key: str, model: str, messages: list,
                          system: str, max_tokens: int) -> tuple:
    """
    Lanza un subproceso Python limpio (sin eventlet monkey-patch) para llamar
    a la API de Anthropic via urllib. Necesario cuando el hub de eventlet NO
    está corriendo y el monkey-patch ya rompió los sockets del proceso actual.
    """
    import subprocess
    import sys

    script = (
        "import sys, json, urllib.request\n"
        "p = json.loads(sys.stdin.read())\n"
        "payload = {'model': p['model'], 'max_tokens': p['max_tokens'], 'messages': p['messages']}\n"
        "if p.get('system'): payload['system'] = p['system']\n"
        "import json as _j\n"
        "body = _j.dumps(payload).encode('utf-8')\n"
        "req = urllib.request.Request(\n"
        "    'https://api.anthropic.com/v1/messages', data=body, method='POST',\n"
        "    headers={'x-api-key': p['api_key'], 'anthropic-version': '2023-06-01',\n"
        "             'content-type': 'application/json'})\n"
        "with urllib.request.urlopen(req, timeout=120) as r:\n"
        "    data = _j.loads(r.read())\n"
        "text = data.get('content', [{}])[0].get('text', '').strip()\n"
        "usage = data.get('usage', {})\n"
        "print(_j.dumps({'text': text, 'in_tok': usage.get('input_tokens', 0),\n"
        "                'out_tok': usage.get('output_tokens', 0)}))\n"
    )
    payload = json.dumps({
        'api_key': api_key, 'model': model, 'messages': messages,
        'system': system, 'max_tokens': max_tokens,
    })

    def _run_subprocess():
        """Corre en un hilo OS real via tpool — no afectado por eventlet."""
        proc = subprocess.Popen(
            [sys.executable, '-c', script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            out_bytes, err_bytes = proc.communicate(
                input=payload.encode('utf-8'), timeout=130
            )
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            raise RuntimeError('Anthropic API: timeout (>130 s) — subprocess terminado')
        if proc.returncode != 0:
            raise RuntimeError(f'Subprocess falló: {err_bytes.decode()[:400]}')
        return out_bytes, err_bytes

    # Llamar directamente (sin tpool):
    #   - Desde un greenlet de eventlet: subprocess.communicate() es
    #     cooperativo porque eventlet parchea os.read() → el hub sigue vivo.
    #   - Desde un OS thread (scheduler via tpool): I/O bloqueante normal — OK.
    # No se usa tpool aquí para evitar deadlock si ya estamos dentro de un
    # tpool worker (el scheduler usa tpool → agente llama _call → no anidar).
    stdout_data, _ = _run_subprocess()

    out = json.loads(stdout_data.decode().strip())
    return out['text'], out['in_tok'], out['out_tok']


def _call(api_key: str, model: str, messages: list,
          system: str, max_tokens: int) -> tuple:
    """
    Despacha la llamada a Anthropic.

    Estrategia de fallback:
    1. _anthropic_blocking (SDK) — funciona en OS threads reales (scheduler
       via tpool) donde httpx/anyio no está afectado por el monkey-patch.
       En greenlets (gunicorn + _bg()) falla con "Trio primitives monkey-patched"
       porque el estado global del proceso está parchado.
    2. _anthropic_subprocess — proceso Python limpio (sin monkey-patch).
       Funciona en TODOS los contextos:
       - Desde greenlet: subprocess.communicate() es cooperativo gracias al
         parche de os.read() de eventlet (no bloquea el hub).
       - Desde OS thread: I/O bloqueante normal, ningún problema.
       NO usa tpool internamente para evitar deadlock si el llamador ya
       está dentro de un tpool worker (scheduler).
    """
    try:
        return _anthropic_blocking(api_key, model, messages, system, max_tokens)
    except Exception as e:
        _log.warning(f'[Claude] SDK falló ({str(e)[:80]}), usando subprocess')

    return _anthropic_subprocess(api_key, model, messages, system, max_tokens)


# ── API pública ───────────────────────────────────────────────────────────────

def _get_key() -> str:
    key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not key:
        raise RuntimeError('ANTHROPIC_API_KEY no configurada en variables de entorno')
    return key


def ask(prompt: str, system: str = '', model: str = HAIKU,
        max_tokens: int = 1024) -> str:
    """Llamada simple: retorna el texto de la respuesta o lanza excepción."""
    try:
        import anthropic  # noqa — confirma que está instalado
    except ImportError:
        raise RuntimeError('Paquete anthropic no instalado. Ejecuta: pip install anthropic')

    key  = _get_key()
    msgs = [{'role': 'user', 'content': prompt}]
    text, in_tok, out_tok = _call(key, model, msgs, system, max_tokens)
    _log.debug(f'[Claude] {model} tokens in={in_tok} out={out_tok}')
    if not text:
        raise ValueError('Respuesta vacía de Claude')
    return text


def ask_json(prompt: str, system: str = '', model: str = HAIKU,
             max_tokens: int = 2048) -> dict:
    """
    Llamada que espera JSON en la respuesta. Retorna dict/list o lanza.
    Extracción robusta: soporta bloques markdown, JSON inline y texto con prefijo.
    """
    text = ask(prompt, system=system, model=model, max_tokens=max_tokens)

    # 1. Bloque markdown ```json … ``` o ``` … ```
    m = re.search(r'```(?:json)?\s*([\s\S]+?)```', text)
    if m:
        return json.loads(m.group(1).strip())

    # 2 & 3. Primer objeto o array JSON completo — raw_decode para en el primer
    # valor válido, ignorando texto adicional que Claude pueda añadir después.
    decoder = json.JSONDecoder()
    for start_char, pattern in [('{', r'\{'), ('[', r'\[')]:
        m = re.search(pattern, text)
        if m:
            try:
                obj, _ = decoder.raw_decode(text, m.start())
                return obj
            except json.JSONDecodeError:
                pass

    raise ValueError(f'No se encontró JSON válido en la respuesta: {text[:200]}')


def ask_with_usage(prompt: str, system: str = '', model: str = HAIKU,
                   max_tokens: int = 1024) -> tuple:
    """Igual que ask() pero retorna (text, input_tokens, output_tokens)."""
    try:
        import anthropic  # noqa
    except ImportError:
        raise RuntimeError('Paquete anthropic no instalado')

    key  = _get_key()
    msgs = [{'role': 'user', 'content': prompt}]
    return _call(key, model, msgs, system, max_tokens)
