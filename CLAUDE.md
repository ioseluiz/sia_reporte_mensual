# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Propósito

Aplicación de escritorio (PyQt6) para consultar las transacciones del SIA de la Autoridad del Canal de Panamá. El usuario selecciona un rango de fechas y los CodRamos de interés; la app consulta SQL Server y muestra los resultados en tabla con opción de exportar a Excel.

## Cómo ejecutar

```bat
ejecutar.bat          ← lanzador principal
diagnostico.bat       ← solo para verificar conexión y esquema
```

Requiere un archivo `.env` en la raíz (copiar de `.env.example`):

```
DB_SERVER_SQLSERVER=agsqlpro-lst.canal.acp
DB_NAME_SQLSERVER=SIADB
DB_USERNAME_SQLSERVER=...
DB_PASSWORD_SQLSERVER=...
```

## Instalar dependencias

```bat
venv\Scripts\pip install -r requirements.txt
```

## Arquitectura MVC

```
main.py                        # Punto de entrada: QApplication + MainController
model/
    database.py                # Conexión persistente a SQL Server vía pymssql
    sia_model.py               # get_ramos() y query_transactions()
view/
    main_window.py             # MainWindow (QMainWindow) — sin lógica de negocio
controller/
    main_controller.py         # Conecta señales del view con el model via QThreadPool
diagnostico.py / diagnostico.bat   # Herramienta de diagnóstico de conexión y esquema
```

**Patrón de threading**: Las queries DB corren en `_Worker(QRunnable)` con `_Signals(QObject)` para emitir resultados al hilo principal vía Qt signals. El flag `_busy` en el controller evita consultas concurrentes.

## Base de datos — Esquema confirmado (SIADB)

- **Motor**: SQL Server en `agsqlpro-lst.canal.acp`
- **Librería**: `pymssql` (no pyodbc — pyodbc falla con TLS en este servidor)
- **Conexión**: persistente y reutilizable via `_ConnectionManager` con reconexión automática

### tblTransacciones (1.6 M filas)
| Columna | Tipo | Notas |
|---------|------|-------|
| ID | int | PK |
| Fecha | smalldatetime | filtro de rango de fechas |
| CodProyecto | nvarchar | FK → tblProyectos (puede tener espacios al inicio) |
| HoraRegular | real | horas a sumar |
| HoraExtra | real | |
| CodRamo | nvarchar | ramo del **empleado** (ej. IAIM, IAIC) — NO usar para filtrar por ramo de proyecto |

### tblProyectos (24 095 filas)
| Columna | Tipo | Notas |
|---------|------|-------|
| CodProyecto | nvarchar | PK, join con tblTransacciones |
| CodProyectoOracle | nvarchar | código Oracle del proyecto |
| CodSubtareaOracle | nvarchar | subtarea Oracle |
| CodRamo | nvarchar | ramo del **proyecto** — este es el filtro correcto |

### Ramos INI disponibles en tblProyectos
`INIC`, `INI-CA`, `INICAR`, `INICIC`, `INICIE`, `INICIH`, `INIE`, `INIEDM`, `INIEEE`, `INIESM`, `INIG`, `INIGGE`, `INIGIG`, `INIGLS`, `INIO`, `INIOCE`, `INIOES`

## Decisiones de diseño importantes

- **`tblProyectos.CodRamo`** es el ramo del proyecto (INIC, INIG…). **`tblTransacciones.CodRamo`** es el ramo del empleado (IAIM, IAIC…). Son conceptos distintos. El filtro de la app usa `p.CodRamo` (proyecto).
- El join usa `t.CodProyecto = p.CodProyecto`. Nota: `CodProyecto` en tblTransacciones puede tener espacios al inicio (ej. `' LCS'`); si el join no devuelve resultados esperados, agregar `LTRIM(RTRIM(...))` en ambos lados.
- `pymssql` en lugar de `pyodbc` porque el ODBC Driver 17 falla en la negociación TLS con este servidor SQL Server corporativo.
- Conexión persistente (`_ConnectionManager`) porque el servidor rechaza nuevas negociaciones TLS frecuentes; la sesión TLS se establece una vez y se reutiliza.
