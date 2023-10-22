import json
import os
from .Connection import Connection


class ConnectionManager:
    def __init__(self):
        self.SETTINGS_FOLDER = None
        self.CONNECTIONS_FILE = None

        self.available_connections = None
        self.open_connections = None

        self.SETTINGS_FOLDER = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "settings"
        )
        self.CONNECTIONS_FILE = os.path.join(self.SETTINGS_FOLDER, "connections.json")
        self.available_connections = self.load_connections()
        self.open_connections = list()

    def _unload(self):
        self.CONNECTIONS_FILE = None
        self.available_connections = None
        self.open_connections = None

    def create_empty_settings(self):
        with open(self.CONNECTIONS_FILE, "w") as f:
            json.dump({"connections": list()}, f)

    def settings_exist(self):
        """
        Checks if the *connections* file exists, if not raises a FileNotFound error

        Raises:
            FileNotFoundError: The connections.json file which stores connections/credentials was not found

        Returns:
            Boolean: only returns True, if no error was encountered
        """
        if not os.path.exists(self.CONNECTIONS_FILE):
            self.create_empty_settings()
            # raise FileNotFoundError(
            #    "The connections.json file could not be found. You may need to reinstall the plugin and load all your connections again :(")

        return True

    def load_connections(self):
        """
        Loads the list of connections & credentials from the *connections* file
        """
        self.settings_exist()

        with open(self.CONNECTIONS_FILE, "r") as f:
            data = json.load(f)["connections"]

            available_connections = list()
            for param in data:
                connectionInstance = Connection(param)
                available_connections.append(connectionInstance)

            return available_connections

    def save_connections(self):
        """
        Saves the list of connections & credentials to the *connections* file
        """
        self.settings_exist()

        connections_list = list()
        for conn in self.available_connections:
            connections_list.append(conn.parameters)

        with open(self.CONNECTIONS_FILE, "w") as f:
            json.dump({"connections": connections_list}, f)

    def refresh_connections(self):
        """
        Searches settings for changes and loads any new connections
        """
        self.settings_exist()

        with open(self.CONNECTIONS_FILE, "r") as f:
            data = json.load(f)["connections"]

            for param in data:
                # Check if connection exists \
                loaded_connection_names = [
                    conn.name for conn in self.available_connections
                ]
                if not param["name"] in loaded_connection_names:
                    self.available_connections.append(Connection(param))

    def add_connection(self, parameters):
        new_conn_params = self.validate_parameters(parameters)

        # ensure that connection names are unique
        if new_conn_params["name"] in [
            conn.name for conn in self.available_connections
        ]:
            raise ReferenceError(
                "A connection with this name already exists. Please choose a different one"
            )

        connectionInstance = Connection(new_conn_params)
        self.available_connections.append(connectionInstance)
        self.save_connections()

    def edit_connection(self, connection, parameters):
        new_conn_params = self.validate_parameters(parameters)

        # Delete old instance
        self.available_connections.remove(connection)

        # Add new connection
        connectionInstance = Connection(new_conn_params)
        self.available_connections.append(connectionInstance)
        self.save_connections()

    def remove_connection(self, connection):
        self.available_connections.remove(connection)
        self.save_connections()

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
