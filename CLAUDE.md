# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Forma de responder (obligatorio)

- Responder **siempre en español**, de forma clara e intuitiva: primero la conclusión, luego el sustento.
- **Sin complacencias**: no validar supuestos del usuario por defecto; si algo está mal, es dudoso o no se sostiene con los datos, decirlo directamente.
- **Verificar antes de responder**: recalcular cifras desde los archivos fuente, contrastar entre años y documentos, y no dar por buena una respuesta sin comprobarla. No apresurarse.
- **Ser crítico**: separar lo medido de lo asumido, señalar limitaciones de los datos y declarar el nivel de certeza cuando una conclusión no esté demostrada.

## Naturaleza del proyecto

No es un repositorio de código: es un proyecto de **análisis financiero de Globant**, sin git, sin build, sin tests ni dependencias declaradas. El trabajo típico es leer los estados financieros, calcular indicadores/tendencias y redactar análisis en Markdown (en español). Los scripts auxiliares que hagan falta (p. ej. Python con `openpyxl`, disponible en el sistema) son ad hoc.

## Contenido

- `globant_perfil.md` — perfil corporativo resumido (historia, misión, visión, servicios, clientes). Es la versión condensada del documento largo.
- `Globant_ historia, misión, visión, servicios y clientes según fuentes oficiales (2026).md` — investigación completa con citas numeradas `[n]` a fuentes oficiales (20-F 2025, 6-K, globant.com, investors.globant.com). Corte: 10/11/2026. Al citar cifras, conservar la fuente.
- `ESTADOS_FINANCIEROS/` — estados financieros anuales 2018–2025 de la entidad con **NIT 900218578** (entidad colombiana, bajo NIIF):
  - `900218578_InformeIntegral_<inicio>_<fin>.xlsx` — estado de resultados integral (28 filas, hoja `InformeIntegral`).
  - `900218578_SituacionFinanciera_<inicio>_<fin>.xlsx` — estado de situación financiera / balance (68 filas, hoja `SituacionFinanciera`).
  - `InformeIntegral_<año>.png` / `SituacionFinanciera_<año>.png` — capturas de los mismos estados (ojo: `Informeintegral_2023.png` usa minúscula; no hay PNG de 2018).

## Estructura de los .xlsx (requiere atención al parsear)

- Fila 2: `NIT 900218578`; fila 4: encabezado `('Cuentas', '<año actual>', '<año anterior>')`; desde la fila 5, una cuenta por fila con 3 columnas: nombre de cuenta, valor año actual, valor año comparativo.
- Los valores son **texto**, no números: formato `'$1.262.519.090 M'` (punto como separador de miles, sufijo ` M`). `'-'` y `''` significan vacío/sin dato. Hay que convertirlos antes de calcular.
- La unidad `M` = **miles de COP** (lo dicen las capturas .png del SIIS: "Cifras en miles de pesos colombianos").
- Cada archivo trae dos años. El año comparativo de un archivo **no siempre coincide** con el año actual del archivo anterior (p. ej. ingresos 2019: 347.742.446 en el archivo 2018–2019 vs 346.570.569 en el 2019–2020) → hay reexpresiones. Decidir explícitamente qué serie usar (normalmente el año actual de cada archivo) e indicarlo.
- El balance comparativo 2024 dentro del archivo 2024–2025 está desplazado una fila en la fuente (las cuentas por cobrar aparecen como inventarios). En el archivo 2020–2021, la columna 2020 es copia de la de 2021. Usar siempre la columna "año actual" del reporte propio de cada año.

## Dashboard (`dashboard_globant/`)

- `python3 dashboard_globant/construir_bd.py` regenera `BD_Dashboard_Globant.xlsx` y valida las cascadas del ER y los totales del ESF (sale con código 1 si algo no cuadra).
- `apps_script/`: código de Apps Script separado por responsabilidad (Code/Datos/Calculos `.gs`; Index/Styles/Charts/JavaScript `.html`). Los cálculos viven en `Calculos.gs`; el cliente solo dibuja.
- Selección de cifras (criterio de la guía): "propio reporte cuando existe y está sano; comparativo posterior cuando la compañía re-expresó". 2018 ← comp. 2019; 2019, 2021, 2022 y 2023 ← re-expresados en el reporte siguiente; 2020 y 2025 ← reporte propio; 2024 ← reporte propio salvo el bloque de patrimonio (re-expresado en el reporte 2025). Ver `FUENTE_ANIO` y `FUENTE_BLOQUE` en `construir_bd.py`. Una re-expresión se distingue de un corrimiento porque aporta información nueva (p. ej. el reporte 2024 reparte provisiones 2023 en 1.089.123/718.545). Las variaciones t−1→t con cambio de base se listan en la hoja `Homogenea` y se marcan con † en la interfaz.
- Análisis vertical del balance según el taller: activo ÷ total activos; pasivo ÷ total pasivos; patrimonio ÷ total patrimonio.
- `dashboard_shiny/` es una segunda opción (no reemplaza Apps Script): su frontend se genera con `Rscript sincronizar.R` desde `apps_script/`; nunca editar `www/` ni `templates/` a mano.
- Diseño: seguir `Globant · Sistema de diseño del Dossier Financiero.html` (bundle; desempaquetar el manifiesto para leerlo). Archivo + IBM Plex Mono; negro #0F1014, lima #D6FC4D solo como fondo/énfasis (nunca dato ni texto sobre claro); series #1C7C55 #2563C9 #C9522B #A8338F #6E7A12; semánticos #0E7A45/#B3261E/#8A5A00. El logotipo de Globant NO se dibuja ni actúa como emisor (`CONFIG.LOGO_URL` para el archivo oficial); pie obligatorio "Documento de análisis. No constituye asesoría de inversión ni opinión de auditoría."
- Sistemas Colombia S.A.S. ≠ Globant Colombia S.A.S. (según la guía, NIT 901.411.533 — no verificado de forma independiente).

## Advertencias de análisis

- Los .xlsx corresponden a la **filial colombiana** (en COP, NIIF local); las cifras de los `.md` son del **grupo consolidado Globant** (US$, 20-F). No mezclar ni comparar directamente sin aclararlo.
