from PyQt5.QtWidgets import QDialog, QFormLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout
from PyQt5.QtGui import QIntValidator
from PyQt5.QtCore import Qt
from qgis.gui import QgsPasswordLineEdit
class EditConnectionDialog(QDialog):

    def __init__(self, parameters=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Connection")
        
        self.parameters = parameters

        # Create form layout
        self.form_layout = QFormLayout()
        
        self.security_notif_label = QLabel()
        self.security_notif_label.setTextFormat(Qt.RichText)
        self.security_notif_label.setWordWrap(True)
        self.security_notif_label.setText("Warning: This information is stored in <strong>plain text</strong>")
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
        
        # Add buttons to form layout
        self.button_box = QVBoxLayout()
        
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        self.button_box.addWidget(self.ok_button)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        self.button_box.addWidget(self.cancel_button)
        
        self.form_layout.addRow(self.button_box)
        
        self.setLayout(self.form_layout)

        self.initialize_parameter_values()
        

    def initialize_parameter_values(self):
        self.name_field.setText(self.parameters["name"])
        self.host_field.setText(self.parameters["host"])
        self.ssh_port_field.setText(str(self.parameters["ssh_port"]))
        self.remote_port_field.setText(str(self.parameters["remote_port"]))
        self.local_port_field.setText(str(self.parameters["local_port"]))
        self.username_field.setText(self.parameters["username"])
        self.password_field.setText(self.parameters["password"])



    def get_connection_info(self):
        connection_info = {
            "name": self.name_field.text(),
            "host": self.host_field.text(),
            "ssh_port": self.ssh_port_field.text(),
            "remote_port": self.remote_port_field.text(),
            "local_port": self.local_port_field.text(),
            "username": self.username_field.text(),
            "password": self.password_field.text()
        }
        return connection_info
