#!/usr/bin/env python3
"""Construye BD_Dashboard_Globant.xlsx a partir de los .xlsx de Supersociedades.

Uso:  python3 construir_bd.py
Lee   ../ESTADOS_FINANCIEROS/900218578_*.xlsx
Crea  BD_Dashboard_Globant.xlsx (hojas: ER, ESF, Deflactor, Empresa, Hitos, Notas, Reexpresiones, Fuentes)

Criterio de selección (guía del Dossier Financiero):
  "Cada ejercicio se toma de la columna limpia: su propio reporte cuando existe y está sano,
   el comparativo posterior cuando la compañía re-expresó la cifra."
  La procedencia de cada año está en FUENTE_ANIO y se publica en la hoja Fuentes.
  Las diferencias entre versiones de una misma cifra se documentan en la hoja Reexpresiones.
"""
import os, re, sys
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, '..', 'ESTADOS_FINANCIEROS')
OUT = os.path.join(BASE, 'BD_Dashboard_Globant.xlsx')
YEARS = list(range(2018, 2026))


def num(v):
    """'$1.262.519.090 M' -> 1262519090 (miles de COP). '-', '', None -> 0."""
    if v is None:
        return 0
    s = str(v).strip()
    if s in ('', '-'):
        return 0
    s = s.replace('$', '').replace('M', '').replace('.', '').replace(' ', '')
    return int(s)


def load(tipo, y):
    f = os.path.join(SRC, f'900218578_{tipo}_{y-1}-12-31_{y}-12-31.xlsx')
    ws = openpyxl.load_workbook(f, data_only=True).active
    rows = {}
    for i, r in enumerate(ws.iter_rows(values_only=True), 1):
        rows[i] = r
    assert rows[4][1] == f'{y}-12-31' and rows[4][2] == f'{y-1}-12-31', (f, rows[4])
    return rows


# ---------------- Definición de cuentas -----------------
# (id, fila_origen, etiqueta, tipo, grupo)
ER_DEF = [
    ('ING', 7, 'Ingresos de actividades ordinarias', 'total', 'Ingresos'),
    ('CV', 8, 'Costo de ventas', 'detalle', 'Costos'),
    ('UB', 9, 'Utilidad bruta', 'subtotal', 'Resultado'),
    ('OI', 10, 'Otros ingresos', 'detalle', 'Operacional'),
    ('GV', 11, 'Gastos de ventas', 'detalle', 'Operacional'),
    ('GA', 12, 'Gastos de administración', 'detalle', 'Operacional'),
    ('OG', 13, 'Otros gastos', 'detalle', 'Operacional'),
    ('OGP', 14, 'Otras ganancias (pérdidas)', 'detalle', 'Operacional'),
    ('UO', 15, 'Utilidad operacional', 'subtotal', 'Resultado'),
    ('IF', 18, 'Ingresos financieros', 'detalle', 'No operacional'),
    ('CF', 19, 'Costos financieros', 'detalle', 'No operacional'),
    ('COB', 23, 'Ganancias (pérdidas) de cobertura', 'detalle', 'No operacional'),
    ('UAI', 24, 'Utilidad antes de impuestos', 'subtotal', 'Resultado'),
    ('IMP', 25, 'Impuesto de renta', 'detalle', 'Impuestos'),
    ('UN', 28, 'Utilidad neta', 'subtotal', 'Resultado'),
]
ER_ZERO_ROWS = [16, 17, 20, 21, 22, 27]  # deben ser 0 en todos los años

