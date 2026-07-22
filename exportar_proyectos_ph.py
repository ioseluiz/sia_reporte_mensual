"""
Exporta a CSV todos los proyectos de tblProyectos cuyo NomProyecto contiene 'PH'.
Uso: ejecutar_exportar_ph.bat  (o directamente con el venv)
"""
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from model.database import get_env_path
load_dotenv(dotenv_path=get_env_path())

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas no está instalado. Ejecuta: venv\\Scripts\\pip install pandas")
    input("\nPresiona Enter para cerrar...")
    sys.exit(1)

from model.sia_model import get_proyectos_ph

print("Consultando tblProyectos donde NomProyecto contiene 'PH'...")
try:
    datos = get_proyectos_ph()
except Exception as exc:
    print(f"Error al consultar la base de datos:\n  {exc}")
    input("\nPresiona Enter para cerrar...")
    sys.exit(1)

if not datos:
    print("No se encontraron proyectos con 'PH' en el nombre.")
    input("\nPresiona Enter para cerrar...")
    sys.exit(0)

nombre_archivo = f"Proyectos_PH_{date.today().isoformat()}.csv"
ruta = Path(__file__).parent / nombre_archivo

df = pd.DataFrame(datos)
df.to_csv(ruta, index=False, encoding="utf-8-sig")

print(f"{len(datos)} registros exportados a:\n  {ruta}")
input("\nPresiona Enter para cerrar...")
