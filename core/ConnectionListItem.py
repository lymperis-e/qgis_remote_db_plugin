"""
This component was largely copied from [Quick Map Services](https://plugins.qgis.org/plugins/quick_map_services),
specifically from the file *qms_service_toolbox.py*. Kudos to the developers of QMS! 

Re-used under GNU GENERAL PUBLIC LICENSE v.2

"""

from __future__ import absolute_import
from os import path
from qgis.PyQt import uic
from qgis.PyQt.QtGui import (
    QImage,
    QPixmap,
    QCursor,
    QFont,
)
from qgis.PyQt.QtWidgets import (
    QApplication,
    QWidget,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QSizePolicy,
    QListWidgetItem,
    QGridLayout,
)
from qgis.PyQt.QtCore import (
    QThread,
    pyqtSignal,
    Qt,
    QTimer,
    QMutex,
    QByteArray
)
from qgis.core import (
    QgsMessageLog,
    QgsGeometry
)

class ConnectionListItem(QWidget):
    def __init__(self, connection, parent=None):
        QWidget.__init__(self, parent)

        self.connection = connection


        # QLayout
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 10, 5, 10)
        self.setLayout(self.layout)

        self.service_icon = QLabel(self)
        self.service_icon.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.service_icon.resize(24, 24)

        # Status dot 
        self.status_label = QLabel(self)
        self.status_label.setTextFormat(Qt.RichText)
        self.status_label.setText(u'\u2022')

        if self.connection.is_connected:
            self.status_label.setStyleSheet("color: green; font-size: 30px")
        else:
            self.status_label.setStyleSheet("color: gray; font-size: 30px")

        self.layout.addWidget(self.status_label)


        # Description layout
        self.service_desc_layout = QGridLayout()
        self.service_desc_layout.setSpacing(0)
        self.layout.addLayout(self.service_desc_layout)

        # Name
        self.service_name = QLabel(self)
        self.service_name.setTextFormat(Qt.RichText)
        self.service_name.setWordWrap(True)
        self.service_name.setText(u"   <strong> {} </strong> {}".format(connection.name, connection.host))
        self.service_desc_layout.addWidget(self.service_name, 0, 0, 1, 3)

        # Info
        self.service_type = QLabel(self)
        self.service_type.setTextFormat(Qt.RichText)
        self.service_type.setWordWrap(False)
        self.service_type.setText(u"   remote: {}, local: {}".format(connection.remote_port, connection.local_port))
        self.service_type.setStyleSheet("color: blue; font-size: 10px")
        self.service_desc_layout.addWidget(self.service_type, 1, 0)

        
        self.service_desc_layout.setColumnStretch(2, 1)


        # Connect Button
        self.connectButton = QToolButton()
        if self.connection.is_connected:
            self.connectButton.setText(self.tr("Disconnect"))
            self.connectButton.clicked.connect(self.disconnect)

        else:
            self.connectButton.setText(self.tr("Connect"))
            self.connectButton.clicked.connect(self.connect)

        self.layout.addWidget(self.connectButton)


        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)


    def connect(self):
        connection = self.connection
        try:
            connection.connect()

            # Report status
            self.report_status(
                "connected", f"> Tunnel opened. Forwarding remote service to local port {connection._server.local_bind_port}")

            # Set the connect button action to disconnect
            self.connectButton.setText("Disconnect")
            self.connectButton.clicked.connect(self.disconnect)

        except Exception as e:
            # Report status
            self.report_status(
                "error", f"> An error occured. Please opmen the Python Console to see more details")
            


    def disconnect(self):
        connection = self.connection

        connection.disconnect()

        # Report status
        self.report_status(
            "disconnected", f"> Connection {connection.name} disconnected")

        # Set the connect button action to disconnect
        self.connectButton.setText("Connect")
        self.connectButton.clicked.connect(self.connect)  
        

    def report_status(self,status,message):
        """
        Sets the status label
        """
        if status == "connected":
            self.status_label.setStyleSheet("color: green; font-size: 30px")

        if status == "disconnected":
            self.status_label.setStyleSheet("color: gray; font-size: 30px")
   

        if status == "error":
            self.status_label.setStyleSheet("color: red; font-size: 30px")
         