ESF_DEF = [
    ('EFE', 7, 'Efectivo y equivalentes', 'detalle', 'Activo corriente'),
    ('CxC', 8, 'Cuentas por cobrar comerciales (corrientes)', 'detalle', 'Activo corriente'),
    ('INV', 9, 'Inventarios corrientes', 'detalle', 'Activo corriente'),
    ('AIC', 10, 'Activos por impuestos corrientes', 'detalle', 'Activo corriente'),
    ('ABC', 11, 'Activos biológicos corrientes', 'detalle', 'Activo corriente'),
    ('OAFC', 12, 'Otros activos financieros corrientes', 'detalle', 'Activo corriente'),
    ('OANFC', 13, 'Otros activos no financieros corrientes', 'detalle', 'Activo corriente'),
    ('APG', 14, 'Activos corrientes pignorados', 'detalle', 'Activo corriente'),
    ('AMV', 16, 'Activos mantenidos para la venta', 'detalle', 'Activo corriente'),
    ('AC', 17, 'Total activo corriente', 'subtotal', 'Activo corriente'),
    ('PI', 19, 'Propiedad de inversión', 'detalle', 'Activo no corriente'),
    ('PPE', 20, 'Propiedades, planta y equipo', 'detalle', 'Activo no corriente'),
    ('PLU', 21, 'Plusvalía', 'detalle', 'Activo no corriente'),
    ('INT', 22, 'Intangibles', 'detalle', 'Activo no corriente'),
    ('ABNC', 23, 'Activos biológicos no corrientes', 'detalle', 'Activo no corriente'),
    ('CxCNC', 24, 'Cuentas por cobrar no corrientes', 'detalle', 'Activo no corriente'),
    ('INVNC', 25, 'Inventarios no corrientes', 'detalle', 'Activo no corriente'),
    ('AID', 26, 'Activos por impuestos diferidos', 'detalle', 'Activo no corriente'),
    ('AICNC', 27, 'Activos por impuestos corrientes (no corriente)', 'detalle', 'Activo no corriente'),
    ('OAFNC', 28, 'Otros activos financieros no corrientes', 'detalle', 'Activo no corriente'),
    ('OANFNC', 29, 'Otros activos no financieros no corrientes', 'detalle', 'Activo no corriente'),
    ('APGNC', 30, 'Activos no corrientes pignorados', 'detalle', 'Activo no corriente'),
    ('ANC', 31, 'Total activo no corriente', 'subtotal', 'Activo no corriente'),
    ('AT', 32, 'TOTAL ACTIVOS', 'total', 'Activo'),
    ('PBE', 36, 'Provisiones por beneficios a empleados', 'detalle', 'Pasivo corriente'),
    ('OPC', 37, 'Otras provisiones corrientes', 'detalle', 'Pasivo corriente'),
    ('CxP', 39, 'Cuentas por pagar comerciales', 'detalle', 'Pasivo corriente'),
    ('PIC', 40, 'Pasivos por impuestos corrientes', 'detalle', 'Pasivo corriente'),
    ('OPFC', 41, 'Otros pasivos financieros corrientes', 'detalle', 'Pasivo corriente'),
    ('OPNFC', 42, 'Otros pasivos no financieros corrientes', 'detalle', 'Pasivo corriente'),
    ('PMV', 44, 'Pasivos de activos para la venta', 'detalle', 'Pasivo corriente'),
    ('PC', 45, 'Total pasivo corriente', 'subtotal', 'Pasivo corriente'),
    ('PBENC', 48, 'Provisiones por beneficios a empleados (no corriente)', 'detalle', 'Pasivo no corriente'),
    ('OPNC', 49, 'Otras provisiones no corrientes', 'detalle', 'Pasivo no corriente'),
    ('CxPNC', 51, 'Cuentas por pagar no corrientes', 'detalle', 'Pasivo no corriente'),
    ('PID', 52, 'Pasivo por impuestos diferidos', 'detalle', 'Pasivo no corriente'),
    ('PICNC', 53, 'Pasivos por impuestos corrientes (no corriente)', 'detalle', 'Pasivo no corriente'),
    ('OPFNC', 54, 'Otros pasivos financieros no corrientes', 'detalle', 'Pasivo no corriente'),
    ('OPNFNC', 55, 'Otros pasivos no financieros no corrientes', 'detalle', 'Pasivo no corriente'),
    ('PNC', 56, 'Total pasivo no corriente', 'subtotal', 'Pasivo no corriente'),
    ('PT', 57, 'TOTAL PASIVOS', 'total', 'Pasivo'),
    ('CAP', 59, 'Capital emitido', 'detalle', 'Patrimonio'),
    ('PRI', 60, 'Prima de emisión', 'detalle', 'Patrimonio'),
    ('APC', 61, 'Acciones propias en cartera', 'detalle', 'Patrimonio'),
    ('ISC', 62, 'Inversión suplementaria al capital', 'detalle', 'Patrimonio'),
    ('OPP', 63, 'Otras participaciones en el patrimonio', 'detalle', 'Patrimonio'),
    ('SRV', 64, 'Superávit por revaluación', 'detalle', 'Patrimonio'),
    ('ORES', 65, 'Otras reservas', 'detalle', 'Patrimonio'),
    ('GACU', 66, 'Ganancias acumuladas', 'detalle', 'Patrimonio'),
    ('PAT', 67, 'TOTAL PATRIMONIO', 'total', 'Patrimonio'),
    ('TPP', 68, 'TOTAL PASIVO + PATRIMONIO', 'total', 'Control'),
]

