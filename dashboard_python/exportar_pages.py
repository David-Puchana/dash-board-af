"""exportar_pages.py — Genera el sitio estático para Cloudflare Pages (sin servidor).

Uso (desde dashboard_python, después de sincronizar.py):
    python3 exportar_pages.py                      # código nuevo y aleatorio para el enlace
    python3 exportar_pages.py --token <código>     # conserva el enlace ya repartido
    python3 exportar_pages.py --expira 2026-11-30  # cambia la fecha de caducidad visible
    python3 exportar_pages.py --publico            # GitHub Pages: ../docs/index.html, público y sin caducidad

Genera pages/ (se sube tal cual a Cloudflare Pages):
  pages/<código>/index.html   la página completa: estilos, gráficos, lógica y cifras dentro del HTML
  pages/404.html              cualquier otra ruta
  pages/robots.txt, _headers  sin indexación, sin referer, sin marcos

Las cifras salen del mismo modelo que app.py (verificado contra Apps Script en pruebas/).
La caducidad de una página estática es solo visual: los datos siguen en el HTML. Retirar de verdad
= borrar el proyecto de Pages.
"""
import argparse
import re
import secrets
import shutil
import sys
from datetime import date
from pathlib import Path

from calculos import construir_modelo
from datos import leer_base_datos
from serializar import json_en_script

AQUI = Path(__file__).resolve().parent
SALIDA = AQUI / "pages"
BD = AQUI / "data" / "BD_Dashboard_Globant.xlsx"
ANIO_VERTICAL_1, ANIO_VERTICAL_2 = 2024, 2025
LOGO_URL = ""

HEADERS = """/*
  X-Robots-Tag: noindex, nofollow
  Referrer-Policy: no-referrer
  X-Content-Type-Options: nosniff
  Content-Security-Policy: frame-ancestors 'none'
  Cache-Control: no-store
"""

PAGINA_404 = """<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><meta name="robots" content="noindex">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>No encontrado</title></head>
<body style="font-family:system-ui,sans-serif;padding:48px;color:#0F1014"><h1 style="font-size:1.4rem">Página no encontrada.</h1></body></html>
"""


def incrustar(html, etiqueta, contenido, antes, despues):
    if html.count(etiqueta) != 1:
        sys.exit(f"Se esperaba exactamente una vez en la plantilla: {etiqueta}. Ejecuta sincronizar.py.")
    if re.search(r"</(script|style)", contenido, re.I):
        sys.exit(f"El contenido de {etiqueta} trae un cierre de etiqueta y no puede incrustarse.")
    return html.replace(etiqueta, antes + contenido + despues, 1)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--token", help="código del enlace (para conservar uno ya repartido)")
    p.add_argument("--expira", default=None, help="último día visible, AAAA-MM-DD (por defecto 2026-11-30; con --publico, sin caducidad)")
    p.add_argument("--publico", action="store_true", help="página pública en ../docs/index.html para GitHub Pages")
    a = p.parse_args()
    if a.expira is None:
        a.expira = "" if a.publico else "2026-11-30"

    token = a.token or secrets.token_urlsafe(32)
    if len(token) < 32 or not re.fullmatch(r"[A-Za-z0-9_-]+", token):
        sys.exit("El código debe tener al menos 32 caracteres [A-Za-z0-9_-].")
    if a.expira:
        date.fromisoformat(a.expira)

    modelo = construir_modelo(leer_base_datos(BD), ANIO_VERTICAL_1, ANIO_VERTICAL_2)
    html = (AQUI / "templates" / "index.html").read_text(encoding="utf-8")
    est = lambda f: (AQUI / "static" / f).read_text(encoding="utf-8")

    html = incrustar(html, '<link rel="stylesheet" href="/static/styles.css">', est("styles.css"), "<style>\n", "</style>")
    html = incrustar(html, '<script src="/static/charts.js"></script>', est("charts.js"), "<script>\n", "</script>")
    html = incrustar(html, '<script src="/static/app.js"></script>', est("app.js"), "<script>\n", "</script>")
    html = html.replace("<head>", '<head>\n  <meta name="referrer" content="no-referrer">'
                        + ("" if a.publico else '\n  <meta name="robots" content="noindex, nofollow">'), 1)

    # Caducidad visual (hora de Bogotá): se evalúa antes de dibujar el dashboard.
    caducidad = ""
    if a.expira:
        caducidad = ("<script>(function(){var hoy=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Bogota'}).format(new Date());"
                     f"if(hoy>{json_en_script(a.expira)}){{window.DASHBOARD_DATA=null;document.addEventListener('DOMContentLoaded',function(){{"
                     "document.body.innerHTML='<h1 style=\"font-family:system-ui,sans-serif;padding:48px;font-size:1.4rem\">"
                     "Este dashboard ya no está disponible.</h1>';});}})();</script>\n  ")
    datos = "<script>window.DASHBOARD_DATA = __MODELO__;</script>"
    html = incrustar(html, datos, "", datos, ("\n  " + caducidad.rstrip()) if caducidad else "")
    valores = {"__LOGO_URL__": json_en_script(LOGO_URL), "__MODELO__": json_en_script(modelo), "__ERROR__": "null"}
    for marca in valores:
        if html.count(marca) != 1:
            sys.exit(f"La plantilla debe contener {marca} exactamente una vez. Ejecuta sincronizar.py.")
    html = re.sub("|".join(valores), lambda m: valores[m.group(0)], html)  # una sola pasada
    if "/static/" in html:
        sys.exit("Quedó una referencia a /static/ en la página.")

    if a.publico:
        docs = AQUI.parent / "docs"
        docs.mkdir(exist_ok=True)
        (docs / "index.html").write_text(html, encoding="utf-8")
        (docs / ".nojekyll").write_text("", encoding="utf-8")  # GitHub Pages sirve los archivos tal cual
        print(f"Página pública generada en {docs}/index.html ({len(html) // 1024} KB)")
        return

    if SALIDA.exists():
        shutil.rmtree(SALIDA)
    (SALIDA / token).mkdir(parents=True)
    (SALIDA / token / "index.html").write_text(html, encoding="utf-8")
    (SALIDA / "404.html").write_text(PAGINA_404, encoding="utf-8")
    (SALIDA / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    (SALIDA / "_headers").write_text(HEADERS, encoding="utf-8")
    print(f"Sitio generado en {SALIDA}/ ({len(html) // 1024} KB)")
    print(f"Ruta secreta: /{token}/")


if __name__ == "__main__":
    main()
