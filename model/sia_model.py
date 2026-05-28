from datetime import date
from .database import get_connection


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
