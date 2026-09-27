import os

from .Connection import Connection
from .db.settings_db import DuplicateNameError, SettingsDatabase
from .utils.logger import PLUGIN_LOGGER
from .utils.ssh_config import DetectedHost, load_from_ssh_config


class ConnectionManager:
    def __init__(self, settings_folder=None):
        self.SETTINGS_FOLDER = settings_folder or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "settings"
        )
        self.database = SettingsDatabase(self.SETTINGS_FOLDER)
        self.database.initialize()
        self.available_connections: list[Connection] = self.load_connections()
        self.open_connections: list[Connection] = []

    def _unload(self):
        self.available_connections = []
        self.open_connections = []

    @staticmethod
    def _instantiate(parameters_list):
        connections = []
        for parameters in parameters_list:
            # An unloadable connection is skipped but stays in the database
            try:
                connections.append(Connection(parameters))
            except Exception as e:
                PLUGIN_LOGGER.warning(
                    "Skipping connection '%s': %s", parameters.get("name", ""), e
                )
        return connections

    def load_connections(self) -> list[Connection]:
        """
        Loads the list of connections & credentials from the settings database
        """
        return self._instantiate(self.database.load_parameters())

    def refresh_connections(self):
        """
        Imports a dropped-in connections.json (if any) and loads any new connections
        """
        self.database.initialize()

        loaded_connection_names = {conn.name for conn in self.available_connections}
        new_parameters = [
            parameters
            for parameters in self.database.load_parameters()
            if parameters.get("name", "") not in loaded_connection_names
        ]
        self.available_connections.extend(self._instantiate(new_parameters))

    def add_connection(self, parameters):
        new_conn_params = self.validate_parameters(parameters)

        # ensure that connection names are unique
        if new_conn_params["name"] in [
            conn.name for conn in self.available_connections
        ]:
            raise DuplicateNameError(new_conn_params["name"])

        connectionInstance = Connection(new_conn_params)
        self.database.insert(new_conn_params)
        self.available_connections.append(connectionInstance)

    def edit_connection(self, connection, parameters):
        new_conn_params = self.validate_parameters(parameters)

        if new_conn_params["name"] != connection.name and new_conn_params["name"] in [
            conn.name for conn in self.available_connections
        ]:
            raise DuplicateNameError(new_conn_params["name"])

        connectionInstance = Connection(new_conn_params)
        self.database.update(connection.name, new_conn_params)

        if connection in self.available_connections:
            index = self.available_connections.index(connection)
            self.available_connections[index] = connectionInstance
        else:
            self.available_connections.append(connectionInstance)

    def remove_connection(self, connection):
        self.database.delete(connection.name)
        self.available_connections.remove(connection)

    def detect_ssh_config_hosts(self, config_path=None):
        """
        Returns a DetectedHost for every host of the user's SSH config. Hosts that
        cannot be imported have `problem` set. Raises OSError if the config is unreadable.
        """
        used_local_ports = {conn.local_port for conn in self.available_connections}
        existing_names = {conn.name for conn in self.available_connections}
        hosts = []

        for parameters, warnings in load_from_ssh_config(config_path, used_local_ports):
            host = DetectedHost(parameters, warnings)
            if parameters["name"] in existing_names:
                host.problem = "already exists"
            else:
                try:
                    Connection(self.validate_parameters(parameters))
                except (TypeError, ValueError) as e:
                    host.problem = str(e)
            hosts.append(host)
        return hosts

    def import_connections(self, parameters_list):
        """
        Adds the given connections. Returns (imported names, (name, reason) pairs).
        """
        imported, skipped = [], []
        for parameters in parameters_list:
            try:
                self.add_connection(parameters)
                imported.append(parameters["name"])
            except (ReferenceError, ValueError) as e:
                skipped.append((parameters["name"], str(e)))
        return imported, skipped

    def validate_parameters(self, parameters):
        """
        Check if the parameters given to create a new connection are valid
        """
        return {
            "name": str(parameters["name"]),
            "host": str(parameters["host"]),
            "ssh_port": int(parameters["ssh_port"]),
            "remote_bind_address": str(parameters["remote_bind_address"]),
            "remote_port": int(parameters["remote_port"]),
            "local_port": int(parameters["local_port"]),
            "username": str(parameters["username"]),
            "password": parameters["password"],
            "id_file": parameters["id_file"],
            "pkey_password": parameters["pkey_password"],
            "ssh_proxy": parameters["ssh_proxy"],
            "ssh_proxy_enabled": parameters["ssh_proxy_enabled"],
        }
