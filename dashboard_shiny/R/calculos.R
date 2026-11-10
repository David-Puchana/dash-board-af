# calculos.R — Modelo analítico (traducción línea por línea de Calculos.gs).
#
#  - Deflactor: índice IPC (primer año = 100) y factor a pesos del último año.
#  - Vertical: ER sobre ingresos; ESF con AV1 (subtotal del grupo) y AV2 (total).
#  - Horizontal: variación absoluta y % nominal y real; índice real base 100.
#  - Indicadores con las definiciones confirmadas por el usuario.
# Los NA se serializan como null en el JSON (el cliente los trata como "sin dato").

dv <- function(a, b) ifelse(is.na(a) | is.na(b) | b == 0, NA_real_, a / b)
var_pct <- function(actual, anterior) ifelse(is.na(anterior) | anterior <= 0 | is.na(actual), NA_real_, (actual - anterior) / anterior)

construir_deflactor <- function(years, filas) {
  inf <- setNames(filas$inflacion, filas$year)
  indice <- numeric(length(years))
  indice[1] <- 100
  for (i in seq_along(years)[-1]) {
    y <- as.character(years[i])
    if (is.na(inf[y])) stop(sprintf("Falta la inflación del año %s en la hoja Deflactor.", y))
    indice[i] <- indice[i - 1] * (1 + inf[[y]] / 100)
  }
  ultimo <- indice[length(indice)]
  lapply(seq_along(years), function(i) {
    y <- as.character(years[i])
    list(year = years[i], inflacion = if (is.na(inf[y])) NA else unname(inf[[y]]), indice = indice[i], factor = ultimo / indice[i])
  })
}

mapa <- function(cuentas) setNames(cuentas, vapply(cuentas, `[[`, "", "id"))
serie <- function(m, id, n) if (!is.null(m[[id]])) m[[id]]$nom else rep(0, n)

enriquecer_cuentas <- function(cuentas, factores) {
  lapply(cuentas, function(c) {
    c$real <- c$nom * factores
    for (k in c("nom", "real")) {
      s <- c[[k]]
      c[[paste0("varAbs_", k)]] <- c(NA, diff(s))
      c[[paste0("varPct_", k)]] <- c(NA, var_pct(s[-1], s[-length(s)]))
    }
    c$indiceReal <- if (c$real[1] > 0) c$real / c$real[1] * 100 else NULL
    c
  })
}

agregar_derivadas_er <- function(cuentas, n) {
  m <- mapa(cuentas)
  ord <- function(id, def) if (!is.null(m[[id]])) m[[id]]$orden else def
  gop <- list(id = "GOP", cuenta = "Gastos operacionales (adm. + ventas)", tipo = "derivada", grupo = "Operacional",
              orden = ord("GA", 6) + 0.5, nom = serie(m, "GA", n) + serie(m, "GV", n))
  oon <- list(id = "OON", cuenta = "Otros ingresos/gastos operacionales netos", tipo = "derivada", grupo = "Operacional",
              orden = ord("OG", 7) + 0.5, nom = serie(m, "OI", n) - serie(m, "OG", n) + serie(m, "OGP", n))
  fin <- list(id = "FIN", cuenta = "Resultado financiero neto", tipo = "derivada", grupo = "No operacional",
              orden = ord("COB", 12) + 0.5, nom = serie(m, "IF", n) - serie(m, "CF", n) + serie(m, "COB", n))
  todas <- c(cuentas, list(gop, oon, fin))
  todas[order(vapply(todas, `[[`, 0, "orden"))]
}

