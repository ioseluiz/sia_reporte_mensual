from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QLabel, QDialogButtonBox, QHBoxLayout,
)
from PyQt6.QtCore import Qt, QRunnable, QThreadPool, QObject, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont


class _TestSignals(QObject):
    done = pyqtSignal(bool, str)


class _TestWorker(QRunnable):
    def __init__(self, server, database, username, password):
        super().__init__()
        self._server = server
        self._database = database
        self._username = username
        self._password = password
        self.signals = _TestSignals()

    @pyqtSlot()
    def run(self):
        try:
            import pymssql
            conn = pymssql.connect(
                server=self._server,
                user=self._username,
                password=self._password,
                database=self._database,
                login_timeout=10,
                as_dict=True,
            )
            conn.close()
            self.signals.done.emit(True, "Conexión exitosa")
        except Exception as exc:
            self.signals.done.emit(False, str(exc))


class SettingsDialog(QDialog):
    """Diálogo para configurar y guardar las credenciales de conexión a SQL Server."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar conexión a la base de datos")
        self.setMinimumWidth(500)
        self.setModal(True)
        self._pool = QThreadPool.globalInstance()
        self._setup_ui()
        self._load_current_values()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        title = QLabel("Credenciales de conexión a SQL Server")
        font = QFont()
        font.setBold(True)
        font.setPointSize(10)
        title.setFont(font)
        layout.addWidget(title)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(8)

        self.txt_server = QLineEdit()
        self.txt_server.setPlaceholderText("ej. agsqlpro-lst.canal.acp")
        form.addRow("Servidor:", self.txt_server)

        self.txt_database = QLineEdit()
        self.txt_database.setPlaceholderText("ej. SIADB")
        form.addRow("Base de datos:", self.txt_database)

        self.txt_username = QLineEdit()
        form.addRow("Usuario:", self.txt_username)

        self.txt_password = QLineEdit()
        self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Contraseña:", self.txt_password)

        layout.addLayout(form)

        # Botón de prueba
        test_row = QHBoxLayout()
        self.btn_test = QPushButton("Probar conexión")
        self.btn_test.clicked.connect(self._test_connection)
        test_row.addWidget(self.btn_test)
        test_row.addStretch()
        layout.addLayout(test_row)

        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        # Ruta del archivo .env
        from model.database import get_env_path
        lbl_path = QLabel(f"Las credenciales se guardan en:\n{get_env_path()}")
        lbl_path.setStyleSheet("color: gray; font-size: 8pt;")
        lbl_path.setWordWrap(True)
        layout.addWidget(lbl_path)

        # Botones Guardar / Cancelar
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.button(QDialogButtonBox.StandardButton.Save).setText("Guardar")
        btn_box.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        btn_box.accepted.connect(self._save)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    # ------------------------------------------------------------------
    # Lógica
    # ------------------------------------------------------------------

    def _load_current_values(self):
        from dotenv import dotenv_values
        from model.database import get_env_path
        vals = dotenv_values(get_env_path())
        self.txt_server.setText(vals.get("DB_SERVER_SQLSERVER", ""))
        self.txt_database.setText(vals.get("DB_NAME_SQLSERVER", ""))
        self.txt_username.setText(vals.get("DB_USERNAME_SQLSERVER", ""))
        self.txt_password.setText(vals.get("DB_PASSWORD_SQLSERVER", ""))

    def _test_connection(self):
        self.btn_test.setEnabled(False)
        self.lbl_status.setText("Probando conexión…")
        self.lbl_status.setStyleSheet("color: gray")
        worker = _TestWorker(
            self.txt_server.text().strip(),
            self.txt_database.text().strip(),
            self.txt_username.text().strip(),
            self.txt_password.text(),
        )
        worker.signals.done.connect(self._on_test_done)
        self._pool.start(worker)

    def _on_test_done(self, success: bool, message: str):
        self.btn_test.setEnabled(True)
        if success:
            self.lbl_status.setText(f"✓ {message}")
            self.lbl_status.setStyleSheet("color: green")
        else:
            self.lbl_status.setText(f"✗ {message}")
            self.lbl_status.setStyleSheet("color: red")

    def _save(self):
        server   = self.txt_server.text().strip()
        database = self.txt_database.text().strip()
        username = self.txt_username.text().strip()
        password = self.txt_password.text()

        if not all([server, database, username, password]):
            self.lbl_status.setText("Todos los campos son obligatorios.")
            self.lbl_status.setStyleSheet("color: red")
            return

        from model.database import write_env
        try:
            write_env(server, database, username, password)
        except OSError as exc:
            self.lbl_status.setText(f"Error al guardar: {exc}")
            self.lbl_status.setStyleSheet("color: red")
            return

        self.accept()
