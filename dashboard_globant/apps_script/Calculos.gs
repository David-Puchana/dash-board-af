/**
 * Calculos.gs — Modelo analítico del dashboard.
 *
 *  - Deflactor: índice IPC (primer año = 100) y factor para expresar todo en pesos del último año.
 *  - Análisis vertical (metodología del taller): ER sobre ingresos; ESF con AV1 (sobre el subtotal
 *    del grupo) y AV2 (sobre el total de activos / total pasivo + patrimonio).
 *  - Análisis horizontal: variación absoluta y % año contra año, nominal y real; índice real base 100.
 *  - Indicadores de liquidez, cobertura y endeudamiento.
 */

/** Divide devolviendo null cuando el denominador es 0 o no hay dato. */
function div_(a, b) {
  if (b === 0 || b === null || b === undefined || a === null || a === undefined) return null;
  return a / b;
}

/** Variación % solo con base positiva (con base ≤ 0 el % no es interpretable). */
function varPct_(actual, anterior) {
  if (anterior === null || anterior <= 0 || actual === null) return null;
  return (actual - anterior) / anterior;
}

function construirDeflactor_(years, filas) {
  const inf = {};
  filas.forEach(function (f) { inf[f.year] = f.inflacion; });
  const indice = [];
  years.forEach(function (y, i) {
    if (i === 0) { indice.push(100); return; }
    if (inf[y] === undefined) throw new Error('Falta la inflación del año ' + y + ' en la hoja Deflactor.');
    indice.push(indice[i - 1] * (1 + inf[y] / 100));
  });
  const ultimo = indice[indice.length - 1];
  return years.map(function (y, i) {
    return { year: y, inflacion: inf[y] === undefined ? null : inf[y], indice: indice[i], factor: ultimo / indice[i] };
  });
}

/** Agrega a cada cuenta: real, variaciones y el índice real (base primer año = 100). */
function enriquecerCuentas_(cuentas, factores) {
  return cuentas.map(function (c) {
    const real = c.nom.map(function (v, i) { return v * factores[i]; });
    const out = Object.assign({}, c, { real: real });
    ['nom', 'real'].forEach(function (k) {
      const s = out[k];
      out['varAbs_' + k] = s.map(function (v, i) { return i === 0 ? null : v - s[i - 1]; });
      out['varPct_' + k] = s.map(function (v, i) { return i === 0 ? null : varPct_(v, s[i - 1]); });
    });
    out.indiceReal = real[0] > 0 ? real.map(function (v) { return v / real[0] * 100; }) : null;
    return out;
  });
}

function mapa_(cuentas) {
  const m = {};
  cuentas.forEach(function (c) { m[c.id] = c; });
  return m;
}

/** Serie de una cuenta; si no existe devuelve ceros (p. ej. INV). */
function serie_(m, id, n) {
  return m[id] ? m[id].nom : new Array(n).fill(0);
}

/** Cuenta derivada del ER: gastos operacionales = administración + ventas (corrige la clasificación de 2023). */
function agregarDerivadasER_(cuentas, n) {
  const m = mapa_(cuentas);
  const ga = serie_(m, 'GA', n), gv = serie_(m, 'GV', n);
  const gop = {
    id: 'GOP', cuenta: 'Gastos operacionales (adm. + ventas)', tipo: 'derivada', grupo: 'Operacional',
    orden: (m.GA ? m.GA.orden : 6) + 0.5,
    nom: ga.map(function (v, i) { return v + gv[i]; })
  };
  const oi = serie_(m, 'OI', n), og = serie_(m, 'OG', n), ogp = serie_(m, 'OGP', n);
  const otrosNetos = {
    id: 'OON', cuenta: 'Otros ingresos/gastos operacionales netos', tipo: 'derivada', grupo: 'Operacional',
    orden: (m.OG ? m.OG.orden : 7) + 0.5,
    nom: oi.map(function (v, i) { return v - og[i] + ogp[i]; })
  };
  const ifin = serie_(m, 'IF', n), cf = serie_(m, 'CF', n), cob = serie_(m, 'COB', n);
  const finNeto = {
    id: 'FIN', cuenta: 'Resultado financiero neto', tipo: 'derivada', grupo: 'No operacional',
    orden: (m.COB ? m.COB.orden : 12) + 0.5,
    nom: ifin.map(function (v, i) { return v - cf[i] + cob[i]; })
  };
  return cuentas.concat([gop, otrosNetos, finNeto]).sort(function (a, b) { return a.orden - b.orden; });
}

