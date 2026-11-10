/**
 * JavaScript.html — Lógica del dossier (sigue la guía "Sistema de diseño del Dossier Financiero").
 * Pide el modelo a Apps Script (getDashboardData) y dibuja las 7 secciones.
 * Vista previa local sin Apps Script: definir window.DASHBOARD_DATA con el JSON del modelo.
 */
(function () {
  'use strict';

  var D = null;
  var S = { modo: 'real', variacion: 'pct', estado: 'er', periodo: null, periodo2: null, cuenta: 'er:ING', puenteDesde: null, puenteHasta: null };
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return Charts.esc(s); };
  var T = Charts.Tip;

  /* =========================================================
     Formatos (es-CO: miles con punto, decimales con coma). BD en MILES de COP.
     ========================================================= */
  var nf = function (d) { return new Intl.NumberFormat('es-CO', { minimumFractionDigits: d, maximumFractionDigits: d }); };
  var nf0 = nf(0), nf1 = nf(1), nf2 = nf(2), nf3 = nf(3);
  var MINUS = '−';
  var ok = function (v) { return v !== null && v !== undefined && isFinite(v); };
  var sg = function (v) { return v > 0 ? '+' : v < 0 ? MINUS : ''; };
  var F = {
    millones: function (v) { return ok(v) ? (v < 0 ? MINUS : '') + nf0.format(Math.abs(v) / 1000) : 'n.a.'; },        // millones de COP
    miles: function (v) { return ok(v) ? (v < 0 ? MINUS : '') + nf0.format(Math.abs(v)) : 'n.a.'; },                  // tal cual la fuente
    corto: function (v) {
      if (!ok(v)) return 'n.a.';
      var p = Math.abs(v) * 1000, s = v < 0 ? MINUS + '$' : '$';
      if (p >= 1e12) return s + nf2.format(p / 1e12) + ' billones';
      if (p >= 1e9) return s + nf1.format(p / 1e9) + ' mil millones';
      return s + nf1.format(p / 1e6) + ' millones';
    },
    partes: function (v) {                                              // valor grande + unidad para tarjetas
      var p = Math.abs(v) * 1000;
      if (p >= 1e12) return { n: (v < 0 ? MINUS : '') + nf2.format(p / 1e12), u: 'billones' };
      return { n: (v < 0 ? MINUS : '') + nf0.format(p / 1e6), u: 'millones' };
    },
    mm: function (v) { return ok(v) ? (v < 0 ? MINUS : '') + nf0.format(Math.abs(v) / 1e6) : ''; },     // eje: miles de millones
    mm1: function (v) { return ok(v) ? (v < 0 ? MINUS : '') + nf1.format(Math.abs(v) / 1e6) : ''; },
    pct: function (v, d) { return ok(v) ? (d === 0 ? nf0 : d === 2 ? nf2 : nf1).format(v * 100) + '%' : 'n.a.'; },
    pctS: function (v, d) { return ok(v) ? sg(v) + (d === 0 ? nf0 : nf1).format(Math.abs(v) * 100) + '%' : 'n.a.'; },
    pp: function (v) { return ok(v) ? sg(v) + nf2.format(Math.abs(v) * 100) + ' pp' : 'n.a.'; },
    x: function (v, d) { return ok(v) ? nf(d === undefined ? 2 : d).format(v) : 'n.a.'; },
    dias: function (v) { return ok(v) ? nf0.format(v) : 'n.a.'; }
  };

  /* =========================================================
     Acceso a datos
     ========================================================= */
  function ys() { return D.meta.years; }
  function L() { return ys().length - 1; }
  function yi(y) { return ys().indexOf(Number(y)); }
  function cta(e, id) { var a = e === 'er' ? D.er : D.esf; for (var i = 0; i < a.length; i++) if (a[i].id === id) return a[i]; return null; }
  function ser(c, modo) { return (modo || S.modo) === 'real' ? c.real : c.nom; }
  function vp(a, b) { return (!ok(a) || a <= 0 || !ok(b)) ? null : (b - a) / a; }
  function ind(id) { for (var i = 0; i < D.indicadores.length; i++) if (D.indicadores[i].id === id) return D.indicadores[i]; return null; }
  function mrg(id) { for (var i = 0; i < D.margenes.length; i++) if (D.margenes[i].id === id) return D.margenes[i].valores; return null; }
  function lblModo() { return S.modo === 'real' ? 'pesos constantes de ' + D.meta.anioBaseReal : 'pesos nominales'; }
  function idxMin(a) { var k = -1; a.forEach(function (v, i) { if (ok(v) && (k < 0 || v < a[k])) k = i; }); return k; }
  function idxMax(a) { var k = -1; a.forEach(function (v, i) { if (ok(v) && (k < 0 || v > a[k])) k = i; }); return k; }
  var COSTOS = ['CV', 'GA', 'GV', 'GOP', 'OG', 'CF', 'IMP'];             // subir es malo
  function tasaEf(i) { return cta('er', 'IMP').nom[i] / cta('er', 'UAI').nom[i]; }

  /* Variaciones con cambio de base contable (hoja Homogenea). Cuentas derivadas = combinación de sus componentes. */
  var HOMO = {};
  var DERIV = { GOP: [['GA', 1], ['GV', 1]], OON: [['OI', 1], ['OG', -1], ['OGP', 1]], FIN: [['IF', 1], ['CF', -1], ['COB', 1]] };
  function initHomo() {
    HOMO = {};
    (D.homogenea || []).forEach(function (r) { HOMO[(r['Estado'] === 'ER' ? 'er' : 'esf') + ':' + r['ID'] + ':' + r['Año']] = r; });
  }
  function vacio(v) { return v === null || v === undefined || v === ''; }
  /** Par (t−1, t) en base homogénea, nominal. flag = la variación mostrada mezcla bases. */
  function par(e, id, k) {
    if (e === 'er' && DERIV[id]) {
      var out = { flag: false, a: 0, b: 0, fuente: 'reporte ' + ys()[k] };
      DERIV[id].forEach(function (t) {
        var q = par(e, t[0], k);
        out.flag = out.flag || q.flag;
        if (out.a === null || q.a === null) { out.a = out.b = null; return; }
        out.a += t[1] * q.a; out.b += t[1] * q.b;
      });
      return out;
    }
    var c = cta(e, id); if (!c) return { flag: false, a: 0, b: 0 };
    var h = HOMO[e + ':' + id + ':' + ys()[k]];
    if (!h) return { flag: false, a: c.nom[k - 1], b: c.nom[k] };
    if (vacio(h['Anterior homogéneo']) || vacio(h['Actual homogéneo'])) return { flag: true, a: null, b: null, fuente: h['Fuente'] };
    return { flag: true, a: Number(h['Anterior homogéneo']), b: Number(h['Actual homogéneo']), fuente: h['Fuente'] };
  }
  function cambioBase(e, id, k) { return k > 0 && par(e, id, k).flag; }
  function notaBase(e, id, k) {
    if (!cambioBase(e, id, k)) return '';
    var q = par(e, id, k), y = ys();
    if (q.a === null) return '† Cambio de base contable: ' + y[k] + ' está re-expresado y ' + y[k - 1] + ' no. No hay una versión homogénea confiable (' + q.fuente + ').';
    var p = vp(q.a, q.b);
    if (S.modo === 'real' && ok(p)) p = (1 + p) / (1 + D.deflactor[k].inflacion / 100) - 1;
    return '† Cambio de base contable: ' + y[k] + ' está re-expresado y ' + y[k - 1] + ' no. En base homogénea (' + q.fuente.toLowerCase() + ') la variación fue ' + F.pctS(p) + '.';
  }

  /** Clase semántica de una variación: pos (mejora), neg (deterioro) o vacía. */
  function semCls(id, diff, estado) {
    if (!ok(diff) || diff === 0 || estado === 'esf') return '';
    var mejora = COSTOS.indexOf(id) !== -1 ? diff < 0 : diff > 0;
    return mejora ? 'pos' : 'neg';
  }
  function deltaChip(diff, mejorSiSube, txt) {
    if (!ok(diff) || Math.abs(diff) < 1e-12) return '<span class="delta flat">' + esc(txt) + '</span>';
    return '<span class="delta ' + ((mejorSiSube ? diff > 0 : diff < 0) ? 'pos' : 'neg') + '">' + esc(txt) + '</span>';
  }
  function cellNum(txt, title) { return '<span class="cell-num"' + (title ? ' title="' + esc(title) + '"' : '') + '>' + esc(txt) + '</span>'; }
  function setAll(sel, txt) { document.querySelectorAll(sel).forEach(function (n) { n.textContent = txt; }); }

  /* =========================================================
     Portada
     ========================================================= */
  function renderPortada() {
    var y = ys(), ING = cta('er', 'ING'), mb = mrg('MB');
    var mult = ING.nom[L()] / ING.nom[0];
    $('hero-periodo').textContent = y[0] + ' – ' + y[L()];
    var cola = idxMin(mb) === L() ? 'el margen bruto tocó su mínimo' : 'el margen bruto quedó en ' + F.pct(mb[L()]);
    $('hero-title').innerHTML = 'Los ingresos nominales se multiplicaron por ' + nf1.format(mult) + ' y <span class="hl">' + cola + '</span>';
    var cuadre = D.cuadre;
    var meta = [
      ['Cortes', y[0] + ' – ' + y[L()], ''],
      ['Fuente', 'Supersociedades', ''],
      ['Unidad', 'Miles de COP', ''],
      ['Archivos', '14 XLSX · 14 capturas', ''],
      ['Cuadre', cuadre.ok ? 'Diferencia cero' : 'Descuadre de ' + F.miles(cuadre.maxDiferencia), cuadre.ok ? 'pos' : 'neg']
    ];
    $('meta-strip').innerHTML = meta.map(function (m) {
      return '<div><div class="k">' + esc(m[0]) + '</div><div class="v ' + m[2] + '">' + esc(m[1]) + '</div></div>';
    }).join('');
    if (window.LOGO_URL) { $('logo-slot').innerHTML = '<img src="' + esc(window.LOGO_URL) + '" alt="Globant">'; $('logo-slot').classList.add('con-logo'); }
  }

  /* =========================================================
     01 Perfil
     ========================================================= */
  function renderPerfil() {
    var kv = {}; D.empresa.forEach(function (e) { kv[e.clave] = e.valor; });
    var p = [];
    if (kv['Grupo']) p.push('<strong>El grupo.</strong> ' + esc(kv['Grupo']) + ' Salió a bolsa en el NYSE en julio de 2014 bajo el símbolo GLOB.');
    p.push('<strong>La sociedad.</strong> ' + esc(kv['Razón social'] || 'Sistemas Colombia S.A.S.') + ', NIT ' + esc(kv['NIT'] || '') + ', con domicilio en ' +
      esc(kv['Ubicación'] || '') + ' y actividad ' + esc(kv['Actividad económica (CIIU)'] || '') + '. Reporta bajo ' + esc(kv['Marco contable'] || 'NIIF') + '.');
    if (kv['Rol de Colombia']) p.push('<strong>El peso de Colombia.</strong> ' + esc(kv['Rol de Colombia']));
    if (kv['Cifras del grupo']) p.push('<strong>El contexto.</strong> ' + esc(kv['Cifras del grupo']));
    if (kv['Servicios']) p.push('<strong>Qué vende.</strong> ' + esc(kv['Servicios']) + ' Clientes: ' + esc(kv['Clientes'] || '') );
    if (kv['Misión']) p.push('<strong>Misión y visión.</strong> ' + esc(kv['Misión']) + ' ' + esc(kv['Visión'] || ''));
    $('perfil-prosa').innerHTML = p.map(function (t) { return '<p>' + t + '</p>'; }).join('');
    $('nota-entidad').innerHTML = '<strong>No confundir las entidades.</strong> ' + esc(kv['Relación con el grupo'] || '');
    var keys = ['Razón social', 'NIT', 'Actividad económica (CIIU)', 'Ubicación', 'Supervisión', 'Marco contable', 'Unidad de las cifras'];
    $('facts-empresa').innerHTML = keys.filter(function (k) { return kv[k]; }).map(function (k) {
      return '<dt>' + esc(k.replace(' (CIIU)', '')) + '</dt><dd>' + esc(kv[k]) + '</dd>';
    }).join('');
    var ING = cta('er', 'ING');
    $('hitos').innerHTML = D.hitos.map(function (h) {
      var y = Number(h['Año']), i = yi(y), amb = String(h['Ámbito'] || '');
      var rev = i >= 0 ? ' <strong>Ingresos de la filial: ' + esc(F.corto(ING.nom[i])) + '.</strong>' : '';
      return '<div class="prov-row"><span class="prov-y">' + y + '</span><span class="prov-t">' + esc(h['Hito']) + rev + '</span><span class="chip ' +
        (/filial/i.test(amb) ? 'ok' : 'info') + '">' + esc(amb) + '</span></div>';
    }).join('');
    // Banda negra
    var mult = ING.nom[L()] / ING.nom[0], multR = ING.real[L()] / ING.real[0], cagr = Math.pow(ING.nom[L()] / ING.nom[0], 1 / L()) - 1;
    $('band-fig').textContent = nf1.format(mult) + '×';
    $('band-cap').textContent = 'crecieron los ingresos entre ' + ys()[0] + ' y ' + ys()[L()];
    $('band-text').innerHTML = 'De ' + esc(F.corto(ING.nom[0])) + ' a ' + esc(F.corto(ING.nom[L()])) + ': un crecimiento compuesto del ' + F.pct(cagr) +
      ' anual. Descontada la inflación, el multiplicador baja a ' + nf1.format(multR) + '×. Esa es la escala sobre la que se leen las cifras que siguen.';
  }

  /* =========================================================
     02 Resumen
     ========================================================= */
  function kpiCompact(o) {
    var d = document.createElement('div');
    d.className = 'kpi compact' + (o.dark ? ' dark' : '');
    d.innerHTML = '<div class="kpi-name">' + esc(o.name) + '</div>' +
      '<div class="kpi-value-row"><span class="kpi-value" title="' + esc(o.title || '') + '">' + esc(o.value) + '</span><span class="kpi-unit">' + esc(o.unit || '') + '</span></div>' +
      '<div class="kpi-foot">' + o.delta + '<span>' + esc(o.note || '') + '</span></div>' +
      '<div class="kpi-spark"></div>';
    setTimeout(function () { Charts.sparkline(d.querySelector('.kpi-spark'), o.spark, o.sparkColor); }, 0);
    return d;
  }

  function renderResumen() {
    var y = ys(), l = L(), P = l - 1;
    var ING = cta('er', 'ING'), UN = cta('er', 'UN'), UO = cta('er', 'UO'), mb = mrg('MB'), END = ind('END');
    $('titulo-resumen').textContent = 'Dónde está la compañía en ' + y[l];
    $('lead-resumen').textContent = 'Cierre del ejercicio ' + y[l] + ' contra ' + y[P] + ', con la trayectoria completa de ' + y.length + ' años debajo de cada cifra. Cifras nominales.';
    var box = $('kpis-resumen'); box.innerHTML = '';
    var vIng = vp(ING.nom[P], ING.nom[l]);
    var primeraCaida = vIng < 0 && ING.varPct_nom.slice(1, l).every(function (v) { return v >= 0; });
    var pi = F.partes(ING.nom[l]), pu = F.partes(UN.nom[l]);
    box.appendChild(kpiCompact({ name: 'Ingresos ordinarios', value: pi.n, unit: pi.u, title: F.miles(ING.nom[l]) + ' miles',
      delta: deltaChip(vIng, true, F.pctS(vIng)), note: primeraCaida ? 'primera caída' : 'vs. ' + y[P], spark: ING.nom, sparkColor: 'var(--s1)' }));
    var IMPc = cta('er', 'IMP'), FINc = cta('er', 'FIN');
    var motores = [['impuestos', IMPc.nom[P] - IMPc.nom[l]], ['resultado financiero', FINc.nom[l] - FINc.nom[P]], ['operación', UO.nom[l] - UO.nom[P]]]
      .filter(function (m) { return m[1] > 0; }).sort(function (a, b) { return b[1] - a[1]; }).map(function (m) { return m[0]; });
    var notaUN = UN.nom[l] > UN.nom[P] && motores.length && motores.indexOf('operación') === -1 ? 'por ' + motores.join(' y ') : 'vs. ' + y[P];
    box.appendChild(kpiCompact({ name: 'Utilidad neta', value: pu.n, unit: pu.u, title: F.miles(UN.nom[l]) + ' miles',
      delta: deltaChip(UN.nom[l] - UN.nom[P], true, F.pctS(vp(UN.nom[P], UN.nom[l]))), note: notaUN, spark: UN.nom, sparkColor: 'var(--s1)' }));
    box.appendChild(kpiCompact({ name: 'Margen bruto', value: nf2.format(mb[l] * 100), unit: '%',
      delta: deltaChip(mb[l] - mb[P], true, F.pp(mb[l] - mb[P])), note: idxMin(mb) === l ? 'mínimo de la serie' : 'vs. ' + y[P], spark: mb, sparkColor: mb[l] < mb[P] ? 'var(--s3)' : 'var(--s1)' }));
    box.appendChild(kpiCompact({ name: 'Endeudamiento', value: nf2.format(END.valores[l] * 100), unit: '%',
      delta: deltaChip(END.valores[l] - END.valores[P], false, F.pp(END.valores[l] - END.valores[P])), note: idxMin(END.valores) === l ? 'mejor dato' : 'vs. ' + y[P],
      spark: END.valores, sparkColor: END.valores[l] < END.valores[P] ? 'var(--s1)' : 'var(--s3)' }));

    var s2 = [
      { name: 'Pesos constantes de ' + D.meta.anioBaseReal, color: 'var(--s1)', values: ING.real },
      { name: 'Pesos nominales', color: 'var(--s2)', values: ING.nom }
    ];
    var f1 = Charts.lines($('ch-ingresos'), {
      categories: y, series: s2, fmtAxis: F.mm, zeroBased: true, height: 260,
      tooltip: function (i) {
        return T.title('Ingresos ' + y[i]) + T.row('Constantes', F.corto(ING.real[i]), 'var(--s1)', true) + T.row('Nominales', F.corto(ING.nom[i]), 'var(--s2)', true) +
          T.note('Inflación del año: ' + (i ? F.pct(D.deflactor[i].inflacion / 100, 2) : 'base') + ' · var. real ' + F.pctS(ING.varPct_real[i]));
      }
    });
    Charts.legend($('leg-ingresos'), s2.map(function (s, k) { return { name: s.name, color: s.color, line: true, key: k }; }), f1.highlightSeries);
    var sm = D.margenes.map(function (m, k) { return { name: m.nombre, color: 'var(--s' + (k + 1) + ')', values: m.valores }; });
    var f2 = Charts.lines($('ch-margenes'), {
      categories: y, series: sm, fmtAxis: function (v) { return F.pct(v, 0); }, zeroBased: true, height: 260,
      tooltip: function (i) { return T.title('Márgenes ' + y[i]) + sm.map(function (s) { return T.row(s.name, F.pct(s.values[i], 2), s.color, true); }).join(''); }
    });
    Charts.legend($('leg-margenes'), sm.map(function (s, k) { return { name: s.name, color: s.color, line: true, key: k }; }), f2.highlightSeries);
  }

  /* =========================================================
     03 Horizontal
     ========================================================= */
  var CLAVE_ER = ['ING', 'CV', 'UB', 'GOP', 'UO', 'IMP', 'UN'];
  var SUBT = ['UB', 'UO', 'UAI', 'UN', 'AC', 'ANC', 'AT', 'PC', 'PNC', 'PT', 'PAT', 'TPP'];
  var CUENTAS = {
    er: ['ING', 'CV', 'UB', 'GOP', 'UO', 'IF', 'CF', 'UAI', 'IMP', 'UN'],
    esf: ['EFE', 'CxC', 'AC', 'PPE', 'INT', 'ANC', 'AT', 'PBE', 'CxP', 'PC', 'PNC', 'PT', 'PAT']
  };

  function periodos() {
    var y = ys(), out = [];
    for (var i = y.length - 1; i > 0; i--) out.push({ v: y[i - 1] + '-' + y[i], t: y[i - 1] + ' → ' + y[i] });
    out.push({ v: y[0] + '-' + y[y.length - 1], t: y[0] + ' → ' + y[y.length - 1] + ' (acumulado)' });
    return out;
  }
  function initHorizontal() {
    if ($('sel-cuenta').options.length) return;
    var opts = periodos().map(function (p) { return '<option value="' + p.v + '">' + p.t + '</option>'; }).join('');
    $('sel-h-periodo').innerHTML = opts; $('sel-h-periodo-2').innerHTML = opts;
    S.periodo = S.periodo2 = periodos()[0].v;
    $('sel-h-periodo').addEventListener('change', function () { S.periodo = this.value; renderTablaClave(); });
    $('sel-h-periodo-2').addEventListener('change', function () { S.periodo2 = this.value; renderTablaFull(); });
    $('sel-cuenta').innerHTML = ['er', 'esf'].map(function (e) {
      return '<optgroup label="' + (e === 'er' ? 'Estado de resultados' : 'Balance') + '">' + CUENTAS[e].filter(function (id) { return cta(e, id); }).map(function (id) {
        return '<option value="' + e + ':' + id + '">' + esc(cta(e, id).cuenta) + '</option>';
      }).join('') + '</optgroup>';
    }).join('');
    $('sel-cuenta').value = S.cuenta;
    $('sel-cuenta').addEventListener('change', function () { S.cuenta = this.value; renderCuenta(); });
    var y = ys(), yo = y.map(function (a) { return '<option value="' + a + '">' + a + '</option>'; }).join('');
    $('sel-puente-desde').innerHTML = yo; $('sel-puente-hasta').innerHTML = yo;
    S.puenteDesde = y[y.length - 2]; S.puenteHasta = y[y.length - 1];
    $('sel-puente-desde').value = S.puenteDesde; $('sel-puente-hasta').value = S.puenteHasta;
    ['sel-puente-desde', 'sel-puente-hasta'].forEach(function (id) {
      $(id).addEventListener('change', function () { S.puenteDesde = Number($('sel-puente-desde').value); S.puenteHasta = Number($('sel-puente-hasta').value); renderPuente(); });
    });
  }

  function filaVar(c, a, b, estado) {
    var s = ser(c), d = s[b] - s[a], p = vp(s[a], s[b]);
    var cb = b === a + 1 && cambioBase(estado, c.id, b);
    var val = (S.variacion === 'pct' ? F.pctS(p) : sg(d) + F.millones(Math.abs(d))) + (cb ? ' †' : '');
    var cls = semCls(c.id, d, estado);
    var tr = SUBT.indexOf(c.id) !== -1 ? (c.tipo === 'total' && estado === 'esf' ? 'tot' : 'sub') : (c.tipo === 'derivada' ? 'der' : '');
    return '<tr class="' + tr + '"><td>' + esc(c.cuenta) + '</td><td>' + cellNum(F.millones(s[a]), F.corto(s[a])) + '</td><td>' + cellNum(F.millones(s[b]), F.corto(s[b])) +
      '</td><td class="' + cls + '">' + cellNum(val, cb ? notaBase(estado, c.id, b) : (S.variacion === 'pct' ? (sg(d) + F.corto(Math.abs(d))) : F.pctS(p))) + '</td></tr>';
  }
  function renderTablaClave() {
    var p = S.periodo.split('-'), a = yi(p[0]), b = yi(p[1]);
    $('tb-h-clave').innerHTML = '<thead><tr><th>Cuenta</th><th>' + p[0] + '</th><th>' + p[1] + '</th><th>' + (S.variacion === 'pct' ? 'Variación %' : 'Variación absoluta') + '</th></tr></thead><tbody>' +
      CLAVE_ER.map(function (id) { return filaVar(cta('er', id), a, b, 'er'); }).join('') + '</tbody>';
    $('foot-h-clave').textContent = 'Cifras en millones de pesos (' + lblModo() + '). Verde = mejora, rojo = deterioro. † = cambio de base contable entre los dos años (pasa el cursor para ver la variación homogénea). Las filas en fondo claro son subtotales.';
  }
  function renderTablaFull() {
    var p = S.periodo2.split('-'), a = yi(p[0]), b = yi(p[1]), e = S.estado;
    var arr = (e === 'er' ? D.er : D.esf).filter(function (c) { var s = ser(c); return s[a] !== 0 || s[b] !== 0; });
    $('tb-h-full').innerHTML = '<thead><tr><th>Cuenta</th><th>' + p[0] + '</th><th>' + p[1] + '</th><th>' + (S.variacion === 'pct' ? 'Variación %' : 'Variación absoluta') + '</th></tr></thead><tbody>' +
      arr.map(function (c) { return filaVar(c, a, b, e); }).join('') + '</tbody>';
  }

  function renderHorizontal() {
    initHorizontal();
    var y = ys(), l = L(), ING = cta('er', 'ING'), CV = cta('er', 'CV'), UB = cta('er', 'UB'), UO = cta('er', 'UO'), UN = cta('er', 'UN'), IMP = cta('er', 'IMP');
    var infAc = D.deflactor[l].indice / D.deflactor[0].indice - 1;
    $('lead-horizontal').innerHTML = 'Variación de cada cuenta contra el ejercicio anterior. Mide el ritmo: qué creció, qué se frenó y en qué año cambió la pendiente. ' +
      'Para comparar años distintos, las cifras se llevan a pesos de ' + D.meta.anioBaseReal + ' con el IPC (inflación acumulada ' + y[0] + '–' + y[l] + ': ' + F.pct(infAc) + ').';
    setAll('.y0', y[0]);
    renderTablaClave();

    // Ritmo de crecimiento de los ingresos
    var v = (S.modo === 'real' ? ING.varPct_real : ING.varPct_nom).slice(1), cats = y.slice(1);
    var primeraNeg = v.findIndex(function (x) { return x < 0; });
    Charts.hbars($('ch-ritmo'), {
      categories: cats.map(String), series: [{ name: 'Variación', values: v }], labelWidth: 46, rowHeight: 30, barHeight: 18, hideAxis: true, rightPad: 150,
      alwaysLabels: true, labelsRight: true, strongIdx: cats.length - 1,
      colorFn: function (x) { return x < 0 ? 'var(--s3)' : 'var(--s1)'; },
      fmtAxis: function (x) { return F.pct(x, 0); }, fmtLabel: function (x) { return nf1.format(x * 100); },
      labelFn: function (x, i) { return sg(x) + nf1.format(Math.abs(x) * 100) + (x < 0 && i === primeraNeg ? ' · primera contracción' : ''); },
      tooltip: function (i) {
        var k = i + 1;
        return T.title('Ingresos ' + y[k - 1] + ' → ' + y[k]) + T.row('Variación', F.pctS(v[i])) + T.row(y[k - 1], F.corto(ser(ING)[k - 1])) + T.row(y[k], F.corto(ser(ING)[k])) +
          T.note(lblModo() + (cambioBase('er', 'ING', k) ? '<br>' + esc(notaBase('er', 'ING', k)) : ''));
      }
    });

    // Prosa (cifras nominales, como se reportan)
    var cagr = Math.pow(ING.nom[l] / ING.nom[0], 1 / l) - 1;
    var vn = ING.varPct_nom, tramo = vn.slice(1).map(function (x) { return F.pctS(x); });
    var peorUO = idxMin(UO.varPct_nom.slice(1)) + 1;
    $('prosa-horizontal').innerHTML = [
      '<strong>' + (vn[l] < 0 ? 'La curva se invirtió en ' + y[l] + '.' : vn[l] < vn[l - 1] ? 'La curva se frenó en ' + y[l] + '.' : 'La curva se aceleró en ' + y[l] + '.') + '</strong> Los ingresos se multiplicaron por ' + nf1.format(ING.nom[l] / ING.nom[0]) +
        ' entre ' + y[0] + ' y ' + y[l] + ' (crecimiento compuesto del ' + F.pct(cagr) + ' anual), pero el reparto es desigual: ' + tramo.join(', ') + '. En pesos constantes, ' + y[l] + ' cerró en ' + F.pctS(ING.varPct_real[l]) + '.',
      '<strong>' + (CV.varPct_nom[l] > vn[l] ? 'El costo creció más rápido que la venta.' : 'La venta creció más que el costo.') + '</strong> En ' + y[l] + ' los ingresos variaron ' + F.pctS(vn[l]) + ' mientras el costo de ventas varió ' + F.pctS(CV.varPct_nom[l]) +
        '. El resultado es una ganancia bruta ' + F.pctS(UB.varPct_nom[l]) + ' y una utilidad operacional ' + F.pctS(UO.varPct_nom[l]) + (peorUO === l ? ': la peor variación operativa de la serie.' : '.'),
      '<strong>La utilidad neta ' + (UN.varPct_nom[l] >= 0 ? 'subió' : 'bajó') + ' ' + F.pct(Math.abs(UN.varPct_nom[l])) + (UO.varPct_nom[l] < 0 && UN.varPct_nom[l] > 0 ? ', pero no por la operación' : '') + '.</strong> ' +
        'El impuesto de renta pasó de ' + F.miles(IMP.nom[l - 1]) + ' a ' + F.miles(IMP.nom[l]) + ' (' + F.pctS(IMP.varPct_nom[l]) + ') y la tasa efectiva de ' + F.pct(tasaEf(l - 1)) + ' a ' + F.pct(tasaEf(l)) + '. ' +
        'Del cambio de ' + F.corto(UN.nom[l] - UN.nom[l - 1]) + ' en la utilidad neta, el impuesto aporta ' + F.corto(IMP.nom[l - 1] - IMP.nom[l]) + ', el resultado financiero ' +
        F.corto(cta('er', 'FIN').nom[l] - cta('er', 'FIN').nom[l - 1]) + ' y la operación ' + F.corto(UO.nom[l] - UO.nom[l - 1]) + '.'
    ].map(function (t) { return '<p>' + t + '</p>'; }).join('');

    // Índice base 100
    var ids = [['er', 'ING'], ['er', 'CV'], ['er', 'GOP'], ['er', 'UN'], ['esf', 'AT']];
    var si = ids.map(function (p, k) {
      var c = cta(p[0], p[1]), s = ser(c);
      return { name: c.cuenta, color: 'var(--s' + (k + 1) + ')', raw: s, values: s.map(function (x) { return s[0] > 0 ? x / s[0] * 100 : null; }) };
    });
    var fi = Charts.lines($('ch-indice'), {
      categories: y, series: si, refLine: 100, height: 330, fmtAxis: function (x) { return nf0.format(x); },
      tooltip: function (i) {
        return T.title(y[i] + ' · índice ' + y[0] + ' = 100') + si.slice().sort(function (a, b) { return (b.values[i] || 0) - (a.values[i] || 0); }).map(function (s) {
          return T.row(s.name, nf0.format(s.values[i]) + ' · ' + F.corto(s.raw[i]), s.color, true);
        }).join('') + T.note(lblModo());
      }
    });
    Charts.legend($('leg-indice'), si.map(function (s, k) { return { name: s.name, color: s.color, line: true, key: k }; }), fi.highlightSeries);

    renderCuenta(); renderHeat(); renderPuente(); renderTablaFull(); renderPrompt();
  }

  function renderCuenta() {
    var p = S.cuenta.split(':'), c = cta(p[0], p[1]), y = ys(), s = ser(c), l = L();
    var vpc = S.modo === 'real' ? c.varPct_real : c.varPct_nom, vab = S.modo === 'real' ? c.varAbs_real : c.varAbs_nom;
    $('titulo-cuenta').textContent = 'Evolución · ' + c.cuenta;
    var mx = idxMax(s);
    Charts.bars($('ch-cuenta-valor'), {
      categories: y, series: [{ name: c.cuenta, values: s }], fmtAxis: F.mm, fmtLabel: F.mm1, height: 260, unit: 'Miles de millones',
      colorFn: function (v, i) { return v < 0 ? 'var(--s3)' : i === l ? 'var(--ink)' : 'var(--s1)'; }, labelIdx: [mx, l], strongIdx: l,
      tooltip: function (i) {
        return T.title(c.cuenta + ' · ' + y[i]) + T.row('Nominal', F.corto(c.nom[i])) + T.row('Pesos de ' + D.meta.anioBaseReal, F.corto(c.real[i])) +
          (i ? T.note('Variación: <b>' + F.pctS(vpc[i]) + '</b> (' + F.corto(vab[i]) + ')') : '');
      }
    });
    Charts.bars($('ch-cuenta-var'), {
      categories: y.slice(1), series: [{ name: 'Variación', values: vpc.slice(1) }], colorBySign: true, alwaysLabels: true, height: 260, unit: 'Variación %',
      fmtAxis: function (v) { return F.pct(v, 0); }, fmtLabel: function (v) { return F.pctS(v, 0); },
      tooltip: function (i) {
        var k = i + 1;
        return T.title(c.cuenta + ' · ' + y[k - 1] + ' → ' + y[k]) + T.row('Variación %', F.pctS(vpc[k])) + T.row('Variación $', F.corto(vab[k])) +
          (vpc[k] === null ? T.note('Sin % porque el año base es cero o negativo.') : '') + (cambioBase(p[0], p[1], k) ? T.note(esc(notaBase(p[0], p[1], k))) : '');
      }
    });
  }

  function renderHeat() {
    var y = ys(), CAP = 0.5;
    var head = '<thead><tr><th>Cuenta</th>' + y.slice(1).map(function (a, i) { return '<th>' + y[i] + '→' + String(a).slice(2) + '</th>'; }).join('') + '</tr></thead>';
    var body = '';
    ['er', 'esf'].forEach(function (e) {
      body += '<tr><td class="grp" colspan="' + y.length + '">' + (e === 'er' ? 'Estado de resultados' : 'Balance') + '</td></tr>';
      CUENTAS[e].forEach(function (id) {
        var c = cta(e, id); if (!c) return;
        var v = S.modo === 'real' ? c.varPct_real : c.varPct_nom;
        body += '<tr><td class="lbl">' + esc(c.cuenta) + '</td>' + y.slice(1).map(function (a, j) {
          var k = j + 1, col = Charts.divergingColor(v[k], CAP), cb = cambioBase(e, id, k);
          var data = ' data-e="' + e + '" data-id="' + id + '" data-k="' + k + '"';
          return col ? '<td class="cell' + (cb ? ' cb' : '') + '"' + data + ' style="background:' + col.bg + ';color:' + col.ink + '">' + F.pctS(v[k], 0) + (cb ? '†' : '') + '</td>'
                     : '<td class="cell na' + (cb ? ' cb' : '') + '"' + data + '>n.a.' + (cb ? '†' : '') + '</td>';
        }).join('') + '</tr>';
      });
    });
    var tb = $('tb-heat'); tb.innerHTML = head + '<tbody>' + body + '</tbody>';
    tb.querySelectorAll('td.cell').forEach(function (td) {
      td.addEventListener('mouseenter', function (ev) {
        var c = cta(td.dataset.e, td.dataset.id), k = Number(td.dataset.k), s = ser(c), v = S.modo === 'real' ? c.varPct_real : c.varPct_nom;
        T.show(T.title(c.cuenta + ' · ' + y[k - 1] + ' → ' + y[k]) + T.row(String(y[k - 1]), F.corto(s[k - 1])) + T.row(String(y[k]), F.corto(s[k])) +
          T.row('Variación $', F.corto(s[k] - s[k - 1])) + T.row('Variación %', F.pctS(v[k])) + T.note(lblModo() + (cambioBase(td.dataset.e, td.dataset.id, k) ? '<br>' + esc(notaBase(td.dataset.e, td.dataset.id, k)) : '')), ev);
      });
      td.addEventListener('mousemove', function (ev) { T.move(ev); });
      td.addEventListener('mouseleave', function () { T.hide(); });
      td.addEventListener('click', function () {
        S.cuenta = td.dataset.e + ':' + td.dataset.id; $('sel-cuenta').value = S.cuenta; renderCuenta();
        $('sel-cuenta').scrollIntoView({ behavior: 'smooth', block: 'center' });
      });
    });
    $('heat-key').innerHTML = '<span>' + MINUS + (CAP * 100) + '% o menos</span><span class="ramp" style="background:linear-gradient(90deg,var(--s3),var(--bone),var(--s2))"></span><span>+' + (CAP * 100) + '% o más</span><span>· † cambio de base contable (la variación mezcla dos clasificaciones)</span>';
  }

  function renderPuente() {
    var a = yi(S.puenteDesde), b = yi(S.puenteHasta), y = ys();
    if (a < 0 || b < 0 || a === b) { $('ch-puente').innerHTML = '<p class="card-sub">Elige dos años distintos.</p>'; return; }
    var v = function (id, i) { return ser(cta('er', id))[i]; }, d = function (id) { return v(id, b) - v(id, a); };
    var st = [
      { label: 'Utilidad neta ' + y[a], value: v('UN', a), kind: 'total', note: 'Punto de partida.' },
      { label: 'Ingresos', value: d('ING'), note: 'Más ingresos suman.' },
      { label: 'Costo de ventas', value: -d('CV'), note: 'Un costo mayor resta.' },
      { label: 'Gastos operacionales', value: -d('GOP'), note: 'Administración + ventas.' },
      { label: 'Otros operacionales', value: d('OON'), note: 'Otros ingresos − otros gastos.' },
      { label: 'Resultado financiero', value: d('FIN'), note: 'Ingresos − costos financieros ± coberturas.' },
      { label: 'Impuesto de renta', value: -d('IMP'), note: 'Un impuesto mayor resta.' },
      { label: 'Utilidad neta ' + y[b], value: v('UN', b), kind: 'total', note: 'Punto de llegada.' }
    ];
    Charts.waterfall($('ch-puente'), {
      steps: st, fmtAxis: F.mm, fmtLabel: F.mm1, height: 340, unit: 'Miles de millones',
      tooltip: function (i) {
        var ids = [null, 'ING', 'CV', 'GOP', 'OON', 'FIN', 'IMP', null][i];
        var nb = ids && b === a + 1 ? notaBase('er', ids, b) : '';
        return T.title(st[i].label) + T.row(st[i].kind === 'total' ? 'Valor' : 'Impacto', F.corto(st[i].value)) + T.note(esc(st[i].note) + ' · ' + lblModo() + (nb ? '<br>' + esc(nb) : ''));
      }
    });
  }

  function renderPrompt() {
    var y = ys(), l = L(), ING = cta('er', 'ING'), AT = cta('esf', 'AT'), c = [];
    ['er', 'esf'].forEach(function (e) {
      CUENTAS[e].forEach(function (id) {
        var x = cta(e, id); if (!x || x.tipo !== 'detalle' && x.tipo !== 'derivada') return;
        for (var k = 1; k <= l; k++) {
          var p = x.varPct_real[k], a = x.varAbs_real[k], base = e === 'er' ? ING.real[k] : AT.real[k];
          if (!ok(p) || Math.abs(p) < 0.2 || Math.abs(a) < 0.03 * base) continue;
          c.push({ x: x, k: k, p: p, peso: Math.abs(a) / base });
        }
      });
    });
    c.sort(function (a, b) { return b.peso - a.peso; });
    var lista = c.slice(0, 10).map(function (o, n) {
      return (n + 1) + '. ' + o.x.cuenta + ', ' + y[o.k - 1] + '→' + y[o.k] + ': ' + F.pctS(o.p) + ' real (' + F.corto(o.x.nom[o.k - 1]) + ' → ' + F.corto(o.x.nom[o.k]) + ' nominal).';
    }).join('\n');
    $('txt-prompt').value =
'Actúa como analista financiero senior especializado en empresas de servicios de tecnología en Colombia.\n\n' +
'EMPRESA: Sistemas Colombia S.A.S. (NIT 900.218.578), sociedad del grupo Globant en Colombia. No confundir con Globant S.A. ni con Globant Colombia S.A.S. Actividad CIIU J6201, Bogotá.\n' +
'DATOS: estados financieros NIIF plenas individuales depositados en la Superintendencia de Sociedades (SIIS), ' + y[0] + '–' + y[l] + ', en miles de COP. Las cifras de 2019, 2021, 2022, 2023 y el patrimonio de 2024 son las re-expresadas por la compañía en el reporte del año siguiente; las variaciones contra el año anterior de esos años mezclan dos clasificaciones contables. ' +
'Las variaciones reales están deflactadas con el IPC de diciembre del DANE a pesos de ' + D.meta.anioBaseReal + '.\n\n' +
'CONTEXTO: el grupo Globant facturó US$2.415,7 M en 2024 (+15,3%) y US$2.454,9 M en 2025 (+1,6%) y en 2025 ejecutó un plan de optimización con reducción de plantilla. ' +
'En la filial, los ingresos ' + y[l] + ' variaron ' + F.pctS(ING.varPct_real[l]) + ' real y la tasa efectiva de impuesto pasó de ' + F.pct(tasaEf(l - 1)) + ' a ' + F.pct(tasaEf(l)) + '.\n\n' +
'VARIACIONES A EXPLICAR (las más grandes en términos reales):\n' + lista + '\n\n' +
'TAREA. Para cada variación:\n' +
'a) Explica las causas más probables (operativas, cambiarias, fiscales, contables o del grupo).\n' +
'b) Separa lo CONFIRMADO por una fuente de lo que es HIPÓTESIS. No inventes cifras.\n' +
'c) Indica si puede deberse a una reclasificación o re-expresión (p. ej. NIIF 16, compensación de impuestos diferidos, cambios entre corriente y no corriente) y no a un cambio económico real.\n' +
'd) Cita las fuentes con enlace: Form 20-F y 6-K de Globant (sec.gov), investors.globant.com, notas a los estados financieros en el SIIS, DANE, Banco de la República y prensa económica colombiana.\n\n' +
'FORMATO: tabla con columnas Variación | Causa probable | Evidencia y fuente | Certeza (confirmado / probable / especulativo), y al final 3 preguntas abiertas para la gerencia.';
  }

  /* =========================================================
     04 Vertical
     ========================================================= */
  function renderVertical() {
    var V = D.vertical, y1 = V.y1, y2 = V.y2, i1 = yi(y1), i2 = yi(y2);
    setAll('.vy1', y1); setAll('.vy2', y2);
    var r = {}; V.er.forEach(function (x) { r[x.id] = x; });
    var ING = cta('er', 'ING'), CV = cta('er', 'CV'), UO = cta('er', 'UO');
    var rep = function (i) {
      var ing = ING.nom[i];
      return { cv: CV.nom[i] / ing, uo: UO.nom[i] / ing, gas: (ing - CV.nom[i] - UO.nom[i]) / ing };
    };
    var a = rep(i1), b = rep(i2);
    var SEG = [['cv', 'Costo de ventas', 'var(--s3)'], ['gas', 'Gastos operacionales netos', 'var(--s5)'], ['uo', 'Utilidad operacional', 'var(--s1)']];
    Charts.hstack($('ch-reparto'), {
      rows: [
        { label: String(y1), right: 'costo ' + F.pct(a.cv, 2), segments: SEG.map(function (s) { return { name: s[1], value: a[s[0]], color: s[2] }; }) },
        { label: String(y2), right: 'costo ' + F.pct(b.cv, 2), rightClass: b.cv > a.cv ? 'neg' : '', segments: SEG.map(function (s) { return { name: s[1], value: b[s[0]], color: s[2] }; }) }
      ],
      legend: SEG.map(function (s) { return { name: s[1], color: s[2] }; }),
      tooltip: function (name) {
        var k = SEG.filter(function (s) { return s[1] === name; })[0][0];
        return T.title(name) + T.row(String(y1), F.pct(a[k], 2)) + T.row(String(y2), F.pct(b[k], 2)) + T.note('Cambio: <b>' + F.pp(b[k] - a[k]) + '</b>' +
          (k === 'gas' ? '<br>Ingresos − costo de ventas − utilidad operacional (incluye otros ingresos y gastos).' : ''));
      }
    });

    // Composición del activo: las 4 cuentas más pesadas del último año + resto
    var AT = cta('esf', 'AT');
    var det = D.esf.filter(function (c) { return c.tipo === 'detalle' && c.grupo.indexOf('Activo') === 0 && (c.nom[i1] || c.nom[i2]); });
    var top = det.slice().sort(function (p, q) { return q.nom[i2] - p.nom[i2]; }).slice(0, 4);
    var nombre = function (c) { return c.id === 'CxC' ? 'Deudores comerciales' : c.cuenta; };
    var col = ['var(--s1)', 'var(--s2)', 'var(--s3)', 'var(--s4)'];
    var share = function (c, i) { return c.nom[i] / AT.nom[i]; };
    var resto = function (i) { return 1 - top.reduce(function (s, c) { return s + share(c, i); }, 0); };
    var segs = function (i) {
      return top.map(function (c, k) { return { name: nombre(c), value: share(c, i), color: col[k] }; })
        .concat([{ name: 'Otras ' + (det.length - top.length) + ' cuentas', value: resto(i), color: '#9A9DA6' }]);
    };
    Charts.hstack($('ch-activo'), {
      rows: [{ label: String(y1), right: 'total ' + F.corto(AT.nom[i1]), segments: segs(i1) }, { label: String(y2), right: 'total ' + F.corto(AT.nom[i2]), segments: segs(i2) }],
      legendList: true,
      legend: segs(i2).map(function (s, k) { var s1 = segs(i1)[k]; return { name: s.name, color: s.color, values: [F.pct(s1.value, 2), F.pct(s.value, 2)] }; }),
      tooltip: function (name) {
        var p1 = segs(i1).filter(function (s) { return s.name === name; })[0], p2 = segs(i2).filter(function (s) { return s.name === name; })[0];
        return T.title(name) + T.row(String(y1), F.pct(p1.value, 2)) + T.row(String(y2), F.pct(p2.value, 2)) + T.note('Cambio: <b>' + F.pp(p2.value - p1.value) + '</b>');
      }
    });

    // Financiación
    var fin = function (i) {
      var t = cta('esf', 'TPP').nom[i];
      return [{ name: 'Pasivo corriente', value: cta('esf', 'PC').nom[i] / t, color: 'var(--s3)' }, { name: 'Pasivo no corriente', value: cta('esf', 'PNC').nom[i] / t, color: 'var(--s5)' },
              { name: 'Patrimonio', value: cta('esf', 'PAT').nom[i] / t, color: 'var(--s1)' }];
    };
    Charts.hstack($('ch-financiacion'), {
      rows: [{ label: String(y1), right: 'patrimonio ' + F.pct(fin(i1)[2].value, 2), segments: fin(i1) }, { label: String(y2), right: 'patrimonio ' + F.pct(fin(i2)[2].value, 2), segments: fin(i2) }],
      legend: fin(i2).map(function (s) { return { name: s.name, color: s.color }; }),
      tooltip: function (name) {
        var p1 = fin(i1).filter(function (s) { return s.name === name; })[0], p2 = fin(i2).filter(function (s) { return s.name === name; })[0];
        return T.title(name) + T.row(String(y1), F.pct(p1.value, 2)) + T.row(String(y2), F.pct(p2.value, 2)) + T.note('Cambio: <b>' + F.pp(p2.value - p1.value) + '</b>');
      }
    });

    // Prosa
    var mb = mrg('MB'), CxC = cta('esf', 'CxC'), AC = cta('esf', 'AC'), PPE = cta('esf', 'PPE'), OAF = cta('esf', 'OAFNC'), k22 = yi(2022);
    $('prosa-vertical-1').innerHTML = '<p><strong>El costo de ventas ' + (b.cv > a.cv ? 'se comió ' + nf1.format((b.cv - a.cv) * 100) + ' puntos de margen' : 'cedió peso') + '.</strong> Pasó del ' +
      F.pct(a.cv, 2) + ' de los ingresos en ' + y1 + ' al ' + F.pct(b.cv, 2) + ' en ' + y2 + ', y el margen bruto quedó en ' + F.pct(mb[i2], 2) +
      (idxMin(mb) === i2 ? ', el mínimo de la serie' : '') + '. En servicios profesionales ese costo suele ser, sobre todo, nómina técnica (no verificado en las notas).</p>';
    $('prosa-vertical-2').innerHTML = '<p><strong>El balance está concentrado en cartera.</strong> Los deudores comerciales son el ' + F.pct(share(CxC, i2)) + ' del activo total y el ' +
      F.pct(CxC.nom[i2] / AC.nom[i2]) + ' del activo corriente. La propiedad, planta y equipo pesa ' + F.pct(share(PPE, i2)) + ' del activo en ' + y2 + ' (' + F.pct(share(PPE, i1)) + ' en ' + y1 + ').' +
      (k22 >= 0 && OAF && OAF.nom[k22] > 0 ? ' Parte de su caída histórica es contable: en la re-expresión de 2022 se trasladaron ' + F.corto(OAF.nom[k22]) + ' a otros activos financieros.' : '') + '</p>';

    // Tablas
    var pc = function (p) { return ok(p) ? '<span class="pbar">' + esc(F.pct(p, 2)) + '<i style="width:' + Math.min(100, Math.abs(p) * 100).toFixed(1) + '%"></i></span>' : ''; };
    $('tb-v-er').innerHTML = '<thead><tr><th>Cuenta</th><th>' + y2 + '</th><th>AV ' + y2 + '</th><th>' + y1 + '</th><th>AV ' + y1 + '</th><th>Δ pp</th><th>Var. %</th></tr></thead><tbody>' +
      V.er.filter(function (x) { return x.v1 !== 0 || x.v2 !== 0; }).map(function (x) {
        var tr = SUBT.indexOf(x.id) !== -1 || x.id === 'ING' ? 'sub' : x.tipo === 'derivada' ? 'der' : '';
        return '<tr class="' + tr + '"><td>' + esc(x.cuenta) + '</td><td>' + cellNum(F.millones(x.v2), F.corto(x.v2)) + '</td><td>' + pc(x.p2) + '</td><td>' +
          cellNum(F.millones(x.v1), F.corto(x.v1)) + '</td><td>' + pc(x.p1) + '</td><td class="' + semCls(x.id, x.dpp, 'er') + '">' + cellNum(F.pp(x.dpp)) +
          '</td><td class="' + semCls(x.id, x.v2 - x.v1, 'er') + '">' + cellNum(F.pctS(vp(x.v1, x.v2))) + '</td></tr>';
      }).join('') + '</tbody>';
    var g = '', body = '';
    V.esf.forEach(function (x) {
      if (x.v1 === 0 && x.v2 === 0) return;
      if (x.tipo === 'detalle' && x.grupo !== g) { g = x.grupo; body += '<tr class="grp"><td colspan="8">' + esc(g) + '</td></tr>'; }
      var tr = x.tipo === 'total' ? 'tot' : x.tipo === 'subtotal' ? 'sub' : '';
      var a1 = function (v) { return x.tipo === 'detalle' ? pc(v) : ''; };
      body += '<tr class="' + tr + '"><td>' + esc(x.cuenta) + '</td><td>' + cellNum(F.millones(x.v2), F.corto(x.v2)) + '</td><td>' + a1(x.av1_2) + '</td><td>' + pc(x.p2) + '</td><td>' +
        cellNum(F.millones(x.v1), F.corto(x.v1)) + '</td><td>' + a1(x.av1_1) + '</td><td>' + pc(x.p1) + '</td><td>' + cellNum(F.pp(x.dpp)) + '</td></tr>';
    });
    $('tb-v-esf').innerHTML = '<thead><tr><th>Cuenta</th><th>' + y2 + '</th><th>AV1</th><th>AV2</th><th>' + y1 + '</th><th>AV1</th><th>AV2</th><th>Δ pp (AV2)</th></tr></thead><tbody>' + body + '</tbody>';
  }

  /* =========================================================
     05 Indicadores
     ========================================================= */
  function fmtInd(i, v) {
    if (!ok(v)) return { n: 'n.a.', u: '' };
    if (i.unidad === '%') return { n: nf2.format(v * 100), u: '%' };
    if (i.unidad === '$') return { n: F.millones(v), u: 'millones' };
    if (i.unidad === 'd') return { n: nf0.format(v), u: 'días' };
    return { n: nf3.format(v), u: 'veces' };
  }
  function lectura(i, v, vals, l) {
    var CxC = cta('esf', 'CxC'), AC = cta('esf', 'AC'), y = ys();
    var mx = idxMax(vals), mn = idxMin(vals), extremo = (i.mejorSiSube ? mx : mn) === l ? 'Mejor dato de la serie. ' : (i.mejorSiSube ? mn : mx) === l ? 'Peor dato de la serie. ' : '';
    switch (i.id) {
      case 'LG': return extremo + 'Por cada $1 de deuda total hay $' + nf2.format(v) + ' de activo corriente' + (v < 1 ? ': no alcanza.' : '.');
      case 'LC': return extremo + 'Se sostiene sobre deudores (' + F.pct(CxC.nom[l] / AC.nom[l], 0) + ' del activo corriente), no sobre caja.';
      case 'PA': return 'Igual a la liquidez corriente: la compañía no tiene inventarios.';
      case 'CG': return extremo + 'El activo corriente sin inventarios cubre ' + nf0.format(v) + ' días de costos y gastos operacionales.';
      case 'DI': return 'El efectivo cubre el ' + F.pct(v) + ' del pasivo corriente. En ' + y.length + ' años nunca superó ' + nf2.format(vals[mx]) + '.';
      case 'CT': return extremo + (v >= 0 ? 'Sobran ' : 'Faltan ') + F.corto(Math.abs(v)) + ' de recursos de corto plazo (' + lblModo() + ').';
      case 'CE': return extremo + 'Los activos cubren ' + nf2.format(v) + ' veces la deuda total' + (v > 1 ? '.' : ': sin margen.');
      case 'END': return extremo + 'Del ' + F.pct(vals[mx]) + ' en ' + y[mx] + ' al ' + F.pct(v) + '.';
      case 'ROT': return extremo + 'La compañía tarda ' + nf0.format(v) + ' días en cobrar lo que factura.';
      default: return '';
    }
  }
  function renderIndicadores() {
    var y = ys(), l = L(), P = l - 1;
    $('nota-coinciden').innerHTML = '<strong>Dos indicadores coinciden.</strong> La compañía reporta inventarios en cero los ' + y.length +
      ' años. Como la prueba ácida resta inventarios y la liquidez corriente no, ambas fórmulas producen exactamente el mismo número: no son dos lecturas distintas de la liquidez.';
    var box = $('kpis-indicadores'); box.innerHTML = ''; box.classList.add('three');
    D.indicadores.forEach(function (i) {
      var vals = i.unidad === '$' && S.modo === 'real' ? i.valoresReales : i.valores, v = vals[l], d = v - vals[P];
      var f = fmtInd(i, v);
      var dt = i.unidad === '%' ? F.pp(d) : i.unidad === '$' ? F.pctS(vp(vals[P], v)) : i.unidad === 'd' ? sg(d) + nf0.format(Math.abs(d)) + ' días' : sg(d) + nf3.format(Math.abs(d));
      var dark = i.id === 'DI';
      var div = document.createElement('div');
      div.className = 'kpi' + (dark ? ' dark' : '');
      div.innerHTML = '<div class="kpi-name">' + esc(i.nombre) + (i.complementario ? ' <span class="chip info" style="margin-left:6px">complementario</span>' : '') + '</div>' +
        '<div class="kpi-formula">' + esc(i.formula.toLowerCase()) + '</div>' +
        '<div class="kpi-value-row"><span class="kpi-value" title="' + esc(i.unidad === '$' ? F.miles(v) + ' miles' : '') + '">' + esc(f.n) + '</span><span class="kpi-unit">' + esc(f.u) + '</span>' +
        (dark ? '<span class="chip crit">dato crítico</span>' : deltaChip(d, i.mejorSiSube, dt)) + '</div>' +
        '<p class="kpi-text">' + esc(lectura(i, v, vals, l)) + '</p><div class="kpi-spark"></div>';
      box.appendChild(div);
      var bueno = i.mejorSiSube ? d >= 0 : d <= 0;
      setTimeout(function () { Charts.sparkline(div.querySelector('.kpi-spark'), vals, dark ? 'var(--lime)' : bueno ? 'var(--s1)' : 'var(--s3)'); }, 0);
    });

    // Tabla: peor momento en rojo, último año en negrita
    $('foot-ind').textContent = 'Capital de trabajo en millones de ' + lblModo() + ' (cambia con el selector Pesos nominales / Pesos de ' + D.meta.anioBaseReal + ' del análisis horizontal); el resto en veces, días o porcentaje, que no dependen de la inflación. En rojo, el peor momento de cada serie.';
    $('tb-ind').innerHTML = '<thead><tr><th>Indicador</th>' + y.map(function (a, k) { return '<th class="' + (k === l ? 'last' : '') + '">' + a + '</th>'; }).join('') + '</tr></thead><tbody>' +
      D.indicadores.map(function (i) {
        var vals = i.unidad === '$' && S.modo === 'real' ? i.valoresReales : i.valores;
        var peor = i.mejorSiSube ? idxMin(vals) : idxMax(vals);
        var u = i.unidad === '%' ? '(%)' : i.unidad === '$' ? '(millones)' : i.unidad === 'd' ? '(días)' : '(veces)';
        return '<tr><td>' + esc(i.nombre) + ' <span class="unit">' + u + '</span></td>' + vals.map(function (v, k) {
          var t = i.unidad === '%' ? nf2.format(v * 100) : i.unidad === '$' ? F.millones(v) : i.unidad === 'd' ? nf0.format(v) : nf3.format(v);
          return '<td class="' + (k === peor ? 'worst ' : '') + (k === l ? 'last' : '') + '">' + cellNum(t) + '</td>';
        }).join('') + '</tr>';
      }).join('') + '</tbody>';

    // Gráficos
    var liq = ['LG', 'LC', 'DI'].map(function (id, k) { var x = ind(id); return { name: x.nombre, color: 'var(--s' + (k + 1) + ')', values: x.valores }; });
    var fl = Charts.lines($('ch-liq'), {
      categories: y, series: liq, refLine: 1, zeroBased: true, height: 260, fmtAxis: function (v) { return nf1.format(v); },
      tooltip: function (k) { return T.title('Liquidez ' + y[k]) + liq.map(function (s) { return T.row(s.name, nf3.format(s.values[k]), s.color, true); }).join('') + T.note('Línea punteada: 1 vez.'); }
    });
    Charts.legend($('leg-liq'), liq.map(function (s, k) { return { name: s.name, color: s.color, line: true, key: k }; }), fl.highlightSeries);
    var hl = function (vals) { var mx = idxMax(vals); return function (v, k) { return v < 0 ? 'var(--s3)' : k === l ? 'var(--ink)' : 'var(--s1)'; }; };
    var CT = ind('CT'), ct = S.modo === 'real' ? CT.valoresReales : CT.valores;
    Charts.bars($('ch-ct'), {
      categories: y, series: [{ name: 'Capital de trabajo', values: ct }], colorFn: hl(ct), labelIdx: [idxMax(ct), idxMin(ct), l], strongIdx: l, height: 260,
      fmtAxis: F.mm, fmtLabel: F.mm1,
      tooltip: function (k) {
        var AC = ser(cta('esf', 'AC')), PC = ser(cta('esf', 'PC'));
        return T.title('Capital de trabajo ' + y[k]) + T.row('Activo corriente', F.corto(AC[k])) + T.row('Pasivo corriente', F.corto(PC[k])) + T.row('Capital de trabajo', F.corto(ct[k])) + T.note(lblModo());
      }
    });
    var CE = ind('CE');
    Charts.bars($('ch-ce'), {
      categories: y, series: [{ name: 'Capacidad', values: CE.valores }], colorFn: hl(CE.valores), labelIdx: [idxMax(CE.valores), l], strongIdx: l, height: 260,
      fmtAxis: function (v) { return nf1.format(v); }, fmtLabel: function (v) { return nf2.format(v); },
      tooltip: function (k) {
        return T.title('Capacidad de endeudamiento ' + y[k]) + T.row('Activo total', F.corto(cta('esf', 'AT').nom[k])) + T.row('Pasivo total', F.corto(cta('esf', 'PT').nom[k])) +
          T.row('Activo ÷ pasivo', nf3.format(CE.valores[k]) + ' veces') + T.row('Endeudamiento', F.pct(ind('END').valores[k]));
      }
    });
    var CG = ind('CG');
    Charts.bars($('ch-cg'), {
      categories: y, series: [{ name: 'Cobertura', values: CG.valores }], colorFn: hl(CG.valores), labelIdx: [idxMax(CG.valores), l], strongIdx: l, height: 260,
      fmtAxis: function (v) { return nf0.format(v); }, fmtLabel: function (v) { return nf0.format(v) + ' d'; },
      tooltip: function (k) {
        var AC = cta('esf', 'AC').nom[k], INV = cta('esf', 'INV') ? cta('esf', 'INV').nom[k] : 0;
        return T.title('Cobertura de gastos ' + y[k]) + T.row('Activo corriente − inventarios', F.corto(AC - INV)) + T.row('Gasto operacional diario', F.corto(CG.gastoDiario[k])) +
          T.row('Cobertura', nf1.format(CG.valores[k]) + ' días');
      }
    });
  }

  /* =========================================================
     06 Diagnóstico
     ========================================================= */
  function renderDiagnostico() {
    var y = ys(), l = L(), END = ind('END').valores, CE = ind('CE').valores, CT = ind('CT').valores, DI = ind('DI').valores, LC = ind('LC').valores;
    var mb = mrg('MB'), mo = mrg('MO'), CxC = cta('esf', 'CxC'), AC = cta('esf', 'AC');
    var kE = idxMax(END), kC = idxMin(CE), kT = idxMin(CT);
    var tasas = y.map(function (_, i) { return tasaEf(i); }), prom = tasas.slice(0, l).reduce(function (a, b) { return a + b; }, 0) / l;
    var UAI = cta('er', 'UAI').nom[l], UN = cta('er', 'UN').nom[l];
    var P = l - 1, solvMejora = END[l] < END[P] && CE[l] > CE[P], opPeor = mb[l] < mb[P] && mo[l] < mo[P], cartera = CxC.nom[l] / AC.nom[l];
    var kTmin = idxMin(tasas), kTmax = idxMax(tasas);
    var kMoMin = idxMin(mo), kMoMax = idxMax(mo), ROT = ind('ROT').valores;
    // TRM de cierre (Banco de la República). Referencia externa citada, no entra en ningún cálculo del modelo.
    var TRM_CIERRE = { 2023: 3822.05, 2024: 4409.15, 2025: 3757.08 };
    var trmVar = (TRM_CIERRE[y[l]] && TRM_CIERRE[y[P]]) ? vp(TRM_CIERRE[y[P]], TRM_CIERRE[y[l]]) : null;
    var kT35 = -1;  // año (desde 2022, tarifa general del 35 %) con la tasa efectiva más alta por encima de ella
    y.forEach(function (a, i) { if (a >= 2022 && ok(tasas[i]) && tasas[i] > 0.35 && (kT35 < 0 || tasas[i] > tasas[kT35])) kT35 = i; });
    var bloques = [
      [solvMejora ? 'La solvencia mejoró' : 'La solvencia no mejoró este año', 'El endeudamiento pasó de ' + F.pct(END[P]) + ' en ' + y[P] + ' a ' + F.pct(END[l]) + ' en ' + y[l] +
        ' (máximo de la serie: ' + F.pct(END[kE]) + ' en ' + y[kE] + ') y la capacidad de endeudamiento de ' + nf2.format(CE[P]) + ' a ' + nf2.format(CE[l]) + ' veces. El capital de trabajo pasó de ' +
        F.corto(CT[P]) + ' a ' + F.corto(CT[l]) + ' (nominal; mínimo de la serie: ' + F.corto(CT[kT]) + ' en ' + y[kT] + ').'],
      [opPeor ? 'Los márgenes se estrecharon, dentro de su franja' : 'Los márgenes se sostienen', 'El margen bruto está en ' + F.pct(mb[l], 2) + (idxMin(mb) === l ? ' (mínimo de la serie)' : '') + ' y el operacional en ' + F.pct(mo[l], 2) +
        ', frente a ' + F.pct(mb[P], 2) + ' y ' + F.pct(mo[P], 2) + ' en ' + y[P] + '. En los ' + y.length + ' años de la serie el margen operacional solo se ha movido entre ' + F.pct(mo[kMoMin], 1) + ' (' + y[kMoMin] + ') y ' +
        F.pct(mo[kMoMax], 1) + ' (' + y[kMoMax] + '). Una franja tan estrecha es propia de una filial que presta servicios al grupo con una remuneración fijada sobre sus costos. Es una hipótesis: la proporción de ingresos con vinculadas y el método de precios de transferencia no son públicos. ' +
        'Si es así, la caída del margen dice más de cómo remunera el grupo a la filial que de su desempeño comercial.'],
      [cartera > 0.7 ? 'Pero la liquidez es cartera, no caja' : 'La liquidez', 'La disponibilidad inmediata es de ' + nf3.format(DI[l]) + ': el efectivo cubre el ' + F.pct(DI[l]) + ' del pasivo corriente. La liquidez corriente de ' +
        nf2.format(LC[l]) + ' se sostiene sobre los deudores comerciales, que son el ' + F.pct(cartera) + ' del activo corriente. ' +
        (ok(trmVar) ? 'Esa cartera sigue a la facturación y a la tasa de cambio más que a la cobranza: en ' + y[l] + ' varió ' + F.pctS(vp(CxC.nom[P], CxC.nom[l])) + ' nominal, casi lo mismo que la TRM de cierre (' +
          F.pctS(trmVar) + ', Banco de la República), y los días de cartera pasaron de ' + nf0.format(ROT[P]) + ' a ' + nf0.format(ROT[l]) + '. ' : '') +
        'Si son sobre todo saldos en dólares con vinculadas del exterior, el riesgo no es el impago sino la tasa de cambio y el momento en que el grupo los liquida. Es una inferencia: no hay desglose público de la cartera.'],
      ['Qué vigilar', 'La tasa efectiva de impuesto pasó de ' + F.pct(tasas[P]) + ' a ' + F.pct(tasas[l]) + '. No es un caso aislado: en la serie ha oscilado entre ' + F.pct(tasas[kTmin]) + ' (' + y[kTmin] + ') y ' +
        F.pct(tasas[kTmax]) + ' (' + y[kTmax] + ').' +
        (kT35 >= 0 ? ' La de ' + y[kT35] + ' superó la tarifa general de renta (35%): sin la conciliación de las notas no se puede separar el efecto de partidas no deducibles, precios de transferencia, impuesto diferido o diferencia en cambio.' : '') +
        ' Como la tasa varía tanto, la utilidad neta no es una buena señal de la operación; mejor seguir el margen bruto, los días de cartera y el efectivo frente al pasivo corriente.']
    ];
    var col = function (bs) { return '<div>' + bs.map(function (b) { return '<h3>' + esc(b[0]) + '</h3><p>' + esc(b[1]) + '</p>'; }).join('') + '</div>'; };
    $('diag-grid').innerHTML = col([bloques[0], bloques[2]]) + col([bloques[1], bloques[3]]);
    var IMPs = cta('er', 'IMP').nom, UAIs = cta('er', 'UAI').nom, sI = 0, sU = 0;
    for (var q = 0; q < l; q++) { sI += IMPs[q]; sU += UAIs[q]; }
    var pond = sI / sU, unPond = UAI * (1 - pond), unProm = UAI * (1 - prom);
    $('emph').innerHTML = '<div><div class="emph-fig">' + F.pct(tasas[l]) + '</div><div class="emph-cap">tasa efectiva de impuesto en ' + y[l] + '</div></div>' +
      '<p>Frente al ' + F.pct(tasas[P]) + ' de ' + y[P] + '. Con la tasa promedio ' + y[0] + '–' + y[P] + ' ponderada por utilidad antes de impuestos (' + F.pct(pond) + '), la utilidad neta de ' + y[l] +
      ' habría sido ' + esc(F.corto(unPond)) + ' en lugar de ' + esc(F.corto(UN)) + ' (' + F.pctS(vp(UN, unPond)) + '); con la media simple de las tasas (' + F.pct(prom) + '), ' + esc(F.corto(unProm)) +
      ' (' + F.pctS(vp(UN, unProm)) + '). El número es sensible al método y mezcla años con tarifas distintas.</p>';
  }

  /* =========================================================
     Arranque, controles, navegación
     ========================================================= */
  function renderAll() {
    setAll('.y-base', D.meta.anioBaseReal);
    setAll('.lbl-modo', lblModo());
    [renderPortada, renderPerfil, renderResumen, renderHorizontal, renderVertical, renderIndicadores, renderDiagnostico].forEach(function (fn) {
      try { fn(); } catch (e) { mostrarError('Error al dibujar (' + fn.name + '): ' + e.message); console.error(e); }
    });
  }
  function mostrarError(msg) { $('estado-carga').hidden = true; var b = $('estado-error'); b.hidden = false; b.textContent = msg; }

  function bindSeg(attr, key, after) {
    document.querySelectorAll('[data-' + attr + ']').forEach(function (b) {
      b.addEventListener('click', function () {
        if (S[key] === b.dataset[attr]) return;
        S[key] = b.dataset[attr];
        document.querySelectorAll('[data-' + attr + ']').forEach(function (x) { x.classList.toggle('is-active', x.dataset[attr] === S[key]); });
        after();
      });
    });
  }

  function scrollSpy() {
    var links = Array.prototype.slice.call(document.querySelectorAll('.nav a'));
    var secs = links.map(function (a) { return document.querySelector(a.getAttribute('href')); });
    // Con <base target="_top"> (Apps Script) un href="#..." navegaría la ventana superior: se desplaza a mano.
    links.forEach(function (a, k) {
      a.addEventListener('click', function (ev) { ev.preventDefault(); if (secs[k]) secs[k].scrollIntoView({ behavior: 'smooth', block: 'start' }); });
    });
    var onScroll = function () {
      var y = window.scrollY + 90, act = -1;
      secs.forEach(function (s, k) { if (s && s.offsetTop <= y) act = k; });
      links.forEach(function (a, k) { a.classList.toggle('is-active', k === act); });
    };
    window.addEventListener('scroll', onScroll, { passive: true }); onScroll();
  }

  function iniciar(m) {
    D = m;
    initHomo();
    $('estado-carga').hidden = true;
    $('contenido').hidden = false;
    $('pie-generado').textContent = 'datos leídos ' + D.meta.generado;
    renderAll();
    bindSeg('modo', 'modo', function () { setAll('.lbl-modo', lblModo()); renderHorizontal(); renderIndicadores(); });
    bindSeg('var', 'variacion', function () { renderTablaClave(); renderTablaFull(); });
    bindSeg('estado', 'estado', renderTablaFull);
    $('btn-copiar').addEventListener('click', function () {
      var ta = $('txt-prompt'), btn = this;
      var done = function () { btn.textContent = 'Copiado'; btn.classList.add('is-done'); setTimeout(function () { btn.textContent = 'Copiar prompt'; btn.classList.remove('is-done'); }, 1800); };
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(ta.value).then(done, function () { ta.select(); document.execCommand('copy'); done(); });
      else { ta.select(); document.execCommand('copy'); done(); }
    });
    scrollSpy();
    var t = null;
    window.addEventListener('resize', function () { clearTimeout(t); t = setTimeout(renderAll, 200); });
  }

  if (window.DASHBOARD_DATA) iniciar(window.DASHBOARD_DATA);
  else if (window.google && google.script && google.script.run) {
    google.script.run
      .withSuccessHandler(function (json) { try { iniciar(JSON.parse(json)); } catch (e) { mostrarError('No se pudo leer el modelo: ' + e.message); } })
      .withFailureHandler(function (e) { mostrarError('Error al leer la hoja de cálculo:\n' + (e && e.message ? e.message : e)); })
      .getDashboardData();
  } else if (window.Shiny && Shiny.addCustomMessageHandler) {
    Shiny.addCustomMessageHandler('modelo', function (json) {
      try { iniciar(typeof json === 'string' ? JSON.parse(json) : json); } catch (e) { mostrarError('No se pudo leer el modelo: ' + e.message); }
    });
    Shiny.addCustomMessageHandler('error', function (msg) { mostrarError(msg); });
  } else mostrarError('No hay conexión con Shiny ni datos de vista previa (window.DASHBOARD_DATA).');
})();
