"""Compara el modelo de Python con el de Apps Script (la versión original) ejecutando los .gs reales en node.

Uso (desde dashboard_python):  python3 pruebas/comparar_con_apps_script.py
Requiere node. Sale con código 1 si hay diferencias.

Corre sobre la BD real y sobre variantes con casos borde (texto donde va un número, celdas vacías,
booleanos, fechas, filas con espacios, números gigantes, bases en cero...). La comparación es exacta,
sin tolerancia. getValues() de Google Sheets se imita: vacío = '', fechas = Date en la zona de la hoja.

Diferencias aceptadas (documentadas en calculos.py y en el LEEME):
  - vertical.esf[*].dpp: Python da null cuando la base de algún año es 0; Apps Script da un número
    por la aritmética de null en JavaScript.
  - meta.generado: hora de cálculo.
Casos en que Python falla a propósito y Apps Script no:
  - Fórmulas sin valor guardado (Google Sheets recalcula; openpyxl no): Python lo dice en vez de leer 0.
"""
import datetime
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from openpyxl import load_workbook

AQUI = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AQUI))
from calculos import construir_modelo  # noqa: E402
from datos import leer_base_datos  # noqa: E402
from serializar import a_json  # noqa: E402

GAS = AQUI.parent / "dashboard_globant" / "apps_script"
BD = AQUI / "data" / "BD_Dashboard_Globant.xlsx"

ARNES_JS = r"""
const fs = require('fs'), vm = require('vm');
const [gas, hojas, y1, y2] = process.argv.slice(2);
const data = JSON.parse(fs.readFileSync(hojas, 'utf8'));
const copia = n => data[n].map(r => r.map(v => v && v.__fecha ? new Date(v.__fecha) : v));
const ctx = { console, HtmlService: {}, Utilities: { formatDate: () => 'X' },
  SpreadsheetApp: { getActiveSpreadsheet: () => ({ getSheetByName: n => data[n]
    ? { getDataRange: () => ({ getValues: () => copia(n) }) } : null }) } };
vm.createContext(ctx);
for (const f of ['Code.gs', 'Datos.gs', 'Calculos.gs']) vm.runInContext(fs.readFileSync(gas + '/' + f, 'utf8'), ctx, { filename: f });
try { process.stdout.write(JSON.stringify(vm.runInContext(`construirModelo_(leerBaseDatos_(), ${+y1}, ${+y2})`, ctx))); }
catch (e) { process.stdout.write(JSON.stringify({ __error: String(e.message) })); }
"""


def valores_de_sheets(ruta):
    """Lo que devolvería getDataRange().getValues() de cada hoja."""
    wb = load_workbook(ruta, data_only=True)
    out = {}
    for ws in wb.worksheets:
        filas = []
        for r in ws.iter_rows(values_only=True):
            filas.append(["" if v is None else {"__fecha": v.isoformat()} if isinstance(v, (datetime.date, datetime.datetime)) else v
                          for v in r])
        while filas and all(v == "" for v in filas[-1]):
            filas.pop()
        out[ws.title] = filas
    return out


def fila(ws, id_):
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, 1).value == id_:
            return r
    raise KeyError(id_)


COL = {y: 6 + i for i, y in enumerate(range(2018, 2026))}


def poner(hoja, id_o_fila, col, valor):
    def f(wb):
        ws = wb[hoja]
        r = fila(ws, id_o_fila) if isinstance(id_o_fila, str) else id_o_fila
        ws.cell(r, col).value = valor
    return f


def fila_espacios(wb):
    ws = wb["Hitos"]
    ws.cell(ws.max_row + 1, 1).value = "  "


