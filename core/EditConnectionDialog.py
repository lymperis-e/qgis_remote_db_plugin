from PyQt5.QtWidgets import (
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QCheckBox,
)
from PyQt5.QtGui import QIntValidator, QColor
from PyQt5.QtCore import Qt
from qgis.gui import QgsPasswordLineEdit, QgsFileWidget

from .utils.QtValidators import IPAddressValidator, PortValidator


class EditConnectionDialog(QDialog):
    def __init__(self, parameters=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Connection")

        self.parameters = parameters

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
        # Add fields to form layout
        self.name_field = QLineEdit()
        self.form_layout.addRow(QLabel("Name:"), self.name_field)

        self.host_field = QLineEdit()
        self.form_layout.addRow(QLabel("Host:"), self.host_field)

        self.ssh_port_field = QLineEdit()
        self.ssh_port_field.setValidator(PortValidator())
        self.form_layout.addRow(QLabel("SSH Port:"), self.ssh_port_field)

        self.remote_bind_address_field = QLineEdit()
        self.remote_bind_address_field.setValidator(IPAddressValidator())
        self.form_layout.addRow(
            QLabel("Remote Bind Address:"), self.remote_bind_address_field
        )

        self.remote_port_field = QLineEdit()
        self.remote_port_field.setValidator(PortValidator())
        self.form_layout.addRow(QLabel("Remote Port:"), self.remote_port_field)

        self.local_port_field = QLineEdit()
        self.local_port_field.setValidator(PortValidator())
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
        # Set the layout
        self.setLayout(self.form_layout)

        # Setup all the signals
        self.connect_signals()

        # Initialize parameter values based on current configuration
        self.initialize_parameter_values()

        # Setup gui based on current configuration
        self.toggle_id_file_fields()
        self.toggle_ssh_proxy_fields()

    def connect_signals(self):
        self.ssh_port_field.textChanged.connect(self.validate_and_enable_ok_button)
        self.remote_bind_address_field.textChanged.connect(
            self.validate_and_enable_ok_button
        )
        self.remote_port_field.textChanged.connect(self.validate_and_enable_ok_button)
        self.local_port_field.textChanged.connect(self.validate_and_enable_ok_button)
        self.username_field.textChanged.connect(self.validate_and_enable_ok_button)

        # Only if use_id_file is checked, show the following fields: id_file_field, pkey_password_field
        self.use_id_file.stateChanged.connect(self.toggle_id_file_fields)

        # Only if ssh_proxy_enabled is checked, show the following fields: ssh_proxy_field
        self.ssh_proxy_enabled_field.stateChanged.connect(self.toggle_ssh_proxy_fields)

    def validate_and_enable_ok_button(self):
        field_color = QColor("red")

        # Create a list to store the validation status of all fields
        field_validators = [
            (self.name_field, self.name_field.hasAcceptableInput()),
            (self.ssh_port_field, self.ssh_port_field.hasAcceptableInput()),
            (
                self.remote_bind_address_field,
                self.remote_bind_address_field.hasAcceptableInput(),
            ),
            (self.remote_port_field, self.remote_port_field.hasAcceptableInput()),
            (self.local_port_field, self.local_port_field.hasAcceptableInput()),
            (self.username_field, bool(self.username_field.text())),
        ]

        # Enable the OK button if all validators are True, and set the text color accordingly
        all_valid = all(valid for _, valid in field_validators)

        for field, valid in field_validators:
            if valid:
                field.setStyleSheet("")  # Reset the text color
            else:
                field.setStyleSheet(f"color: {field_color.name()}")

        self.ok_button.setEnabled(all_valid)

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

    def get_parameters(self):
        """
        Load parameters from the current configuration and set the values of the fields
        safely, to handle the case where the parameters are None
        """

        return {
            "name": self.parameters.get("name"),
            "host": self.parameters.get("host"),
            "ssh_port": self.parameters.get("ssh_port"),
            "remote_bind_address": self.parameters.get("remote_bind_address"),
            "remote_port": self.parameters.get("remote_port"),
            "local_port": self.parameters.get("local_port"),
            "username": self.parameters.get("username"),
            "password": self.parameters.get("password"),
            "id_file": self.parameters.get("id_file"),
            "pkey_password": self.parameters.get("pkey_password"),
            "ssh_proxy": self.parameters.get("ssh_proxy"),
            "ssh_proxy_enabled": self.parameters.get("ssh_proxy_enabled"),
        }

    def initialize_parameter_values(self):
        name = str(self.parameters.get("name"))
        host = str(self.parameters.get("host"))
        ssh_port = str(self.parameters.get("ssh_port"))
        remote_bind_address = str(self.parameters.get("remote_bind_address"))
        remote_port = str(self.parameters.get("remote_port"))
        local_port = str(self.parameters.get("local_port"))
        username = str(self.parameters.get("username"))
        password = (
            str(self.parameters.get("password"))
            if self.parameters.get("password")
            else None
        )
        id_file = (
            str(self.parameters.get("id_file"))
            if self.parameters.get("id_file")
            else None
        )
        pkey_password = (
            str(self.parameters.get("pkey_password"))
            if self.parameters.get("pkey_password")
            else None
        )
        ssh_proxy = (
            str(self.parameters.get("ssh_proxy"))
            if self.parameters.get("ssh_proxy")
            else None
        )
        ssh_proxy_enabled = self.parameters.get("ssh_proxy_enabled") is True

        self.name_field.setText(name)
        self.host_field.setText(host)
        self.ssh_port_field.setText(ssh_port)
        self.remote_bind_address_field.setText(remote_bind_address)
        self.remote_port_field.setText(remote_port)
        self.local_port_field.setText(local_port)
        self.username_field.setText(username)
        self.password_field.setText(password)
        self.id_file_field.setFilePath(id_file)
        self.pkey_password_field.setText(pkey_password)
        self.ssh_proxy_field.setText(ssh_proxy)

        # Checkboxes
        self.ssh_proxy_enabled_field.setChecked(ssh_proxy_enabled)

        # If id_file is not None, then use_id_file should be checked
        self.use_id_file.setChecked(id_file is not None)

    def get_connection_info(self):
        connection_info = {
            "name": self.name_field.text(),
            "host": self.host_field.text(),
            "ssh_port": self.ssh_port_field.text(),
            "remote_bind_address": self.remote_bind_address_field.text(),
            "remote_port": self.remote_port_field.text(),
            "local_port": self.local_port_field.text(),
            "username": self.username_field.text(),
            "password": self.get_text_or_none(self.password_field),
            "id_file": self.get_path_or_none(self.id_file_field),
            "pkey_password": self.get_text_or_none(self.pkey_password_field)
            if self.use_id_file.isChecked()
            and self.id_file_field.filePath() is not None
            else None,
            "ssh_proxy": self.get_text_or_none(self.ssh_proxy_field)
            if self.ssh_proxy_enabled_field.isChecked()
            else None,
            "ssh_proxy_enabled": self.get_checked_or_none(self.ssh_proxy_enabled_field),
        }
        return connection_info
