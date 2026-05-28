"""
Script de diagnóstico: conecta a la BD y muestra la estructura real
de las tablas para identificar nombres correctos de tablas y columnas.
Ejecutar con: venv\Scripts\python.exe diagnostico.py
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

try:
    import pymssql
except ImportError:
    print("ERROR: pymssql no está instalado. Ejecuta: venv\\Scripts\\pip install pymssql")
    input("\nPresiona Enter para cerrar...")
    sys.exit(1)

server   = os.getenv("DB_SERVER_SQLSERVER")
database = os.getenv("DB_NAME_SQLSERVER")
username = os.getenv("DB_USERNAME_SQLSERVER")
password = os.getenv("DB_PASSWORD_SQLSERVER")

print(f"Servidor : {server}")
print(f"Base de datos: {database}")
print(f"Usuario  : {username}")
print()

try:
    conn = pymssql.connect(
        server=server, user=username, password=password,
        database=database, as_dict=True, login_timeout=15,
    )
    print("✓ Conexión exitosa\n")
except Exception as e:
    print(f"✗ Error de conexión:\n  {e}")
    input("\nPresiona Enter para cerrar...")
    sys.exit(1)

cur = conn.cursor()

# ── 1. Todas las tablas de la BD ─────────────────────────────────────────────
cur.execute("""
    SELECT TABLE_SCHEMA, TABLE_NAME
    FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_TYPE = 'BASE TABLE'
    ORDER BY TABLE_NAME
""")
tablas = cur.fetchall()
print(f"=== Tablas en '{database}' ({len(tablas)} total) ===")
for t in tablas:
    print(f"  {t['TABLE_SCHEMA']}.{t['TABLE_NAME']}")

# ── 2. tblTransacciones ───────────────────────────────────────────────────────
print("\n=== tblTransacciones ===")
try:
    cur.execute("SELECT COUNT(*) AS n FROM tblTransacciones")
    print(f"  Filas: {cur.fetchone()['n']}")

    cur.execute("""
        SELECT COLUMN_NAME, DATA_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'tblTransacciones'
        ORDER BY ORDINAL_POSITION
    """)
    cols = cur.fetchall()
    print(f"  Columnas ({len(cols)}):")
    for c in cols:
        print(f"    {c['COLUMN_NAME']}  ({c['DATA_TYPE']})")

    cur.execute("SELECT TOP 3 * FROM tblTransacciones")
    filas = cur.fetchall()
    if filas:
        print("  Primeras 3 filas:")
        for f in filas:
            print(f"    {dict(f)}")
    else:
        print("  (tabla vacía)")
except Exception as e:
    print(f"  ERROR: {e}")

# ── 3. tblProyectos ───────────────────────────────────────────────────────────
print("\n=== tblProyectos ===")
try:
    cur.execute("SELECT COUNT(*) AS n FROM tblProyectos")
    print(f"  Filas: {cur.fetchone()['n']}")

    cur.execute("""
        SELECT COLUMN_NAME, DATA_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'tblProyectos'
        ORDER BY ORDINAL_POSITION
    """)
    cols = cur.fetchall()
    print(f"  Columnas ({len(cols)}):")
    for c in cols:
        print(f"    {c['COLUMN_NAME']}  ({c['DATA_TYPE']})")
except Exception as e:
    print(f"  ERROR: {e}")

# ── 4. CodRamo distintos en tblProyectos ─────────────────────────────────────
print("\n=== CodRamo distintos en tblProyectos (primeros 40) ===")
try:
    cur.execute("""
        SELECT DISTINCT CodRamo, COUNT(*) AS proyectos
        FROM tblProyectos
        WHERE CodRamo IS NOT NULL
        GROUP BY CodRamo
        ORDER BY CodRamo
    """)
    for row in cur.fetchall()[:40]:
        print(f"  '{row['CodRamo']}'  ({row['proyectos']} proyectos)")
except Exception as e:
    print(f"  ERROR: {e}")

# ── 5. CodRamo distintos INI% en tblProyectos ────────────────────────────────
print("\n=== CodRamo 'INI%' en tblProyectos ===")
try:
    cur.execute("""
        SELECT DISTINCT CodRamo
        FROM tblProyectos
        WHERE CodRamo LIKE 'INI%' AND CodRamo IS NOT NULL
        ORDER BY CodRamo
    """)
    ramos = cur.fetchall()
    if ramos:
        for row in ramos:
            print(f"  '{row['CodRamo']}'")
    else:
        print("  (ninguno con prefijo INI%)")
except Exception as e:
    print(f"  ERROR: {e}")

# ── 6. Investigación de proyectos con discrepancias ──────────────────────────
print("\n=== Investigación de CodProyectos con discrepancias ===")
for cod in ['24479', '24003', '24697']:
    print(f"\n--- Proyecto '{cod}' ---")

    # ¿Existe en tblProyectos y con qué formato exacto?
    cur.execute("""
        SELECT CodProyecto, CodRamo, CodProyectoOracle, CodSubtareaOracle
        FROM tblProyectos
        WHERE CodProyecto LIKE %s
    """, (f'%{cod}%',))
    rows = cur.fetchall()
    print(f"  tblProyectos ({len(rows)} fila/s):")
    for r in rows:
        print(f"    CodProyecto='{r['CodProyecto']}' | CodRamo='{r['CodRamo']}' "
              f"| Oracle={r['CodProyectoOracle']}.{r['CodSubtareaOracle']}")

    # ¿Existe en tblTransacciones y con qué formato exacto?
    cur.execute("""
        SELECT DISTINCT CodProyecto, COUNT(*) AS n
        FROM tblTransacciones
        WHERE CodProyecto LIKE %s
        GROUP BY CodProyecto
    """, (f'%{cod}%',))
    rows = cur.fetchall()
    print(f"  tblTransacciones ({len(rows)} valor/es distinto/s de CodProyecto):")
    for r in rows:
        print(f"    CodProyecto='{r['CodProyecto']}'  ({r['n']} filas)")

    # ¿El JOIN directo funciona?
    cur.execute("""
        SELECT COUNT(*) AS join_directo
        FROM tblTransacciones t
        INNER JOIN tblProyectos p ON t.CodProyecto = p.CodProyecto
        WHERE t.CodProyecto LIKE %s
    """, (f'%{cod}%',))
    r = cur.fetchone()
    print(f"  JOIN directo (=):     {r['join_directo']} filas")

    # ¿El JOIN con LTRIM/RTRIM funciona?
    cur.execute("""
        SELECT COUNT(*) AS join_trim
        FROM tblTransacciones t
        INNER JOIN tblProyectos p
               ON LTRIM(RTRIM(t.CodProyecto)) = LTRIM(RTRIM(p.CodProyecto))
        WHERE t.CodProyecto LIKE %s
    """, (f'%{cod}%',))
    r = cur.fetchone()
    print(f"  JOIN con LTRIM/RTRIM: {r['join_trim']} filas")

conn.close()
print("\n--- Fin del diagnóstico ---")
input("\nPresiona Enter para cerrar...")
