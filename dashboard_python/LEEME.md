# Dossier financiero · Sistemas Colombia S.A.S. (Python)

Tercera opción de despliegue, paralela a Apps Script (`../dashboard_globant/`) y Shiny (`../dashboard_shiny/`). Las tres comparten el diseño y la lógica de interfaz. La referencia es **Apps Script**:

- `pruebas/comparar_con_apps_script.py` ejecuta los `.gs` reales en node y compara el modelo **sin tolerancia**. Lo hace sobre la BD y sobre 22 variantes con casos borde: texto donde va un número, celdas vacías, booleanos, fechas, bases en cero, inflación de −100 %, etc.
- `pruebas/comparar_con_shiny.py` compara con el modelo de R sobre la BD actual.

## Estructura

| Archivo | Equivale a | Qué es |
|---|---|---|
| `app.py` | `Code.gs` / `app.R` | Configuración y servidor (Flask) |
| `datos.py` | `Datos.gs` / `R/datos.R` | Lectura de `data/BD_Dashboard_Globant.xlsx` |
| `calculos.py` | `Calculos.gs` / `R/calculos.R` | Deflactor, vertical, horizontal, indicadores |
| `serializar.py` | `JSON.stringify` | JSON del modelo (NaN e Infinity → null) |
| `templates/index.html` | `Index.html` | Estructura de la página (generado) |
| `static/styles.css`, `charts.js`, `app.js` | `Styles`, `Charts`, `JavaScript.html` | Diseño, gráficos e interfaz (generados) |
| `sincronizar.py` | `sincronizar.R` | Regenera los archivos generados y copia la BD |
| `pruebas/comparar_con_apps_script.py` | — | Compara con Apps Script, con casos borde (requiere node) |
| `pruebas/comparar_con_shiny.py` | — | Compara con Shiny (requiere R) |

**No edites los archivos generados.** Los cambios de diseño o interfaz se hacen en `../dashboard_globant/apps_script/`; después se ejecuta `python3 sincronizar.py`.

El modelo se calcula en el servidor y viaja dentro de la página (`window.DASHBOARD_DATA`, que `app.js` ya admitía). Solo se recalcula cuando cambia la fecha de modificación del `.xlsx`, así que basta con reemplazar el archivo para actualizar el dashboard, sin reiniciar nada.

## Acceso: enlace secreto con caducidad

No hay login. La página solo se sirve en `https://<subdominio>/<DASH_TOKEN>/`; cualquier otra ruta da 404. El código del enlace (43 caracteres aleatorios) se guarda en `ajustes.conf` (ver `ajustes.ejemplo`), nunca en el código.

- **El enlace es la llave:** quien lo tenga, entra. Si se filtra, cambia `DASH_TOKEN` y ejecuta `docker compose up -d`: el enlace viejo deja de funcionar al instante.
- **Caducidad:** con `EXPIRA=AAAA-MM-DD`, desde el día siguiente (hora de Bogotá) la página responde 410, «Este dashboard ya no está disponible».
- **Rastros:** la página va con `noindex`, `robots.txt` lo prohíbe todo y `Referrer-Policy: no-referrer` evita que la URL se envíe a otros sitios.
- **Rutas sin el código:** `/static/` (código de la interfaz, sin cifras) y `/salud` (solo `{"ok": true|false}`) responden sin el código.
- **Sin el código no arranca:** la app se niega a arrancar si `DASH_TOKEN` falta o tiene menos de 32 caracteres.

## Probar en local

```bash
cd dashboard_python
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
python3 sincronizar.py
DASH_TOKEN=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))') .venv/bin/python app.py   # imprime el enlace
.venv/bin/python pruebas/comparar_con_apps_script.py   # requiere node
.venv/bin/python pruebas/comparar_con_shiny.py         # opcional, requiere Rscript + readxl + jsonlite
```

## Publicar en la VM (Docker + Cloudflare)

1. Copia la carpeta `dashboard_python` a la VM (por ejemplo, a `/srv/dossier`). Debe incluir `data/BD_Dashboard_Globant.xlsx`.
2. Crea `ajustes.conf` a partir de `ajustes.ejemplo`, con el código generado en la VM y `chmod 600`.
3. Dentro de esa carpeta, ejecuta `docker compose up -d --build`. El servicio queda **solo en `127.0.0.1:8050`**, con límite de memoria y sistema de archivos de solo lectura.
4. Comprueba que responde: `curl -s 127.0.0.1:8050/salud` debe devolver `{"ok":true}`.
5. **Túnel de Cloudflare:** añade un *Public hostname* con el subdominio.
   - Si `cloudflared` corre en el host, apunta a `http://localhost:8050`.
   - Si corre en un contenedor, `localhost` no es el host y el puerto solo escucha en 127.0.0.1: conecta `cloudflared` a la red de este compose y apunta a `http://dossier-financiero:8050`.
   - La app debe servirse en la **raíz** del subdominio, no bajo una subruta como `/dossier`.
