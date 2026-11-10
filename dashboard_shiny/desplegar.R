# desplegar.R — Publica la app en shinyapps.io.
#
# 1) Una sola vez: crea la cuenta en https://www.shinyapps.io, entra a Account → Tokens → Show
#    y copia el comando setAccountInfo(...). Ejecútalo en R (NO lo guardes en este archivo):
#      rsconnect::setAccountInfo(name = "TU_CUENTA", token = "…", secret = "…")
# 2) Desde la carpeta dashboard_shiny:  Rscript desplegar.R
#
# Ojo: en el plan gratuito la app es PÚBLICA para cualquiera que tenga la URL.

if (!nrow(rsconnect::accounts())) stop("Primero configura la cuenta con rsconnect::setAccountInfo() (ver paso 1).")

source("sincronizar.R")

rsconnect::deployApp(
  appDir = ".",
  appName = "dossier-sistemas-colombia",
  appTitle = "Dossier financiero · Sistemas Colombia S.A.S.",
  appFiles = c("app.R", "R/datos.R", "R/calculos.R", "templates/index.html",
               "www/styles.css", "www/charts.js", "www/app.js", "data/BD_Dashboard_Globant.xlsx"),
  forceUpdate = TRUE
)