# Inflación anual IPC Colombia (DANE), variación diciembre-diciembre, %.
IPC = {2018: 3.18, 2019: 3.80, 2020: 1.61, 2021: 5.62, 2022: 13.12, 2023: 9.28, 2024: 5.20, 2025: 5.10}


# año → (reporte de origen, columna 1=actual 2=comparativa, descripción, estado)
FUENTE_ANIO = {
    2018: (2019, 2, 'Comparativo del reporte 2019 (no hay reporte 2018)', 'OK'),
    2019: (2020, 2, 'Cifra re-expresada en el reporte 2020', 'AVISO'),
    2020: (2020, 1, 'Reporte 2020 (el comparativo del reporte 2021 está duplicado)', 'OK'),
    2021: (2022, 2, 'Cifra re-expresada en el reporte 2022', 'AVISO'),
    2022: (2023, 2, 'Cifra re-expresada en el reporte 2023', 'AVISO'),
    2023: (2024, 2, 'Cifra re-expresada en el reporte 2024', 'AVISO'),
    2024: (2024, 1, 'Reporte 2024; patrimonio re-expresado en el reporte 2025 (el resto de ese comparativo está corrido una fila)', 'AVISO'),
    2025: (2025, 1, 'Reporte 2025', 'OK'),
}

# Excepciones por bloque de filas: (tipo, año) → (filas, reporte, columna). El comparativo 2024 del reporte 2025
# está corrido en el activo, pero su bloque de patrimonio es sano y re-expresa 2024 (otras participaciones → reservas).
# El pasivo NO corriente de 2022 (filas 46-55) se toma de su reporte propio: el comparativo del reporte 2023 usa la
# clasificación atípica de la nota 3 (arrendamientos en otros pasivos financieros, provisiones no corrientes dentro de
# otros pasivos no financieros), que el reporte 2024 abandona al re-expresar 2023. El total no corriente es idéntico en
# las dos versiones. El pasivo corriente (filas 41-42) sigue en el reporte 2023: su reclasificación de financieros a no
# financieros va en el mismo sentido que la re-expresión del reporte 2024, así que no se trata como atípica.
FUENTE_BLOQUE = {
    ('SituacionFinanciera', 2022): (range(46, 56), 2022, 1),
    ('SituacionFinanciera', 2024): (range(59, 68), 2025, 2),
}
# Columnas comparativas que NO sirven para calcular variaciones homogéneas (están dañadas en la fuente).
# Pares t-1 → t que ya comparten clasificación aunque vengan de reportes distintos, cuando la "base homogénea" del
# reporte t sería la atípica: no se marcan con †. 2022 (reporte 2022) → 2023 (re-expresado por el reporte 2024).
PAR_YA_HOMOGENEO = {
    ('SituacionFinanciera', 2023): range(46, 56),
}
COMPARATIVO_DANADO = {
    ('SituacionFinanciera', 2021): range(1, 200),   # copia de la columna 2021
    ('SituacionFinanciera', 2025): range(1, 59),    # activo y pasivo corridos una fila (el patrimonio está sano)
}


def fuente(tipo, y, row):
    b = FUENTE_BLOQUE.get((tipo, y))
    if b and row in b[0]:
        return b[1], b[2]
    ry, col, *_ = FUENTE_ANIO[y]
    return ry, col


