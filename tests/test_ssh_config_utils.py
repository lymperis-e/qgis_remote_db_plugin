import importlib
import unittest
from unittest.mock import patch

from test_helpers import (
    ensure_project_root_on_path,
    install_qgis_stub,
    install_sshtunnel_stub,
    install_sshconf_stub,
)


ensure_project_root_on_path()
install_qgis_stub()
install_sshtunnel_stub()
install_sshconf_stub()

ssh_config_module = importlib.import_module("src.core.utils.ssh_config")


class FakeParsedConfig:
    def __init__(self):
        self._hosts = {
            "dev-db": {"hostname": "10.0.0.5", "user": "alice", "port": 2200},
            "prod-db": {"hostname": "db.example.com", "proxycommand": "ssh jump"},
        }

    def hosts(self):
        return list(self._hosts.keys())

    def host(self, host_name):
        return self._hosts[host_name]


class TestSshConfigUtils(unittest.TestCase):
    def test_parse_ssh_config_returns_host_mapping(self):
        with patch.object(
            ssh_config_module, "read_ssh_config", return_value=FakeParsedConfig()
        ):
            parsed = ssh_config_module.parse_ssh_config("dummy_path")

        self.assertIn("dev-db", parsed)
        self.assertEqual(parsed["dev-db"]["hostname"], "10.0.0.5")
        self.assertIn("prod-db", parsed)

    def test_convert_to_connection_params_maps_and_defaults(self):
        input_config = {
            "dev-db": {"hostname": "10.0.0.5", "port": 2200, "user": "alice"},
            "prod-db": {"hostname": "db.example.com", "proxycommand": "ssh jump"},
        }

        connections = ssh_config_module.convert_to_connection_params(input_config)

        self.assertEqual(len(connections), 2)

        first = connections[0]
        self.assertEqual(first.name, "dev-db")
        self.assertEqual(first.host, "10.0.0.5")
        self.assertEqual(first.ssh_port, 2200)
        self.assertEqual(first.username, "alice")

        second = connections[1]
        self.assertEqual(second.name, "prod-db")
        self.assertEqual(second.password, "changeme")
        self.assertEqual(second.remote_port, 5432)
        self.assertEqual(second.local_port, 5433)
        self.assertEqual(second.ssh_proxy, "ssh jump")


if __name__ == "__main__":
    unittest.main()
