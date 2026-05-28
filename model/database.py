import os
import sys
import threading
import pymssql
from dotenv import load_dotenv


def get_env_path() -> str:
    """Ruta absoluta al archivo .env según si corre como exe o en desarrollo."""
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), ".env")
    # Desarrollo: raíz del proyecto (un nivel arriba de model/)
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")


def write_env(server: str, database: str, username: str, password: str) -> None:
    """Escribe las credenciales en .env y reinicia la conexión."""
    path = get_env_path()
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            f"DB_SERVER_SQLSERVER={server}\n"
            f"DB_NAME_SQLSERVER={database}\n"
            f"DB_USERNAME_SQLSERVER={username}\n"
            f"DB_PASSWORD_SQLSERVER={password}\n"
        )
    load_dotenv(dotenv_path=path, override=True)
    _manager.reset()


load_dotenv(dotenv_path=get_env_path())


class _ConnectionManager:
    """
    Mantiene una sola conexión persistente al servidor SQL Server vía pymssql.
    pymssql implementa el protocolo TDS directamente sin depender de ODBC,
    evitando problemas de negociación TLS del stack ODBC de Windows.
    """

    def __init__(self):
        self._conn = None
        self._lock = threading.Lock()

    def reset(self) -> None:
        """Cierra la conexión actual para que se reconecte con las nuevas credenciales."""
        with self._lock:
            self._close_silently(self._conn)
            self._conn = None

    def get(self) -> pymssql.Connection:
        with self._lock:
            if self._conn is None:
                self._conn = self._connect()
            else:
                self._conn = self._validate_or_reconnect(self._conn)
            return self._conn

    def _connect(self) -> pymssql.Connection:
        server = os.getenv("DB_SERVER_SQLSERVER")
        database = os.getenv("DB_NAME_SQLSERVER")
        username = os.getenv("DB_USERNAME_SQLSERVER")
        password = os.getenv("DB_PASSWORD_SQLSERVER")

        missing = [
            name
            for name, val in {
                "DB_SERVER_SQLSERVER": server,
                "DB_NAME_SQLSERVER": database,
                "DB_USERNAME_SQLSERVER": username,
                "DB_PASSWORD_SQLSERVER": password,
            }.items()
            if not val
        ]
        if missing:
            raise ValueError(
                f"Faltan las siguientes variables en el archivo .env: {', '.join(missing)}"
            )

        return pymssql.connect(
            server=server,
            user=username,
            password=password,
            database=database,
            login_timeout=15,
            as_dict=True,
        )

    def _validate_or_reconnect(self, conn: pymssql.Connection) -> pymssql.Connection:
        try:
            conn.cursor().execute("SELECT 1")
            return conn
        except Exception:
            self._close_silently(conn)
            return self._connect()

    @staticmethod
    def _close_silently(conn):
        try:
            conn.close()
        except Exception:
            pass


_manager = _ConnectionManager()


def get_connection() -> pymssql.Connection:
    """Devuelve la conexión persistente, reconectando si es necesario."""
    return _manager.get()