def extract(tipo, defs):
    reps = {y: load(tipo, y) for y in range(2019, 2026)}
    data, alt = {}, {}
    for code, row, *_ in defs:
        data[code], alt[code] = {}, {}
        for y in YEARS:
            ry, col = fuente(tipo, y, row)
            data[code][y] = num(reps[ry][row][col])
            # versión alternativa: el reporte propio si se usó un comparativo, o el comparativo siguiente
            if col == 2 and y in reps:
                alt[code][y] = (num(reps[y][row][1]), f'Reporte {y}')
            elif col == 1 and y + 1 in reps:
                alt[code][y] = (num(reps[y + 1][row][2]), f'Comparativo del reporte {y + 1}')
    return reps, data, alt


def homogeneas(tipo, defs, reps, data):
    """Variaciones t-1→t con cambio de base: el par usado no sale del mismo reporte.
    Devuelve filas con la variación homogénea según el reporte t (sus dos columnas), si está disponible."""
    out = []
    for code, row, label, *_ in defs:
        for y in range(2019, 2026):
            if row in PAR_YA_HOMOGENEO.get((tipo, y), ()):
                continue
            danado = row in COMPARATIVO_DANADO.get((tipo, y), ())
            prev_h, cur_h = num(reps[y][row][2]), num(reps[y][row][1])
            if danado:
                # Sin comparativo confiable: se marca solo si la cifra de t se re-expresó después de su reporte propio
                if cur_h != data[code][y]:
                    out.append((code, label, y, None, None, 'No disponible: el comparativo del reporte %d está dañado' % y))
            elif prev_h != data[code][y - 1] or cur_h != data[code][y]:
                out.append((code, label, y, prev_h, cur_h, 'Reporte %d (ambas columnas, misma base)' % y))
    return out


er_reps, ER, ER_ALT = extract('InformeIntegral', ER_DEF)
esf_reps, ESF, ESF_ALT = extract('SituacionFinanciera', ESF_DEF)

# ---------------- Validaciones aritméticas -----------------
errores = []
for y in YEARS:
    ry, col, *_ = FUENTE_ANIO[y]
    for r in ER_ZERO_ROWS:
        if num(er_reps[ry][r][col]) != 0:
            errores.append(f'ER {y}: fila {r} distinta de cero ({er_reps[ry][r][0]})')
for y in YEARS:
    g = lambda c: ER[c][y]
    if g('ING') - g('CV') != g('UB'):
        errores.append(f'ER {y}: ING-CV != UB')
    if g('UB') + g('OI') - g('GV') - g('GA') - g('OG') + g('OGP') != g('UO'):
        errores.append(f'ER {y}: cascada a UO no cuadra')
    if g('UO') + g('IF') - g('CF') + g('COB') != g('UAI'):
        errores.append(f'ER {y}: cascada a UAI no cuadra')
    if g('UAI') - g('IMP') != g('UN'):
        errores.append(f'ER {y}: UAI-IMP != UN')
    e = lambda c: ESF[c][y]
    det = lambda grp: sum(ESF[c][y] for c, _, _, t, gr in ESF_DEF if t == 'detalle' and gr == grp)
    for grp, tot in [('Activo corriente', 'AC'), ('Activo no corriente', 'ANC'), ('Pasivo corriente', 'PC'),
                     ('Pasivo no corriente', 'PNC'), ('Patrimonio', 'PAT')]:
        if det(grp) != e(tot):
            errores.append(f'ESF {y}: suma detalle {grp} = {det(grp):,} vs total {e(tot):,} (dif {det(grp)-e(tot):,})')
    if e('AC') + e('ANC') != e('AT'):
        errores.append(f'ESF {y}: AC+ANC != AT')
    if e('PC') + e('PNC') != e('PT'):
        errores.append(f'ESF {y}: PC+PNC != PT')
    if e('PT') + e('PAT') != e('AT') or e('TPP') != e('AT'):
        errores.append(f'ESF {y}: AT != PT+PAT')

print('== Validaciones aritméticas ==')
print('\n'.join(errores) if errores else 'OK: todas las cascadas y totales cuadran')

