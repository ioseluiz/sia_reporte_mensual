# SIA - Reporte Mensual

Aplicación de escritorio para consultar las horas registradas en el Sistema de Información Administrativa (SIA) de la Autoridad del Canal de Panamá. Permite seleccionar un rango de fechas y los CodRamo de interés para ver el total de horas cargadas por proyecto Oracle, con opción de exportar a Excel.

## Requisitos previos

- Python 3.10 o superior
- Acceso a la red corporativa (servidor `agsqlpro-lst.canal.acp`)
- Credenciales de la base de datos SIADB

## Instalación

### 1. Crear y activar el entorno virtual

```bat
python -m venv venv
venv\Scripts\activate
```

### 2. Instalar dependencias

```bat
venv\Scripts\pip install -r requirements.txt
```

### 3. Configurar credenciales

Copiar el archivo de ejemplo y completar con las credenciales reales:

```bat
copy .env.example .env
```

Editar `.env`:

```
DB_SERVER_SQLSERVER=agsqlpro-lst.canal.acp
DB_NAME_SQLSERVER=SIADB
DB_USERNAME_SQLSERVER=tu_usuario
DB_PASSWORD_SQLSERVER=tu_contraseña
```

> **Importante:** El archivo `.env` contiene credenciales y está excluido del control de versiones. No compartirlo ni subirlo al repositorio.

## Ejecución

```bat
ejecutar.bat
```

O directamente:

```bat
venv\Scripts\python.exe main.py
```

## Diagnóstico de conexión

Si hay problemas de conexión a la base de datos, ejecutar:

```bat
diagnostico.bat
```

Muestra la estructura real de las tablas y verifica que la conexión funcione correctamente.

## Uso de la aplicación

1. **Seleccionar fechas:** Ingresar la fecha inicial y final del período a consultar.
2. **Seleccionar CodRamo:** Marcar los ramos de transacción (unidades que registraron horas) que se desean incluir. Se cargan automáticamente desde la base de datos al iniciar.
3. **Consultar:** Presionar el botón **Consultar** para ejecutar la query.
4. **Filtrar resultados:**
   - Seleccionar un **Proyecto Oracle** en el combo para ver solo los proyectos de ese código Oracle.
   - Seleccionar una **Subtarea Oracle** para afinar el filtro (se actualiza según el Proyecto Oracle elegido).
   - Usar el campo **Filtrar** para búsqueda libre por cualquier columna.
   - El total de horas se recalcula automáticamente con cada filtro aplicado.
5. **Ver detalle:** Hacer doble clic en cualquier fila para ver todas las transacciones individuales del proyecto y CodRamo de esa fila, con el total de HoraRegular.
6. **Exportar:** Usar el botón **Exportar a Excel** para guardar los resultados visibles. El detalle de cada proyecto también puede exportarse desde su ventana.

### Reporte Horas L-V (< 8h) — preview interactivo y correo por sección

El botón **Reporte Horas L-V (< 8h)** abre un preview modal antes de exportar:

- Una pestaña por `CodRamo`. Cada fila tiene un checkbox Sí/No para incluirla o excluirla.
- Estado visual por fila: **Faltante** (0 h) en rojo pastel, **Incompleto** (0 < h < 8) en ámbar.
- En cada pestaña se puede editar el supervisor de la sección (Nombre, Correo Para, CC) y marcar si se quiere enviar correo para esa sección. Los valores se prellenan desde `config/supervisores.json` (véase `config/supervisores.example.json` como plantilla).
- Botón **Guardar como default** persiste el supervisor de esa sección en el JSON local.
- La barra superior permite Marcar / Desmarcar todo, filtrar por estado, y filtrar texto libre — todas las acciones aplican a la pestaña activa.
- Botón **Descargar Excel** — guarda un `.xlsx` con una hoja por sección, incluyendo sólo las filas marcadas (si no se toca ningún checkbox, el resultado es idéntico al reporte previo).
- Botón **Crear borradores de correo** — para cada sección con "Enviar correo" activo y supervisor válido, crea un borrador en Outlook (vía COM) con Para/CC/Asunto/cuerpo HTML poblados desde `templates/correo_menores_8.html`, más un `.xlsx` adjunto con las filas de esa sección. Los borradores se abren en Outlook para revisión — **no se envían automáticamente**.

Ambos botones pueden usarse en el mismo preview: se puede descargar y luego crear borradores, o viceversa, sin cerrar el diálogo.

Requisitos adicionales:
- `pywin32` para la creación de borradores en Outlook (incluido en `requirements.txt`).
- Outlook debe estar instalado y con un perfil configurado. Si Outlook no está disponible, la descarga de Excel sigue funcionando.

Configuración inicial del mapeo de supervisores:

```bat
copy config\supervisores.example.json config\supervisores.json
```

Y editar `config/supervisores.json` con los correos reales por `CodRamo`. Este archivo está en `.gitignore`.

## Arquitectura

```
main.py                     Punto de entrada (QApplication + MainController)
model/
  database.py               Conexión persistente a SQL Server vía pymssql
  sia_model.py              Consultas: get_ramos(), query_transactions(), get_project_transactions()
view/
  main_window.py            Ventana principal (formulario + tabla de resultados)
  detail_dialog.py          Diálogo de detalle de transacciones por proyecto
  report_preview_dialog.py  Preview del reporte <8h con selección por fila y datos de supervisor
controller/
  main_controller.py        Conecta señales del view con el model via QThreadPool
core/
  supervisores_repo.py      Load/save de config/supervisores.json (mapeo CodRamo → supervisor)
  template_render.py        Renderiza templates/correo_menores_8.html con datos de la sección
  email_outlook.py          Crea borradores de correo en Outlook vía COM (win32com)
templates/
  correo_menores_8.html     Plantilla del cuerpo del correo (Jinja-style con string replace)
  mensaje_ejemplo.msg       Correo de referencia (fuente original de la plantilla)
config/
  supervisores.example.json Plantilla del mapeo CodRamo → supervisor (versionable)
  supervisores.json         Mapeo real con correos (git-ignorado)
diagnostico.py              Script de diagnóstico de conexión y esquema de BD
```

Las queries a la base de datos corren en hilos secundarios (`QThreadPool`) para no bloquear la interfaz. El flag `_busy` en el controlador previene consultas concurrentes.

## Notas técnicas

- Se usa `pymssql` en lugar de `pyodbc` porque el ODBC Driver 17 falla en la negociación TLS con este servidor SQL Server corporativo.
- La conexión se mantiene persistente y se reutiliza entre consultas para evitar que el servidor rechace nuevas negociaciones TLS frecuentes.
- `tblProyectos.CodRamo` es el ramo del **proyecto** (INIC, INIG…). `tblTransacciones.CodRamo` es el ramo del **empleado** (IAIM, IAIC…). El selector de la UI y los filtros de la consulta usan el ramo de la transacción.
