/**
 * Code.gs — Punto de entrada del dashboard (web app + menú en la hoja).
 *
 * Archivos del proyecto:
 *   Code.gs        → doGet, include, menú y API pública para el cliente
 *   Datos.gs       → lectura de las hojas de la base de datos
 *   Calculos.gs    → análisis vertical, horizontal (deflactado) e indicadores
 *   Index.html     → estructura de la página
 *   Styles.html    → estilos (CSS)
 *   Charts.html    → librería de gráficos SVG con efectos hover
 *   JavaScript.html→ lógica de la interfaz (render de secciones)
 */

/** Configuración general. Si el script NO está vinculado a la hoja, pega aquí el ID del Google Sheet. */
const CONFIG = {
  SPREADSHEET_ID: '',          // vacío = usa la hoja a la que está vinculado el script
  ANIO_VERTICAL_1: 2024,       // años del análisis vertical
  ANIO_VERTICAL_2: 2025,
  // URL pública del logotipo OFICIAL (la guía prohíbe dibujarlo). Vacío = se muestra el espacio reservado.
  LOGO_URL: 'https://statics.globant.com/com/public/2025-11/Globant%20%281%29_0.svg',
  TITULO: 'Dossier financiero · Sistemas Colombia S.A.S.'
};

/** Sirve la web app. */
function plantilla_() {
  const t = HtmlService.createTemplateFromFile('Index');
  t.logoUrl = CONFIG.LOGO_URL || '';
  return t;
}

function doGet() {
  return plantilla_()
    .evaluate()
    .setTitle(CONFIG.TITULO)
    .addMetaTag('viewport', 'width=device-width, initial-scale=1')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

/** Inserta el contenido de otro archivo HTML (Styles, Charts, JavaScript). */
function include(nombreArchivo) {
  return HtmlService.createHtmlOutputFromFile(nombreArchivo).getContent();
}

/** Menú dentro de Google Sheets para abrir el dashboard sin publicarlo. */
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Dashboard')
    .addItem('Abrir dashboard', 'abrirDashboard')
    .addToUi();
}

function abrirDashboard() {
  const html = plantilla_()
    .evaluate()
    .setWidth(1400)
    .setHeight(900);
  SpreadsheetApp.getUi().showModelessDialog(html, CONFIG.TITULO);
}

/**
 * API llamada desde el cliente con google.script.run.
 * Devuelve un string JSON (evita las restricciones de tipos de google.script.run).
 */
function getDashboardData() {
  const fuente = leerBaseDatos_();
  const modelo = construirModelo_(fuente, CONFIG.ANIO_VERTICAL_1, CONFIG.ANIO_VERTICAL_2);
  return JSON.stringify(modelo);
}

/** Útil para probar desde el editor: Ejecutar → probarModelo y revisar el registro. */
function probarModelo() {
  const m = JSON.parse(getDashboardData());
  Logger.log('Años: ' + m.meta.years.join(', '));
  m.indicadores.forEach(function (i) {
    Logger.log(i.nombre + ': ' + i.valores.map(function (v) { return v === null ? 'n.a.' : Math.round(v * 100) / 100; }).join(' | '));
  });
}