HOMO = [('ER',) + r for r in homogeneas('InformeIntegral', ER_DEF, er_reps, ER)] + \
       [('ESF',) + r for r in homogeneas('SituacionFinanciera', ESF_DEF, esf_reps, ESF)]

# Quitar cuentas de ESF que son cero en todos los años (se conserva INV: lo usa la prueba ácida)
ESF_DEF_USE = [d for d in ESF_DEF if d[3] != 'detalle' or d[0] == 'INV'
               or any(ESF[d[0]][y] for y in YEARS)]
# Homogenea solo con cuentas que están en la base (sin filas huérfanas)
_USADAS = {d[0] for d in ESF_DEF_USE}
HOMO = [h for h in HOMO if h[0] == 'ER' or h[1] in _USADAS]

# ---------------- Reexpresiones -----------------
def desc_usada(tipo, y, row):
    """Procedencia de una cifra concreta: la del bloque si la fila tiene excepción, si no la del año."""
    b = FUENTE_BLOQUE.get(('InformeIntegral' if tipo == 'ER' else 'SituacionFinanciera', y))
    if b and row in b[0]:
        return f'Reporte {b[1]}' if b[2] == 1 else f'Cifra re-expresada en el reporte {b[1]}'
    return FUENTE_ANIO[y][2]


reexp = []
for tipo, defs, D, A in [('ER', ER_DEF, ER, ER_ALT), ('ESF', ESF_DEF, ESF, ESF_ALT)]:
    for code, row, label, *_ in defs:
        for y, (v, fuente_alt) in A[code].items():
            if v != D[code][y]:
                reexp.append((tipo, y, code, label, D[code][y], desc_usada(tipo, y, row), v, fuente_alt, D[code][y] - v))
# Los años marcados como re-expresados deben tener diferencias reales con su reporte propio
for y, (ry, col, _, est) in FUENTE_ANIO.items():
    if col == 2 and y >= 2019 and not any(r[1] == y for r in reexp):
        errores.append(f'{y}: marcado como re-expresado pero no difiere del reporte propio')

# ---------------- Escritura -----------------
wb = openpyxl.Workbook()
H = Font(bold=True, color='FFFFFF')
HF = PatternFill('solid', fgColor='1C5CAB')
BOLD = Font(bold=True)


def header(ws, cols):
    ws.append(cols)
    for c in ws[1]:
        c.font, c.fill = H, HF
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    ws.freeze_panes = 'C2'


def write_stmt(ws, defs, D):
    header(ws, ['ID', 'Cuenta', 'Tipo', 'Grupo', 'Orden'] + [str(y) for y in YEARS])
    for i, (code, _, label, tipo, grp) in enumerate(defs, 1):
        ws.append([code, label, tipo, grp, i] + [D[code][y] for y in YEARS])
        if tipo != 'detalle':
            for c in ws[ws.max_row]:
                c.font = BOLD
    for col in range(6, 6 + len(YEARS)):
        for r in range(2, ws.max_row + 1):
            ws.cell(r, col).number_format = '#,##0'
        ws.column_dimensions[get_column_letter(col)].width = 16
    ws.column_dimensions['B'].width = 46
    ws.column_dimensions['D'].width = 20


ws = wb.active
ws.title = 'ER'
write_stmt(ws, ER_DEF, ER)
write_stmt(wb.create_sheet('ESF'), ESF_DEF_USE, ESF)

# Deflactor
ws = wb.create_sheet('Deflactor')
header(ws, ['Año', 'Inflación IPC dic-dic (%)', 'Índice IPC (dic-2018 = 100)', 'Factor a pesos de 2025', 'Fuente'])
ws.freeze_panes = 'B2'
for i, y in enumerate(YEARS):
    r = i + 2
    idx = '=100' if y == 2018 else f'=C{r-1}*(1+B{r}/100)'
    ws.append([y, IPC[y], idx, f'=$C${len(YEARS)+1}/C{r}', 'DANE – IPC total nacional, variación anual a diciembre'])
    ws.cell(r, 3).number_format = '0.00'
    ws.cell(r, 4).number_format = '0.0000'
