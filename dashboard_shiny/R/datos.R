# datos.R — Lectura de la base de datos (equivalente a Datos.gs).
#
# Lee data/BD_Dashboard_Globant.xlsx (la misma BD que se sube a Google Sheets):
#   ER, ESF        ID | Cuenta | Tipo | Grupo | Orden | 2018 ... 2025   (miles de COP)
#   Deflactor      Año | Inflación IPC dic-dic (%) | ...
#   Empresa        Clave | Valor
#   Hitos, Notas, Reexpresiones, Fuentes   tablas que se pasan tal cual al cliente

leer_hoja <- function(ruta, hoja) {
  if (!hoja %in% readxl::excel_sheets(ruta)) stop(sprintf('No existe la hoja "%s" en la BD.', hoja))
  df <- readxl::read_excel(ruta, sheet = hoja, .name_repair = "minimal")
  df <- as.data.frame(df, check.names = FALSE, stringsAsFactors = FALSE)
  df[rowSums(!is.na(df) & df != "") > 0, , drop = FALSE]
}

a_numero <- function(v) {
  if (is.numeric(v)) return(ifelse(is.na(v), 0, v))
  s <- trimws(as.character(v))
  s[is.na(s) | s == "" | s == "-"] <- "0"
  neg <- grepl("-", s, fixed = TRUE)
  s <- gsub("[^0-9,]", "", s)
  s <- sub(",", ".", s, fixed = TRUE)
  n <- suppressWarnings(as.numeric(s))
  n[is.na(n)] <- 0
  ifelse(neg, -n, n)
}

leer_estado <- function(ruta, hoja) {
  df <- leer_hoja(ruta, hoja)
  cols_anio <- grep("^[0-9]{4}$", names(df), value = TRUE)
  if (!length(cols_anio)) stop(sprintf('La hoja "%s" no tiene columnas de años.', hoja))
  for (k in c("ID", "Cuenta", "Tipo", "Grupo", "Orden"))
    if (!k %in% names(df)) stop(sprintf('Falta la columna "%s" en la hoja "%s".', k, hoja))
  df <- df[order(as.numeric(df$Orden)), , drop = FALSE]
  cuentas <- lapply(seq_len(nrow(df)), function(i) {
    list(
      id = trimws(as.character(df$ID[i])),
      cuenta = trimws(as.character(df$Cuenta[i])),
      tipo = trimws(as.character(df$Tipo[i])),
      grupo = trimws(as.character(df$Grupo[i])),
      orden = as.numeric(df$Orden[i]),
      nom = vapply(cols_anio, function(cn) a_numero(df[[cn]][i]), numeric(1), USE.NAMES = FALSE)
    )
  })
  list(years = as.integer(cols_anio), cuentas = cuentas)
}

leer_deflactor <- function(ruta) {
  df <- leer_hoja(ruta, "Deflactor")
  col_inf <- grep("^Inflación", names(df), value = TRUE)[1]
  if (is.na(col_inf)) stop("Falta la columna de inflación en la hoja Deflactor.")
  data.frame(year = as.integer(df[["Año"]]), inflacion = a_numero(df[[col_inf]]))
}

leer_tabla <- function(ruta, hoja) {
  if (!hoja %in% readxl::excel_sheets(ruta)) return(data.frame())
  leer_hoja(ruta, hoja)
}

leer_base_datos <- function(ruta) {
  emp <- leer_tabla(ruta, "Empresa")
  list(
    er = leer_estado(ruta, "ER"),
    esf = leer_estado(ruta, "ESF"),
    deflactor = leer_deflactor(ruta),
    empresa = lapply(seq_len(nrow(emp)), function(i) list(clave = as.character(emp[i, 1]), valor = as.character(emp[i, 2]))),
    hitos = leer_tabla(ruta, "Hitos"),
    notas = leer_tabla(ruta, "Notas"),
    reexpresiones = leer_tabla(ruta, "Reexpresiones"),
    fuentes = leer_tabla(ruta, "Fuentes"),
    homogenea = leer_tabla(ruta, "Homogenea")
  )
}