VARIANTES = {
    "base": lambda wb: None,
    "orden_texto_punto": poner("ER", "GA", 5, "6.5"),
    "orden_texto_coma": poner("ER", "GA", 5, "4,5"),
    "orden_vacio": poner("ER", "GA", 5, None),
    "orden_booleano": poner("ER", "GA", 5, True),
    "tipo_vacio": poner("ER", "OGP", 3, None),
    "cuenta_vacia": poner("ER", "OGP", 2, None),
    "valor_booleano": poner("ER", "OGP", COL[2020], True),
    "valor_texto_miles": poner("ER", "OGP", COL[2020], "$1.234.567 M"),
    "valor_texto_negativo": poner("ER", "OGP", COL[2020], "-1.234,5"),
    "valor_gigante": poner("ER", "OGP", COL[2020], "9" * 400),
    "patrimonio_cero_2018": poner("ESF", "PAT", COL[2018], 0),
    "ingresos_cero_2018": poner("ER", "ING", COL[2018], 0),
    "fila_solo_espacios": fila_espacios,
    "fecha_en_tabla": poner("Hitos", 2, 2, datetime.datetime(2024, 3, 1)),
    "empresa_booleano": poner("Empresa", 2, 2, False),
    "empresa_decimal": poner("Empresa", 2, 2, 2.5),
    "deflactor_anio_texto": poner("Deflactor", 3, 1, "2019"),
    "deflactor_anio_decimal_texto": poner("Deflactor", 3, 1, "2019.0"),
    "inflacion_texto": poner("Deflactor", 3, 2, "3,8"),
    "inflacion_menos_100": poner("Deflactor", 3, 2, -100),
}
# Con la BD real, la base del vertical (2024-2025) nunca es 0; esta variante prueba la diferencia aceptada.
VARIANTES_DPP = {"patrimonio_cero_2024": poner("ESF", "PAT", COL[2024], 0)}


def diferencias(a, b, ruta="m", out=None, ignorar_dpp=False):
    out = [] if out is None else out
    num = (int, float)
    if isinstance(a, bool) or isinstance(b, bool) or not (isinstance(a, num) and isinstance(b, num)):
        if type(a) is not type(b):
            out.append(f"{ruta}: {a!r} ({type(a).__name__}) vs {b!r} ({type(b).__name__})")
            return out
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{ruta}.{k}: solo en {'python' if k in a else 'apps script'}")
            elif ignorar_dpp and k == "dpp" and ruta.startswith("m.vertical.esf[") and a[k] is None:
                continue
            else:
                diferencias(a[k], b[k], f"{ruta}.{k}", out, ignorar_dpp)
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append(f"{ruta}: longitud {len(a)} vs {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            diferencias(x, y, f"{ruta}[{i}]", out, ignorar_dpp)
    elif a != b:
        out.append(f"{ruta}: {a!r} vs {b!r}")
    return out


def modelo_python(ruta):
    try:
        m = json.loads(a_json(construir_modelo(leer_base_datos(ruta), 2024, 2025)))
        m["meta"]["generado"] = "X"
        return m
    except Exception as e:
        return {"__error": str(e)}


def modelo_apps_script(ruta, tmp):
    hojas = Path(tmp) / "hojas.json"
    hojas.write_text(json.dumps(valores_de_sheets(ruta), default=str), encoding="utf-8")
    arnes = Path(tmp) / "arnes.js"
    arnes.write_text(ARNES_JS, encoding="utf-8")
    salida = subprocess.run(["node", str(arnes), str(GAS), str(hojas), "2024", "2025"], capture_output=True, text=True,
                            check=True, env={**os.environ, "TZ": "America/Bogota"}).stdout
    return json.loads(salida)


def main():
    fallos = 0
    with tempfile.TemporaryDirectory() as tmp:
        casos = [(n, f, False) for n, f in VARIANTES.items()] + [(n, f, True) for n, f in VARIANTES_DPP.items()]
        for nombre, mutar, ignorar_dpp in casos:
            ruta = Path(tmp) / f"{nombre}.xlsx"
            wb = load_workbook(BD)
            mutar(wb)
            wb.save(ruta)
            difs = diferencias(modelo_python(ruta), modelo_apps_script(ruta, tmp), ignorar_dpp=ignorar_dpp)
            print(f"{'OK  ' if not difs else 'FALLA'} {nombre}" + (f": {len(difs)} diferencias" if difs else ""))
            for d in difs[:8]:
                print("      " + d)
            fallos += bool(difs)

        ruta = Path(tmp) / "inflacion_formula.xlsx"
        wb = load_workbook(BD)
        wb["Deflactor"].cell(3, 2).value = "=3.8"
        wb.save(ruta)
        error = modelo_python(ruta).get("__error", "")
        ok = "fórmulas sin valor calculado" in error and "Deflactor!B3" in error
        print(f"{'OK  ' if ok else 'FALLA'} inflacion_formula (Python debe avisar): {error or 'no avisó'}")
        fallos += not ok

    if fallos:
        print(f"\n{fallos} casos con diferencias.")
        sys.exit(1)
    print("\nModelo idéntico al de Apps Script en todos los casos.")


if __name__ == "__main__":
    main()
