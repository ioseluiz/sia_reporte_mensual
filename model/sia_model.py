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
    Devuelve los usuarios con menos de 8 horas regulares diarias de lunes a viernes,
    excluyendo usuarios que inician con 'ZZ' o 'zz'.
    """
    conn = get_connection()
    cursor = conn.cursor()
    sql = """
        SELECT
            u.NomUsuario,
            u.CodRamo,
            t.Fecha,
            ROUND(SUM(t.HoraRegular), 2) AS HorasRegulares
        FROM tblTransacciones t
        INNER JOIN tblUsuarios u ON t.IP = u.IP
        WHERE t.Fecha >= %s AND t.Fecha <= %s
          AND u.NomUsuario NOT LIKE 'ZZ%' AND u.NomUsuario NOT LIKE 'zz%'
          AND ((DATEPART(dw, t.Fecha) + @@DATEFIRST - 2) % 7) < 5
        GROUP BY u.NomUsuario, u.CodRamo, t.Fecha
        HAVING ROUND(SUM(t.HoraRegular), 2) < 8
        ORDER BY u.CodRamo, u.NomUsuario, t.Fecha
    """
    cursor.execute(sql, (start_date, end_date))
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
    Retorna NomUsuario, CodProyecto, DescProyecto, HoraRegular, HoraExtra, HoraComp y Fecha.
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
            t.Fecha
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