function analisisVertical_(years, er, esf, y1, y2) {
  const i1 = years.indexOf(y1), i2 = years.indexOf(y2);
  if (i1 === -1 || i2 === -1) throw new Error('Los años del análisis vertical (' + y1 + ', ' + y2 + ') no están en la BD.');
  const mER = mapa_(er), mESF = mapa_(esf);
  const ing1 = mER.ING.nom[i1], ing2 = mER.ING.nom[i2];

  const erRows = er.filter(function (c) {
    return c.tipo !== 'derivada' || c.id === 'GOP';
  }).map(function (c) {
    const p1 = div_(c.nom[i1], ing1), p2 = div_(c.nom[i2], ing2);
    return { id: c.id, cuenta: c.cuenta, tipo: c.tipo, grupo: c.grupo, v1: c.nom[i1], v2: c.nom[i2],
             p1: p1, p2: p2, dpp: (p1 === null || p2 === null) ? null : (p2 - p1) };
  });

  // Subtotal de referencia para AV1 según el grupo
  const totalGrupo = {
    'Activo corriente': 'AC', 'Activo no corriente': 'ANC', 'Activo': 'AT',
    'Pasivo corriente': 'PC', 'Pasivo no corriente': 'PNC', 'Pasivo': 'TPP',
    'Patrimonio': 'PAT', 'Control': 'TPP'
  };
  // AV2 según el taller: activo ÷ total activos; pasivo ÷ total pasivos; patrimonio ÷ total patrimonio.
  const esfRows = esf.map(function (c) {
    const esActivo = c.grupo.indexOf('Activo') === 0;
    const baseId = esActivo ? 'AT' : c.grupo === 'Patrimonio' ? 'PAT' : c.grupo === 'Control' ? 'TPP' : 'PT';
    const base = mESF[baseId];
    const ref = mESF[totalGrupo[c.grupo]] || base;
    return {
      id: c.id, cuenta: c.cuenta, tipo: c.tipo, grupo: c.grupo, lado: esActivo ? 'Activo' : 'Pasivo y patrimonio', baseAV2: baseId,
      v1: c.nom[i1], v2: c.nom[i2],
      av1_1: div_(c.nom[i1], ref.nom[i1]), av1_2: div_(c.nom[i2], ref.nom[i2]),
      p1: div_(c.nom[i1], base.nom[i1]), p2: div_(c.nom[i2], base.nom[i2]),
      dpp: div_(c.nom[i2], base.nom[i2]) - div_(c.nom[i1], base.nom[i1])
    };
  });
  return { y1: y1, y2: y2, er: erRows, esf: esfRows };
}

function indicadores_(years, er, esf) {
  const n = years.length;
  const E = mapa_(esf), R = mapa_(er);
  const s = function (m, id) { return serie_(m, id, n); };
  const AT = s(E, 'AT'), PT = s(E, 'PT'), AC = s(E, 'AC'), PC = s(E, 'PC'), INV = s(E, 'INV'),
        EFE = s(E, 'EFE'), PAT = s(E, 'PAT'), CXC = s(E, 'CxC'), CV = s(R, 'CV'), GA = s(R, 'GA'), GV = s(R, 'GV'), ING = s(R, 'ING');
  const map = function (fn) { return years.map(function (_, i) { return fn(i); }); };
  // Gasto operacional diario: (costo de ventas + gastos de administración + gastos de ventas) ÷ 365
  const gastoDiario = map(function (i) { return (CV[i] + GA[i] + GV[i]) / 365; });

  // Definiciones según el documento de requerimientos (captura de indicadores).
  return [
    { id: 'LG', nombre: 'Liquidez general', formula: 'Activo corriente ÷ Pasivo total', unidad: 'x',
      descripcion: 'Pesos de activo corriente por cada peso de deuda total.',
      valores: map(function (i) { return div_(AC[i], PT[i]); }), mejorSiSube: true },
    { id: 'LC', nombre: 'Liquidez corriente', formula: 'Activo corriente ÷ Pasivo corriente', unidad: 'x',
      descripcion: 'Pesos de activo corriente por cada peso de deuda de corto plazo.',
      valores: map(function (i) { return div_(AC[i], PC[i]); }), mejorSiSube: true },
    { id: 'PA', nombre: 'Prueba ácida', formula: '(Activo corriente − Inventarios) ÷ Pasivo corriente', unidad: 'x',
      descripcion: 'Liquidez sin inventarios. La filial no tiene inventarios: coincide con la liquidez corriente.',
      valores: map(function (i) { return div_(AC[i] - INV[i], PC[i]); }), mejorSiSube: true },
    { id: 'CG', nombre: 'Cobertura de gastos', formula: '(Activo corriente − Inventarios) ÷ [(Costo de ventas + Gastos de administración y ventas) ÷ 365]', unidad: 'd',
      descripcion: 'Días de costos y gastos operacionales que se pueden cubrir con el activo corriente sin inventarios.',
      valores: map(function (i) { return div_(AC[i] - INV[i], gastoDiario[i]); }),
      gastoDiario: gastoDiario, mejorSiSube: true },
    { id: 'DI', nombre: 'Disponibilidad inmediata', formula: 'Efectivo y equivalentes ÷ Pasivo corriente', unidad: 'x',
      descripcion: 'Proporción de la deuda de corto plazo que se puede pagar hoy con caja.',
      valores: map(function (i) { return div_(EFE[i], PC[i]); }), mejorSiSube: true },
    { id: 'CT', nombre: 'Capital de trabajo', formula: 'Activo corriente − Pasivo corriente', unidad: '$',
      descripcion: 'Recursos de corto plazo que quedan después de cubrir la deuda de corto plazo (miles de COP).',
      valores: map(function (i) { return AC[i] - PC[i]; }), mejorSiSube: true },
    { id: 'CE', nombre: 'Capacidad de endeudamiento', formula: 'Activo total ÷ Pasivo total', unidad: 'x',
      descripcion: 'Veces que los activos cubren la deuda total; por encima de 1 hay margen para tomar más deuda.',
      valores: map(function (i) { return div_(AT[i], PT[i]); }), mejorSiSube: true },
    // Complementarios (no están en los requerimientos; ayudan a leer la estructura de financiación)
    { id: 'END', nombre: 'Endeudamiento total', formula: 'Pasivo total ÷ Activo total', unidad: '%', complementario: true,
      descripcion: 'Porción del activo financiada por terceros (inverso de la capacidad de endeudamiento).',
      valores: map(function (i) { return div_(PT[i], AT[i]); }), mejorSiSube: false },
    { id: 'ROT', nombre: 'Rotación de cartera', formula: 'Deudores comerciales corrientes ÷ Ingresos × 365', unidad: 'd', complementario: true,
      descripcion: 'Días que tarda en promedio la compañía en cobrar lo que factura.',
      valores: map(function (i) { return div_(CXC[i] * 365, ING[i]); }), mejorSiSube: false }
  ];
}

