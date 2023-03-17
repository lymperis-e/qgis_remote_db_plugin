from PyQt5.QtWidgets import QDialog, QFormLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout
from PyQt5.QtGui import QIntValidator
from qgis.gui import QgsPasswordLineEdit
class AddConnectionDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Connection")
        
        # Create form layout
        self.form_layout = QFormLayout()
        
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