for col, w in zip('ABCDE', [8, 22, 24, 22, 52]):
    ws.column_dimensions[col].width = w

# Empresa
ws = wb.create_sheet('Empresa')
header(ws, ['Clave', 'Valor'])
empresa = [
    ('Razón social', 'Sistemas Colombia S.A.S.'),
    ('Relación con el grupo', 'Sociedad del grupo Globant en Colombia. No es Globant S.A. (matriz) ni Globant Colombia S.A.S., que según la guía del dossier es otra sociedad (NIT 901.411.533).'),
    ('NIT', '900.218.578'),
    ('Actividad económica (CIIU)', 'J6201 – Actividades de desarrollo de sistemas informáticos'),
    ('Ubicación', 'Bogotá D.C.'),
    ('Supervisión', 'Superintendencia de Sociedades – estado: Vigilancia'),
    ('Marco contable', 'NIIF Plenas – Individuales'),
    ('Unidad de las cifras', 'Miles de pesos colombianos (COP)'),
    ('Fuente de las cifras', 'SIIS – Superintendencia de Sociedades (Informe Integral y Situación Financiera, cortes 2019–2025)'),
    ('Grupo', 'Globant S.A. – NYSE: GLOB. Fundada en 2003 en Argentina por Martín Migoya, Guibert Englebienne, Martín Umaran y Néstor Nocetti.'),
    ('Misión', 'No publica una misión formal única. Formulación vigente (sección Stay Relevant): ayudar a las organizaciones a prosperar en un futuro impulsado por IA.'),
    ('Visión', 'No existe una declaración de visión formal vigente. Hay menciones puntuales: “reinventar la industria y los negocios de nuestros clientes” (carta del CEO, Integrated Report 2019) y “reinventar industrias y organizaciones” (comunicado Globant–LALIGA, 2022).'),
    ('Servicios', 'Core Studios (Digital, GUT, Enterprise), AI Industry Studios, AI Pods (suscripción por tokens) y Globant Enterprise AI; plataforma Glob.AI (2026).'),
    ('Clientes', 'The Walt Disney Company (8,7% de ingresos 2025), Google, Electronic Arts, Santander, FIFA, Formula 1, LALIGA, YPF, Riot Games, LA Clippers.'),
    ('Cifras del grupo', 'Ingresos 2025: US$2.454,9 M (+1,6%). Plantilla al 30/06/2026: 27.411 Globers; 31 países. Cifras consolidadas en US$, no comparables directamente con la filial.'),
    ('Rol de Colombia', 'Según la investigación de fuentes del proyecto (20-F 2025), Colombia está entre los cuatro principales centros de entrega del grupo, junto con Argentina, India y México.'),
]
for k, v in empresa:
    ws.append([k, v])
ws.column_dimensions['A'].width = 28
ws.column_dimensions['B'].width = 120

# Hitos
ws = wb.create_sheet('Hitos')
header(ws, ['Año', 'Hito', 'Ámbito'])
hitos = [
    (2003, 'Fundación de Globant en Buenos Aires por cuatro socios.', 'Grupo'),
    (2006, 'Primera oficina fuera de Buenos Aires (Tandil); firma a Google como cliente.', 'Grupo'),
    (2008, 'Constitución de Sistemas Colombia S.A.S. según el SIIS (los reportes 2021–2023 muestran 2008-04-10; los de 2019, 2020, 2024 y 2025 muestran 2009-10-23).', 'Filial'),
    (2009, 'Introduce su modelo de Studios.', 'Grupo'),
    (2014, 'IPO en el NYSE (18 de julio, GLOB, US$10 por acción).', 'Grupo'),
    (2021, 'El grupo supera US$1.000 M de ingresos (US$1.297,1 M). La filial crece 51% nominal.', 'Grupo / Filial'),
    (2022, 'La filial supera $1 billón de COP en ingresos. Joint venture con LALIGA (Sportian).', 'Grupo / Filial'),
    (2025, 'Lanzamiento de AI Pods; Plan de Optimización del Negocio. Ingresos de la filial caen 0,5% nominal.', 'Grupo / Filial'),
    (2026, 'Plataforma Glob.AI (agosto).', 'Grupo'),
]
for h in hitos:
    ws.append(list(h))
