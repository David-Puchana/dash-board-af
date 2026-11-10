# Dossier financiero · Sistemas Colombia S.A.S. (Shiny)

Segunda opción de despliegue, paralela a la versión de Apps Script en `../dashboard_globant/`, que se mantiene sin cambios. Las dos comparten el diseño y la lógica de interfaz. El modelo que calcula R es idéntico al de Apps Script (verificado campo por campo).

## Estructura

| Archivo | Equivale a | Qué es |
|---|---|---|
| `app.R` | `Code.gs` | Configuración, UI (plantilla) y servidor |
| `R/datos.R` | `Datos.gs` | Lectura de `data/BD_Dashboard_Globant.xlsx` |
| `R/calculos.R` | `Calculos.gs` | Deflactor, vertical, horizontal, indicadores |
| `templates/index.html` | `Index.html` | Estructura de la página (generado) |
| `www/styles.css` | `Styles.html` | Estilos de la guía (generado) |
| `www/charts.js` | `Charts.html` | Gráficos SVG con efectos hover (generado) |
| `www/app.js` | `JavaScript.html` | Lógica de la interfaz (generado) |
| `sincronizar.R` | — | Regenera los archivos marcados como "generado" y copia la BD |
| `desplegar.R` | — | Publica en shinyapps.io |

**No edites los archivos generados.** Haz los cambios de diseño o interfaz en `../dashboard_globant/apps_script/` y ejecuta `Rscript sincronizar.R`.

## Probar en local

```bash
cd dashboard_shiny
Rscript sincronizar.R
Rscript -e 'shiny::runApp(".", launch.browser = TRUE)'
```

Paquetes: `shiny`, `readxl`, `jsonlite` y `rsconnect` (este último solo para desplegar).

## Publicar en shinyapps.io

1. Crea una cuenta en https://www.shinyapps.io.
2. Entra a **Account → Tokens → Show** y ejecuta en R el comando que aparece. No lo guardes en ningún archivo del proyecto:
   ```r
   rsconnect::setAccountInfo(name = "TU_CUENTA", token = "…", secret = "…")
   ```
3. Desde `dashboard_shiny`:
   ```bash
   Rscript desplegar.R
   ```
   Queda publicada en `https://TU_CUENTA.shinyapps.io/dossier-sistemas-colombia/`.

En el plan gratuito la app es pública y tiene un límite de horas activas al mes.

## Actualizar datos

Regenera la BD con `python3 ../dashboard_globant/construir_bd.py`, luego ejecuta `Rscript sincronizar.R` y vuelve a desplegar. Los años del análisis vertical y el logotipo (`LOGO_URL`) se configuran en `CONFIG`, dentro de `app.R`.
