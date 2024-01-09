import ipaddress
import re
from .install_packages.check_dependencies import check

DEPENDENCIES_EXIST = False
try:
    from .sshtunnel.sshtunnel import SSHTunnelForwarder

    DEPENDENCIES_EXIST = True
except:
    try:
        check(["paramiko"])
    finally:
        from .sshtunnel.sshtunnel import SSHTunnelForwarder

        DEPENDENCIES_EXIST = True


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
                "Invalid remote host address format (Should be a valid IPv4 address)"
            )

        if not self._validate_ip_or_domain(self.remote_bind_address):
            raise ValueError(
                "Invalid remote bind IP address format (Should be a valid IPv4 address)"
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
        )
        return tunnel_server

    def connect(self):
        if self._server:
            try:
                self._server.start()
                self.is_connected = True

            except Exception as e:
                self.is_connected = False
                print(e)

    def disconnect(self):
        if self._server:
            self._server.stop()
            self.is_connected = False
