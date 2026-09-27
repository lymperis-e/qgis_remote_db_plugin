from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QStyle,
    QVBoxLayout,
)


class ImportSSHConfigDialog(QDialog):
    """Lets the user pick which of the detected SSH config hosts to import."""

    def __init__(self, hosts, config_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import SSH Config")
        self.setMinimumSize(520, 360)
        self._hosts = hosts

        layout = QVBoxLayout(self)

        header = QLabel(f"Hosts found in <b>{config_path}</b>:")
        header.setTextFormat(Qt.TextFormat.RichText)
        header.setWordWrap(True)
        layout.addWidget(header)

        self.hosts_list = QListWidget()
        warning_icon = self.style().standardIcon(
            QStyle.StandardPixmap.SP_MessageBoxWarning
        )
        for index, host in enumerate(hosts):
            item = QListWidgetItem(self._describe(host))
            item.setData(Qt.ItemDataRole.UserRole, index)
            if host.importable:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
                if host.warnings:
                    item.setIcon(warning_icon)
                    item.setToolTip("\n".join(host.warnings))
            else:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                item.setCheckState(Qt.CheckState.Unchecked)
                item.setToolTip(host.problem)
            self.hosts_list.addItem(item)
        self.hosts_list.itemChanged.connect(self._update_import_button)
        layout.addWidget(self.hosts_list)

        hint = QLabel(
            "Review the remote and local ports of the imported connections before "
            "connecting. Hover over a host for details."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.import_button = self.buttons.addButton(
            "Import", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self._update_import_button()

    @staticmethod
    def _describe(host):
        p = host.parameters
        text = (
            f"{p['name']}  —  {p['username']}@{p['host']}:{p['ssh_port']}   "
            f"localhost:{p['local_port']} → {p['remote_bind_address']}:{p['remote_port']}"
        )
        if not host.importable:
            text += f"   ({host.problem})"
        return text

    def _checked_items(self):
        items = (self.hosts_list.item(i) for i in range(self.hosts_list.count()))
        return [
            item for item in items if item.checkState() == Qt.CheckState.Checked
        ]

    def _update_import_button(self, *_):
        count = len(self._checked_items())
        self.import_button.setEnabled(count > 0)
        self.import_button.setText(f"Import ({count})" if count else "Import")

    def selected_parameters(self):
        return [
            self._hosts[item.data(Qt.ItemDataRole.UserRole)].parameters
            for item in self._checked_items()
        ]
