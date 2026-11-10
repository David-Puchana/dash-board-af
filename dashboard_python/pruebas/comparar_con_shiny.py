"""Compara el modelo de Python con el de Shiny (R) campo por campo.

Uso (desde dashboard_python):  python3 pruebas/comparar_con_shiny.py
Requiere Rscript con readxl y jsonlite. Sale con código 1 si hay diferencias.
Tolerancia numérica relativa 1e-9 (mismas operaciones en coma flotante).

Equivalencias de representación aceptadas (el cliente no las distingue):
  - Celda vacía en las tablas (procedencia, homogenea, hitos, notas, reexpresiones): Python y Apps Script
    envían '', Shiny envía null (app.js usa vacio()). Solo se acepta dentro de esas tablas.
  - indiceReal sin base positiva: Python y Apps Script envían null, Shiny omite la clave (app.js no lo lee).
"""
import json
import math
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AQUI))
from calculos import construir_modelo  # noqa: E402
from datos import leer_base_datos  # noqa: E402
from serializar import a_json  # noqa: E402

TABLAS = ("modelo.procedencia[", "modelo.homogenea[", "modelo.hitos[", "modelo.notas[", "modelo.reexpresiones[")

SHINY = AQUI.parent / "dashboard_shiny"
BD = AQUI / "data" / "BD_Dashboard_Globant.xlsx"
R = f"""
source('R/datos.R'); source('R/calculos.R')
cat(modelo_json(construir_modelo(leer_base_datos('{BD}'), 2024L, 2025L)))
"""


def comparar(a, b, ruta, difs):
    if ruta.startswith(TABLAS) and a == "" and b is None:
        return
    if isinstance(a, bool) or isinstance(b, bool):
        if a is not b:
            difs.append(f"{ruta}: {a!r} vs {b!r}")
        return
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k == "indiceReal" and a.get(k) is None and k not in b:
                continue
            if k not in a or k not in b:
                difs.append(f"{ruta}.{k}: solo en {'python' if k in a else 'shiny'}")
            else:
                comparar(a[k], b[k], f"{ruta}.{k}", difs)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            difs.append(f"{ruta}: longitud {len(a)} vs {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            comparar(x, y, f"{ruta}[{i}]", difs)
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        if not math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9):
            difs.append(f"{ruta}: {a} vs {b}")
    elif a != b:
        difs.append(f"{ruta}: {a!r} vs {b!r}")


def main():
    py = json.loads(a_json(construir_modelo(leer_base_datos(BD), 2024, 2025)))
    r = json.loads(subprocess.run(["Rscript", "-e", R], cwd=SHINY, capture_output=True, text=True, check=True).stdout)
    py["meta"].pop("generado"); r["meta"].pop("generado")
    difs = []
    comparar(py, r, "modelo", difs)
    if difs:
        print(f"{len(difs)} diferencias:")
        print("\n".join(difs[:60]))
        sys.exit(1)
    print("Modelo idéntico al de Shiny.")


if __name__ == "__main__":
    main()