function margenes_(years, er) {
  const R = mapa_(er);
  const n = years.length;
  const ing = serie_(R, 'ING', n);
  return [
    { id: 'MB', nombre: 'Margen bruto', valores: serie_(R, 'UB', n).map(function (v, i) { return div_(v, ing[i]); }) },
    { id: 'MO', nombre: 'Margen operacional', valores: serie_(R, 'UO', n).map(function (v, i) { return div_(v, ing[i]); }) },
    { id: 'MN', nombre: 'Margen neto', valores: serie_(R, 'UN', n).map(function (v, i) { return div_(v, ing[i]); }) }
  ];
}

/** Diferencia máxima entre activo y pasivo + patrimonio (debe ser cero). */
function cuadre_(years, esf) {
  const E = mapa_(esf);
  let maxDif = 0;
  years.forEach(function (_, i) { maxDif = Math.max(maxDif, Math.abs(E.AT.nom[i] - E.PT.nom[i] - E.PAT.nom[i])); });
  return { maxDiferencia: maxDif, ok: maxDif === 0 };
}

/** Ensambla el modelo completo que consume el cliente. */
function construirModelo_(fuente, y1, y2) {
  const years = fuente.er.years;
  if (fuente.esf.years.join() !== years.join()) throw new Error('Los años de ER y ESF no coinciden.');
  const n = years.length;
  const deflactor = construirDeflactor_(years, fuente.deflactor);
  const factores = deflactor.map(function (d) { return d.factor; });

  const erBase = agregarDerivadasER_(fuente.er.cuentas, n);
  const er = enriquecerCuentas_(erBase, factores);
  const esf = enriquecerCuentas_(fuente.esf.cuentas, factores);

  const indic = indicadores_(years, er, esf);
  indic.forEach(function (ind) {
    if (ind.unidad === '$') ind.valoresReales = ind.valores.map(function (v, i) { return v * factores[i]; });
  });

  return {
    meta: {
      years: years,
      anioBaseReal: years[n - 1],
      unidad: 'Miles de pesos colombianos (COP)',
      generado: Utilities.formatDate(new Date(), 'America/Bogota', 'yyyy-MM-dd HH:mm')
    },
    procedencia: fuente.fuentes,
    homogenea: fuente.homogenea,
    cuadre: cuadre_(years, esf),
    empresa: fuente.empresa,
    hitos: fuente.hitos,
    notas: fuente.notas,
    reexpresiones: fuente.reexpresiones,
    deflactor: deflactor,
    er: er,
    esf: esf,
    vertical: analisisVertical_(years, er, esf, y1, y2),
    indicadores: indic,
    margenes: margenes_(years, er)
  };
}
