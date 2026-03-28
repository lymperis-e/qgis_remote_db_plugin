"""
This component was largely copied from [Quick Map Services](https://plugins.qgis.org/plugins/quick_map_services),
specifically from the file *qms_service_toolbox.py*. Kudos to the developers of QMS!

Re-used under GNU GENERAL PUBLIC LICENSE v.2

"""

from qgis.PyQt.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QSizePolicy,
    QGridLayout,
    QMenu,
    QAction,
    QMessageBox,
    QDialog,
)
from qgis.PyQt.QtCore import Qt, pyqtSignal

from .EditConnectionDialog import EditConnectionDialog
from .Connection import Connection
from .ConnectionOperationRunner import ConnectionOperationRunner
from .utils.logger import PLUGIN_LOGGER


class ConnectionListItem(QWidget):
    connectionDeleted = pyqtSignal()
    connectionEdited = pyqtSignal()

    def __init__(self, connection: Connection, connectionManager, parent=None):
        QWidget.__init__(self, parent)

        self.connection: Connection = connection
        self.connectionManager = connectionManager

        # QLayout
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 10, 5, 10)
        self.setLayout(self.layout)

        self.service_icon = QLabel(self)
        self.service_icon.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.service_icon.resize(24, 24)

        # Status dot
        self.status_label = QLabel(self)
        self.status_label.setTextFormat(Qt.TextFormat.RichText)
        self.status_label.setText("\u2022")

        self.layout.addWidget(self.status_label)

        # Description layout
        self.service_desc_layout = QGridLayout()
        self.service_desc_layout.setSpacing(0)
        self.layout.addLayout(self.service_desc_layout)

        # Name
        self.service_name = QLabel(self)
        self.service_name.setTextFormat(Qt.TextFormat.RichText)
        self.service_name.setWordWrap(True)
        self.service_name.setText(
            f"   <strong> {connection.name} </strong> {connection.host}"
        )
        self.service_desc_layout.addWidget(self.service_name, 0, 0, 1, 3)

        # Info
        self.service_type = QLabel(self)
        self.service_type.setTextFormat(Qt.TextFormat.RichText)
        self.service_type.setWordWrap(False)
        self.service_type.setText(
            f"   remote: {connection.remote_port}, local: {connection.local_port}"
        )
        self.service_type.setStyleSheet("color: blue; font-size: 10px")
        self.service_desc_layout.addWidget(self.service_type, 1, 0)

        self.connection_status_text = QLabel(self)
        self.connection_status_text.setTextFormat(Qt.TextFormat.RichText)
        self.connection_status_text.setWordWrap(False)
        self.connection_status_text.setStyleSheet(
            "color: #6b7280; font-size: 10px; padding-left: 8px;"
        )
        self.connection_status_text.setText("Not connected")
        self.service_desc_layout.addWidget(self.connection_status_text, 1, 1)

        if self.connection.is_connected:
            self.report_status("connected", "")
        else:
            self.report_status("disconnected", "")

        self.service_desc_layout.setColumnStretch(2, 1)

        # Connect Button
        self.connectButton = QToolButton()
        if self.connection.is_connected:
            self._set_button_state("disconnect")
        else:
            self._set_button_state("connect")

        self.layout.addWidget(self.connectButton)

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.showContextMenu)

        self.operation_runner = ConnectionOperationRunner(self.connection, self)
        self.operation_runner.operationFinished.connect(
            self._on_connection_operation_finished
        )

    def connect(self):
        if self.operation_runner.has_active_operation():
            return

        self.report_status("connecting", "")
        self._set_button_state("connecting")
        self.operation_runner.start_connect()

    def disconnect(self):
        if self.operation_runner.has_active_operation():
            return

        self.report_status("disconnecting", "")
        self._set_button_state("disconnecting")
        self.operation_runner.start_disconnect()

    def _on_connection_operation_finished(self, operation, success, error_message):

        if operation == "connect":
            if success:
                bind_port = self.connection.local_port
                if self.connection._server and getattr(
                    self.connection._server, "local_bind_port", None
                ):
                    bind_port = self.connection._server.local_bind_port

                self.report_status(
                    "connected",
                    f"> Tunnel opened. Forwarding remote service to local port {bind_port}",
                )
                self._set_button_state("disconnect")
                return

            PLUGIN_LOGGER.warning(error_message)
            if "timed out" in (error_message or "").lower():
                self.report_status(
                    "timed_out",
                    f"> Connection timed out: {error_message}",
                )
            else:
                self.report_status(
                    "error",
                    f"> Connection failed: {error_message or 'See Python Console for details'}",
                )
            self._set_button_state("connect")
            return

        if operation == "disconnect":
            if success:
                self.report_status(
                    "disconnected",
                    f"> Connection {self.connection.name} disconnected",
                )
                self._set_button_state("connect")
                return

            PLUGIN_LOGGER.warning(error_message)
            self.report_status(
                "error",
                f"> Disconnection failed: {error_message or 'See Python Console for details'}",
            )
            if self.connection.is_connected:
                self._set_button_state("disconnect")
            else:
                self._set_button_state("connect")

    def _set_button_state(self, state):
        try:
            self.connectButton.clicked.disconnect()
        except TypeError:
            pass

        if state == "connect":
            self.connectButton.setEnabled(True)
            self.connectButton.setText(self.tr("Connect"))
            self.connectButton.clicked.connect(self.connect)
            return

        if state == "disconnect":
            self.connectButton.setEnabled(True)
            self.connectButton.setText(self.tr("Disconnect"))
            self.connectButton.clicked.connect(self.disconnect)
            return

        if state == "connecting":
            self.connectButton.setEnabled(False)
            self.connectButton.setText(self.tr("Connecting..."))
            return

        if state == "disconnecting":
            self.connectButton.setEnabled(False)
            self.connectButton.setText(self.tr("Disconnecting..."))
            return

    def report_status(self, status, message):
        """
        Sets the status label
        """
        if status == "connected":
            self.status_label.setStyleSheet("color: green; font-size: 30px")
            self.connection_status_text.setStyleSheet(
                "color: #166534; font-size: 10px; padding-left: 8px"
            )
            self.connection_status_text.setText("Connected")
            return

        if status == "connecting":
            self.status_label.setStyleSheet("color: orange; font-size: 30px")
            self.connection_status_text.setStyleSheet(
                "color: #9a3412; font-size: 10px; padding-left: 8px"
            )
            self.connection_status_text.setText("Connecting...")
            return

        if status == "disconnecting":
            self.status_label.setStyleSheet("color: orange; font-size: 30px")
            self.connection_status_text.setStyleSheet(
                "color: #9a3412; font-size: 10px; padding-left: 8px"
            )
            self.connection_status_text.setText("Disconnecting...")
            return

        if status == "disconnected":
            self.status_label.setStyleSheet("color: gray; font-size: 30px")
            self.connection_status_text.setStyleSheet(
                "color: #6b7280; font-size: 10px; padding-left: 8px"
            )
            self.connection_status_text.setText("Not connected")
            return

        if status == "timed_out":
            self.status_label.setStyleSheet("color: #f59e0b; font-size: 30px")
            self.connection_status_text.setStyleSheet(
                "color: #92400e; font-size: 10px; padding-left: 8px"
            )
            self.connection_status_text.setText("Timed out")
            return

        if status == "error":
            self.status_label.setStyleSheet("color: red; font-size: 30px")
            self.connection_status_text.setStyleSheet(
                "color: #991b1b; font-size: 10px; padding-left: 8px"
            )
            self.connection_status_text.setText("Failed")

    def showContextMenu(self, point):
        menu = QMenu(self)

        action1 = QAction("Edit connection", self)
        action1.triggered.connect(self.edit_connection_dialog)
        action1.setEnabled(
            not self.connection.is_connected
        )  # disable editing while connected

        action2 = QAction("Delete connection", self)
        action2.triggered.connect(self.delete_connection)
        action2.setEnabled(
            not self.connection.is_connected
        )  # disable deletion while connected
        menu.addAction(action1)
        menu.addAction(action2)

        menu.exec(self.mapToGlobal(point))

    def delete_connection(self):
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            "Are you sure you want to delete the selected object?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        # If the user clicked 'Yes', call the delObj() function
        if reply == QMessageBox.StandardButton.Yes:
            self.connectionManager.remove_connection(self.connection)
            self.connectionDeleted.emit()

    def shutdown(self):
        """Stop any in-flight operation and disconnect synchronously.

        Call this before the plugin closes or unloads.
        """
        self.operation_runner.shutdown()

    def edit_connection_dialog(self):
        dialog = EditConnectionDialog(self.connection.parameters)
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted:
            connection_info = dialog.get_connection_info()

            try:
                self.connectionManager.edit_connection(
                    connection=self.connection, parameters=connection_info
                )

                # Repopulate connections list
                self.connectionEdited.emit()

            # Duplicate connection Name
            except ReferenceError as e:
                notify_user = QMessageBox(self)
                notify_user.setText(str(e))
                notify_user.exec()

            # Invalid port
            except ValueError as e:
                notify_user = QMessageBox(self)
                notify_user.setText(str(e))
                notify_user.exec()

            except Exception as e:
                error_message = QMessageBox(self)
                error_message.setText(f"An error occurred: {str(e)}")
                error_message.exec()