ws.column_dimensions['B'].width = 120
ws.column_dimensions['C'].width = 16

# Notas de calidad de datos
ws = wb.create_sheet('Notas')
header(ws, ['N°', 'Tema', 'Nota', 'Impacto'])
notas = [
    (1, 'El balance 2020–2021 duplica la columna comparativa', 'En el reporte de corte 2021 las columnas 2021 y 2020 son idénticas, también en la vista web del SIIS. Ninguna coincide con el 2020 real (total activos $262.106.073 M frente a $379.223.013 M). 2020 se toma de su propio reporte.', 'Defecto de la fuente'),
    (2, 'El balance 2024–2025 corre el comparativo 2024 una fila', 'Los $385.798.378 M de deudores comerciales aparecen rotulados como inventarios y los impuestos corrientes como activos biológicos. 2024 se toma de su propio reporte, que sí es coherente.', 'Defecto de la fuente'),
    (3, 'El reporte 2023 usa una clasificación atípica del balance', 'En sus dos columnas (2023 y 2022) ubica los arrendamientos en otros pasivos financieros no corrientes y las provisiones no corrientes dentro de otros pasivos no financieros; en la columna 2023 pone además el impuesto diferido en activos por impuestos corrientes no corrientes. El reporte 2024 re-expresa 2023 con la clasificación habitual y aporta información nueva (reparte las provisiones en 1.089.123 y 718.545), así que no es un corrimiento: 2023 se toma del reporte 2024 y el pasivo no corriente de 2022 de su reporte propio, que usa la clasificación habitual. El pasivo corriente de 2022 sigue en el reporte 2023 (su paso de 6.128.026 de financieros a no financieros va en el mismo sentido que la re-expresión del reporte 2024).', 'Criterio aplicado'),
    (4, 'Re-expresiones usadas: 2019, 2021, 2022, 2023 y patrimonio 2024', 'La compañía re-expresó esas cifras en el reporte del año siguiente (p. ej. ingresos 2019: 347.742.446 → 346.570.569; costo de ventas 2021: 594.737.380 → 560.715.684; PPE 2022: 132.934.182 → 43.204.382 con reclasificación a otros activos financieros; patrimonio 2024: otras participaciones 26.721.326 pasan a otras reservas). Se usa la cifra re-expresada, según el criterio del dossier.', 'Criterio aplicado'),
    (12, 'Cambio de base en las variaciones', 'Usar la cifra re-expresada del año t deja el año t−1 en la base anterior, así que algunas variaciones mezclan dos clasificaciones (p. ej. gastos operacionales 2020→2021: +77,4% mostrado frente a +22,9% en base homogénea). Esas variaciones se marcan con † y el detalle muestra la variación homogénea según el reporte del año t (hoja Homogenea).', 'Criterio aplicado'),
    (13, 'Incongruencia en la re-expresión de 2019', 'En el reporte 2020 la utilidad neta 2019 baja 3,2 M mientras el patrimonio 2019 sube 3,2 M (ganancias acumuladas +12,6 M, otras reservas −9,4 M). Sin las notas a los estados financieros no se puede descartar un error de la fuente.', 'Sin resolver'),
    (5, 'Clasificación del gasto en 2023', 'En 2023 el gasto operacional se reportó como "Gastos de ventas" ($153.051.701 M); en el reporte 2024 se reclasificó a administración. Los análisis usan gastos operacionales = administración + ventas.', 'Controlado'),
    (6, 'Unidad', 'El sufijo "M" significa miles, no millones (lo indican las capturas del SIIS). Los ingresos de 2024 (1.268.553.410) equivalen a 1,27 billones de pesos.', 'Lectura'),
    (7, 'Inventarios en cero', 'La compañía reporta inventarios en cero los ocho años: la prueba ácida y la liquidez corriente dan exactamente el mismo número.', 'Lectura'),
    (8, 'Deflactor', 'Se usa el IPC de diciembre a diciembre (DANE) para llevar todo a pesos de 2025. Para partidas de flujo un IPC promedio anual sería más preciso; no se calculó su efecto. El IPC 2025 (5,10%) proviene de prensa que cita al DANE, no del boletín oficial.', 'Supuesto'),
    (9, 'No confundir las entidades', 'El NIT 900.218.578 corresponde a Sistemas Colombia S.A.S., no a Globant S.A. Las cifras del grupo (US$) provienen de reportes corporativos y no son comparables con estos archivos.', 'Alcance'),
    (10, 'Fecha de constitución', 'El SIIS muestra dos fechas de constitución según el reporte: 2008-04-10 (cortes 2021–2023) y 2009-10-23 (cortes 2019, 2020, 2024 y 2025).', 'Sin resolver'),
    (11, 'Validación contra la fuente', 'Las cifras de los 14 .xlsx coinciden con las capturas .png del SIIS, y las cascadas del estado de resultados y los totales del balance cuadran en los 8 años.', 'Verificado'),
]
for n in notas:
    ws.append(list(n))
