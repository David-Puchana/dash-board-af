/**
 * Datos.gs — Lectura de la base de datos en Google Sheets.
 *
 * Hojas esperadas (las crea construir_bd.py dentro de BD_Dashboard_Globant.xlsx):
 *   ER            ID | Cuenta | Tipo | Grupo | Orden | 2018 ... 2025   (miles de COP)
 *   ESF           ID | Cuenta | Tipo | Grupo | Orden | 2018 ... 2025
 *   Deflactor     Año | Inflación IPC dic-dic (%) | ...
 *   Empresa       Clave | Valor
 *   Hitos         Año | Hito | Ámbito
 *   Notas         N° | Tema | Nota | Impacto
 *   Reexpresiones Estado | Año | ID | Cuenta | Valor usado | Fuente usada | Valor alternativo | Fuente alternativa | Diferencia
 *   Fuentes       Año | Procedencia | Estado | Archivo ER | Archivo ESF | Columna
 *   Homogenea     Estado | ID | Cuenta | Año | Anterior homogéneo | Actual homogéneo | Fuente  (variaciones con cambio de base)
 */

const HOJAS = {
  ER: 'ER',
  ESF: 'ESF',
  DEFLACTOR: 'Deflactor',
  EMPRESA: 'Empresa',
  HITOS: 'Hitos',
  NOTAS: 'Notas',
  REEXP: 'Reexpresiones',
  FUENTES: 'Fuentes',
  HOMOGENEA: 'Homogenea'
};

function abrirLibro_() {
  if (CONFIG.SPREADSHEET_ID) return SpreadsheetApp.openById(CONFIG.SPREADSHEET_ID);
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  if (!ss) throw new Error('El script no está vinculado a una hoja. Define CONFIG.SPREADSHEET_ID en Code.gs.');
  return ss;
}

/** Lee una hoja completa → { head: [..], rows: [[..], ..] } sin filas vacías. */
function leerHoja_(ss, nombre, obligatoria) {
  const sh = ss.getSheetByName(nombre);
  if (!sh) {
    if (obligatoria === false) return { head: [], rows: [] };
    throw new Error('No existe la hoja "' + nombre + '" en el libro.');
  }
  const valores = sh.getDataRange().getValues();
  const head = valores.shift().map(function (h) { return String(h).trim(); });
  const rows = valores.filter(function (r) {
    return r.some(function (c) { return c !== '' && c !== null; });
  });
  return { head: head, rows: rows };
}

/** Convierte cualquier celda a número (acepta números, "1.234.567", "$1.234 M", "-"). */
function aNumero_(v) {
  if (typeof v === 'number') return v;
  if (v === null || v === undefined) return 0;
  const s = String(v).trim();
  if (s === '' || s === '-') return 0;
  const negativo = s.indexOf('-') !== -1;
  const limpio = s.replace(/[^\d,]/g, '').replace(',', '.');
  const n = Number(limpio);
  return isNaN(n) ? 0 : (negativo ? -n : n);
}

function col_(head, nombre) {
  const i = head.indexOf(nombre);
  if (i === -1) throw new Error('Falta la columna "' + nombre + '".');
  return i;
}

/** Lee un estado financiero (ER o ESF). */
function leerEstado_(ss, nombre) {
  const t = leerHoja_(ss, nombre);
  const years = [];
  const idxYears = [];
  t.head.forEach(function (h, i) {
    if (/^\d{4}$/.test(h)) { years.push(Number(h)); idxYears.push(i); }
  });
  if (!years.length) throw new Error('La hoja "' + nombre + '" no tiene columnas de años.');
  const iId = col_(t.head, 'ID'), iCta = col_(t.head, 'Cuenta'), iTipo = col_(t.head, 'Tipo'),
        iGrp = col_(t.head, 'Grupo'), iOrd = col_(t.head, 'Orden');
  const cuentas = t.rows.map(function (r) {
    return {
      id: String(r[iId]).trim(),
      cuenta: String(r[iCta]).trim(),
      tipo: String(r[iTipo]).trim(),
      grupo: String(r[iGrp]).trim(),
      orden: Number(r[iOrd]) || 0,
      nom: idxYears.map(function (i) { return aNumero_(r[i]); })
    };
  }).sort(function (a, b) { return a.orden - b.orden; });
  return { years: years, cuentas: cuentas };
}

/** Lee la hoja Deflactor. El índice se recalcula aquí (no depende de las fórmulas de la hoja). */
function leerDeflactor_(ss) {
  const t = leerHoja_(ss, HOJAS.DEFLACTOR);
  const iAnio = col_(t.head, 'Año');
  const iInf = t.head.findIndex(function (h) { return h.indexOf('Inflación') === 0; });
  if (iInf === -1) throw new Error('Falta la columna de inflación en la hoja Deflactor.');
  const filas = t.rows.map(function (r) {
    return { year: Number(r[iAnio]), inflacion: aNumero_(r[iInf]) };
  }).sort(function (a, b) { return a.year - b.year; });
  return filas;
}

function leerClaveValor_(ss, nombre) {
  const t = leerHoja_(ss, nombre, false);
  const out = [];
  t.rows.forEach(function (r) { out.push({ clave: String(r[0]), valor: String(r[1]) }); });
  return out;
}

function leerTablaObjetos_(ss, nombre) {
  const t = leerHoja_(ss, nombre, false);
  return t.rows.map(function (r) {
    const o = {};
    t.head.forEach(function (h, i) { o[h] = r[i]; });
    return o;
  });
}

/** Punto único de lectura. */
function leerBaseDatos_() {
  const ss = abrirLibro_();
  return {
    er: leerEstado_(ss, HOJAS.ER),
    esf: leerEstado_(ss, HOJAS.ESF),
    deflactor: leerDeflactor_(ss),
    empresa: leerClaveValor_(ss, HOJAS.EMPRESA),
    hitos: leerTablaObjetos_(ss, HOJAS.HITOS),
    notas: leerTablaObjetos_(ss, HOJAS.NOTAS),
    reexpresiones: leerTablaObjetos_(ss, HOJAS.REEXP),
    fuentes: leerTablaObjetos_(ss, HOJAS.FUENTES),
    homogenea: leerTablaObjetos_(ss, HOJAS.HOMOGENEA)
  };
}
