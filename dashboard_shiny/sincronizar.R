# sincronizar.R — Copia el frontend y la BD desde la versión de Apps Script.
#
# Uso (desde la carpeta dashboard_shiny):  Rscript sincronizar.R
# Genera:
#   www/styles.css   ← Styles.html (contenido de <style>)
#   www/charts.js    ← Charts.html (contenido de <script>)
#   www/app.js       ← JavaScript.html (contenido de <script>)
#   templates/index.html ← Index.html (scriptlets de Apps Script → etiquetas estándar + plantilla Shiny)
#   data/BD_Dashboard_Globant.xlsx ← ../dashboard_globant/BD_Dashboard_Globant.xlsx
# Así ambas versiones comparten exactamente el mismo diseño y la misma lógica de interfaz.

origen <- "../dashboard_globant/apps_script"
leer <- function(f) paste(readLines(file.path(origen, f), encoding = "UTF-8", warn = FALSE), collapse = "\n")
entre <- function(txt, abre, cierra) {
  ini <- regexpr(abre, txt); fin <- regexpr(cierra, txt)
  if (ini < 0 || fin < 0) stop("No se encontró ", abre, " … ", cierra)
  substr(txt, ini + attr(ini, "match.length"), fin - 1)
}
escribir <- function(txt, ruta) { con <- file(ruta, "w", encoding = "UTF-8"); writeLines(txt, con); close(con) }

estilos <- leer("Styles.html")
escribir(trimws(entre(estilos, "<style>", "</style>")), "www/styles.css")
links_fuentes <- regmatches(estilos, gregexpr("<link[^>]*>", estilos))[[1]]

escribir(trimws(entre(leer("Charts.html"), "<script>", "</script>")), "www/charts.js")
# app.js: misma lógica que JavaScript.html; solo se reemplaza el arranque para recibir el modelo desde Shiny.
# (Los archivos de Apps Script NO se modifican.)
app_js <- trimws(entre(leer("JavaScript.html"), "<script>", "</script>"))
arranque_gas <- "  } else mostrarError('No hay conexión con Apps Script ni datos de vista previa (window.DASHBOARD_DATA).');"
arranque_shiny <- paste0(
  "  } else if (window.Shiny && Shiny.addCustomMessageHandler) {\n",
  "    Shiny.addCustomMessageHandler('modelo', function (json) {\n",
  "      try { iniciar(typeof json === 'string' ? JSON.parse(json) : json); } catch (e) { mostrarError('No se pudo leer el modelo: ' + e.message); }\n",
  "    });\n",
  "    Shiny.addCustomMessageHandler('error', function (msg) { mostrarError(msg); });\n",
  "  } else mostrarError('No hay conexión con Shiny ni datos de vista previa (window.DASHBOARD_DATA).');")
if (!grepl(arranque_gas, app_js, fixed = TRUE)) stop("No se encontró el bloque de arranque en JavaScript.html")
app_js <- sub(arranque_gas, arranque_shiny, app_js, fixed = TRUE)
escribir(app_js, "www/app.js")

index <- leer("Index.html")
index <- sub("<?!= include('Styles'); ?>",
             paste(c("{{ headContent() }}", links_fuentes, '<link rel="stylesheet" href="styles.css">'), collapse = "\n  "),
             index, fixed = TRUE)
index <- sub("<?!= include('Charts'); ?>", '<script src="charts.js"></script>', index, fixed = TRUE)
index <- sub("<?!= include('JavaScript'); ?>", '<script src="app.js"></script>', index, fixed = TRUE)
index <- sub("<?!= JSON.stringify(logoUrl) ?>", "{{ logo_url }}", index, fixed = TRUE)
index <- sub('<base target="_top">\n  ', "", index, fixed = TRUE)
if (grepl("<?", index, fixed = TRUE)) stop("Quedó un scriptlet de Apps Script sin convertir en Index.html")
escribir(index, "templates/index.html")

ok <- file.copy("../dashboard_globant/BD_Dashboard_Globant.xlsx", "data/BD_Dashboard_Globant.xlsx", overwrite = TRUE)
if (!ok) stop("No se pudo copiar la base de datos")
cat("Sincronizado: www/styles.css, www/charts.js, www/app.js, templates/index.html, data/BD_Dashboard_Globant.xlsx\n")