analisis_vertical <- function(years, er, esf, y1, y2) {
  i1 <- match(y1, years); i2 <- match(y2, years)
  if (is.na(i1) || is.na(i2)) stop(sprintf("Los años del análisis vertical (%s, %s) no están en la BD.", y1, y2))
  mER <- mapa(er); mESF <- mapa(esf)
  ing1 <- mER$ING$nom[i1]; ing2 <- mER$ING$nom[i2]
  er_rows <- lapply(Filter(function(c) c$tipo != "derivada" || c$id == "GOP", er), function(c) {
    p1 <- dv(c$nom[i1], ing1); p2 <- dv(c$nom[i2], ing2)
    list(id = c$id, cuenta = c$cuenta, tipo = c$tipo, grupo = c$grupo, v1 = c$nom[i1], v2 = c$nom[i2],
         p1 = p1, p2 = p2, dpp = if (is.na(p1) || is.na(p2)) NA else p2 - p1)
  })
  total_grupo <- c("Activo corriente" = "AC", "Activo no corriente" = "ANC", "Activo" = "AT",
                   "Pasivo corriente" = "PC", "Pasivo no corriente" = "PNC", "Pasivo" = "TPP",
                   "Patrimonio" = "PAT", "Control" = "TPP")
  # AV2 según el taller: activo ÷ total activos; pasivo ÷ total pasivos; patrimonio ÷ total patrimonio.
  esf_rows <- lapply(esf, function(c) {
    es_activo <- startsWith(c$grupo, "Activo")
    base_id <- if (es_activo) "AT" else if (c$grupo == "Patrimonio") "PAT" else if (c$grupo == "Control") "TPP" else "PT"
    base <- mESF[[base_id]]
    ref_id <- unname(total_grupo[c$grupo])
    ref <- if (!is.na(ref_id) && !is.null(mESF[[ref_id]])) mESF[[ref_id]] else base
    list(id = c$id, cuenta = c$cuenta, tipo = c$tipo, grupo = c$grupo, lado = if (es_activo) "Activo" else "Pasivo y patrimonio", baseAV2 = base_id,
         v1 = c$nom[i1], v2 = c$nom[i2],
         av1_1 = dv(c$nom[i1], ref$nom[i1]), av1_2 = dv(c$nom[i2], ref$nom[i2]),
         p1 = dv(c$nom[i1], base$nom[i1]), p2 = dv(c$nom[i2], base$nom[i2]),
         dpp = dv(c$nom[i2], base$nom[i2]) - dv(c$nom[i1], base$nom[i1]))
  })
  list(y1 = y1, y2 = y2, er = er_rows, esf = esf_rows)
}

indicadores <- function(years, er, esf) {
  n <- length(years)
  E <- mapa(esf); R <- mapa(er)
  AT <- serie(E, "AT", n); PT <- serie(E, "PT", n); AC <- serie(E, "AC", n); PC <- serie(E, "PC", n)
  INV <- serie(E, "INV", n); EFE <- serie(E, "EFE", n); CXC <- serie(E, "CxC", n)
  CV <- serie(R, "CV", n); GA <- serie(R, "GA", n); GV <- serie(R, "GV", n); ING <- serie(R, "ING", n)
  gasto_diario <- (CV + GA + GV) / 365
  list(
    list(id = "LG", nombre = "Liquidez general", formula = "Activo corriente ÷ Pasivo total", unidad = "x",
         descripcion = "Pesos de activo corriente por cada peso de deuda total.", valores = dv(AC, PT), mejorSiSube = TRUE),
    list(id = "LC", nombre = "Liquidez corriente", formula = "Activo corriente ÷ Pasivo corriente", unidad = "x",
         descripcion = "Pesos de activo corriente por cada peso de deuda de corto plazo.", valores = dv(AC, PC), mejorSiSube = TRUE),
    list(id = "PA", nombre = "Prueba ácida", formula = "(Activo corriente − Inventarios) ÷ Pasivo corriente", unidad = "x",
         descripcion = "Liquidez sin inventarios. La filial no tiene inventarios: coincide con la liquidez corriente.", valores = dv(AC - INV, PC), mejorSiSube = TRUE),
    list(id = "CG", nombre = "Cobertura de gastos", formula = "(Activo corriente − Inventarios) ÷ [(Costo de ventas + Gastos de administración y ventas) ÷ 365]", unidad = "d",
         descripcion = "Días de costos y gastos operacionales que se pueden cubrir con el activo corriente sin inventarios.",
         valores = dv(AC - INV, gasto_diario), gastoDiario = gasto_diario, mejorSiSube = TRUE),
    list(id = "DI", nombre = "Disponibilidad inmediata", formula = "Efectivo y equivalentes ÷ Pasivo corriente", unidad = "x",
         descripcion = "Proporción de la deuda de corto plazo que se puede pagar hoy con caja.", valores = dv(EFE, PC), mejorSiSube = TRUE),
    list(id = "CT", nombre = "Capital de trabajo", formula = "Activo corriente − Pasivo corriente", unidad = "$",
         descripcion = "Recursos de corto plazo que quedan después de cubrir la deuda de corto plazo (miles de COP).", valores = AC - PC, mejorSiSube = TRUE),
    list(id = "CE", nombre = "Capacidad de endeudamiento", formula = "Activo total ÷ Pasivo total", unidad = "x",
         descripcion = "Veces que los activos cubren la deuda total; por encima de 1 hay margen para tomar más deuda.", valores = dv(AT, PT), mejorSiSube = TRUE),
    list(id = "END", nombre = "Endeudamiento total", formula = "Pasivo total ÷ Activo total", unidad = "%", complementario = TRUE,
         descripcion = "Porción del activo financiada por terceros (inverso de la capacidad de endeudamiento).", valores = dv(PT, AT), mejorSiSube = FALSE),
    list(id = "ROT", nombre = "Rotación de cartera", formula = "Deudores comerciales corrientes ÷ Ingresos × 365", unidad = "d", complementario = TRUE,
         descripcion = "Días que tarda en promedio la compañía en cobrar lo que factura.", valores = dv(CXC * 365, ING), mejorSiSube = FALSE)
  )
}

