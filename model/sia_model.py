from datetime import date
from .database import get_connection


def get_proyectos_ph() -> list[dict]:
    """Devuelve todos los registros de tblProyectos cuyo NomProyecto contiene 'PH'."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT *
        FROM tblProyectos
        WHERE NomProyecto LIKE '%PH%'
        ORDER BY CodProyecto
    """)
    return cursor.fetchall()


def get_ramos() -> list[str]:
    """
    Devuelve los CodRamo distintos de tblTransacciones para proyectos INICA (p.CodRamo LIKE 'INI%').
    Estos son los ramos de los empleados/unidades que han registrado horas en proyectos INICA.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT t.CodRamo
        FROM tblTransacciones t
        INNER JOIN tblProyectos p ON t.CodProyecto = p.CodProyecto
        WHERE p.CodRamo LIKE 'INI%'
          AND t.CodRamo IS NOT NULL
        ORDER BY t.CodRamo
    """)
    return [row["CodRamo"] for row in cursor.fetchall()]


def get_project_transactions(
    cod_proyecto: str, start_date: date, end_date: date, ramos: list[str]
) -> list[dict]:
    """
    Devuelve las filas de tblTransacciones para un proyecto, rango de fechas y
    CodRamo de transacción específico. Los ramos son t.CodRamo (ramo del empleado),
    garantizando que TotalHoras del resumen coincida con la suma del detalle.
    """
    if not ramos:
        return []

    placeholders = ", ".join(["%s" for _ in ramos])
    sql = f"""
        SELECT
            t.ID,
            t.Fecha,
            t.IP,
            u.NomUsuario,
            t.HoraRegular,
            t.HoraExtra,
            t.HoraComp,
            t.CodRamo
        FROM tblTransacciones t
        LEFT JOIN tblUsuarios u ON t.IP = u.IP
        WHERE t.CodProyecto = %s
          AND t.Fecha >= %s
          AND t.Fecha <= %s
          AND t.CodRamo IN ({placeholders})
        ORDER BY t.Fecha, t.ID
    """
    params = [cod_proyecto, start_date, end_date] + list(ramos)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, params)
    return cursor.fetchall()


def query_transactions(
    start_date: date, end_date: date, ramos: list[str]
) -> list[dict]:
    """
    Consulta horas regulares por proyecto en el rango de fechas y ramos dados.

    Join: tblTransacciones.CodProyecto = tblProyectos.CodProyecto
    Filtro de ramo: tblProyectos.CodRamo (ramo del proyecto, no del empleado)

    Filtro: t.CodRamo IN (ramos) — ramos del empleado seleccionados en la UI.
    Solo proyectos INICA (p.CodRamo LIKE 'INI%').
    Columnas: CodProyecto, CodProyectoOracle, CodSubtareaOracle, CodRamo (t), TotalHoras
    """
    if not ramos:
        return []

    placeholders = ", ".join(["%s" for _ in ramos])
    sql = f"""
        SELECT
            p.CodProyecto,
            p.CodProyectoOracle,
            p.CodSubtareaOracle,
            t.CodRamo,
            SUM(t.HoraRegular) AS TotalHoras
        FROM tblTransacciones t
        INNER JOIN tblProyectos p ON t.CodProyecto = p.CodProyecto
        WHERE t.Fecha >= %s
          AND t.Fecha <= %s
          AND t.CodRamo IN ({placeholders})
          AND p.CodRamo LIKE 'INI%'
        GROUP BY p.CodProyecto, p.CodProyectoOracle, p.CodSubtareaOracle, t.CodRamo
        ORDER BY p.CodProyecto, t.CodRamo
    """
    params = [start_date, end_date] + list(ramos)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, params)
    return cursor.fetchall()


def get_collaborators() -> list[dict]:
    """
    Devuelve los colaboradores de tblUsuarios, excluyendo a los
    que tienen nombres inactivos/de prueba que inician con 'ZZ' o 'zz',
    y excluyendo la columna 'Clave'.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT IP, NomUsuario, Grado, CodRamo, Acceso, AccesoEstimar, Salario
        FROM tblUsuarios
        WHERE NomUsuario NOT LIKE 'ZZ%' AND NomUsuario NOT LIKE 'zz%'
        ORDER BY NomUsuario
    """)
    return cursor.fetchall()


