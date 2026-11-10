// capturas.js — Toma las imágenes de la guía de lectura desde docs/index.html.
//
// Uso (desde dashboard_python/guia):
//   NODE_PATH=<carpeta con node_modules de puppeteer-core> node capturas.js [ruta de Chrome]
// Requiere puppeteer-core y un Chrome instalado (por defecto /usr/bin/google-chrome).
// Escribe img/<nombre>.png. Cada captura es el componente completo del dashboard ya dibujado.

const path = require('path');
const fs = require('fs');
const puppeteer = require('puppeteer-core');

const PAGINA = 'file://' + path.resolve(__dirname, '../../docs/index.html');
const SALIDA = path.join(__dirname, 'img');
const CHROME = process.argv[2] || '/usr/bin/google-chrome';

// [nombre, selector, contenedor a capturar (closest), alto máximo en px]
const CAPTURAS = [
  ['portada', '#hero-title', 'section, header, .hero', 760],
  ['perfil', '#perfil', null, 1300],
  ['banda', '#band-fig', 'section, .band', 400],
  ['kpis-resumen', '#kpis-resumen', null, 600],
  ['ingresos', '#ch-ingresos', '.card', 700],
  ['margenes', '#ch-margenes', '.card', 700],
  ['tabla-clave', '#tb-h-clave', '.card, .tbl-box', 700],
  ['ritmo', '#ch-ritmo', '.card', 700],
  ['indice', '#ch-indice', '.card', 700],
  ['cuenta', '#ch-cuenta-valor', '.card', 700],
  ['mapa', '#tb-heat', '.card', 1400],
  ['puente', '#ch-puente', '.card', 700],
  ['tabla-completa', '#tb-h-full', '.card, .tbl-box', 620],
  ['reparto', '#ch-reparto', '.card', 700],
  ['activo', '#ch-activo', '.card', 700],
  ['financiacion', '#ch-financiacion', '.card', 700],
  ['v-er', '#tb-v-er', '.card, .tbl-box', 900],
  ['v-esf', '#tb-v-esf', '.card, .tbl-box', 620],
  ['kpis-indicadores', '#kpis-indicadores', null, 1400],
  ['tabla-indicadores', '#tb-ind', '.card, .tbl-box', 900],
  ['liquidez', '#ch-liq', '.card', 700],
  ['capital-trabajo', '#ch-ct', '.card', 700],
  ['capacidad', '#ch-ce', '.card', 700],
  ['cobertura', '#ch-cg', '.card', 700],
  ['diagnostico', '#diagnostico', null, 1600],
];

(async () => {
  fs.mkdirSync(SALIDA, { recursive: true });
  const navegador = await puppeteer.launch({ executablePath: CHROME, headless: true, args: ['--no-sandbox', '--disable-gpu'] });
  try {
    const pagina = await navegador.newPage();
    await pagina.setViewport({ width: 1400, height: 1000, deviceScaleFactor: 1.5 });
    await pagina.emulateMediaFeatures([{ name: 'prefers-reduced-motion', value: 'reduce' }]);
    await pagina.goto(PAGINA, { waitUntil: 'networkidle0' });
    await pagina.waitForSelector('#diag-grid h3', { timeout: 15000 });
    const error = await pagina.$eval('#estado-error', (e) => (e.hidden ? '' : e.textContent));
    if (error) throw new Error('El dashboard muestra un error: ' + error);
    await pagina.evaluate(() => document.fonts.ready);
    // Sin la barra fija superior encima de las capturas.
    await pagina.addStyleTag({ content: '.topnav{position:static!important}' });

    for (const [nombre, selector, contenedor, altoMax] of CAPTURAS) {
      const caja = await pagina.evaluate((sel, cont) => {
        let el = document.querySelector(sel);
        if (!el) return null;
        if (cont) el = el.closest(cont) || el;
        el.scrollIntoView({ block: 'start' });
        const r = el.getBoundingClientRect();
        return { x: r.left + window.scrollX, y: r.top + window.scrollY, width: r.width, height: r.height };
      }, selector, contenedor);
      if (!caja) throw new Error('No se encontró ' + selector);
      await new Promise((r) => setTimeout(r, 150));
      const clip = { x: Math.max(0, caja.x - 8), y: Math.max(0, caja.y - 8), width: caja.width + 16, height: Math.min(caja.height, altoMax) + 16 };
      await pagina.screenshot({ path: path.join(SALIDA, nombre + '.png'), clip, captureBeyondViewport: true });
      console.log(nombre.padEnd(18), Math.round(caja.width) + '×' + Math.round(Math.min(caja.height, altoMax)) + (caja.height > altoMax ? ' (recortada)' : ''));
    }
    // Texto del diagnóstico, para que la guía lo reproduzca (la imagen no se puede buscar ni leer en voz alta).
    const diag = await pagina.$$eval('#diag-grid h3', (hs) => hs.map((h) => ({ titulo: h.textContent, texto: h.nextElementSibling ? h.nextElementSibling.textContent : '' })));
    fs.writeFileSync(path.join(SALIDA, 'diagnostico.json'), JSON.stringify(diag, null, 2));
  } finally {
    await navegador.close();
  }
})().catch((e) => { console.error(e.message); process.exit(1); });
