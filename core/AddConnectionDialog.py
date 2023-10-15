from PyQt5.QtWidgets import (
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QCheckBox,
    QFileDialog,
    QPushButton,
    QVBoxLayout,
)
from PyQt5.QtGui import QIntValidator
from PyQt5.QtCore import Qt
from qgis.gui import QgsPasswordLineEdit, QgsFileWidget


class AddConnectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Connection")

        # Create form layout
        self.form_layout = QFormLayout()

        self.security_notif_label = QLabel()
        self.security_notif_label.setTextFormat(Qt.RichText)
        self.security_notif_label.setWordWrap(True)
        self.security_notif_label.setText(
            "Warning: This information is stored in <strong>plain text</strong>"
        )
        self.form_layout.addRow(self.security_notif_label)

        # Add fields to form layout
        self.name_field = QLineEdit()
        self.form_layout.addRow(QLabel("Name:"), self.name_field)

        self.host_field = QLineEdit()
        self.form_layout.addRow(QLabel("Host:"), self.host_field)

        self.ssh_port_field = QLineEdit()
        self.ssh_port_field.setValidator(QIntValidator(1001, 65535, self))
        self.form_layout.addRow(QLabel("SSH Port:"), self.ssh_port_field)

        self.remote_port_field = QLineEdit()
        self.remote_port_field.setValidator(QIntValidator(1001, 65535, self))
        self.form_layout.addRow(QLabel("Remote Port:"), self.remote_port_field)

        self.local_port_field = QLineEdit()
        self.local_port_field.setValidator(QIntValidator(1001, 65535, self))
        self.form_layout.addRow(QLabel("Local Port:"), self.local_port_field)

        self.username_field = QLineEdit()
        self.form_layout.addRow(QLabel("Username:"), self.username_field)

        self.password_field = QgsPasswordLineEdit()
        self.form_layout.addRow(QLabel("Password:"), self.password_field)

        self.use_id_file = QCheckBox()
        self.form_layout.addRow(QLabel("Use Private Key File:"), self.use_id_file)

        self.id_file_field = QgsFileWidget()
        self.if_file_label = QLabel("Private Key File:")
        self.form_layout.addRow(self.if_file_label, self.id_file_field)

        self.pkey_password_field = QgsPasswordLineEdit()
        self.pkey_password_label = QLabel("Private Key Password:")
        self.form_layout.addRow(self.pkey_password_label, self.pkey_password_field)

        self.ssh_proxy_enabled_field = QCheckBox()
        self.form_layout.addRow(QLabel("Use Proxy:"), self.ssh_proxy_enabled_field)

        self.ssh_proxy_field = QLineEdit()
        self.ssh_proxy_label = QLabel("Proxy Host:")
        self.form_layout.addRow(self.ssh_proxy_label, self.ssh_proxy_field)

        # Add buttons to form layout
        self.button_box = QVBoxLayout()

        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        self.button_box.addWidget(self.ok_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        self.button_box.addWidget(self.cancel_button)

        self.form_layout.addRow(self.button_box)

        # Set layout
        self.setLayout(self.form_layout)

        # Only if use_id_file is checked, show the following fields: id_file_field, pkey_password_field
        # Only if ssh_proxy_enabled is checked, show the following fields: ssh_proxy_field
        self.use_id_file.stateChanged.connect(self.toggle_id_file_fields)
        self.ssh_proxy_enabled_field.stateChanged.connect(self.toggle_ssh_proxy_fields)

        self.toggle_id_file_fields()
        self.toggle_ssh_proxy_fields()

    def toggle_id_file_fields(self):
        if self.use_id_file.isChecked():
            self.if_file_label.show()
            self.pkey_password_label.show()
            self.id_file_field.show()
            self.pkey_password_field.show()
        else:
            self.if_file_label.hide()
            self.pkey_password_label.hide()
            self.id_file_field.hide()
            self.pkey_password_field.hide()

    def toggle_ssh_proxy_fields(self):
        if self.ssh_proxy_enabled_field.isChecked():
            self.ssh_proxy_label.show()
            self.ssh_proxy_field.show()
        else:
            self.ssh_proxy_label.hide()
            self.ssh_proxy_field.hide()

    def get_text_or_none(self, field):
        return field.text() if field.text() and len(field.text()) > 0 else None

    def get_path_or_none(self, field):
        return (
            field.filePath() if field.filePath() and len(field.filePath()) > 0 else None
        )

    def get_checked_or_none(self, field):
        return field.isChecked() if field.isChecked() else None

    def get_connection_info(self):
        connection_info = {
            "name": self.name_field.text(),
            "host": self.host_field.text(),
            "ssh_port": self.ssh_port_field.text(),
            "remote_port": self.remote_port_field.text(),
            "local_port": self.local_port_field.text(),
            "username": self.username_field.text(),
            "password": self.get_text_or_none(self.password_field),
            "id_file": self.get_path_or_none(self.id_file_field),
            "pkey_password": self.get_text_or_none(self.pkey_password_field)
            if self.use_id_file.isChecked()
            else None,
            "ssh_proxy": self.get_text_or_none(self.ssh_proxy_field)
            if self.ssh_proxy_enabled_field.isChecked()
            else None,
            "ssh_proxy_enabled": self.get_checked_or_none(self.ssh_proxy_enabled_field),
        }
        return connection_info
