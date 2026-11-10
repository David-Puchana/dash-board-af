"""exportar_guia.py — Genera la guía de lectura del dashboard (HTML y PDF).

Uso (desde dashboard_python/guia, después de regenerar docs/ y de tomar las capturas):
    NODE_PATH=<node_modules con puppeteer-core> node capturas.js     # img/*.png desde docs/index.html
    python3 exportar_guia.py                                          # guia.html y ../../Guia_lectura_dashboard.pdf

Las cifras de «Qué dice hoy» salen del mismo modelo que el dashboard (calculos.py), así que la guía
no puede contradecir a la página. El contexto externo (Globant, TRM, informe de variaciones) es texto
fijo con su nivel de certeza; las referencias externas están en CONTEXTO y TRM_*.
"""
import html
import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
from calculos import construir_modelo  # noqa: E402
from datos import leer_base_datos  # noqa: E402

BD = AQUI.parent / "data" / "BD_Dashboard_Globant.xlsx"
HTML_SALIDA = AQUI / "guia.html"
PDF_SALIDA = AQUI.parent.parent / "Guia_lectura_dashboard.pdf"
URL_DASHBOARD = "https://david-puchana.github.io/dash-board-af/"
CHROME = "google-chrome"

# Referencias externas (las mismas que cita el diagnóstico de la página). TRM de cierre: certificada por la
# Superfinanciera y publicada por el Banco de la República. TRM promedio: Actualícese, según el informe.
TRM_CIERRE = {2019: 3277.14, 2020: 3432.50, 2021: 3981.16, 2022: 4810.20, 2023: 3822.05, 2024: 4409.15, 2025: 3757.08}
TRM_PROMEDIO = {2024: 4071.28, 2025: 4052.86}
GLOBANT_CLIENTES_COLOMBIA_2023_MUSD = 25.1  # 20-F FY2023, ingresos con clientes ubicados en Colombia


# ----------------------------------------------------------------- formato
def num(v, d=0):
    s = f"{abs(v):,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("−" if v < 0 else "") + s


def pct(v, d=1):
    return "n.a." if v is None else num(v * 100, d) + "%"


def pcts(v, d=1):
    return "n.a." if v is None else ("+" if v > 0 else "") + pct(v, d)


def veces(v, d=2):
    return num(v, d)


def corto(miles):
    """Cifra en miles de COP → texto corto."""
    if abs(miles) >= 1e9:
        return ("−" if miles < 0 else "") + "$" + num(abs(miles) / 1e9, 2) + " billones"
    return ("−" if miles < 0 else "") + "$" + num(abs(miles) / 1e6, 1) + " mil millones"


def vp(a, b):
    return None if a is None or b is None or a <= 0 else (b - a) / a


def lista(xs):
    xs = list(xs)
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " y " + xs[-1]


def esc(s):
    return html.escape(s, quote=False)


# ----------------------------------------------------------------- bloques HTML
CERTEZA = {"C": ("CONFIRMADO", "c"), "P": ("PROBABLE", "p"), "H": ("HIPÓTESIS", "h")}


def c(clave):
    t, k = CERTEZA[clave]
    return f'<span class="cert {k}">{t}</span>'


def pieza(titulo, img=None, muestra=None, leer=None, hoy=None, interaccion=None, contexto=None, ancho="completo"):
    partes = [f'<div class="pieza"><h3>{esc(titulo)}</h3>']
    if img:
        partes.append(f'<figure class="{ancho}"><img src="img/{img}.png" alt="{esc(titulo)}"></figure>')
    if muestra or leer:
        partes.append('<div class="dos">')
        if muestra:
            partes.append(f'<div><h4>Qué muestra</h4><p>{muestra}</p></div>')
        if leer:
            partes.append(f'<div><h4>Cómo leerlo</h4><p>{leer}</p></div>')
        partes.append("</div>")
    if hoy:
        partes.append(f'<div class="caja hoy"><h4>Qué dice hoy</h4><p>{hoy}</p></div>')
    if interaccion:
        partes.append(f'<div class="caja int"><h4>Interacción</h4><p>{interaccion}</p></div>')
    if contexto:
        partes.append(f'<div class="caja ctx"><h4>Contexto Globant</h4><p>{contexto}</p></div>')
    partes.append("</div>")
    return "\n".join(partes)


def seccion(num_, titulo, intro, cuerpo, salto=True):
    return (f'<section class="{"salto" if salto else ""}"><div class="sec-head"><span class="sec-num">{num_}</span>'
            f'<h2>{esc(titulo)}</h2></div><p class="lead">{intro}</p>{cuerpo}</section>')


def tabla(cabecera, filas, clase=""):
    th = "".join(f"<th>{h}</th>" for h in cabecera)
    tr = "".join("<tr>" + "".join(f"<td>{x}</td>" for x in f) + "</tr>" for f in filas)
    return f'<table class="tbl {clase}"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>'


