"""calculos.py — Modelo analítico (traducción de Calculos.gs).

Única diferencia deliberada con Apps Script: en el vertical del balance, dpp es null cuando la base
de algún año es 0 (como Shiny). Apps Script devuelve un número por la aritmética de null en JavaScript
(null - x = -x), que no tiene sentido como cambio en puntos.

  - Deflactor: índice IPC (primer año = 100) y factor a pesos del último año.
  - Vertical: ER sobre ingresos; ESF con AV1 (subtotal del grupo) y AV2 (total del lado).
  - Horizontal: variación absoluta y % nominal y real; índice real base 100.
  - Indicadores de liquidez, cobertura y endeudamiento.
None se serializa como null (el cliente lo trata como "sin dato").
"""
import math
from datetime import datetime
from zoneinfo import ZoneInfo


def div(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b


def var_pct(actual, anterior):
    """Variación % solo con base positiva (con base ≤ 0 el % no es interpretable)."""
    if anterior is None or anterior <= 0 or actual is None:
        return None
    return (actual - anterior) / anterior


def construir_deflactor(years, filas):
    inf = {f["year"]: f["inflacion"] for f in filas}
    indice = []
    for i, y in enumerate(years):
        if i == 0:
            indice.append(100)
            continue
        if y not in inf:
            raise ValueError(f"Falta la inflación del año {y} en la hoja Deflactor.")
        indice.append(indice[i - 1] * (1 + inf[y] / 100))
    ultimo = indice[-1]
    return [{"year": y, "inflacion": inf.get(y), "indice": indice[i], "factor": div_js(ultimo, indice[i])}
            for i, y in enumerate(years)]


def div_js(a, b):
    """a / b con la semántica de JavaScript (x/0 = ±Infinity, 0/0 = NaN); al serializar, ambos van a null."""
    if b != 0:
        return a / b
    if a == 0 or math.isnan(a):
        return math.nan
    return math.copysign(math.inf, a) * math.copysign(1, b)


def mapa(cuentas):
    return {c["id"]: c for c in cuentas}


def serie(m, id_, n):
    return m[id_]["nom"] if id_ in m else [0] * n


def enriquecer_cuentas(cuentas, factores):
    out = []
    for c in cuentas:
        o = dict(c)
        o["real"] = [v * f for v, f in zip(c["nom"], factores)]
        for k in ("nom", "real"):
            s = o[k]
            o["varAbs_" + k] = [None] + [s[i] - s[i - 1] for i in range(1, len(s))]
            o["varPct_" + k] = [None] + [var_pct(s[i], s[i - 1]) for i in range(1, len(s))]
        r = o["real"]
        o["indiceReal"] = [v / r[0] * 100 for v in r] if r[0] > 0 else None
        out.append(o)
    return out


def agregar_derivadas_er(cuentas, n):
    m = mapa(cuentas)
    s = lambda id_: serie(m, id_, n)
    orden = lambda id_, defecto: m[id_]["orden"] if id_ in m else defecto
    ga, gv = s("GA"), s("GV")
    oi, og, ogp = s("OI"), s("OG"), s("OGP")
    ifin, cf, cob = s("IF"), s("CF"), s("COB")
    derivadas = [
        {"id": "GOP", "cuenta": "Gastos operacionales (adm. + ventas)", "tipo": "derivada", "grupo": "Operacional",
         "orden": orden("GA", 6) + 0.5, "nom": [a + b for a, b in zip(ga, gv)]},
        {"id": "OON", "cuenta": "Otros ingresos/gastos operacionales netos", "tipo": "derivada", "grupo": "Operacional",
         "orden": orden("OG", 7) + 0.5, "nom": [a - b + c for a, b, c in zip(oi, og, ogp)]},
        {"id": "FIN", "cuenta": "Resultado financiero neto", "tipo": "derivada", "grupo": "No operacional",
         "orden": orden("COB", 12) + 0.5, "nom": [a - b + c for a, b, c in zip(ifin, cf, cob)]},
    ]
    return sorted(cuentas + derivadas, key=lambda c: c["orden"])


TOTAL_GRUPO = {
    "Activo corriente": "AC", "Activo no corriente": "ANC", "Activo": "AT",
    "Pasivo corriente": "PC", "Pasivo no corriente": "PNC", "Pasivo": "TPP",
    "Patrimonio": "PAT", "Control": "TPP",
}


def analisis_vertical(years, er, esf, y1, y2):
    if y1 not in years or y2 not in years:
        raise ValueError(f"Los años del análisis vertical ({y1}, {y2}) no están en la BD.")
    i1, i2 = years.index(y1), years.index(y2)
    m_er, m_esf = mapa(er), mapa(esf)
    ing1, ing2 = m_er["ING"]["nom"][i1], m_er["ING"]["nom"][i2]

    er_rows = []
    for c in er:
        if c["tipo"] == "derivada" and c["id"] != "GOP":
            continue
        p1, p2 = div(c["nom"][i1], ing1), div(c["nom"][i2], ing2)
        er_rows.append({"id": c["id"], "cuenta": c["cuenta"], "tipo": c["tipo"], "grupo": c["grupo"],
                        "v1": c["nom"][i1], "v2": c["nom"][i2], "p1": p1, "p2": p2,
                        "dpp": None if p1 is None or p2 is None else p2 - p1})

    # AV2 según el taller: activo ÷ total activos; pasivo ÷ total pasivos; patrimonio ÷ total patrimonio.
    esf_rows = []
    for c in esf:
        es_activo = c["grupo"].startswith("Activo")
        base_id = "AT" if es_activo else "PAT" if c["grupo"] == "Patrimonio" else "TPP" if c["grupo"] == "Control" else "PT"
        base = m_esf[base_id]
        ref = m_esf.get(TOTAL_GRUPO.get(c["grupo"]), base)
        p1, p2 = div(c["nom"][i1], base["nom"][i1]), div(c["nom"][i2], base["nom"][i2])
        esf_rows.append({
            "id": c["id"], "cuenta": c["cuenta"], "tipo": c["tipo"], "grupo": c["grupo"],
            "lado": "Activo" if es_activo else "Pasivo y patrimonio", "baseAV2": base_id,
            "v1": c["nom"][i1], "v2": c["nom"][i2],
            "av1_1": div(c["nom"][i1], ref["nom"][i1]), "av1_2": div(c["nom"][i2], ref["nom"][i2]),
            "p1": p1, "p2": p2, "dpp": None if p1 is None or p2 is None else p2 - p1,
        })
    return {"y1": y1, "y2": y2, "er": er_rows, "esf": esf_rows}


def indicadores(years, er, esf):
    n = len(years)
    E, R = mapa(esf), mapa(er)
    AT, PT, AC, PC, INV, EFE, CXC = (serie(E, k, n) for k in ("AT", "PT", "AC", "PC", "INV", "EFE", "CxC"))
    CV, GA, GV, ING = (serie(R, k, n) for k in ("CV", "GA", "GV", "ING"))
    rng = range(n)
    gasto_diario = [(CV[i] + GA[i] + GV[i]) / 365 for i in rng]
    return [
        {"id": "LG", "nombre": "Liquidez general", "formula": "Activo corriente ÷ Pasivo total", "unidad": "x",
         "descripcion": "Pesos de activo corriente por cada peso de deuda total.",
         "valores": [div(AC[i], PT[i]) for i in rng], "mejorSiSube": True},
        {"id": "LC", "nombre": "Liquidez corriente", "formula": "Activo corriente ÷ Pasivo corriente", "unidad": "x",
         "descripcion": "Pesos de activo corriente por cada peso de deuda de corto plazo.",
         "valores": [div(AC[i], PC[i]) for i in rng], "mejorSiSube": True},
        {"id": "PA", "nombre": "Prueba ácida", "formula": "(Activo corriente − Inventarios) ÷ Pasivo corriente", "unidad": "x",
         "descripcion": "Liquidez sin inventarios. La filial no tiene inventarios: coincide con la liquidez corriente.",
         "valores": [div(AC[i] - INV[i], PC[i]) for i in rng], "mejorSiSube": True},
        {"id": "CG", "nombre": "Cobertura de gastos",
         "formula": "(Activo corriente − Inventarios) ÷ [(Costo de ventas + Gastos de administración y ventas) ÷ 365]", "unidad": "d",
         "descripcion": "Días de costos y gastos operacionales que se pueden cubrir con el activo corriente sin inventarios.",
         "valores": [div(AC[i] - INV[i], gasto_diario[i]) for i in rng], "gastoDiario": gasto_diario, "mejorSiSube": True},
        {"id": "DI", "nombre": "Disponibilidad inmediata", "formula": "Efectivo y equivalentes ÷ Pasivo corriente", "unidad": "x",
         "descripcion": "Proporción de la deuda de corto plazo que se puede pagar hoy con caja.",
         "valores": [div(EFE[i], PC[i]) for i in rng], "mejorSiSube": True},
        {"id": "CT", "nombre": "Capital de trabajo", "formula": "Activo corriente − Pasivo corriente", "unidad": "$",
         "descripcion": "Recursos de corto plazo que quedan después de cubrir la deuda de corto plazo (miles de COP).",
         "valores": [AC[i] - PC[i] for i in rng], "mejorSiSube": True},
        {"id": "CE", "nombre": "Capacidad de endeudamiento", "formula": "Activo total ÷ Pasivo total", "unidad": "x",
         "descripcion": "Veces que los activos cubren la deuda total; por encima de 1 hay margen para tomar más deuda.",
         "valores": [div(AT[i], PT[i]) for i in rng], "mejorSiSube": True},
        {"id": "END", "nombre": "Endeudamiento total", "formula": "Pasivo total ÷ Activo total", "unidad": "%", "complementario": True,
         "descripcion": "Porción del activo financiada por terceros (inverso de la capacidad de endeudamiento).",
         "valores": [div(PT[i], AT[i]) for i in rng], "mejorSiSube": False},
        {"id": "ROT", "nombre": "Rotación de cartera", "formula": "Deudores comerciales corrientes ÷ Ingresos × 365", "unidad": "d",
         "complementario": True, "descripcion": "Días que tarda en promedio la compañía en cobrar lo que factura.",
         "valores": [div(CXC[i] * 365, ING[i]) for i in rng], "mejorSiSube": False},
    ]


def margenes(years, er):
    R, n = mapa(er), len(years)
    ing = serie(R, "ING", n)
    def m(id_, nombre, cta):
        return {"id": id_, "nombre": nombre, "valores": [div(v, ing[i]) for i, v in enumerate(serie(R, cta, n))]}
    return [m("MB", "Margen bruto", "UB"), m("MO", "Margen operacional", "UO"), m("MN", "Margen neto", "UN")]


def cuadre(esf):
    E = mapa(esf)
    dif = max(abs(a - p - q) for a, p, q in zip(E["AT"]["nom"], E["PT"]["nom"], E["PAT"]["nom"]))
    return {"maxDiferencia": dif, "ok": dif == 0}


def construir_modelo(fuente, y1, y2):
    years = fuente["er"]["years"]
    if fuente["esf"]["years"] != years:
        raise ValueError("Los años de ER y ESF no coinciden.")
    n = len(years)
    deflactor = construir_deflactor(years, fuente["deflactor"])
    factores = [d["factor"] for d in deflactor]
    er = enriquecer_cuentas(agregar_derivadas_er(fuente["er"]["cuentas"], n), factores)
    esf = enriquecer_cuentas(fuente["esf"]["cuentas"], factores)
    indic = indicadores(years, er, esf)
    for ind in indic:
        if ind["unidad"] == "$":
            ind["valoresReales"] = [v * f for v, f in zip(ind["valores"], factores)]
    return {
        "meta": {"years": years, "anioBaseReal": years[-1], "unidad": "Miles de pesos colombianos (COP)",
                 "generado": datetime.now(ZoneInfo("America/Bogota")).strftime("%Y-%m-%d %H:%M")},
        "procedencia": fuente["fuentes"],
        "homogenea": fuente["homogenea"],
        "cuadre": cuadre(esf),
        "empresa": fuente["empresa"],
        "hitos": fuente["hitos"],
        "notas": fuente["notas"],
        "reexpresiones": fuente["reexpresiones"],
        "deflactor": deflactor,
        "er": er,
        "esf": esf,
        "vertical": analisis_vertical(years, er, esf, y1, y2),
        "indicadores": indic,
        "margenes": margenes(years, er),
    }
