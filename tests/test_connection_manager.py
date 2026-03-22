import importlib
import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from test_helpers import (
    ensure_project_root_on_path,
    install_qgis_stub,
    install_sshtunnel_stub,
)


ensure_project_root_on_path()
install_qgis_stub()
install_sshtunnel_stub()

manager_module = importlib.import_module("src.core.ConnectionManager")
ConnectionManager = manager_module.ConnectionManager


class FakeConnection:
    def __init__(self, parameters):
        self.parameters = parameters
        self.name = parameters.get("name", "")


class TestConnectionManager(unittest.TestCase):
    def _build_manager(self, temp_dir):
        manager = ConnectionManager.__new__(ConnectionManager)
        manager.SETTINGS_FOLDER = temp_dir
        manager.CONNECTIONS_FILE = os.path.join(temp_dir, "connections.json")
        manager.available_connections = []
        manager.open_connections = []
        return manager

    def _params(self, name="conn1"):
        return {
            "name": name,
            "host": "127.0.0.1",
            "ssh_port": "22",
            "remote_bind_address": "127.0.0.1",
            "remote_port": "5432",
            "local_port": "15432",
            "username": "user",
            "password": "pass",
            "id_file": "",
            "pkey_password": "",
            "ssh_proxy": "",
            "ssh_proxy_enabled": False,
        }

    def test_settings_exist_creates_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = self._build_manager(temp_dir)
            self.assertFalse(os.path.exists(manager.CONNECTIONS_FILE))

            result = manager.settings_exist()

            self.assertTrue(result)
            self.assertTrue(os.path.exists(manager.CONNECTIONS_FILE))

    def test_save_then_load_connections_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = self._build_manager(temp_dir)
            manager.available_connections = [FakeConnection(self._params())]

            manager.save_connections()

            with patch("src.core.ConnectionManager.Connection", FakeConnection):
                loaded = manager.load_connections()

            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].name, "conn1")
            self.assertEqual(loaded[0].parameters["remote_port"], "5432")

    def test_add_connection_rejects_duplicate_name(self):
        manager = self._build_manager(tempfile.gettempdir())
        manager.available_connections = [FakeConnection(self._params(name="dupe"))]
        manager.save_connections = Mock()

        with self.assertRaises(ReferenceError):
            manager.add_connection(self._params(name="dupe"))

    def test_refresh_connections_adds_only_new_names(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = self._build_manager(temp_dir)
            manager.available_connections = [
                FakeConnection(self._params(name="existing"))
            ]

            os.makedirs(manager.SETTINGS_FOLDER, exist_ok=True)
            with open(manager.CONNECTIONS_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "connections": [
                            self._params(name="existing"),
                            self._params(name="new_conn"),
                        ]
                    },
                    f,
                )

            with patch("src.core.ConnectionManager.Connection", FakeConnection):
                manager.refresh_connections()

            names = [conn.name for conn in manager.available_connections]
            self.assertEqual(names.count("existing"), 1)
            self.assertIn("new_conn", names)

    def test_validate_parameters_casts_expected_types(self):
        manager = self._build_manager(tempfile.gettempdir())

        validated = manager.validate_parameters(self._params())

        self.assertIsInstance(validated["ssh_port"], int)
        self.assertIsInstance(validated["remote_port"], int)
        self.assertIsInstance(validated["local_port"], int)
        self.assertEqual(validated["host"], "127.0.0.1")

    def test_load_connections_raises_for_corrupted_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = self._build_manager(temp_dir)

            with open(manager.CONNECTIONS_FILE, "w", encoding="utf-8") as f:
                f.write("{not-valid-json")

            with self.assertRaises(json.JSONDecodeError):
                manager.load_connections()

    def test_load_connections_raises_for_missing_connections_key(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = self._build_manager(temp_dir)

            with open(manager.CONNECTIONS_FILE, "w", encoding="utf-8") as f:
                json.dump({"unexpected": []}, f)

            with self.assertRaises(KeyError):
                manager.load_connections()

    def test_refresh_save_cycles_keep_unique_names_and_valid_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = self._build_manager(temp_dir)
            manager.available_connections = [
                FakeConnection(self._params(name="existing"))
            ]

            snapshots = [
                [self._params(name="existing"), self._params(name="new_a")],
                [
                    self._params(name="existing"),
                    self._params(name="new_a"),
                    self._params(name="new_b"),
                ],
                [
                    self._params(name="existing"),
                    self._params(name="new_a"),
                    self._params(name="new_b"),
                ],
            ]

            for snapshot in snapshots:
                with open(manager.CONNECTIONS_FILE, "w", encoding="utf-8") as f:
                    json.dump({"connections": snapshot}, f)

                with patch("src.core.ConnectionManager.Connection", FakeConnection):
                    manager.refresh_connections()

                manager.save_connections()

            names = [conn.name for conn in manager.available_connections]
            self.assertEqual(len(names), len(set(names)))
            self.assertEqual(set(names), {"existing", "new_a", "new_b"})

            with open(manager.CONNECTIONS_FILE, "r", encoding="utf-8") as f:
                persisted = json.load(f)

            persisted_names = [item["name"] for item in persisted["connections"]]
            self.assertEqual(len(persisted_names), len(set(persisted_names)))
            self.assertEqual(set(persisted_names), {"existing", "new_a", "new_b"})


if __name__ == "__main__":
    unittest.main()
