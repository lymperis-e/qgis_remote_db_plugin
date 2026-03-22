import importlib
import unittest

from test_helpers import (
    StubForwarder,
    ensure_project_root_on_path,
    install_qgis_stub,
    install_sshtunnel_stub,
)


ensure_project_root_on_path()
install_qgis_stub()
install_sshtunnel_stub()

connection_module = importlib.import_module("src.core.Connection")
Connection = connection_module.Connection


class TestConnection(unittest.TestCase):
    def setUp(self):
        StubForwarder.reset()

    def _params(self, **overrides):
        base = {
            "name": "db1",
            "host": "127.0.0.1",
            "ssh_port": 22,
            "username": "user",
            "password": "pass",
            "id_file": "",
            "pkey_password": "",
            "ssh_proxy": "",
            "ssh_proxy_enabled": False,
            "remote_bind_address": "127.0.0.1",
            "remote_port": 5432,
            "local_port": 15432,
        }
        base.update(overrides)
        return base

    def test_validate_ip_or_domain(self):
        conn = Connection(self._params())
        self.assertTrue(conn._validate_ip_or_domain("192.168.1.1"))
        self.assertTrue(conn._validate_ip_or_domain("example.com"))
        self.assertFalse(conn._validate_ip_or_domain("bad_host"))

    def test_invalid_host_raises(self):
        with self.assertRaises(ValueError):
            Connection(self._params(host="not a host"))

    def test_connect_success_sets_connected(self):
        conn = Connection(self._params())
        conn.connect()

        self.assertTrue(conn.is_connected)
        self.assertEqual(len(StubForwarder.instances), 1)
        self.assertTrue(StubForwarder.instances[0].started)

    def test_connect_failure_recreates_server(self):
        StubForwarder.fail_next_start = True
        conn = Connection(self._params())
        first_server = conn._server

        conn.connect()

        self.assertFalse(conn.is_connected)
        self.assertTrue(first_server.stopped)
        self.assertIsNot(conn._server, first_server)
        self.assertEqual(len(StubForwarder.instances), 2)

    def test_disconnect_stops_server(self):
        conn = Connection(self._params())
        conn.connect()
        server = conn._server

        conn.disconnect()

        self.assertFalse(conn.is_connected)
        self.assertTrue(server.stopped)


if __name__ == "__main__":
    unittest.main()
