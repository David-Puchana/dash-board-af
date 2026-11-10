"""app.py — Dossier financiero de Sistemas Colombia S.A.S. en Python (Flask).

Arquitectura (equivalente a Apps Script y Shiny):
  datos.py              lectura del .xlsx                      (≈ Datos.gs)
  calculos.py           modelo analítico                       (≈ Calculos.gs)
  serializar.py         JSON con la semántica de JSON.stringify
  templates/index.html  estructura de la página                (generado por sincronizar.py)
  static/               estilos, gráficos y lógica de interfaz (generados por sincronizar.py; sin datos)
El modelo se calcula en el servidor y viaja embebido en la página (window.DASHBOARD_DATA).
Se recalcula solo cuando cambia la fecha de modificación del .xlsx.

Acceso por enlace secreto: la página solo se sirve en /<DASH_TOKEN>/. Cualquier otra ruta da 404,
salvo /static (código de la interfaz, sin cifras), /salud y /robots.txt.
Con EXPIRA=AAAA-MM-DD, desde el día siguiente (hora de Bogotá) la página responde 410.
"""
import hmac
import os
import re
import threading
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, Response, abort, redirect

from calculos import construir_modelo
from datos import leer_base_datos
from serializar import json_en_script

AQUI = Path(__file__).resolve().parent
ZONA = ZoneInfo("America/Bogota")

CONFIG = {
    "BD": os.environ.get("DATA_PATH", str(AQUI / "data" / "BD_Dashboard_Globant.xlsx")),
    "ANIO_VERTICAL_1": int(os.environ.get("ANIO_VERTICAL_1", "2024")),
    "ANIO_VERTICAL_2": int(os.environ.get("ANIO_VERTICAL_2", "2025")),
    # URL pública del logotipo OFICIAL (la guía prohíbe dibujarlo). Vacío = espacio reservado.
    "LOGO_URL": os.environ.get("LOGO_URL", ""),
    "TOKEN": os.environ.get("DASH_TOKEN", ""),
    "EXPIRA": os.environ.get("EXPIRA", "").strip(),
}

if len(CONFIG["TOKEN"]) < 32 or not re.fullmatch(r"[A-Za-z0-9_-]+", CONFIG["TOKEN"]):
    raise RuntimeError("DASH_TOKEN debe tener al menos 32 caracteres [A-Za-z0-9_-]. "
                       "Genera uno con: python3 -c 'import secrets; print(secrets.token_urlsafe(32))'")
EXPIRA = date.fromisoformat(CONFIG["EXPIRA"]) if CONFIG["EXPIRA"] else None

PLANTILLA = (AQUI / "templates" / "index.html").read_text(encoding="utf-8")
MARCAS = {"__LOGO_URL__": 1, "__MODELO__": 1, "__ERROR__": 1}
for marca, veces in MARCAS.items():
    if PLANTILLA.count(marca) != veces:
        raise RuntimeError(f"templates/index.html debe contener {marca} exactamente una vez: ejecuta sincronizar.py")
_MARCA = re.compile("|".join(MARCAS))

PAGINA_VENCIDA = """<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Dashboard no disponible</title></head>
<body style="font-family:system-ui,sans-serif;padding:48px;color:#0F1014">
<h1 style="font-size:1.4rem">Este dashboard ya no está disponible.</h1></body></html>"""

app = Flask(__name__, static_folder="static", static_url_path="/static")

_cache = {"mtime": None, "json": None, "error": None}
_lock = threading.Lock()


def modelo_json():
    """Devuelve (json, error). Recalcula solo si el .xlsx cambió."""
    ruta = CONFIG["BD"]
    try:
        mtime = os.stat(ruta).st_mtime_ns
    except OSError as e:
        return None, f"No se encontró la base de datos: {e.strerror}"
    with _lock:
        if _cache["mtime"] != mtime:
            try:
                modelo = construir_modelo(leer_base_datos(ruta), CONFIG["ANIO_VERTICAL_1"], CONFIG["ANIO_VERTICAL_2"])
                _cache.update(mtime=mtime, json=json_en_script(modelo), error=None)
            except Exception as e:  # el error se muestra en la página, como en Apps Script y Shiny
                _cache.update(mtime=mtime, json=None, error=f"Error al leer la base de datos: {e}")
        return _cache["json"], _cache["error"]


def vencido():
    return EXPIRA is not None and datetime.now(ZONA).date() > EXPIRA


def token_valido(token):
    return hmac.compare_digest(token.encode(), CONFIG["TOKEN"].encode())


@app.after_request
def cabeceras(resp):
    resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Content-Security-Policy"] = "frame-ancestors 'none'"
    if resp.mimetype == "text/html":
        resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/<token>")
def sin_barra(token):
    if not token_valido(token):
        abort(404)
    return redirect(f"/{token}/", code=308)


@app.get("/<token>/")
def index(token):
    if not token_valido(token):
        abort(404)
    if vencido():
        return Response(PAGINA_VENCIDA, status=410, mimetype="text/html")
    datos, error = modelo_json()
    valores = {
        "__LOGO_URL__": json_en_script(CONFIG["LOGO_URL"]),
        "__MODELO__": datos or "null",
        "__ERROR__": json_en_script(error),
    }
    html = _MARCA.sub(lambda m: valores[m.group(0)], PLANTILLA)  # una sola pasada: lo insertado no se vuelve a recorrer
    return Response(html, mimetype="text/html")


@app.get("/robots.txt")
def robots():
    return Response("User-agent: *\nDisallow: /\n", mimetype="text/plain")


@app.get("/salud")
def salud():
    _, error = modelo_json()
    return ({"ok": False}, 500) if error else {"ok": True}


if __name__ == "__main__":
    print(f"Dashboard en http://127.0.0.1:8050/{CONFIG['TOKEN']}/")
    app.run(host="127.0.0.1", port=8050, debug=False)
