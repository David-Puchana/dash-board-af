# Dossier financiero · Sistemas Colombia S.A.S. (Apps Script)

Diseño según `../Globant · Sistema de diseño del Dossier Financiero.html`.

## Contenido

| Archivo | Qué es |
|---|---|
| `BD_Dashboard_Globant.xlsx` | Base de datos para subir a Google Sheets (8 hojas) |
| `construir_bd.py` | Regenera la BD desde `../ESTADOS_FINANCIEROS/*.xlsx` y valida que todo cuadre |
| `apps_script/Code.gs` | `doGet`, `include`, menú "Dashboard" y API `getDashboardData` |
| `apps_script/Datos.gs` | Lectura de las hojas |
| `apps_script/Calculos.gs` | Deflactor, análisis vertical, horizontal e indicadores |
| `apps_script/Index.html` | Estructura de la página |
| `apps_script/Styles.html` | Estilos (tokens de la guía del Dossier Financiero) |
| `apps_script/Charts.html` | Librería de gráficos SVG con efectos hover |
| `apps_script/JavaScript.html` | Lógica de la interfaz |

## Hojas de la BD

`ER`, `ESF` (cuentas × años 2018–2025, en miles de COP), `Deflactor` (IPC DANE, editable), `Empresa`, `Hitos`, `Notas`, `Reexpresiones` (versión usada vs. alternativa), `Fuentes` (procedencia y estado OK/AVISO por año).
Los nombres de las hojas y de las columnas `ID`, `Cuenta`, `Tipo`, `Grupo`, `Orden` y los años **no deben cambiarse**.

## Instalación

1. En Google Drive: **Nuevo → Subir archivo** → `BD_Dashboard_Globant.xlsx`. Ábrelo con **Hojas de cálculo de Google** y guárdalo como Google Sheets (**Archivo → Guardar como Hojas de cálculo de Google**).
2. En esa hoja: **Extensiones → Apps Script**.
3. Crea los archivos con estos nombres exactos (sin extensión en el editor) y pega el contenido de cada uno:
   - Script: `Code`, `Datos`, `Calculos`
   - HTML: `Index`, `Styles`, `Charts`, `JavaScript`
4. Guarda y ejecuta la función `probarModelo` una vez para autorizar. En el registro deben salir los indicadores.
5. Para verlo:
   - **Dentro de Sheets:** recarga la hoja y usa el menú **Dashboard → Abrir dashboard**.
   - **Como web app:** **Implementar → Nueva implementación → Aplicación web**, ejecutar como *Yo*, y abre la URL.

Si el script no está vinculado a la hoja, pega el ID del Sheet en `CONFIG.SPREADSHEET_ID` (`Code.gs`).

Logotipo: la guía prohíbe dibujarlo. Pega la URL pública del archivo oficial en `CONFIG.LOGO_URL`; si está vacío, se muestra el espacio reservado.

## Actualizar datos

- Cambiar la inflación: edita la columna B de la hoja `Deflactor`. El índice se recalcula en el script.
- Cambiar los años del análisis vertical: `CONFIG.ANIO_VERTICAL_1/2` en `Code.gs`.
- Agregar un año: añade la columna del año en `ER` y `ESF` y la fila en `Deflactor`.
