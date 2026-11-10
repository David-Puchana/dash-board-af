"""serializar.py — JSON del modelo con la semántica de JSON.stringify de Apps Script."""
import json
import math


def _finito(o):
    """NaN e ±Infinity pasan a null, como hace JSON.stringify."""
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: _finito(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_finito(v) for v in o]
    return o


def a_json(obj):
    return json.dumps(_finito(obj), ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def json_en_script(obj):
    """JSON seguro dentro de <script>: sin '</script>', '<!--' ni separadores de línea Unicode."""
    return a_json(obj).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