6. **Comprobación desde fuera:** `https://<subdominio>/` debe dar 404 y `https://<subdominio>/<DASH_TOKEN>/` debe mostrar el dashboard.

## Retirarlo

Borra el *Public hostname* del túnel y luego, en la VM, `docker compose down --rmi local` dentro de `/srv/dossier` y borra la carpeta. La caducidad (`EXPIRA`) solo oculta la página: no sustituye este paso.

## Actualizar datos

Regenera la BD con `python3 ../dashboard_globant/construir_bd.py`, ejecuta `python3 sincronizar.py` y reemplaza `data/BD_Dashboard_Globant.xlsx` en la VM. No hace falta reconstruir ni reiniciar el contenedor.

- **Reemplaza el archivo de una sola vez:** súbelo con otro nombre y luego `mv` sobre el original. Si se copia encima mientras se escribe, puede quedar en caché un archivo a medias hasta la siguiente modificación.
- Si el `.xlsx` tiene fórmulas en celdas que se leen, deben tener su valor calculado guardado (ábrelo y guárdalo en Excel o LibreOffice). Si no, la página muestra qué celdas fallan, en vez de leerlas como 0. Google Sheets recalcula y no tiene este problema.

Los años del análisis vertical y el logotipo se configuran con `ANIO_VERTICAL_1/2` y `LOGO_URL` en `docker-compose.yml`; para aplicar estos cambios hay que ejecutar `docker compose up -d`.

## Diferencias con las otras versiones

- **Única diferencia deliberada con Apps Script:** si la base del análisis vertical del balance es cero en alguno de los dos años, el cambio en puntos (`dpp`) es `null`, como en Shiny. Apps Script devuelve un número por la aritmética de `null` en JavaScript, y ese número no tiene sentido. Con los datos actuales no ocurre.
- **Fórmulas sin valor guardado:** Python avisa del error; Apps Script recalcula.
- **Hora de «generado»:** es la del último recálculo del modelo, que solo cambia cuando cambia el `.xlsx`. En Apps Script es la de cada carga.
- **Frente a Shiny:** las celdas vacías de las tablas llegan como `''` (Shiny envía `null`) e `indiceReal` sin base positiva llega como `null` (Shiny omite la clave). El cliente no distingue ninguna de las dos.

## Alternativa sin servidor: Cloudflare Pages (página estática)

`python3 exportar_pages.py` genera `pages/` con una sola página que lleva todo dentro: estilos, gráficos, lógica y cifras calculadas por el mismo modelo verificado. No hace falta servidor, Docker ni la VM.

- **Ruta secreta:** la página queda en `pages/<código>/index.html`; cualquier otra ruta muestra `404.html`. Para conservar un enlace ya repartido al actualizar datos, usa `--token <código>`.
- **Encabezados:** `_headers` aplica en Pages `noindex`, `no-referrer` y la prohibición de mostrarse dentro de otras páginas.
- **Caducidad (`--expira`, por defecto 2026-11-30):** es **solo visual**. Las cifras siguen en el HTML y alguien con el enlace puede leerlas en el código fuente. Para retirarlo de verdad, borra el proyecto en Cloudflare Pages.
- **Subir:** en Cloudflare, *Workers & Pages → Create → Pages → Upload assets*, y arrastra la carpeta `pages/` completa. Después, en *Custom domains*, añade el subdominio.
- **Actualizar:** `python3 sincronizar.py && python3 exportar_pages.py --token <código>` y vuelve a subir `pages/` en *Create deployment*.
- **Copia `*.pages.dev`:** Pages también publica el sitio en una dirección de este tipo; con la ruta secreta, la protección es la misma.

## Página pública en GitHub Pages

`python3 exportar_pages.py --publico` genera `../docs/index.html` (más `.nojekyll`): una sola página con todo dentro, sin ruta secreta, sin `noindex` y sin caducidad. GitHub Pages la publica desde la carpeta `/docs` de la rama `main`. Para actualizar, regenérala, haz commit y push.

## Guía de lectura (PDF)

`Guia_lectura_dashboard.pdf`, en la raíz del repo, se genera desde el dashboard. Las cifras de cada «Qué dice hoy» salen del mismo modelo (`calculos.py`) y las imágenes son capturas de `docs/index.html`, así que la guía no puede contradecir a la página. Para regenerarla después de cambiar datos o diseño:

```bash
cd dashboard_python
python3 sincronizar.py && python3 exportar_pages.py --publico     # 1. página actualizada
cd guia
NODE_PATH=<node_modules con puppeteer-core> node capturas.js      # 2. capturas (npm i puppeteer-core; usa google-chrome)
python3 exportar_guia.py                                          # 3. guia.html y ../../Guia_lectura_dashboard.pdf
```

El contexto externo (Globant, TRM, informe de variaciones) es texto fijo en `exportar_guia.py`, con su nivel de certeza. Las TRM están en `TRM_CIERRE` y `TRM_PROMEDIO`, y deben coincidir con las del diagnóstico en `JavaScript.html`.