# ----------------------------------------------------------------- contenido
def construir(m):
    y = m["meta"]["years"]
    n, l, P = len(y), len(y) - 1, len(y) - 2
    R = {x["id"]: x for x in m["er"]}
    E = {x["id"]: x for x in m["esf"]}
    I = {x["id"]: x for x in m["indicadores"]}
    M = {x["id"]: x for x in m["margenes"]}
    V = m["vertical"]
    ve = {x["id"]: x for x in V["esf"]}
    vr = {x["id"]: x for x in V["er"]}
    nom = lambda d, k: d[k]["nom"]
    real = lambda d, k: d[k]["real"]
    vr_real = lambda d, k, i: d[k]["varPct_real"][i]
    vr_nom = lambda d, k, i: d[k]["varPct_nom"][i]
    ia, ib = y.index(V["y1"]), y.index(V["y2"])
    mb, mo, mn = M["MB"]["valores"], M["MO"]["valores"], M["MN"]["valores"]
    tasa = [nom(R, "IMP")[i] / nom(R, "UAI")[i] for i in range(n)]
    fac = [d["factor"] for d in m["deflactor"]]
    imin = lambda a: min(range(n), key=lambda i: a[i])
    imax = lambda a: max(range(n), key=lambda i: a[i])
    ING, CV, CxC, AC = nom(R, "ING"), nom(R, "CV"), nom(E, "CxC"), nom(E, "AC")
    trm = lambda i: vp(TRM_CIERRE.get(y[i - 1]), TRM_CIERRE.get(y[i])) if i > 0 and y[i] in TRM_CIERRE and y[i - 1] in TRM_CIERRE else None
    vcxc = lambda i: vp(CxC[i - 1], CxC[i])
    contra = [i for i in range(1, n) if trm(i) is not None and abs(trm(i)) > 0.1 and trm(i) * vcxc(i) < 0]
    sube = lambda v: ("bajó " if v < 0 else "subió ") + pct(abs(v))
    reexp = [f["Año"] for f in m["procedencia"] if "re-expres" in str(f.get("Procedencia", "")).lower()]
    ld = lambda k: I[k]["valores"]
    fin_ = nom(R, "FIN")
    aid, pid = nom(E, "AID"), nom(E, "PID")

    # Frase de cartera y TRM, idéntica en lógica al diagnóstico de la página.
    frase_cartera = (f"En {y[l]} la cartera varió {pcts(vcxc(l))} nominal, "
                     f"{'en línea con' if abs(vcxc(l) - trm(l)) < 0.03 else 'frente a'} la TRM de cierre ({pcts(trm(l))}), "
                     f"con ingresos de {pcts(vp(ING[P], ING[l]))}.")
    if contra:
        k = contra[0]
        frase_cartera += (f" Es compatible con saldos en dólares, pero no es un patrón de la serie: en {y[k]} la TRM {sube(trm(k))} "
                          f"y la cartera {sube(vcxc(k))}. Además, el resultado financiero de {y[l]} fue {corto(fin_[l])}, sin la pérdida "
                          f"cambiaria que tendría una cartera grande en dólares en un año de revaluación.")

    S = []

    # ---------------------------------------------------------- 00
    infl = fac[0] - 1
    S.append(seccion("00", "Antes de empezar", (
        "El dashboard es una sola página con seis secciones: Perfil, Resumen, Horizontal, Vertical, Indicadores y Diagnóstico. "
        "El menú negro de arriba lleva a cada una. Casi todo responde al cursor: al pasarlo por una barra, una línea, una celda o una cifra aparece el detalle."),
        "<h3>Las unidades</h3>" + tabla(["Lo que ves", "Qué significa"], [
            ["Cifras de la fuente", f"Supersociedades publica en miles de pesos: {num(ING[l])} en la fuente son {corto(ING[l])}."],
            ["Tablas del dashboard", f"En millones de pesos, para que se lean mejor: {num(ING[l] / 1e3)} = {corto(ING[l])}."],
            ["Ejes de los gráficos", "En miles de millones: 1.200 = 1,2 billones."],
            ["billones · mil millones", "1 billón = un millón de millones (12 ceros). 1 mil millones = 9 ceros."],
            ["pp (puntos porcentuales)", f"La diferencia entre dos porcentajes. Si el margen bruto pasa de {pct(mb[P], 2)} a {pct(mb[l], 2)}, "
                                         f"cae {num((mb[P] - mb[l]) * 100, 2)} pp (no {num((mb[P] - mb[l]) * 100, 2)}%)."],
            ["veces · días", f"Los indicadores se miden en veces ({veces(ld('LC')[l])} = hay {veces(ld('LC')[l])} pesos de activo corriente por cada peso de deuda de corto plazo) o en días."],
        ]) +
        "<h3>Pesos nominales y pesos constantes</h3>"
        f"<p>Un peso de {y[0]} compraba más que uno de {y[l]}: los precios subieron {pct(infl)} en ese tiempo (IPC del DANE). Por eso el dashboard ofrece dos maneras de ver el dinero:</p>"
        f"<ul><li><b>Pesos nominales:</b> las cifras tal como se reportaron cada año.</li>"
        f"<li><b>Pesos de {y[l]} (constantes):</b> cada año se lleva a precios de {y[l]} con el IPC. Si una cifra crece en pesos constantes, creció más que la inflación.</li></ul>"
        f"<p>El selector <i>Pesos nominales / Pesos de {y[l]}</i> está en el análisis horizontal y también cambia el capital de trabajo en Indicadores. "
        "El Resumen, el análisis vertical y los indicadores en veces, días o porcentaje no dependen de la inflación.</p>"
        "<h3>Colores y símbolos</h3>" + tabla(["Símbolo", "Significado"], [
            ['<span class="pos">+31,7%</span> · <span class="neg">−0,5%</span>', "Verde = mejora, rojo = deterioro. Depende de la cuenta: si un costo baja, es verde."],
            ["Barras verdes y negras", "El verde es la serie normal y el negro marca el dato que importa, casi siempre el último año."],
            ["Naranja", "Valores negativos o que empeoran (una caída de ingresos, un capital de trabajo negativo)."],
            ["Azul ↔ naranja", "En el mapa de variaciones: azul = la cuenta creció, naranja = cayó. Cuanto más intenso, más grande el cambio."],
            ["†", "Cambio de base contable: la compañía re-expresó la cifra de un año en el reporte siguiente y el año anterior quedó en la base vieja. "
                  "Al pasar el cursor, el dashboard muestra la variación homogénea, con las dos cifras del mismo reporte."],
            ["n.a.", "No aplica: el porcentaje no tiene sentido porque el año base es cero o negativo."],
        ]) +
        '<div class="caja ctx"><h4>Contexto Globant y niveles de certeza</h4><p>Los recuadros de contexto complementan la lectura con el '
        "<i>Informe de explicación de diez variaciones 2018–2025</i>, que cruza las cifras con el Form 20-F de Globant, el Banco de la República (TRM), el DANE y la prensa. "
        f"Cada afirmación lleva su certeza: {c('C')} lo dice una fuente; {c('P')} lo apoyan los datos sin prueba directa; {c('H')} inferencia del analista. "
        "Esta guía revisa esas certezas contra la serie completa y, donde la serie no las sostiene, las rebaja. Ninguna lectura tuvo acceso a las notas a los estados financieros.</p></div>"
        '<div class="caja"><h4>De dónde salen las cifras</h4><p>Cada año se toma de su propio reporte en Supersociedades. Cuando la compañía corrigió la cifra en el reporte del año siguiente, '
        f"se usa la versión corregida ({lista(str(a) for a in reexp)}). Dos excepciones por bloque: en 2022 el pasivo no corriente sale de su reporte propio, porque el comparativo "
        f"del reporte 2023 usa una clasificación atípica que el reporte 2024 abandona; en 2024 solo el patrimonio sale del reporte siguiente. Los totales cuadran en los {n} años: "
        f"el activo es igual al pasivo más el patrimonio (diferencia máxima: {num(m['cuadre']['maxDiferencia'])}).</p></div>",
        salto=False))

    # ---------------------------------------------------------- 01
    mult = ING[l] / ING[0]
    mult_real = real(R, "ING")[l] / real(R, "ING")[0]
    cagr = mult ** (1 / (n - 1)) - 1
    S.append(seccion("01", "Portada y perfil", "Antes de los números, el contexto: qué empresa es y por qué no hay que confundirla con el grupo.",
        pieza("Portada", "portada",
              "El titular resume el hallazgo principal en una frase; la franja de abajo dice de dónde salen los datos.",
              f"El fondo lima resalta la parte que más importa. «Cuadre: Diferencia cero» confirma que en los {n} años el activo es igual al pasivo más el patrimonio.",
              f"Los ingresos nominales se multiplicaron por {num(mult, 1)} entre {y[0]} y {y[l]}, pero el margen bruto de {y[l]} ({pct(mb[l], 2)}) "
              f"es {'el más bajo de la serie' if imin(mb) == l else 'bajo'}: la empresa vende mucho más, pero cada venta le deja menos.") +
        pieza("Perfil: «De Buenos Aires a Bogotá»", "perfil",
              "A la izquierda, quién es Globant y quién es la sociedad analizada; debajo, los hitos año por año. A la derecha, la ficha legal.",
              "El recuadro «No confundir las entidades» es clave: Sistemas Colombia S.A.S. es una filial. Las cifras del grupo están en dólares y no se comparan con las de esta sociedad, en pesos.",
              interaccion="Al pasar el cursor por cada hito o dato de la ficha, la fila se resalta.") +
        pieza("Banda negra del crecimiento", "banda",
              "El tamaño del crecimiento en una sola cifra.", None,
              f"De {corto(ING[0])} ({y[0]}) a {corto(ING[l])} ({y[l]}): un crecimiento compuesto del {pct(cagr)} anual. "
              f"Descontada la inflación, el multiplicador baja de {num(mult, 1)} a {num(mult_real, 1)} veces.")))

    # ---------------------------------------------------------- 02
    caidas_previas = [i for i in range(1, l) if vr_nom(R, "ING", i) < 0]
    un_nom = vr_nom(R, "UN", l)
    endpp = (ld("END")[P] - ld("END")[l]) * 100
    ing_real = real(R, "ING")
    k22 = y.index(2022) if 2022 in y else None
    usd_2024 = ING[y.index(2024)] * 1000 / TRM_PROMEDIO[2024] / 1e6 if 2024 in y else None
    mb_hist = [mb[i] for i in range(n) if y[i] <= 2023]
    S.append(seccion("02", f"Resumen: dónde está la compañía en {y[l]}", "La foto rápida: cuatro cifras clave y dos gráficos de tendencia. Todo en pesos nominales.",
        pieza("Tarjetas de indicador", "kpis-resumen",
              f"Ingresos, utilidad neta, margen bruto y endeudamiento de {y[l]} frente a {y[P]}. La línea de abajo es la historia de los {n} años.",
              "La cifra grande es el último año. La etiqueta de color dice cuánto cambió (verde = mejoró). La línea va en naranja cuando la tendencia empeora.",
              f"Los ingresos variaron {pcts(vr_nom(R, 'ING', l))}{' (la primera caída nominal de la serie)' if vr_nom(R, 'ING', l) < 0 and not caidas_previas else ''}. " +
              (f"La utilidad neta subió {pct(un_nom)}, pero por menos impuestos y un mejor resultado financiero, no por la operación (la utilidad operacional cayó {pct(abs(vr_nom(R, 'UO', l)))}). "
               if un_nom > 0 and vr_nom(R, 'UO', l) < 0 else f"La utilidad neta varió {pcts(un_nom)} y la operacional {pcts(vr_nom(R, 'UO', l))}. ") +
              f"El margen bruto ({pct(mb[l], 2)}) {'está en su mínimo' if imin(mb) == l else 'bajó'}. "
              f"El endeudamiento bajó {num(endpp, 1)} pp, al {pct(ld('END')[l])}{': el mejor dato de la serie' if imin(ld('END')) == l else ''}.",
              "La tarjeta se eleva al pasar el cursor; si te detienes en el número, aparece el valor exacto en miles de pesos.") +
        pieza("Ingresos de actividades ordinarias", "ingresos",
              f"Los ingresos de cada año contados de dos maneras: en pesos nominales y en pesos de {y[l]}.",
              f"La distancia entre las dos líneas es el efecto de la inflación: grande en los primeros años y nula en {y[l]}, porque ese año las dos medidas coinciden.",
              f"Crecimiento fuerte hasta {y[k22] if k22 is not None else ''} y estancamiento después: en pesos de {y[l]}, los ingresos de {y[l]} ({corto(ing_real[l])}) "
              f"son menores que los de {y[k22]} ({corto(ing_real[k22])}) y {y[P]} ({corto(ing_real[P])})." if k22 is not None else None,
              "Una línea vertical marca el año bajo el cursor y la ficha muestra los dos valores, la inflación del año y la variación real.",
              f"La filial factura sobre todo al propio grupo, no a clientes colombianos {c('H')}: sus ingresos de 2024 equivalen a unos US${num(usd_2024, 1)} M "
              f"a la TRM promedio, mientras que los ingresos de Globant con clientes ubicados en Colombia fueron de US${num(GLOBANT_CLIENTES_COLOMBIA_2023_MUSD, 1)} M en 2023, según el 20-F. "
              f"La caída de {y[l]} coincide con un año flojo del grupo (ingresos consolidados +1,6%; Latinoamérica cerca de −9% interanual en el primer trimestre, según la gerencia) "
              f"y con su plan de optimización de abril de 2025 {c('C')}; "
              "que una cosa cause la otra no está demostrado." if usd_2024 else None,
              ancho="medio") +
        pieza("Márgenes sobre ingresos", "margenes",
              "Cuántos pesos quedan de cada 100 vendidos: después del costo de ventas (bruto), después de los gastos de operación (operacional) y al final (neto).",
              "Cuanto más alta la línea, mejor. Una línea que baja mientras los ingresos suben significa que la empresa vende más pero gana menos por cada venta.",
              f"El margen bruto se movió entre {pct(min(mb_hist), 1)} y {pct(max(mb_hist), 1)} de {y[0]} a 2023 y luego bajó a {pct(mb[P], 2)} en {y[P]} y a {pct(mb[l], 2)} en {y[l]}. "
              f"El operacional bajó de {pct(mo[P], 2)} a {pct(mo[l], 2)}{', el mínimo de la serie' if imin(mo) == l else ''}. "
              f"El neto subió a {pct(mn[l], 2)}, por impuestos, no por la operación.",
              contexto=(f"El margen operacional se ha movido en una franja corta, entre {pct(mo[imin(mo)], 2)} ({y[imin(mo)]}) y {pct(mo[imax(mo)], 2)} ({y[imax(mo)]}). "
                        f"Es compatible con una filial a la que el grupo remunera sobre sus costos (precios de transferencia) {c('H')}, aunque también con un servicio intensivo "
                        f"en nómina de márgenes bajos."
                        + (f" La TRM promedio casi no cambió ({num(TRM_PROMEDIO[y[P]], 0)} → {num(TRM_PROMEDIO[y[l]], 0)}, según el informe), así que el tipo de cambio promedio "
                           f"no parece explicar la caída del margen operacional {c('H')}." if y[P] in TRM_PROMEDIO and y[l] in TRM_PROMEDIO else "")),
              ancho="medio")))

    # ---------------------------------------------------------- 03
    crec_real = [f"{pcts(vr_real(R, 'ING', i))} ({y[i]})" for i in range(1, n)]
    heat = {"er": ["ING", "CV", "UB", "GOP", "UO", "IF", "CF", "UAI", "IMP", "UN"],
            "esf": ["EFE", "CxC", "AC", "PPE", "INT", "ANC", "AT", "PBE", "CxP", "PC", "PNC", "PT", "PAT"]}
    suben = [d[k]["cuenta"].lower() for e, d in (("er", R), ("esf", E)) for k in heat[e]
             if d[k]["varPct_real"][l] is not None and d[k]["varPct_real"][l] > 0]
    total_heat = sum(1 for e, d in (("er", R), ("esf", E)) for k in heat[e] if d[k]["varPct_real"][l] is not None)
    puente = [("Ingresos", "ING", 1), ("Costo de ventas", "CV", -1), ("Gastos operacionales", "GOP", -1),
              ("Otros operacionales", "OON", 1), ("Resultado financiero", "FIN", 1), ("Impuesto de renta", "IMP", -1)]
    imp_p = [f"{t} {('+' if s * (real(R, k)[l] - real(R, k)[P]) > 0 else '−')}{num(abs(real(R, k)[l] - real(R, k)[P]) / 1e6, 1)}" for t, k, s in puente]
    k2023 = y.index(2023) if 2023 in y else None
    S.append(seccion("03", "Análisis horizontal: el ritmo", (
        "Compara cada cuenta contra el año anterior: qué creció, qué se frenó y cuándo cambió la tendencia. Arriba hay tres controles: "
        f"<i>Variación % / absoluta</i>, <i>Pesos nominales / Pesos de {y[l]}</i> y el período. Por defecto se ve {y[P]} → {y[l]} en pesos de {y[l]}."),
        pieza("Tabla de cuentas clave", "tabla-clave",
              "Las siete líneas que más pesan en el estado de resultados, en millones de pesos, con su variación.",
              "Las filas con fondo claro son subtotales. En la última columna, verde y rojo dicen si el cambio es bueno o malo para la empresa.",
              f"En pesos de {y[l]}, los ingresos variaron {pcts(vr_real(R, 'ING', l))} y el costo de ventas {pcts(vr_real(R, 'CV', l))}. "
              f"Por eso la utilidad bruta varía {pcts(vr_real(R, 'UB', l))} y la operacional {pcts(vr_real(R, 'UO', l))}. "
              f"La utilidad neta varía {pcts(vr_real(R, 'UN', l))} porque el impuesto cae {pct(abs(vr_real(R, 'IMP', l)))}.",
              "Al detenerse en una cifra aparece el valor en palabras. Si una variación lleva †, la ficha explica el cambio de base contable.") +
        pieza("Ritmo de crecimiento de los ingresos", "ritmo",
              "Cuánto crecieron los ingresos cada año frente al anterior.", "Barras verdes hacia la derecha = crecimiento; naranjas hacia la izquierda = caída.",
              f"En pesos de {y[l]}: {lista(crec_real)}. En nominal, 2023 fue {pcts(vr_nom(R, 'ING', k2023))} y {y[l]} {pcts(vr_nom(R, 'ING', l))}." if k2023 else None,
              contexto=(f"El salto de 2021 coincide con una contratación masiva (más de 2.000 empleados directos solo en ese año, según el blog de Globant) y con la "
                        f"absorción de Belatrix Colombia y Grupo Assa Colombia el 7 de julio de 2021, según el 20-F 2021 {c('C')}. Parte de la cifra de 2021 es crecimiento por fusión, "
                        f"no orgánico {c('P')}; cuánto, no se puede medir sin las notas."), ancho="medio") +
        pieza("Crecimiento acumulado (índice = 100 en el primer año)", "indice",
              "Cinco cuentas que arrancan en el mismo punto para comparar cuál creció más, aunque sus tamaños sean muy distintos.",
              "Un valor de 372 significa «3,72 veces lo del primer año». Si dos líneas se separan, una creció más rápido.",
              f"En pesos de {y[l]}: ingresos {num(R['ING']['indiceReal'][l])}, costo de ventas {num(R['CV']['indiceReal'][l])}, gastos operacionales {num(R['GOP']['indiceReal'][l])}, "
              f"utilidad neta {num(R['UN']['indiceReal'][l])} y activos {num(E['AT']['indiceReal'][l])}. "
              + ("El costo creció más que la venta: es la explicación visual de la caída del margen bruto." if R['CV']['indiceReal'][l] > R['ING']['indiceReal'][l] else ""),
              "Pasa el cursor por un año para ver las cinco cuentas ordenadas; pasa por la leyenda para aislar una línea.") +
        pieza("Evolución por cuenta", "cuenta",
              "A la izquierda, el valor de una cuenta cada año; a la derecha, cuánto cambió frente al año anterior.",
              "Elige la cuenta en el selector. El último año va en negro y el máximo lleva su cifra encima.",
              interaccion="La ficha muestra el valor nominal y en pesos constantes y, si hay cambio de base, la variación homogénea. También se llega aquí con un clic en el mapa de variaciones.") +
        pieza("Mapa de variaciones", "mapa",
              "Todas las variaciones anuales de las cuentas principales en una tabla de colores: filas = cuentas, columnas = pares de años.",
              "Azul = creció, naranja = cayó; cuanto más intenso, más fuerte (se satura en ±50%). Las celdas con † tienen cambio de base contable.",
              f"En pesos de {y[l]}, la última columna tiene {total_heat - len(suben)} de {total_heat} cuentas a la baja. Suben: {lista(suben)}.",
              contexto=(f"Varias celdas extremas son contables, no económicas. La caída de propiedad, planta y equipo en 2021→2022 ({pcts(vr_real(E, 'PPE', y.index(2022)))} real) "
                        f"es una reclasificación de 89.729.800 (miles) a otros activos financieros: con la cifra original la variación es +2,3% {c('C')}. "
                        f"El {pcts(vr_real(E, 'CxC', y.index(2021)))} de la cartera en 2020→2021 incluye 26.862.502 reclasificados del largo al corto plazo y la fusión de julio de 2021; "
                        f"sin la reclasificación sería +73,9% {c('C')}. Las dos celdas llevan †.")) +
        pieza("Qué movió la utilidad neta (puente)", "puente",
              "Cómo se pasa de la utilidad neta de un año a la del otro, partida por partida.",
              "Las barras negras son los puntos de partida y de llegada. Verde = empujó la utilidad hacia arriba; rojo = hacia abajo. Un costo que baja aparece en verde.",
              f"En pesos de {y[l]}, de {num(real(R, 'UN')[P] / 1e6, 1)} a {num(real(R, 'UN')[l] / 1e6, 1)} mil millones: {lista(imp_p)} (mil millones).",
              "Elige cualquier par de años con los dos selectores. La ficha explica cada barra y avisa si hay cambio de base.",
              contexto=(f"La tasa efectiva de impuesto pasó de {pct(tasa[P])} a {pct(tasa[l])}. Sin la conciliación de las notas no se sabe por qué; el informe propone partidas no deducibles, "
                        f"ajustes de precios de transferencia, impuesto diferido o diferencia en cambio fiscal {c('H')}. Sobre el impuesto diferido, la base muestra que la posición cambia de signo "
                        f"dos veces: activo en 2021 ({corto(aid[y.index(2021)])}), pasivo en 2022 ({corto(pid[y.index(2022)])}) y activo desde 2023 ({corto(aid[y.index(2023)])}). "
                        f"Los {corto(aid[y.index(2023)])} de 2023 figuraban en el reporte 2023 como impuestos corrientes no corrientes; el reporte 2024 los reclasificó a impuesto diferido. "
                        f"Sin las notas no se sabe cuándo cambió el neteo bajo NIC 12.")) +
        pieza("Tabla completa", "tabla-completa",
              "Todas las cuentas del estado de resultados o del balance (botón «Estado de resultados / Balance») para el período elegido.",
              f"Igual que la tabla clave. Las filas en cursiva son cuentas calculadas por el dashboard (por ejemplo, gastos operacionales = administración + ventas). "
              f"Incluye la opción «acumulado {y[0]} → {y[l]}». La captura muestra solo el comienzo de la tabla.")))

    # ---------------------------------------------------------- 04
    sh = lambda k, i: nom(E, k)[i] / nom(E, "AT")[i]
    shp = lambda k, i: nom(E, k)[i] / nom(E, "PT")[i]
    S.append(seccion("04", "Análisis vertical: la estructura",
        f"No mira el ritmo, sino el reparto: qué parte del total representa cada cuenta. Compara {y[ia]} con {y[ib]}, con la metodología del taller.",
        pieza("Reparto de cada 100 pesos de ingreso", "reparto",
              "De cada 100 pesos vendidos: cuántos se van en costo de ventas, cuántos en gastos de operación y cuántos quedan como utilidad operacional.",
              "Compara las dos barras: si el costo crece, la utilidad se achica.",
              f"El costo de ventas pasó de {num(vr['CV']['p1'] * 100, 2)} a {num(vr['CV']['p2'] * 100, 2)} pesos de cada 100; los gastos, de {num(vr['GOP']['p1'] * 100, 2)} a "
              f"{num(vr['GOP']['p2'] * 100, 2)}; la utilidad operacional, de {num(vr['UO']['p1'] * 100, 2)} a {num(vr['UO']['p2'] * 100, 2)}.",
              contexto=(f"En una empresa de servicios de tecnología el costo de ventas es, sobre todo, nómina: el 20-F lo describe así para el grupo {c('C')}. "
                        "Que el costo pese tanto es esperable en este modelo; lo que importa es la tendencia."), ancho="medio") +
        pieza("Composición del activo", "activo",
              "En qué tiene la empresa su dinero: las cuatro cuentas más grandes del activo y el resto agrupado.",
              f"En la lista, la cifra gris es {y[ia]} y la negra es {y[ib]}.",
              f"El {pct(sh('CxC', ib))} del activo son cuentas por cobrar a clientes. La propiedad, planta y equipo es el {pct(sh('PPE', ib))} del activo.",
              contexto=(frase_cartera + f" Que sea cartera en dólares con vinculadas del exterior es {c('H')}: sin las notas no se conoce su moneda ni su contraparte. "
                        "La propiedad, planta y equipo sigue bajando; el 20-F asocia el plan de optimización de 2025 al cierre de oficinas del grupo "
                        f"{c('C')}, pero no se sabe qué sedes de Colombia se cerraron."), ancho="medio") +
        pieza("Financiación del activo", "financiacion",
              "Quién financia los activos: deudas de corto plazo, de largo plazo o los propios socios (patrimonio).", None,
              f"El patrimonio pasó de financiar el {pct(sh('PAT', ia))} al {pct(sh('PAT', ib))} del activo: la empresa depende menos de terceros.") +
        pieza("Estado de resultados comparativo", "v-er",
              f"Cada cuenta del estado de resultados en millones y como porcentaje de los ingresos (AV), en {y[ib]} y {y[ia]}.",
              f"«AV {y[ib]}» responde a: de cada 100 pesos vendidos, ¿cuántos fueron a esta cuenta? «Δ pp» es cuánto cambió ese peso.") +
        pieza("Estado de situación financiera comparativo", "v-esf",
              "Cada cuenta del balance con dos pesos relativos, como en el taller.",
              "AV1 = peso dentro de su grupo (por ejemplo, dentro del activo corriente). AV2 = peso dentro del total de su lado: activos sobre el total de activos, "
              "pasivos sobre el total de pasivos y patrimonio sobre el total del patrimonio. La captura muestra solo el comienzo de la tabla.",
              f"Las cuentas por cobrar son el {pct(CxC[ib] / AC[ib])} del activo corriente. En el pasivo, las provisiones por beneficios a empleados son el "
              f"{pct(shp('PBE', ib), 2)} (frente a {pct(shp('PBE', ia), 2)}) y las cuentas por pagar el {pct(shp('CxP', ib), 2)} (frente a {pct(shp('CxP', ia), 2)}).")))

    # ---------------------------------------------------------- 05
    def peor(k):
        v = ld(k)
        return imin(v) if I[k]["mejorSiSube"] else imax(v)

    def mejor(k):
        v = ld(k)
        return imax(v) if I[k]["mejorSiSube"] else imin(v)

    filas_ind = [
        ["Liquidez general", "¿Con lo que tengo a corto plazo cubro toda mi deuda?", f"{veces(ld('LG')[l], 3)} veces"],
        ["Liquidez corriente", "¿Cubro la deuda de corto plazo con el activo de corto plazo?", f"{veces(ld('LC')[l], 3)}"],
        ["Prueba ácida", "¿Y si no cuento los inventarios?", f"{veces(ld('PA')[l], 3)} (igual: no hay inventarios)"],
        ["Cobertura de gastos", "¿Cuántos días de operación pago con el activo corriente?", f"{num(ld('CG')[l])} días ({num(ld('CG')[P])} en {y[P]})"],
        ["Disponibilidad inmediata", "¿Qué parte de la deuda de corto plazo pago hoy con la caja?", f"{veces(ld('DI')[l], 3)}: el {pct(ld('DI')[l])}"],
        ["Capital de trabajo", "¿Cuánto me sobra de corto plazo después de pagar la deuda de corto plazo?", corto(ld('CT')[l])],
        ["Capacidad de endeudamiento", "¿Cuántas veces cubren mis activos toda mi deuda?", f"{veces(ld('CE')[l])} veces"],
        ["Endeudamiento total", "¿Qué parte del activo está financiada con deuda?", pct(ld('END')[l])],
        ["Rotación de cartera", "¿A cuántos días de ingresos equivale la cartera al cierre?", f"{num(ld('ROT')[l])} días ({num(ld('ROT')[P])} en {y[P]})"],
    ]
    mejores_ultimo = [I[k]["nombre"].lower() for k in ("LG", "LC", "CE", "END") if mejor(k) == l]
    lg_bajo1 = [str(y[i]) for i in range(n) if ld("LG")[i] < 1]
    ct_neg = [str(y[i]) for i in range(n) if ld("CT")[i] < 0]
    S.append(seccion("05", "Indicadores de salud financiera",
        "Los siete indicadores solicitados más dos complementarios (endeudamiento total y rotación de cartera). Cada tarjeta trae su fórmula.",
        pieza("Tarjetas de indicador", "kpis-indicadores",
              f"Nombre, fórmula, cifra de {y[l]} con su variación, una frase de lectura y la línea de los {n} años.",
              "Verde si mejora, naranja si empeora. Liquidez corriente y prueba ácida dan lo mismo porque la empresa no tiene inventarios: no son dos lecturas distintas.") +
        tabla(["Indicador", "Pregunta que responde", str(y[l])], filas_ind) +
        pieza("Tabla de indicadores", "tabla-indicadores",
              f"Los nueve indicadores en los {n} años.", "En rojo, el peor año de cada indicador; en negrita, el último año. El capital de trabajo está en millones de pesos.",
              f"Los peores años de liquidez y solvencia son {lista(sorted({str(y[peor(k)]) for k in ('LG', 'LC', 'CE', 'END', 'CT')}))} (liquidez general {veces(ld('LG')[peor('LG')], 3)} en {y[peor('LG')]}). "
              f"{y[l]} es el mejor año en {lista(mejores_ultimo)}, pero no en caja: el peor año de disponibilidad inmediata fue {y[peor('DI')]} ({veces(ld('DI')[peor('DI')], 3)}).") +
        pieza("Razones de liquidez", "liquidez",
              "Tres líneas en veces; la punteada en 1 es la frontera.", None,
              f"La liquidez general estuvo bajo 1 en {lista(lg_bajo1)}. La disponibilidad inmediata vive pegada al cero: nunca superó {veces(max(ld('DI')), 2)}.", ancho="medio") +
        pieza("Capital de trabajo", "capital-trabajo",
              "Barras en miles de millones. La captura está en pesos de 2025 (el selector por defecto); el texto usa cifras nominales, como el diagnóstico.", None,
              (f"Fue negativo en {lista(ct_neg)}: la deuda de corto plazo superaba al activo de corto plazo. " if ct_neg else "")
              + f"En {y[l]} es {corto(ld('CT')[l])} (nominal).", ancho="medio") +
        pieza("Capacidad de endeudamiento", "capacidad",
              "Activo total ÷ pasivo total. Más alto = más margen para pedir prestado.", None,
              f"En {y[l]} llega a {veces(ld('CE')[l])} veces{', el máximo de la serie' if mejor('CE') == l else ''}.", ancho="medio") +
        pieza("Cobertura de gastos", "cobertura",
              "Días de costos y gastos que se pagarían con el activo corriente.", None,
              f"Pasó de {num(ld('CG')[P])} a {num(ld('CG')[l])} días. Casi todo ese activo son cuentas por cobrar, así que esos días dependen de que la cartera se convierta en caja.",
              "En los cuatro gráficos, al pasar el cursor se atenúan las demás barras o líneas y la ficha trae los componentes de la fórmula.", ancho="medio")))

    # ---------------------------------------------------------- 06
    S.append(seccion("06", "Diagnóstico", "La conclusión: qué dicen juntas la lectura del ritmo, la de la estructura y la de los indicadores.",
        pieza("Diagnóstico del dashboard", "diagnostico",
              "Cuatro bloques, cada uno con un titular y la evidencia numérica, y un recuadro lima con la cifra que más condiciona la lectura del año.",
              "Los titulares y las cifras se calculan solos a partir de los datos: si cambian los datos, cambia el diagnóstico. Lo que es inferencia lo dice el propio texto.",
              "<br>".join(f"<b>{esc(b['titulo'])}.</b> {esc(b['texto'])}" for b in json.loads((AQUI / 'img' / 'diagnostico.json').read_text(encoding='utf-8')))) +
        '<div class="caja"><h4>Lo que el dashboard no puede decir</h4><p>No explica por qué cayeron los márgenes ni en qué moneda está la cartera: con estos datos no se puede separar '
        "precio, volumen, tipo de cambio ni los precios que la filial cobra al grupo. Eso solo lo resuelven las notas a los estados financieros.</p></div>"
        '<div class="caja ctx"><h4>Contexto Globant</h4><p>El informe deja tres preguntas abiertas para la gerencia: qué son los 89,7 mil millones reclasificados en 2022, '
        "qué parte de los ingresos y de la cartera es con vinculadas (y en qué moneda), y cómo se concilia la tasa efectiva de impuesto con la tarifa general del 35%.</p></div>"))

    # ---------------------------------------------------------- Anexo A
    S.append(seccion("A", "Anexo A · Qué significa que algo suba o baje",
        "Una cifra que sube no siempre es buena ni una que baja siempre es mala: depende de la cuenta y de por qué se movió.",
        "<h3>Análisis horizontal: variación contra el año anterior</h3>" + tabla(["Cuenta", "Si sube", "Si baja", "En Sistemas Colombia"], [
            ["Ingresos", "Más actividad facturada. Es bueno si los costos suben menos.", "Menos actividad o un peso más fuerte (si factura en dólares).",
             f"En pesos de {y[l]} cayeron en {lista([str(y[i]) for i in range(1, n) if vr_real(R, 'ING', i) < 0])}."],
            ["Costo de ventas", "Más nómina técnica. Normal si los ingresos suben al mismo ritmo; alerta si sube más.", "Menos personal o reclasificación hacia gastos.",
             f"En {y[l]} varió {pcts(vr_real(R, 'CV', l))} frente a {pcts(vr_real(R, 'ING', l))} de los ingresos (real): por eso se comprimió el margen."],
            ["Gastos operacionales", "Más estructura administrativa.", "Ahorro o reclasificación.",
             "2021 tiene una reclasificación de 34.021.696 (miles) del costo al gasto (†): no es un salto real del gasto."],
            ["Utilidad bruta y operacional", "La operación deja más.", "La operación deja menos.", f"En {y[l]}: {pcts(vr_real(R, 'UB', l))} y {pcts(vr_real(R, 'UO', l))} real."],
            ["Impuesto de renta", "Más carga tributaria.", "Alivio que sube la utilidad neta sin que mejore la operación.",
             f"La tasa efectiva ha ido de {pct(min(tasa))} a {pct(max(tasa))}: no es una señal estable."],
            ["Utilidad neta", "Ganó más: hay que ver si fue por la operación, los impuestos o el resultado financiero.", "Ganó menos.",
             f"{y[l]} sube, pero por impuestos y por el resultado financiero."],
            ["Efectivo", "Más caja disponible.", "Menos caja.", f"Siempre bajo frente a las deudas de corto plazo (disponibilidad máxima de {veces(max(ld('DI')), 2)})."],
            ["Cuentas por cobrar", "Más ventas sin cobrar, o efecto de la TRM si son en dólares. Alerta si crece más que los ingresos.", "Se cobró más o el peso se revaluó.",
             f"{pcts(vcxc(y.index(2024)))} nominal en 2024 (TRM {pcts(trm(y.index(2024)))}) y {pcts(vcxc(l))} en {y[l]} (TRM {pcts(trm(l))}); pero en 2023 subió con la TRM a la baja. "
             f"La lectura cambiaria es {c('H')}."],
            ["Propiedad, planta y equipo", "Inversión en sedes o equipos, o arrendamientos registrados como activo (NIIF 16).", "Depreciación, cierre de sedes o reclasificación.",
             f"{pcts(vr_real(E, 'PPE', y.index(2020)))} en 2020 (probables arrendamientos de nuevas sedes) {c('P')}; {pcts(vr_real(E, 'PPE', y.index(2022)))} en 2022 por reclasificación {c('C')}."],
            ["Pasivos", "Más obligaciones (proveedores, empleados, impuestos).", "Pagó deudas o hay menos provisiones.",
             f"En {y[l]} las provisiones a empleados son el {pct(shp('PBE', l))} del pasivo, por encima de las cuentas por pagar ({pct(shp('CxP', l))})."],
            ["Patrimonio", "Retuvo utilidades o se capitalizó: más respaldo propio.", "Repartió dividendos o tuvo pérdidas.", f"En {y[l]}: {pcts(vr_real(E, 'PAT', l))} real."],
        ], "anexo") +
        '<div class="caja"><h4>Antes de concluir, revisa tres cosas</h4><p>1) ¿La variación lleva †? Entonces mezcla dos formas de contar: mira la variación homogénea. '
        f"2) ¿Es nominal o real? Una cifra puede subir en pesos corrientes y caer descontada la inflación (ingresos de 2023: {pcts(vr_nom(R, 'ING', k2023))} nominal y "
        f"{pcts(vr_real(R, 'ING', k2023))} real). 3) ¿Hubo un evento? La fusión de 2021, la reclasificación de 2022 o un movimiento fuerte de la TRM pueden explicar saltos que no son operativos.</p></div>"
        "<h3>Análisis vertical: el peso de cada cuenta</h3>" + tabla(["Peso de…", "Si sube", "Si baja", "En Sistemas Colombia"], [
            ["Costo de ventas sobre ingresos", "Cada peso vendido cuesta más.", "Mejora la eficiencia o el precio.", f"De {num(vr['CV']['p1'] * 100, 2)} a {num(vr['CV']['p2'] * 100, 2)} de cada 100 ({y[ia]} → {y[ib]})."],
            ["Gastos sobre ingresos", "La estructura pesa más.", "Economías de escala o recortes.", f"De {pct(vr['GOP']['p1'], 2)} a {pct(vr['GOP']['p2'], 2)}."],
            ["Utilidad operacional sobre ingresos", "Más ganancia por peso vendido.", "Menos ganancia por peso vendido.",
             f"De {pct(vr['UO']['p1'], 2)} a {pct(vr['UO']['p2'], 2)}{': el mínimo de la serie' if imin(mo) == l else ''}."],
            ["Cartera sobre activo total", "El activo depende más de que paguen.", "Más activo en caja u otros rubros.",
             f"{pct(sh('CxC', ib))} del activo y {pct(CxC[ib] / AC[ib])} del activo corriente."],
            ["Efectivo sobre activo", "Más colchón inmediato.", "Menos liquidez inmediata.", f"{pct(sh('EFE', ib))}."],
            ["Propiedad, planta y equipo sobre activo", "Modelo más intensivo en activos.", "Modelo más liviano.", f"{pct(sh('PPE', ib))}: una empresa de personas, no de infraestructura."],
            ["Pasivo corriente sobre pasivo total", "Más presión de caja de corto plazo.", "Más deuda a largo plazo.", f"De {pct(shp('PC', ia), 0)} a {pct(shp('PC', ib), 0)} del pasivo."],
            ["Patrimonio sobre el total financiado", "Menos dependencia de terceros.", "Más apalancamiento.", f"De {pct(sh('PAT', ia))} a {pct(sh('PAT', ib))} del activo."],
        ], "anexo")))

    # ---------------------------------------------------------- Anexo B
    def ind(nombre, formula, mide, interpreta, caso, ctx=None):
        return (f'<div class="ind"><div class="ind-head"><h3>{nombre}</h3><span class="formula">{formula}</span></div>'
                f'<div class="dos"><div><h4>Qué mide</h4><p>{mide}</p></div><div><h4>Cómo se interpreta</h4><p>{interpreta}</p></div></div>'
                f'<p class="caso"><b>Sistemas Colombia:</b> {caso}</p>' + (f'<p class="caso ctxp"><b>Contexto Globant:</b> {ctx}</p>' if ctx else "") + "</div>")

    S.append(seccion("B", "Anexo B · Los indicadores, uno por uno",
        "Para cada indicador: la fórmula, qué mide, cómo se interpreta y qué significa para una filial que presta servicios de tecnología y no tiene inventarios.",
        ind("Liquidez general", "activo corriente ÷ pasivo total", "Si lo que se convierte en dinero en menos de un año alcanza para pagar toda la deuda.",
            "Mayor que 1: alcanza. Menor que 1: con el activo de corto plazo no se cubre toda la deuda.",
            f"{veces(ld('LG')[l], 3)} en {y[l]} ({veces(ld('LG')[P], 3)} en {y[P]}). Estuvo bajo 1 en {lista(lg_bajo1)}, con un mínimo de {veces(min(ld('LG')), 3)} en {y[imin(ld('LG'))]}.",
            f"Casi todo el activo corriente son cuentas por cobrar. Si son saldos en dólares con vinculadas {c('H')}, el indicador dependería de la TRM y de los pagos del grupo.") +
        ind("Liquidez corriente", "activo corriente ÷ pasivo corriente", "Cuántos pesos de activo de corto plazo hay por cada peso de deuda de corto plazo.",
            "Sobre 1 hay colchón; bajo 1 hay riesgo de no poder pagar a tiempo.",
            f"{veces(ld('LC')[l], 3)} en {y[l]}{', el mejor dato de la serie' if mejor('LC') == l else ''} (mínimo de {veces(min(ld('LC')), 3)} en {y[imin(ld('LC'))]}).",
            "El colchón es cartera, no caja: el indicador puede verse sano aunque la caja sea escasa.") +
        ind("Prueba ácida", "(activo corriente − inventarios) ÷ pasivo corriente", "La liquidez corriente sin contar inventarios.",
            "Sirve en empresas que venden productos.", f"{veces(ld('PA')[l], 3)}, idéntica a la liquidez corriente: los inventarios son cero en los {n} años.",
            "Una empresa de servicios vende horas de trabajo. Aquí la prueba exigente de verdad es la disponibilidad inmediata.") +
        ind("Cobertura de gastos", "(AC − inventarios) ÷ [(costo de ventas + gastos adm. y ventas) ÷ 365]",
            "Cuántos días podría operar la empresa solo con su activo de corto plazo, sin facturar nada nuevo.", "Más días = más resistencia ante una interrupción de ingresos.",
            f"{num(ld('CG')[l])} días en {y[l]} ({num(ld('CG')[P])} en {y[P]}; mínimo de {num(min(ld('CG')))} en {y[imin(ld('CG'))]}).",
            "Esos días son, sobre todo, cartera por cobrar; contando solo la caja, la cobertura es de pocos días.") +
        ind("Disponibilidad inmediata", "efectivo y equivalentes ÷ pasivo corriente", "Qué parte de la deuda de corto plazo se puede pagar hoy solo con la caja.",
            "Valores muy bajos indican dependencia del recaudo.",
            f"{veces(ld('DI')[l], 3)} (el efectivo cubre el {pct(ld('DI')[l])} del pasivo corriente). Nunca superó {veces(max(ld('DI')), 2)}; el peor dato fue {y[peor('DI')]} ({veces(ld('DI')[peor('DI')], 3)}).",
            f"En un grupo multinacional es común que la caja se administre de forma centralizada {c('H')}. Un valor bajo no es necesariamente una crisis, pero es la mayor fragilidad del balance.") +
        ind("Capital de trabajo", "activo corriente − pasivo corriente", "Los recursos de corto plazo que quedan después de cubrir las deudas de corto plazo.",
            "Positivo: hay colchón. Negativo: las deudas de corto plazo superan a los activos de corto plazo.",
            f"{corto(ld('CT')[l])} en {y[l]} (nominal; {corto(ld('CT')[P])} en {y[P]})." + (f" Fue negativo en {lista(ct_neg)}." if ct_neg else ""),
            f"Crece con la cartera. Que parte del aumento de 2024 fuera cambiario es {c('H')}: el resultado financiero de 2024 ({corto(fin_[y.index(2024)])}) no muestra una ganancia cambiaria.") +
        ind("Capacidad de endeudamiento", "activo total ÷ pasivo total", "Cuántas veces cubren los activos el total de la deuda.", "Más alto = más margen para pedir prestado.",
            f"{veces(ld('CE')[l])} veces en {y[l]}{', el máximo de la serie' if mejor('CE') == l else ''} (mínimo de {veces(min(ld('CE')))} en {y[imin(ld('CE'))]}).",
            f"Por rótulo, los otros pasivos financieros son {corto(sum(nom(E, k)[l] for k in ('OPFC', 'OPFNC') if k in E))} de un pasivo de {corto(nom(E, 'PT')[l])}. Parte de los otros pasivos no financieros "
            f"no corrientes ({corto(nom(E, 'OPNFNC')[l])}) podrían ser arrendamientos (NIIF 16), que sí son pasivos financieros {c('H')}: la base anota que el reporte 2023 movió los arrendamientos de fila. En {y[l]} la mejora viene sobre todo de la caída del pasivo ({pcts(vp(nom(E, 'PT')[P], nom(E, 'PT')[l]))} nominal), "
            f"más que del patrimonio ({pcts(vp(nom(E, 'PAT')[P], nom(E, 'PAT')[l]))}).") +
        ind("Endeudamiento total (complementario)", "pasivo total ÷ activo total", "Qué porcentaje del activo está financiado con recursos de terceros.",
            "Más bajo = menos dependencia de terceros.",
            f"{pct(ld('END')[l])} en {y[l]}, frente a {pct(max(ld('END')))} en {y[imax(ld('END'))]}{'. Es el mejor dato de la serie' if mejor('END') == l else ''}.",
            "El pasivo más grande son las provisiones por beneficios a empleados (vacaciones, primas y bonificaciones): son propias de una empresa de personas.") +
        ind("Rotación de cartera (complementario)", "cuentas por cobrar corrientes ÷ ingresos × 365", "A cuántos días de ingresos equivale la cartera al cierre del año.",
            "Más días = más capital inmovilizado en cartera. Si la cartera está en otra moneda, el saldo también refleja la tasa de cambio al cierre.",
            f"{num(ld('ROT')[l])} días en {y[l]}, frente a {num(ld('ROT')[P])} en {y[P]} (unos {num(ld('ROT')[y.index(2020)])} en 2019–2020).",
            f"El salto de 2024 tiene un mecanismo posible: ingresos a TRM promedio y cartera a TRM de cierre más alta. Su peso es {c('H')}: en 2023 los días subieron "
            f"({num(ld('ROT')[y.index(2022)])} → {num(ld('ROT')[k2023])}) con la TRM a la baja.")))

    # ---------------------------------------------------------- Anexo C
    v = lambda d, k, a: pcts(vr_real(d, k, y.index(a)))
    S.append(seccion("C", "Anexo C · Las diez variaciones más grandes, explicadas",
        f"Resumen del <i>Informe de explicación de diez variaciones 2018–2025</i>. Variaciones en pesos de {y[l]}. La última columna da la certeza del informe y, "
        "donde esta guía la cambia, la certeza revisada contra la serie completa.",
        tabla(["Variación", "Causa probable", "Certeza"], [
            [f"1. Propiedad, planta y equipo 2019→2020: {v(E, 'PPE', 2020)}", "Probable registro de nuevos arrendamientos de sedes como activos por derecho de uso (NIIF 16), en plena expansión. No es inversión en caja. Los dos años vienen del mismo reporte.", c("P")],
            [f"2. Cartera 2020→2021: {v(E, 'CxC', 2021)}", "Reclasificación de 26.862.502 del largo al corto plazo (sin ella, +73,9%), absorción de Belatrix Colombia y Grupo Assa Colombia (7-jul-2021), ingresos +51,2% nominal y TRM de cierre +16%.", c("C") + " hechos · " + c("P") + " peso"],
            [f"3. Costo de ventas 2018→2019: {v(R, 'CV', 2019)}", "Más contratación para atender proyectos del grupo (ingresos +55,5% nominal). La re-expresión de 2019 es inmaterial.", c("P")],
            [f"4. Costo de ventas 2019→2020: {v(R, 'CV', 2020)}", "Contratación sostenida (300 a 400 personas por mes, ritmo que Forbes reportó a mediados de 2021) y depreciación de los nuevos activos por derecho de uso.", c("P")],
            [f"5. Costo de ventas 2020→2021: {v(R, 'CV', 2021)}", "Fusiones de julio de 2021, más de 2.000 contrataciones y apertura de Barranquilla. En base homogénea sería +45,4%: la reclasificación de 34.021.696 al gasto lo subestima.", c("C") + " hechos · " + c("P") + " magnitud"],
            [f"6. Costo de ventas 2021→2022: {v(R, 'CV', 2022)}", "Primer año completo con las sociedades absorbidas, inflación de 13,1%, salario mínimo +10,1% y nuevas sedes.", c("P")],
            [f"7. Propiedad, planta y equipo 2021→2022: {v(E, 'PPE', 2022)}", "Reclasificación de 89.729.800 a otros activos financieros. Con la cifra original, +2,3%. Qué son esos activos sigue sin conocerse.", c("C") + " reclasificación"],
            [f"8. Cartera 2023→2024: {v(E, 'CxC', 2024)}", "TRM de cierre +15,4% sobre una cartera presumiblemente en dólares, ingresos +15,6% nominal y días de cartera de 92 a 111.", "Informe: " + c("P") + "<br>Revisada: " + c("H")],
            [f"9. Cartera 2024→2025: {v(E, 'CxC', 2025)}", "Revaluación del peso (TRM −14,8%), casi igual a la caída nominal de la cartera (−16,1%), con ingresos planos.", "Informe: " + c("P") + "<br>Revisada: " + c("H")],
            [f"10. Cartera 2019→2020: {v(E, 'CxC', 2020)}", "Crecimiento operativo: ingresos +38,6% nominal con días de cartera estables (unos 71).", c("P")],
        ], "anexo") +
        '<div class="caja"><h4>Por qué esta guía rebaja las variaciones 8 y 9</h4><p>' + frase_cartera +
        " La coincidencia de 2024–2025 es real, pero una lectura cambiaria debería verse en toda la serie y en el resultado financiero, y no se ve.</p></div>"
        '<div class="caja ctx"><h4>Lectura de conjunto</h4><p>El crecimiento de la filial lo explican, probablemente, la operación (prestar servicios al grupo es ' + c("H") + ') y la fusión de 2021. '
        "La caída de propiedad, planta y equipo de 2022 es casi toda contable; en la cartera de 2021, la reclasificación explica una cuarta parte del salto (de +101,3% a +73,9% real) "
        "y el resto es fusión y crecimiento. El efecto cambiario sobre la cartera es plausible en 2024–2025, "
        "pero no se sostiene en toda la serie. Lo que no se puede confirmar sin las notas: la composición de la cartera con vinculadas, la naturaleza de los 89,7 mil millones reclasificados "
        "y la conciliación de la tasa de impuesto.</p></div>"))

    return y, n, "\n".join(S)


