# Dossier financiero · Sistemas Colombia S.A.S.

Análisis financiero 2018–2025 de **Sistemas Colombia S.A.S.** (NIT 900.218.578), sociedad del grupo Globant en Colombia, a partir de sus estados financieros depositados ante la Superintendencia de Sociedades. El mismo dashboard está implementado de tres formas: **Google Apps Script**, **Shiny (R)** y **Python**.

**Ver el dashboard:** https://&lt;cuenta&gt;.github.io/dossier-financiero-globant/

> Documento de análisis. No constituye asesoría de inversión ni opinión de auditoría.

## Qué contiene el análisis

- **Perfil:** historia del grupo, la filial y por qué no deben confundirse Globant S.A., Globant Colombia S.A.S. y Sistemas Colombia S.A.S.
- **Trazabilidad de los datos:** de qué reporte sale cada cifra, re-expresiones y defectos de la fuente.
- **Análisis horizontal:** variación absoluta y porcentual año contra año, en términos nominales y **reales** (deflactados con el IPC del DANE, en pesos del último año).
- **Análisis vertical:**
  - estado de resultados sobre ingresos;
  - balance con AV1, sobre el subtotal del grupo;
  - balance con AV2, sobre el total de activos, de pasivos o de patrimonio.
- **Indicadores:**
  - liquidez general y corriente, prueba ácida y disponibilidad inmediata;
  - cobertura de gastos en días y capital de trabajo;
  - capacidad de endeudamiento y endeudamiento total;
  - rotación de cartera y márgenes bruto, operacional y neto.
- **Diagnóstico:** lectura de las tendencias, con los límites de lo que los datos permiten afirmar.

## Datos

- **Fuente:** estados de resultados integral y de situación financiera de 2018 a 2025, publicados en el SIIS de la Superintendencia de Sociedades (`ESTADOS_FINANCIEROS/`). Las cifras están en **miles de pesos colombianos**, bajo NIIF Plenas – Individuales.
- **Depuración:** `dashboard_globant/construir_bd.py` genera `BD_Dashboard_Globant.xlsx`.
  - Comprueba que cuadren las cascadas del estado de resultados y los totales del balance.
  - Si algo no cuadra, se detiene con error.
- **Criterio de selección:** se usa el reporte propio de cada año cuando existe y es coherente, y el comparativo del reporte siguiente cuando la compañía re-expresó la cifra.
  - Hay dos excepciones por bloque de filas. El pasivo no corriente de 2022 sale de su reporte propio, porque el comparativo del reporte 2023 usa una clasificación atípica que el reporte 2024 abandona. El patrimonio de 2024 sale del reporte 2025.
  - Cada decisión queda registrada en las hojas `Fuentes`, `Reexpresiones` y `Homogenea` de la base.
  - Las variaciones que comparan bases distintas se marcan con † en la interfaz.
- **Defectos de la fuente que se corrigen:**
  - El balance del reporte 2021 duplica la columna 2020.
  - El reporte 2025 corre una fila el comparativo 2024.

Las cifras son de la **filial colombiana**, en COP y bajo NIIF locales. No son comparables directamente con las cifras consolidadas del grupo Globant (en US$, según el Form 20-F) que aparecen en el perfil.

## Estructura

```
├── ESTADOS_FINANCIEROS/     Estados financieros originales (.xlsx y capturas)
├── dashboard_globant/       Versión Apps Script (la original) y construcción de la base
│   ├── construir_bd.py
│   ├── BD_Dashboard_Globant.xlsx
│   └── apps_script/         Code, Datos, Calculos (.gs) · Index, Styles, Charts, JavaScript (.html)
├── dashboard_shiny/         Versión Shiny (R)
├── dashboard_python/        Versión Python: servidor Flask y exportador a página estática
└── docs/                    Página pública (GitHub Pages), generada
```

Las tres versiones comparten el mismo frontend: HTML, CSS y gráficos SVG propios, sin librerías externas. El frontend vive en `dashboard_globant/apps_script/`, y las versiones de Shiny y Python lo copian con su propio script de sincronización. Lo que cambia entre versiones es dónde se lee el Excel y se calcula el modelo.

| Versión | Lee los datos de | Calcula en | Publicación |
|---|---|---|---|
| Apps Script | Google Sheets | `Calculos.gs` | Web app de Google |
| Shiny | `.xlsx` con `readxl` | `R/calculos.R` | shinyapps.io |
| Python | `.xlsx` con `openpyxl` | `calculos.py` | Flask + Docker, o página estática |

## Uso

**Apps Script:** instrucciones en [`dashboard_globant/LEEME.md`](dashboard_globant/LEEME.md).

**Shiny:**
```bash
cd dashboard_shiny
Rscript sincronizar.R
Rscript -e 'shiny::runApp(".", launch.browser = TRUE)'
```

**Python (servidor local):**
```bash
cd dashboard_python
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
python3 sincronizar.py
DASH_TOKEN=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))') .venv/bin/python app.py
```

**Regenerar la página pública:**
```bash
cd dashboard_python
python3 sincronizar.py
python3 exportar_pages.py --publico   # escribe ../docs/index.html
```

Más detalle de cada versión en su `LEEME.md`.

## Verificación

La versión de Python se contrasta con las otras dos:

- **`pruebas/comparar_con_apps_script.py`** ejecuta los `.gs` originales en Node y compara el modelo completo **sin tolerancia**.
  - Lo hace sobre la base real y sobre 22 variantes con casos borde: texto donde va un número, celdas vacías, booleanos, fechas, bases en cero, inflación de −100 %…
  - La prueba se validó reintroduciendo errores a propósito: los detecta.
- **`pruebas/comparar_con_shiny.py`** compara con el modelo de R.

La única diferencia deliberada con Apps Script está documentada en [`dashboard_python/LEEME.md`](dashboard_python/LEEME.md).

## Créditos y avisos

- **Fuentes:** Superintendencia de Sociedades (SIIS), DANE (IPC), y Form 20-F y comunicados de Globant para el perfil del grupo.
- **Contexto de las variaciones:** [informe de explicación de diez variaciones 2018–2025](<Sistemas Colombia S.A.S. (Globant)_ explicación de diez variaciones de los estados financieros 2018-2025.md>), con una nota de revisión al inicio sobre las dos afirmaciones que la base no sostiene.
- **Logotipo:** el de Globant se carga desde su servidor oficial (`statics.globant.com`), no se redibuja ni se copia al repositorio. Se configura con `LOGO_URL`; si se deja vacío, se muestra un espacio reservado. Es marca de Globant y se usa solo para identificar al grupo analizado.
- **Vínculo con Globant:** este trabajo no está afiliado ni respaldado por Globant ni por Sistemas Colombia S.A.S.