def get_users_under_8_hours(start_date, end_date) -> list[dict]:
    """
    Devuelve, por cada empleado de ramos INI y cada dia L-V del rango, las filas
    con menos de 8 horas regulares registradas — incluyendo dias sin ningun
    registro (HorasRegulares = 0.00). Parte de la lista maestra tblUsuarios
    (CodRamo LIKE 'INI%%', excluyendo 'ZZ%%'/'zz%%') CROSS JOIN dias laborables,
    con LEFT JOIN a las horas agregadas por (IP, Fecha), para no omitir empleados
    que no llenaron SIA en un dia dado.
    """
    conn = get_connection()
    cursor = conn.cursor()
    sql = """
        WITH DiasCal AS (
            SELECT CAST(%s AS date) AS Dia
            UNION ALL
            SELECT DATEADD(day, 1, Dia)
            FROM DiasCal
            WHERE Dia < CAST(%s AS date)
        ),
        DiasLaborables AS (
            SELECT Dia
            FROM DiasCal
            WHERE ((DATEPART(dw, Dia) + @@DATEFIRST - 2) % 7) < 5
        ),
        EmpleadosINI AS (
            SELECT IP, NomUsuario, CodRamo
            FROM tblUsuarios
            WHERE NomUsuario NOT LIKE 'ZZ%' AND NomUsuario NOT LIKE 'zz%'
              AND CodRamo LIKE 'INI%'
        ),
        HorasPorDia AS (
            SELECT t.IP, CAST(t.Fecha AS date) AS Fecha,
                   SUM(t.HoraRegular) AS Horas
            FROM tblTransacciones t
            WHERE t.Fecha >= %s AND t.Fecha <= %s
            GROUP BY t.IP, CAST(t.Fecha AS date)
        )
        SELECT
            e.NomUsuario,
            e.CodRamo,
            d.Dia AS Fecha,
            ROUND(ISNULL(h.Horas, 0), 2) AS HorasRegulares
        FROM EmpleadosINI e
        CROSS JOIN DiasLaborables d
        LEFT JOIN HorasPorDia h
            ON h.IP = e.IP AND h.Fecha = d.Dia
        WHERE ROUND(ISNULL(h.Horas, 0), 2) < 8
        ORDER BY e.CodRamo, e.NomUsuario, d.Dia
        OPTION (MAXRECURSION 32767)
    """
    cursor.execute(sql, (start_date, end_date, start_date, end_date))
    return cursor.fetchall()


def get_user_ramos() -> list[str]:
    """
    Devuelve los CodRamo distintos de tblUsuarios (ramos de los empleados),
    excluyendo usuarios inactivos/de prueba ('ZZ%').
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT CodRamo
        FROM tblUsuarios
        WHERE CodRamo IS NOT NULL
          AND LTRIM(RTRIM(CodRamo)) <> ''
          AND NomUsuario NOT LIKE 'ZZ%'
          AND NomUsuario NOT LIKE 'zz%'
        ORDER BY CodRamo
    """)
    return [row["CodRamo"] for row in cursor.fetchall()]


def get_users_by_ramo(cod_ramo: str) -> list[dict]:
    """
    Devuelve los empleados (IP, NomUsuario) que pertenecen a un CodRamo
    dado en tblUsuarios, excluyendo 'ZZ%'.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT IP, NomUsuario
        FROM tblUsuarios
        WHERE CodRamo = %s
          AND NomUsuario NOT LIKE 'ZZ%'
          AND NomUsuario NOT LIKE 'zz%'
        ORDER BY NomUsuario
    """, (cod_ramo,))
    return cursor.fetchall()


def get_all_transactions_by_ip(ip: str, start_date, end_date) -> list[dict]:
    """
    Devuelve TODAS las columnas de tblTransacciones para un empleado (IP)
    en el rango de fechas, junto con el NomUsuario. Une por IP.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            u.NomUsuario,
            t.ID,
            t.Fecha,
            t.FechaCreacion,
            t.CreadoPor,
            t.CodProyecto,
            t.CodRamo,
            t.HoraRegular,
            t.HoraExtra,
            t.HoraComp,
            t.Salario,
            t.IP
        FROM tblTransacciones t
        INNER JOIN tblUsuarios u ON t.IP = u.IP
        WHERE t.IP = %s
          AND t.Fecha >= %s
          AND t.Fecha <= %s
        ORDER BY t.Fecha, t.ID
    """, (ip, start_date, end_date))
    return cursor.fetchall()


