"""datos.py — Lectura de la base de datos (equivalente a Datos.gs).

Hojas de data/BD_Dashboard_Globant.xlsx:
  ER, ESF        ID | Cuenta | Tipo | Grupo | Orden | 2018 ... 2025   (miles de COP)
  Deflactor      Año | Inflación IPC dic-dic (%) | ...
  Empresa        Clave | Valor
  Hitos, Notas, Reexpresiones, Fuentes, Homogenea   tablas que se pasan tal cual al cliente

La referencia es Apps Script: cada conversión imita lo que hace JavaScript con lo que devuelve
getValues() de Google Sheets (vacío = '', fechas = Date). pruebas/comparar_con_apps_script.py
lo comprueba ejecutando los .gs reales sobre la BD y sobre variantes con casos borde.
"""
import math
import re
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from openpyxl import load_workbook

ZONA_HOJA = ZoneInfo("America/Bogota")  # zona con la que Google Sheets interpreta las fechas de la hoja
_NUM_JS = re.compile(r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?")


def _vacia(c):
    """Vacío según el filtro de filas de Apps Script: '' o null (un texto con solo espacios NO lo es)."""
    return c is None or c == ""


def _fecha_iso(v):
    """Fecha de getValues() serializada por JSON.stringify: ISO en UTC con milisegundos."""
    if not isinstance(v, datetime):
        v = datetime(v.year, v.month, v.day)
    if v.tzinfo is None:
        v = v.replace(tzinfo=ZONA_HOJA)
    return v.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{v.microsecond // 1000:03d}Z"


def js_string(v):
    """String(v) de JavaScript para los tipos que puede traer una celda."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        if math.isnan(v):
            return "NaN"
        if math.isinf(v):
            return "Infinity" if v > 0 else "-Infinity"
        if v.is_integer() and abs(v) < 1e21:
            return str(int(v))
        return repr(v)
    if isinstance(v, (datetime, date)):
        return _fecha_iso(v)
    return str(v)


def js_number(v):
    """Number(v) de JavaScript: '' → 0, texto no numérico → NaN, true → 1."""
    if v is None:
        return 0
    if isinstance(v, bool):
        return 1 if v else 0
    if isinstance(v, (int, float)):
        return v
    s = str(v).strip()
    if s == "":
        return 0
    if not _NUM_JS.fullmatch(s):
        return math.nan
    n = float(s)
    return int(n) if n.is_integer() and abs(n) < 2**53 else n


def _celda(c):
    """Celda de tabla tal como la entrega Apps Script: vacío = '', fechas en ISO UTC."""
    if c is None:
        return ""
    if isinstance(c, (datetime, date)):
        return _fecha_iso(c)
    return c


def a_numero(v):
    """aNumero_ de Datos.gs: acepta números, '1.234.567', '$1.234 M' y '-'. El punto es separador de miles."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return v
    if v is None:
        return 0
    s = js_string(v).strip()
    if s in ("", "-"):
        return 0
    negativo = "-" in s
    limpio = re.sub(r"[^\d,]", "", s).replace(",", ".", 1)
    if limpio == "":
        return 0
    try:
        n = float(limpio)
    except ValueError:
        return 0
    if n.is_integer() and abs(n) < 2**53:
        n = int(n)
    return -n if negativo else n


def leer_hoja(libro, nombre, obligatoria=True):
    if nombre not in libro.sheetnames:
        if not obligatoria:
            return [], []
        raise ValueError(f'No existe la hoja "{nombre}" en la BD.')
    filas = list(libro[nombre].iter_rows(values_only=True))
    if not filas:
        return [], []
    ancho = max(len(r) for r in filas)
    head = [js_string(h).strip() for h in filas[0]] + [""] * (ancho - len(filas[0]))
    rows = [list(r) + [None] * (ancho - len(r)) for r in filas[1:] if any(not _vacia(c) for c in r)]
    return head, rows


def _col(head, nombre, hoja):
    if nombre not in head:
        raise ValueError(f'Falta la columna "{nombre}" en la hoja "{hoja}".')
    return head.index(nombre)


def leer_estado(libro, nombre):
    head, rows = leer_hoja(libro, nombre)
    idx_years = [i for i, h in enumerate(head) if re.fullmatch(r"\d{4}", h)]
    if not idx_years:
        raise ValueError(f'La hoja "{nombre}" no tiene columnas de años.')
    i_id, i_cta, i_tipo, i_grp, i_ord = (_col(head, k, nombre) for k in ("ID", "Cuenta", "Tipo", "Grupo", "Orden"))
    cuentas = []
    for r in rows:
        orden = js_number(r[i_ord])
        if isinstance(orden, float) and math.isnan(orden):
            orden = 0  # Number(x) || 0
        cuentas.append({
            "id": js_string(r[i_id]).strip(),
            "cuenta": js_string(r[i_cta]).strip(),
            "tipo": js_string(r[i_tipo]).strip(),
            "grupo": js_string(r[i_grp]).strip(),
            "orden": orden,
            "nom": [a_numero(r[i]) for i in idx_years],
        })
    cuentas.sort(key=lambda c: c["orden"])  # estable, como Array.prototype.sort en V8
    return {"years": [int(head[i]) for i in idx_years], "cuentas": cuentas}


def leer_deflactor(libro):
    head, rows = leer_hoja(libro, "Deflactor")
    i_anio = _col(head, "Año", "Deflactor")
    i_inf = next((i for i, h in enumerate(head) if h.startswith("Inflación")), None)
    if i_inf is None:
        raise ValueError("Falta la columna de inflación en la hoja Deflactor.")
    filas = []
    for r in rows:
        anio = js_number(r[i_anio])
        if isinstance(anio, float) and not anio.is_integer():
            continue  # año no numérico o fraccionario: Apps Script nunca lo encuentra al buscar un año
        filas.append({"year": int(anio), "inflacion": a_numero(r[i_inf])})
    return sorted(filas, key=lambda f: f["year"])


def leer_tabla(libro, nombre):
    head, rows = leer_hoja(libro, nombre, obligatoria=False)
    out = []
    for r in rows:
        o = {}
        for i, h in enumerate(head):
            o[h] = _celda(r[i])  # como Apps Script: con encabezados repetidos gana la última columna
        out.append(o)
    return out


def _formulas_sin_valor(ruta):
    """Fórmulas sin valor guardado en celdas que se leen. openpyxl no recalcula (Google Sheets sí):
    sin este control, una inflación escrita como fórmula se leería como 0 sin aviso."""
    formulas = load_workbook(ruta, read_only=True, data_only=False)
    valores = load_workbook(ruta, read_only=True, data_only=True)
    try:
        hallazgos = []
        for nombre in formulas.sheetnames:
            head = None
            for fila_f, fila_v in zip(formulas[nombre].iter_rows(), valores[nombre].iter_rows(values_only=True)):
                if head is None:
                    head = [js_string(h).strip() for h in fila_v]
                for j, (cf, v) in enumerate(zip(fila_f, fila_v)):
                    if not (isinstance(cf.value, str) and cf.value.startswith("=") and v is None):
                        continue
                    col = head[j] if j < len(head) else ""
                    if nombre == "Deflactor" and not (col == "Año" or col.startswith("Inflación")):
                        continue  # el índice y el factor de la hoja no se leen: se recalculan en calculos.py
                    hallazgos.append(f"{nombre}!{cf.coordinate}")
        return hallazgos
    finally:
        formulas.close()
        valores.close()


def leer_base_datos(ruta):
    sin_valor = _formulas_sin_valor(ruta)
    if sin_valor:
        raise ValueError("Hay fórmulas sin valor calculado en " + ", ".join(sin_valor[:10])
                         + ("…" if len(sin_valor) > 10 else "")
                         + ". Abre el archivo en Excel o LibreOffice y guárdalo para que queden calculadas.")
    libro = load_workbook(ruta, read_only=True, data_only=True)
    try:
        _, emp = leer_hoja(libro, "Empresa", obligatoria=False)
        return {
            "er": leer_estado(libro, "ER"),
            "esf": leer_estado(libro, "ESF"),
            "deflactor": leer_deflactor(libro),
            "empresa": [{"clave": js_string(r[0]), "valor": js_string(r[1])} for r in emp],
            "hitos": leer_tabla(libro, "Hitos"),
            "notas": leer_tabla(libro, "Notas"),
            "reexpresiones": leer_tabla(libro, "Reexpresiones"),
            "fuentes": leer_tabla(libro, "Fuentes"),
            "homogenea": leer_tabla(libro, "Homogenea"),
        }
    finally:
        libro.close()
