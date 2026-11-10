"""sincronizar.py — Copia el frontend y la BD desde la versión de Apps Script.

Uso (desde dashboard_python):  python3 sincronizar.py
Genera (no editar a mano):
  static/styles.css     ← Styles.html (contenido de <style>)
  static/charts.js      ← Charts.html (contenido de <script>)
  static/app.js         ← JavaScript.html (contenido de <script>, sin cambios)
  templates/index.html  ← Index.html (scriptlets → etiquetas estándar; marcas __LOGO_URL__, __MODELO__ y __ERROR__)
  data/BD_Dashboard_Globant.xlsx ← ../dashboard_globant/BD_Dashboard_Globant.xlsx
"""
import re
import shutil
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
ORIGEN = AQUI.parent / "dashboard_globant" / "apps_script"
BD_ORIGEN = AQUI.parent / "dashboard_globant" / "BD_Dashboard_Globant.xlsx"


def leer(nombre):
    return (ORIGEN / nombre).read_text(encoding="utf-8")


def entre(txt, abre, cierra, archivo):
    bloques = re.findall(re.escape(abre) + r"(.*?)" + re.escape(cierra), txt, re.S)
    if len(bloques) != 1:
        sys.exit(f"Se esperaba exactamente un bloque {abre} … {cierra} en {archivo} y hay {len(bloques)}: "
                 "revisa sincronizar.py antes de seguir.")
    return bloques[0].strip() + "\n"


def reemplazar(txt, viejo, nuevo):
    if viejo not in txt:
        sys.exit(f"No se encontró en Index.html: {viejo}")
    return txt.replace(viejo, nuevo, 1)


def main():
    for d in ("static", "templates", "data"):
        (AQUI / d).mkdir(exist_ok=True)

    estilos = leer("Styles.html")
    (AQUI / "static/styles.css").write_text(entre(estilos, "<style>", "</style>", "Styles.html"), encoding="utf-8")
    links_fuentes = re.findall(r"<link[^>]*>", estilos)
    (AQUI / "static/charts.js").write_text(entre(leer("Charts.html"), "<script>", "</script>", "Charts.html"), encoding="utf-8")
    # app.js arranca solo con window.DASHBOARD_DATA, que inyecta app.py: no hace falta tocar la lógica.
    (AQUI / "static/app.js").write_text(entre(leer("JavaScript.html"), "<script>", "</script>", "JavaScript.html"), encoding="utf-8")

    index = leer("Index.html")
    index = reemplazar(index, "<?!= include('Styles'); ?>",
                       "\n  ".join(links_fuentes + ['<link rel="stylesheet" href="/static/styles.css">']))
    index = reemplazar(index, "<?!= JSON.stringify(logoUrl) ?>", "__LOGO_URL__")
    index = reemplazar(index, "<?!= include('Charts'); ?>",
                       '<script>window.DASHBOARD_DATA = __MODELO__;</script>\n  <script src="/static/charts.js"></script>')
    # El error del servidor se pinta con un script propio: funciona aunque app.js no cargue.
    aviso_error = ("<script>(function (e) { if (e === null) return; var c = document.getElementById('estado-carga'); "
                   "if (c) c.hidden = true; var b = document.getElementById('estado-error'); "
                   "if (b) { b.hidden = false; b.textContent = e; } })(__ERROR__);</script>")
    index = reemplazar(index, "<?!= include('JavaScript'); ?>", '<script src="/static/app.js"></script>\n  ' + aviso_error)
    index = index.replace('<base target="_top">\n  ', "", 1)
    if "<?" in index:
        sys.exit("Quedó un scriptlet de Apps Script sin convertir en Index.html")
    (AQUI / "templates/index.html").write_text(index, encoding="utf-8")

    shutil.copy2(BD_ORIGEN, AQUI / "data/BD_Dashboard_Globant.xlsx")
    print("Sincronizado: static/styles.css, static/charts.js, static/app.js, templates/index.html, data/BD_Dashboard_Globant.xlsx")


if __name__ == "__main__":
    main()
