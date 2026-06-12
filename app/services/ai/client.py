"""
Cliente Anthropic compartido para todos los agentes IA de QoriCash.
"""
import os
import logging

_log = logging.getLogger(__name__)

# Modelos disponibles
HAIKU   = 'claude-haiku-4-5-20251001'   # rápido y económico — tareas repetitivas
SONNET  = 'claude-sonnet-4-6'            # análisis complejos

def get_client():
    """Retorna instancia del cliente Anthropic. Lanza si falta la API key."""
    try:
        import anthropic
        key = os.environ.get('ANTHROPIC_API_KEY', '')
        if not key:
            raise RuntimeError('ANTHROPIC_API_KEY no configurada en variables de entorno')
        return anthropic.Anthropic(api_key=key)
    except ImportError:
        raise RuntimeError('Paquete anthropic no instalado. Ejecuta: pip install anthropic')

def ask(prompt: str, system: str = '', model: str = HAIKU, max_tokens: int = 1024) -> str:
    """
    Llamada simple: retorna texto de respuesta o lanza excepción.
    """
    client = get_client()
    msgs = [{'role': 'user', 'content': prompt}]
    kwargs = dict(model=model, max_tokens=max_tokens, messages=msgs)
    if system:
        kwargs['system'] = system
    response = client.messages.create(**kwargs)
    return response.content[0].text.strip()

def ask_json(prompt: str, system: str = '', model: str = HAIKU, max_tokens: int = 2048) -> dict:
    """
    Llamada que espera JSON en la respuesta. Retorna dict o lanza excepción.
    Extracción robusta: soporta markdown code blocks, JSON inline, y texto con prefijo.
    """
    import json, re
    text = ask(prompt, system=system, model=model, max_tokens=max_tokens)
    if not text:
        raise ValueError('Respuesta vacía de Claude')

    # 1. Bloque markdown ```json ... ``` o ``` ... ```
    m = re.search(r'```(?:json)?\s*([\s\S]+?)```', text)
    if m:
        return json.loads(m.group(1).strip())

    # 2. Primer objeto JSON completo { ... } en el texto
    m2 = re.search(r'(\{[\s\S]*\})', text)
    if m2:
        return json.loads(m2.group(1))

    # 3. Primera array JSON [ ... ]
    m3 = re.search(r'(\[[\s\S]*\])', text)
    if m3:
        return json.loads(m3.group(1))

    raise ValueError(f'No se encontró JSON válido en la respuesta: {text[:200]}')