margenes <- function(years, er) {
  R <- mapa(er); n <- length(years); ing <- serie(R, "ING", n)
  list(
    list(id = "MB", nombre = "Margen bruto", valores = dv(serie(R, "UB", n), ing)),
    list(id = "MO", nombre = "Margen operacional", valores = dv(serie(R, "UO", n), ing)),
    list(id = "MN", nombre = "Margen neto", valores = dv(serie(R, "UN", n), ing))
  )
}

cuadre <- function(esf) {
  E <- mapa(esf)
  dif <- max(abs(E$AT$nom - E$PT$nom - E$PAT$nom))
  list(maxDiferencia = dif, ok = dif == 0)
}

construir_modelo <- function(fuente, y1, y2) {
  years <- fuente$er$years
  if (!identical(fuente$esf$years, years)) stop("Los años de ER y ESF no coinciden.")
  n <- length(years)
  deflactor <- construir_deflactor(years, fuente$deflactor)
  factores <- vapply(deflactor, `[[`, 0, "factor")
  er <- enriquecer_cuentas(agregar_derivadas_er(fuente$er$cuentas, n), factores)
  esf <- enriquecer_cuentas(fuente$esf$cuentas, factores)
  indic <- lapply(indicadores(years, er, esf), function(ind) {
    if (ind$unidad == "$") ind$valoresReales <- ind$valores * factores
    ind
  })
  list(
    meta = list(years = years, anioBaseReal = years[n], unidad = "Miles de pesos colombianos (COP)",
                generado = format(Sys.time(), "%Y-%m-%d %H:%M", tz = "America/Bogota")),
    procedencia = fuente$fuentes,
    homogenea = fuente$homogenea,
    cuadre = cuadre(esf),
    empresa = fuente$empresa,
    hitos = fuente$hitos,
    notas = fuente$notas,
    reexpresiones = fuente$reexpresiones,
    deflactor = deflactor,
    er = er,
    esf = esf,
    vertical = analisis_vertical(years, er, esf, y1, y2),
    indicadores = indic,
    margenes = margenes(years, er)
  )
}

# JSON para el cliente: NA -> null, sin redondeo, data.frames por filas.
modelo_json <- function(modelo) {
  jsonlite::toJSON(modelo, auto_unbox = TRUE, na = "null", null = "null", digits = NA, dataframe = "rows")
}