def search_user_transactions(username: str, start_date, end_date) -> list[dict]:
    """
    Busca transacciones individuales filtradas por parte del nombre de usuario y un rango de fechas.
    Retorna NomUsuario, CodProyecto, DescProyecto, HoraRegular, HoraExtra, HoraComp,
    Fecha (de la transaccion) y FechaCreacion (cuando se ingreso el registro).
    """
    conn = get_connection()
    cursor = conn.cursor()
    sql = """
        SELECT
            u.NomUsuario,
            t.CodProyecto,
            CAST(p.DescProyecto AS NVARCHAR(MAX)) AS DescProyecto,
            t.HoraRegular,
            t.HoraExtra,
            t.HoraComp,
            t.Fecha,
            t.FechaCreacion
        FROM tblTransacciones t
        INNER JOIN tblUsuarios u ON t.IP = u.IP
        LEFT JOIN tblProyectos p ON t.CodProyecto = p.CodProyecto
        WHERE t.Fecha >= %s AND t.Fecha <= %s
          AND u.NomUsuario LIKE %s
        ORDER BY t.Fecha, u.NomUsuario
    """
    cursor.execute(sql, (start_date, end_date, f"%{username}%"))
    return cursor.fetchall()


def search_project_transactions(cod_proyecto: str, start_date, end_date) -> list[dict]:
    """
    Busca transacciones individuales de tblTransacciones filtradas por CodProyecto
    (SIA) y rango de fechas. Trim en ambos lados porque CodProyecto puede tener
    espacios al inicio en tblTransacciones. Retorna NomUsuario, CodProyecto,
    DescProyecto, CodRamo (empleado), HoraRegular, HoraExtra, HoraComp, Fecha.
    """
    conn = get_connection()
    cursor = conn.cursor()
    sql = """
        SELECT
            u.NomUsuario,
            LTRIM(RTRIM(t.CodProyecto)) AS CodProyecto,
            CAST(p.DescProyecto AS NVARCHAR(MAX)) AS DescProyecto,
            t.CodRamo,
            t.HoraRegular,
            t.HoraExtra,
            t.HoraComp,
            t.Fecha
        FROM tblTransacciones t
        INNER JOIN tblUsuarios u ON t.IP = u.IP
        LEFT JOIN tblProyectos p ON LTRIM(RTRIM(t.CodProyecto)) = LTRIM(RTRIM(p.CodProyecto))
        WHERE t.Fecha >= %s AND t.Fecha <= %s
          AND LTRIM(RTRIM(t.CodProyecto)) LIKE %s
        ORDER BY t.Fecha, u.NomUsuario
    """
    cursor.execute(sql, (start_date, end_date, f"%{cod_proyecto.strip()}%"))
    return cursor.fetchall()


def get_project_ramos() -> list[str]:
    """
    Devuelve los CodRamo distintos de tblProyectos (ramo del proyecto, no del empleado).
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT CodRamo
        FROM tblProyectos
        WHERE CodRamo IS NOT NULL
        ORDER BY CodRamo
    """)
    return [row["CodRamo"] for row in cursor.fetchall()]


def get_project_hours_summary(ramos: list[str]) -> list[dict]:
    """
    Resumen por proyecto: totales de HoraRegular, HoraComp, HoraExtra y su suma total,
    considerando TODAS las transacciones historicas (sin filtro de fecha).
    Incluye TODOS los proyectos de los ramos seleccionados aunque no tengan
    transacciones (LEFT JOIN).
    """
    if not ramos:
        return []

    placeholders = ", ".join(["%s" for _ in ramos])
    sql = f"""
        SELECT
            LTRIM(RTRIM(p.CodProyecto)) AS CodProyecto,
            p.NomProyecto,
            p.CodRamo,
            ISNULL(SUM(t.HoraRegular), 0) AS TotalHoraRegular,
            ISNULL(SUM(t.HoraComp), 0)   AS TotalHoraComp,
            ISNULL(SUM(t.HoraExtra), 0)  AS TotalHoraExtra,
            ISNULL(SUM(ISNULL(t.HoraRegular,0) + ISNULL(t.HoraComp,0) + ISNULL(t.HoraExtra,0)), 0) AS TotalHoras
        FROM tblProyectos p
        LEFT JOIN tblTransacciones t
            ON LTRIM(RTRIM(t.CodProyecto)) = LTRIM(RTRIM(p.CodProyecto))
        WHERE p.CodRamo IN ({placeholders})
        GROUP BY p.CodProyecto, p.NomProyecto, p.CodRamo
        ORDER BY p.CodProyecto
    """

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, list(ramos))
    return cursor.fetchall()


def get_project_hours_detail(cod_proyecto: str) -> list[dict]:
    """
    Detalle de TODAS las transacciones para UN CodProyecto exacto (con trim en la
    comparacion), sin filtro de fecha. Sustenta los totales del resumen.
    """
    conn = get_connection()
    cursor = conn.cursor()
    sql = """
        SELECT
            t.Fecha,
            u.NomUsuario,
            t.CodRamo,
            t.HoraRegular,
            t.HoraComp,
            t.HoraExtra,
            t.IP,
            t.ID
        FROM tblTransacciones t
        INNER JOIN tblUsuarios u ON t.IP = u.IP
        WHERE LTRIM(RTRIM(t.CodProyecto)) = LTRIM(RTRIM(%s))
        ORDER BY t.Fecha, u.NomUsuario
    """
    cursor.execute(sql, (cod_proyecto,))
    return cursor.fetchall()