CSS = """
@page { size: A4; margin: 14mm 13mm 16mm; }
:root { --ink:#0F1014; --ink2:#55575F; --rule:#E2E2DE; --bone:#F4F4F2; --lima:#D6FC4D; --pos:#0E7A45; --neg:#B3261E; --warn:#8A5A00; --s1:#1C7C55; }
* { box-sizing: border-box; }
body { font: 10.2px/1.55 'Archivo', system-ui, sans-serif; color: var(--ink); margin: 0; }
h1, h2, h3 { margin: 0; letter-spacing: -0.01em; }
p { margin: 0 0 6px; }
.portada { height: 262mm; display: flex; flex-direction: column; justify-content: space-between; background: var(--ink); color: #fff; padding: 20mm 16mm; border-radius: 4px; break-after: page; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.portada .kicker { font: 600 10px 'IBM Plex Mono', monospace; letter-spacing: .12em; color: var(--lima); }
.portada h1 { font-size: 40px; line-height: 1.05; margin: 14px 0; max-width: 150mm; }
.portada h1 span { background: var(--lima); color: var(--ink); padding: 0 4px; }
.portada .sub { font-size: 13px; color: #C9CAC4; max-width: 140mm; }
.portada table { border-collapse: collapse; color: #fff; font-size: 10.5px; }
.portada td { padding: 4px 26px 4px 0; vertical-align: top; }
.portada .lbl { font: 600 9px 'IBM Plex Mono', monospace; letter-spacing: .1em; color: #8C8E86; }
.portada .gen { font: 9px 'IBM Plex Mono', monospace; color: #8C8E86; }
section.salto { break-before: page; }
.sec-head { display: flex; align-items: baseline; gap: 10px; border-bottom: 2px solid var(--ink); padding-bottom: 6px; margin: 4px 0 8px; }
.sec-num { font: 600 11px 'IBM Plex Mono', monospace; background: var(--lima); padding: 2px 6px; }
.sec-head h2 { font-size: 19px; }
.lead { font-size: 11px; color: var(--ink2); margin-bottom: 10px; }
h3 { font-size: 12.5px; margin: 12px 0 6px; }
h4 { font: 600 8.5px 'IBM Plex Mono', monospace; letter-spacing: .1em; text-transform: uppercase; color: var(--ink2); margin: 0 0 3px; }
.pieza { break-inside: avoid; margin-bottom: 12px; }
figure { margin: 4px 0 8px; border: 1px solid var(--rule); border-radius: 6px; overflow: hidden; }
figure img { display: block; width: 100%; }
figure.medio { width: 62%; }
.dos { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 6px; }
.caja { background: var(--bone); border-radius: 6px; padding: 7px 10px; margin: 6px 0; break-inside: avoid; }
.caja.hoy { border-left: 3px solid var(--ink); }
.caja.int { background: #fff; border: 1px dashed var(--rule); }
.caja.ctx { background: #F2F8EE; border-left: 3px solid var(--s1); }
.cert { font: 600 7.5px 'IBM Plex Mono', monospace; letter-spacing: .06em; padding: 1px 4px; border-radius: 3px; white-space: nowrap; }
.cert.c { background: #DDF0E4; color: var(--pos); }
.cert.p { background: #FBEBC9; color: var(--warn); }
.cert.h { background: #E9E6F5; color: #4B3C8C; }
.tbl { width: 100%; border-collapse: collapse; margin: 6px 0 10px; font-size: 9.6px; break-inside: auto; }
.tbl th { text-align: left; font: 600 8px 'IBM Plex Mono', monospace; letter-spacing: .08em; text-transform: uppercase; color: var(--ink2); border-bottom: 1.5px solid var(--ink); padding: 4px 6px; }
.tbl td { border-bottom: 1px solid var(--rule); padding: 4px 6px; vertical-align: top; }
.tbl tr { break-inside: avoid; }
.tbl.anexo td:first-child { font-weight: 600; width: 19%; }
.pos { color: var(--pos); font-weight: 600; } .neg { color: var(--neg); font-weight: 600; }
ul { margin: 0 0 6px 16px; padding: 0; }
.ind { break-inside: avoid; border-top: 1px solid var(--rule); padding-top: 6px; margin-bottom: 8px; }
.ind-head { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; }
.ind-head h3 { margin: 0 0 4px; }
.formula { font: 9px 'IBM Plex Mono', monospace; color: var(--ink2); text-align: right; }
.caso { background: var(--bone); padding: 4px 8px; border-radius: 4px; }
.caso.ctxp { background: #F2F8EE; }
.pie { margin-top: 14px; border-top: 1px solid var(--rule); padding-top: 6px; font-size: 8.5px; color: var(--ink2); font-style: italic; }
"""


