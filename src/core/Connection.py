import ipaddress
import re
import logging
from .dependencies import check

DEPENDENCIES_EXIST = False
try:
    from .sshtunnel.sshtunnel import SSHTunnelForwarder

    DEPENDENCIES_EXIST = True
except Exception as e:
    try:
        check(["paramiko", "sshconf"])
    finally:
        from .sshtunnel.sshtunnel import SSHTunnelForwarder

        DEPENDENCIES_EXIST = True

from dataclasses import dataclass

# from .utils.timeout import timeout
from .utils.logger import PLUGIN_LOGGER


@dataclass
class IConnection:
    name: str
    host: str
    ssh_port: int = 22
    username: str = ""
    id_file: str = ""
    pkey_password: str = ""
    ssh_proxy: str = ""
    ssh_proxy_enabled: bool = False
    password: str = ""
    remote_bind_address: str = "127.0.0.1"
    remote_port: int = 22
    local_port: int = 0
    is_connected: bool = False

    # Make the class subscriptable
    def __getitem__(self, key):
        return getattr(self, key, None)


class Connection:
    def __init__(self, connection_params):
        self.parameters = connection_params

        self.name = connection_params.get("name", "")
        self.host = connection_params.get("host", "")
        self.ssh_port = connection_params.get("ssh_port", 22)
        self.user = connection_params.get("username", "")

        self.id_file = connection_params.get("id_file", "")
        self.pkey_password = connection_params.get("pkey_password", "")

        self.ssh_proxy = connection_params.get("ssh_proxy", "")
        self.ssh_proxy_enabled = connection_params.get("ssh_proxy_enabled", False)

        self.password = connection_params.get("password", "")

        self.remote_bind_address = connection_params.get(
            "remote_bind_address", "127.0.0.1"
        )
        self.remote_port = connection_params.get("remote_port", 22)
        self.local_port = connection_params.get("local_port", 0)

        self.logger = PLUGIN_LOGGER

        self._server = self._get_server()
        self.is_connected = False

    def _validate_ip_or_domain(self, input_text):
        # Check if the input is a valid IP address
        try:
            ipaddress.IPv4Address(input_text)
            return True
        except ipaddress.AddressValueError:
            # Check if the input is a valid domain name
            domain_pattern = r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            if re.match(domain_pattern, input_text):
                return True
            return False

    def _get_server(self):
        if not self._validate_ip_or_domain(self.host):
            raise ValueError(
                f"Remote host should be a valid IPv4 address. Got {self.host}"
            )

        if not self._validate_ip_or_domain(self.remote_bind_address):
            raise ValueError(
                f"Remote bind address should be a valid IPv4 address. Got {self.remote_bind_address}"
            )

        tunnel_server = SSHTunnelForwarder(
            self.host,
            ssh_username=self.user,
            ssh_password=self.password,
            ssh_pkey=self.id_file,
            ssh_private_key_password=self.pkey_password,
            ssh_proxy=self.ssh_proxy,
            ssh_proxy_enabled=self.ssh_proxy_enabled,
            remote_bind_address=(self.remote_bind_address, self.remote_port),
            local_bind_address=("0.0.0.0", self.local_port),
            ssh_port=self.ssh_port,
            logger=self.logger,
        )
        return tunnel_server

    def connect(self):
        if self._server:
            try:
                self._server.start()
                self.is_connected = True
            except Exception as e:
                self.is_connected = False

                # Delete server instance to avoid memory leaks and recreate it
                self._server.stop()
                # del self._server
                self._server = None
                self._server = self._get_server()

                print(e)
                print(self._server)
        else:
            raise ValueError("Server is not properly configured.")

    def disconnect(self):
        if self._server:
            self._server.stop()
            self.is_connected = False