def get_all_projects(only_active: bool = True) -> list[dict]:
    """
    Lista todos los proyectos de tblProyectos con conteo de integrantes,
    para poder navegar del proyecto a sus integrantes. Si only_active=True,
    filtra por ProyectoActivo = 1.
    """
    sql = """
        SELECT
            LTRIM(RTRIM(p.CodProyecto)) AS CodProyecto,
            p.NomProyecto,
            p.CodRamo,
            p.CodProyectoOracle,
            p.FechaRec,
            p.Abierto,
            p.ProyectoActivo,
            (
                SELECT COUNT(*) FROM tblIntegrantes i
                WHERE LTRIM(RTRIM(i.CodProyecto)) = LTRIM(RTRIM(p.CodProyecto))
            ) AS NumIntegrantes
        FROM tblProyectos p
    """
    if only_active:
        sql += " WHERE p.ProyectoActivo = 1"
    sql += " ORDER BY p.CodRamo, p.CodProyecto"

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql)
    return cursor.fetchall()


def get_project_members(cod_proyecto: str) -> list[dict]:
    """
    Devuelve TODAS las columnas de tblIntegrantes para un proyecto exacto
    (con LTRIM/RTRIM porque CodProyecto puede tener espacios). Ademas,
    intenta unir con tblUsuarios por IP si dicha columna existe, para
    incluir NomUsuario legible. Cae al SELECT plano si el join falla.
    """
    conn = get_connection()
    param = (cod_proyecto,)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT i.*, u.NomUsuario
            FROM tblIntegrantes i
            LEFT JOIN tblUsuarios u ON i.IP = u.IP
            WHERE LTRIM(RTRIM(i.CodProyecto)) = LTRIM(RTRIM(%s))
        """, param)
        return cursor.fetchall()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        cursor = conn.cursor()
        cursor.execute("""
            SELECT *
            FROM tblIntegrantes
            WHERE LTRIM(RTRIM(CodProyecto)) = LTRIM(RTRIM(%s))
        """, param)
        return cursor.fetchall()


def get_projects_without_members(only_active: bool = True) -> list[dict]:
    """
    Devuelve los proyectos de tblProyectos que NO tienen ningun integrante
    registrado en tblIntegrantes. Si only_active=True (por defecto), filtra
    ademas por ProyectoActivo = 1.

    Sirve para detectar proyectos huerfanos (sin responsables asignados).
    """
    sql = """
        SELECT
            LTRIM(RTRIM(p.CodProyecto)) AS CodProyecto,
            p.NomProyecto,
            p.CodRamo,
            p.CodProyectoOracle,
            p.FechaRec,
            p.Abierto,
            p.ProyectoActivo
        FROM tblProyectos p
        WHERE NOT EXISTS (
            SELECT 1 FROM tblIntegrantes i
            WHERE LTRIM(RTRIM(i.CodProyecto)) = LTRIM(RTRIM(p.CodProyecto))
        )
    """
    if only_active:
        sql += " AND p.ProyectoActivo = 1"
    sql += " ORDER BY p.CodRamo, p.CodProyecto"

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql)
    return cursor.fetchall()


def get_siadb_schema() -> list[dict]:
    """
    Devuelve una fila por columna de cada tabla de usuario del SIADB.
    Excluye vistas y objetos de sistema (TABLE_TYPE = 'BASE TABLE') y tablas
    internas como sysdiagrams. Sirve como catalogo del esquema para analistas.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            c.TABLE_SCHEMA,
            c.TABLE_NAME,
            c.ORDINAL_POSITION,
            c.COLUMN_NAME,
            c.DATA_TYPE,
            c.CHARACTER_MAXIMUM_LENGTH,
            c.NUMERIC_PRECISION,
            c.NUMERIC_SCALE,
            c.IS_NULLABLE
        FROM INFORMATION_SCHEMA.COLUMNS c
        INNER JOIN INFORMATION_SCHEMA.TABLES t
            ON t.TABLE_SCHEMA = c.TABLE_SCHEMA
           AND t.TABLE_NAME = c.TABLE_NAME
        WHERE t.TABLE_TYPE = 'BASE TABLE'
          AND t.TABLE_NAME <> 'sysdiagrams'
        ORDER BY c.TABLE_SCHEMA, c.TABLE_NAME, c.ORDINAL_POSITION
    """)
    return cursor.fetchall()