ws.column_dimensions['B'].width = 24
ws.column_dimensions['C'].width = 120
ws.column_dimensions['D'].width = 30
for r in range(2, ws.max_row + 1):
    ws.cell(r, 3).alignment = Alignment(wrap_text=True, vertical='top')

# Reexpresiones
ws = wb.create_sheet('Reexpresiones')
header(ws, ['Estado', 'Año', 'ID', 'Cuenta', 'Valor usado', 'Fuente usada', 'Valor alternativo', 'Fuente alternativa', 'Diferencia'])
ws.freeze_panes = 'A2'
for row in reexp:
    ws.append(list(row))
for col in 'EGI':
    for r in range(2, ws.max_row + 1):
        ws[f'{col}{r}'].number_format = '#,##0'
    ws.column_dimensions[col].width = 18
for col in 'FH':
    ws.column_dimensions[col].width = 44
ws.column_dimensions['D'].width = 46

# Variaciones homogéneas (cambio de base)
ws = wb.create_sheet('Homogenea')
header(ws, ['Estado', 'ID', 'Cuenta', 'Año', 'Anterior homogéneo', 'Actual homogéneo', 'Fuente'])
ws.freeze_panes = 'A2'
for r in HOMO:
    ws.append(list(r))
for col in 'EF':
    for rr in range(2, ws.max_row + 1):
        ws[f'{col}{rr}'].number_format = '#,##0'
    ws.column_dimensions[col].width = 20
ws.column_dimensions['C'].width = 46
ws.column_dimensions['G'].width = 56

# Fuentes
ws = wb.create_sheet('Fuentes')
header(ws, ['Año', 'Procedencia', 'Estado', 'Archivo ER', 'Archivo ESF', 'Columna'])
for y in YEARS:
    ry, col, desc, est = FUENTE_ANIO[y]
    for (t, yb), (filas, rb, cb) in FUENTE_BLOQUE.items():
        if yb == y and t == 'SituacionFinanciera':
            desc += (f'; filas {filas.start}-{filas.stop - 1} del balance desde el '
                     + (f'reporte propio {rb} (900218578_SituacionFinanciera_{rb-1}-12-31_{rb}-12-31.xlsx, columna actual)' if cb == 1
                        else f'comparativo del reporte {rb} (900218578_SituacionFinanciera_{rb-1}-12-31_{rb}-12-31.xlsx)'))
    ws.append([y, desc, est, f'900218578_InformeIntegral_{ry-1}-12-31_{ry}-12-31.xlsx',
               f'900218578_SituacionFinanciera_{ry-1}-12-31_{ry}-12-31.xlsx',
               'Actual' if col == 1 else 'Comparativa'])
for col, w in zip('ABCDEF', [8, 62, 10, 52, 56, 14]):
    ws.column_dimensions[col].width = w

wb.save(OUT)
print(f'\nReexpresiones detectadas: {len(reexp)}')
print(f'Variaciones con cambio de base: {len(HOMO)}')
print(f'Cuentas ESF incluidas: {len(ESF_DEF_USE)} de {len(ESF_DEF)}')
print(f'BD creada: {OUT}')
if errores:
    sys.exit(1)
