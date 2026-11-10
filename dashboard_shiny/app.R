# app.R — Dossier financiero de Sistemas Colombia S.A.S. en Shiny.
#
# Arquitectura (equivalente a la versión de Apps Script):
#   R/datos.R          lectura de data/BD_Dashboard_Globant.xlsx      (≈ Datos.gs)
#   R/calculos.R       modelo analítico                               (≈ Calculos.gs)
#   templates/index.html  estructura de la página                     (≈ Index.html)
#   www/styles.css     estilos de la guía                             (≈ Styles.html)
#   www/charts.js      gráficos SVG con efectos hover                 (≈ Charts.html)
#   www/app.js         lógica de la interfaz                          (≈ JavaScript.html)
# Los archivos de www/ y templates/ se generan con sincronizar.R desde ../dashboard_globant/apps_script.
# Shiny carga automáticamente los scripts de R/.

library(shiny)

CONFIG <- list(
  BD = "data/BD_Dashboard_Globant.xlsx",
  ANIO_VERTICAL_1 = 2024L,
  ANIO_VERTICAL_2 = 2025L,
  # URL pública del logotipo OFICIAL (la guía prohíbe dibujarlo). Vacío = espacio reservado.
  LOGO_URL = ""
)

# El modelo se calcula una vez al arrancar la app (los datos son estáticos).
MODELO_JSON <- tryCatch(
  modelo_json(construir_modelo(leer_base_datos(CONFIG$BD), CONFIG$ANIO_VERTICAL_1, CONFIG$ANIO_VERTICAL_2)),
  error = function(e) structure(conditionMessage(e), class = "error_modelo")
)

ui <- htmlTemplate(
  "templates/index.html",
  logo_url = HTML(jsonlite::toJSON(CONFIG$LOGO_URL, auto_unbox = TRUE))
)

server <- function(input, output, session) {
  if (inherits(MODELO_JSON, "error_modelo")) {
    session$sendCustomMessage("error", paste("Error al leer la base de datos:", unclass(MODELO_JSON)))
  } else {
    session$sendCustomMessage("modelo", as.character(MODELO_JSON))
  }
}

shinyApp(ui, server)