def main():
    faltan = [p for p in ("portada.png", "diagnostico.png", "mapa.png", "diagnostico.json") if not (AQUI / "img" / p).exists()]
    if faltan:
        sys.exit("Faltan capturas en img/ (" + ", ".join(faltan) + "): ejecuta capturas.js primero.")
    m = construir_modelo(leer_base_datos(BD), 2024, 2025)
    y, n, cuerpo = construir(m)
    hoy = datetime.now(ZoneInfo("America/Bogota")).strftime("%d/%m/%Y")
    pagina = f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>Guía de lectura · Dossier financiero</title>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>
<div class="portada"><div><div class="kicker">GUÍA DE LECTURA · DOSSIER FINANCIERO</div>
<h1>Cómo leer cada tabla y cada <span>gráfico del dashboard.</span></h1>
<p class="sub">Qué muestra cada pieza, cómo se lee y qué está diciendo hoy sobre Sistemas Colombia S.A.S., la sociedad del grupo Globant en Colombia.</p></div>
<div><table><tr><td class="lbl">EMPRESA</td><td class="lbl">PERÍODO</td><td class="lbl">FUENTE</td></tr>
<tr><td>Sistemas Colombia S.A.S.<br>NIT 900.218.578</td><td>{y[0]} – {y[-1]}<br>{n} ejercicios</td><td>Supersociedades (SIIS)<br>IPC del DANE</td></tr></table>
<p class="gen" style="margin-top:18px">Dashboard: {URL_DASHBOARD}<br>Generada el {hoy} desde el dashboard: las cifras salen del mismo modelo que la página.</p></div></div>
{cuerpo}
<p class="pie">Documento de análisis. No constituye asesoría de inversión ni opinión de auditoría. Fuentes: Superintendencia de Sociedades (SIIS), DANE; contexto: Form 20-F y 6-K de Globant (sec.gov),
Banco de la República, Actualícese, Forbes Colombia y el blog de Globant, según el informe de variaciones.</p>
</body></html>"""
    HTML_SALIDA.write_text(pagina, encoding="utf-8")
    with tempfile.TemporaryDirectory() as perfil:  # perfil propio: no choca con un Chrome abierto
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-sandbox", f"--user-data-dir={perfil}", "--no-pdf-header-footer",
                        "--virtual-time-budget=15000", f"--print-to-pdf={PDF_SALIDA}", HTML_SALIDA.as_uri()], check=True, capture_output=True)
    print(f"Guía generada: {HTML_SALIDA} y {PDF_SALIDA}")


if __name__ == "__main__":
    main()
