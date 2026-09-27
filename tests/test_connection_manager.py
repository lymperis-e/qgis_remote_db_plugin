import importlib
import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

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
SettingsDatabase = importlib.import_module("src.core.db.settings_db").SettingsDatabase
LegacyConnectionsFile = importlib.import_module(
    "src.core.db.legacy_connections"
).LegacyConnectionsFile


class FakeConnection:
    def __init__(self, parameters):
        if parameters.get("host") == "invalid host":
            raise ValueError("invalid host")
        self.parameters = parameters
        self.name = parameters.get("name", "")


def _params(name="conn1", **overrides):
    params = {
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
    params.update(overrides)
    return params


class ManagerTestCase(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.folder = self._temp.name
        self.json_file = os.path.join(self.folder, "connections.json")
        self.backups = os.path.join(self.folder, ".backups")
        self.backup_file = os.path.join(self.backups, "connections.old.json.bk")
        self.db_file = os.path.join(self.folder, "connections.db")
        patcher = patch("src.core.ConnectionManager.Connection", FakeConnection)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self._temp.cleanup()

    def manager(self):
        return ConnectionManager(settings_folder=self.folder)

    def write_json(self, data, encoding="utf-8"):
        text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
        with open(self.json_file, "w", encoding=encoding) as f:
            f.write(text)

    def db_rows(self):
        db = sqlite3.connect(self.db_file)
        db.row_factory = sqlite3.Row
        try:
            return db.execute("SELECT * FROM connections ORDER BY id").fetchall()
        finally:
            db.close()

    def names(self, manager):
        return [conn.name for conn in manager.available_connections]


class TestLegacyMigration(ManagerTestCase):
    def test_fresh_install_creates_database(self):
        manager = self.manager()

        self.assertTrue(os.path.isfile(self.db_file))
        self.assertFalse(os.path.exists(self.json_file))
        self.assertEqual(manager.available_connections, [])

    def test_creates_missing_settings_folder(self):
        folder = os.path.join(self.folder, "does", "not", "exist")
        manager = ConnectionManager(settings_folder=folder)

        self.assertTrue(os.path.isfile(manager.database.DATABASE_FILE))

    def test_migrates_json_and_renames_it(self):
        self.write_json({"connections": [_params("a"), _params("b")]})
        with open(self.json_file, "rb") as f:
            original = f.read()

        manager = self.manager()

        self.assertEqual(self.names(manager), ["a", "b"])
        self.assertFalse(os.path.exists(self.json_file))
        with open(self.backup_file, "rb") as f:
            self.assertEqual(f.read(), original)
        self.assertEqual([row["name"] for row in self.db_rows()], ["a", "b"])

    def test_settings_folder_only_contains_current_settings(self):
        self.write_json({"connections": [_params("a")]})

        self.manager()

        self.assertEqual(
            sorted(os.listdir(self.folder)), [".backups", "connections.db"]
        )
        self.assertEqual(os.listdir(self.backups), ["connections.old.json.bk"])

    def test_backups_folder_not_created_when_nothing_to_back_up(self):
        self.manager()

        self.assertFalse(os.path.exists(self.backups))

    def test_backups_folder_creation_failure_keeps_json(self):
        self.write_json({"connections": [_params("a")]})
        # A file in place of the folder makes its creation fail
        with open(self.backups, "w", encoding="utf-8") as f:
            f.write("")

        manager = self.manager()

        self.assertEqual(self.names(manager), ["a"])
        self.assertTrue(os.path.isfile(self.json_file))

        os.remove(self.backups)
        manager = self.manager()
        self.assertEqual(self.names(manager), ["a"])
        self.assertEqual(len(self.db_rows()), 1)
        self.assertTrue(os.path.isfile(self.backup_file))
        self.assertFalse(os.path.exists(self.json_file))

    def test_migrated_values_are_typed(self):
        self.write_json({"connections": [_params("a", ssh_proxy_enabled=True)]})

        params = self.manager().available_connections[0].parameters

        self.assertEqual(params["ssh_port"], 22)
        self.assertEqual(params["remote_port"], 5432)
        self.assertEqual(params["local_port"], 15432)
        self.assertIs(params["ssh_proxy_enabled"], True)
        self.assertEqual(params["password"], "pass")

    def test_migration_survives_restart(self):
        self.write_json({"connections": [_params("a")]})
        self.manager()

        manager = self.manager()

        self.assertEqual(self.names(manager), ["a"])
        self.assertEqual(len(self.db_rows()), 1)

    def test_corrupted_json_is_left_untouched(self):
        self.write_json("{not-valid-json")

        manager = self.manager()

        self.assertEqual(manager.available_connections, [])
        self.assertTrue(os.path.isfile(self.json_file))
        self.assertFalse(os.path.exists(self.backup_file))

    def test_missing_connections_key_is_left_untouched(self):
        self.write_json({"unexpected": []})

        self.manager()

        self.assertTrue(os.path.isfile(self.json_file))
        self.assertFalse(os.path.exists(self.backup_file))

    def test_empty_json_file_is_migrated(self):
        self.write_json("")

        manager = self.manager()

        self.assertEqual(manager.available_connections, [])
        self.assertFalse(os.path.exists(self.json_file))
        self.assertTrue(os.path.isfile(self.backup_file))

    def test_bom_and_unicode_are_supported(self):
        self.write_json(
            {"connections": [_params("σύνδεση", password="κωδικός€")]},
            encoding="utf-8-sig",
        )

        manager = self.manager()

        self.assertEqual(self.names(manager), ["σύνδεση"])
        self.assertEqual(
            manager.available_connections[0].parameters["password"], "κωδικός€"
        )

    def test_top_level_list_is_supported(self):
        self.write_json([_params("a")])

        self.assertEqual(self.names(self.manager()), ["a"])

    def test_nulls_missing_keys_and_extra_keys(self):
        entry = {"name": "minimal", "host": "10.0.0.1", "id_file": None, "custom": [1]}
        self.write_json({"connections": [entry]})

        params = self.manager().available_connections[0].parameters

        self.assertEqual(params, {"name": "minimal", "host": "10.0.0.1", "custom": [1]})

    def test_odd_values_do_not_break_migration(self):
        entry = _params(
            "odd",
            ssh_port="not-a-port",
            remote_port=2**80,
            local_port=5433.0,
            password=1234,
            ssh_proxy={"nested": True},
            ssh_proxy_enabled="yes",
        )
        self.write_json({"connections": [entry]})

        params = self.manager().available_connections[0].parameters

        self.assertEqual(params["ssh_port"], "not-a-port")
        self.assertIn("remote_port", params)
        self.assertEqual(params["local_port"], 5433)
        self.assertEqual(params["password"], "1234")
        self.assertEqual(params["ssh_proxy"], '{"nested": true}')
        self.assertEqual(params["ssh_proxy_enabled"], "yes")
        self.assertFalse(os.path.exists(self.json_file))

    def test_duplicate_names(self):
        self.write_json(
            {
                "connections": [
                    _params("dupe"),
                    _params("dupe"),
                    _params("dupe", host="10.0.0.2"),
                ]
            }
        )

        manager = self.manager()

        self.assertEqual(self.names(manager), ["dupe", "dupe (2)"])
        self.assertEqual(
            manager.available_connections[1].parameters["host"], "10.0.0.2"
        )

    def test_nameless_connection_gets_a_name(self):
        entry = _params()
        del entry["name"]
        self.write_json({"connections": [entry]})

        self.assertEqual(self.names(self.manager()), ["Unnamed connection"])

    def test_invalid_entries_are_skipped_but_kept_in_backup(self):
        self.write_json({"connections": [_params("good"), "garbage", 42]})

        manager = self.manager()

        self.assertEqual(self.names(manager), ["good"])
        with open(self.backup_file, encoding="utf-8") as f:
            self.assertIn("garbage", f.read())

    def test_all_entries_invalid_leaves_json_untouched(self):
        self.write_json({"connections": ["garbage"]})

        self.manager()

        self.assertTrue(os.path.isfile(self.json_file))

    def test_reimport_is_idempotent(self):
        self.write_json({"connections": [_params("a"), _params("b")]})
        self.manager()
        # e.g. the rename failed previously, or the user restored the file
        self.write_json({"connections": [_params("a"), _params("b")]})

        manager = self.manager()

        self.assertEqual(self.names(manager), ["a", "b"])
        self.assertEqual(len(self.db_rows()), 2)

    def test_existing_backup_is_not_overwritten(self):
        os.makedirs(self.backups)
        with open(self.backup_file, "w", encoding="utf-8") as f:
            f.write("previous backup")
        self.write_json({"connections": [_params("a")]})

        self.manager()

        with open(self.backup_file, encoding="utf-8") as f:
            self.assertEqual(f.read(), "previous backup")
        self.assertTrue(
            os.path.isfile(os.path.join(self.backups, "connections.old.1.json.bk"))
        )
        self.assertFalse(os.path.exists(self.json_file))

    def test_rename_failure_falls_back_to_copy(self):
        self.write_json({"connections": [_params("a")]})

        with patch(
            "src.core.db.legacy_connections.os.rename",
            side_effect=OSError,
        ):
            manager = self.manager()

        self.assertEqual(self.names(manager), ["a"])
        self.assertFalse(os.path.exists(self.json_file))
        self.assertTrue(os.path.isfile(self.backup_file))

    def test_json_kept_when_it_cannot_be_moved(self):
        self.write_json({"connections": [_params("a")]})

        with patch(
            "src.core.db.legacy_connections.os.rename",
            side_effect=OSError,
        ), patch(
            "src.core.db.legacy_connections.os.remove",
            side_effect=OSError,
        ):
            manager = self.manager()

        self.assertEqual(self.names(manager), ["a"])
        self.assertTrue(os.path.isfile(self.json_file))

    def test_database_failure_during_migration_rolls_back(self):
        self.write_json({"connections": [_params("a"), _params("b")]})
        original_insert = SettingsDatabase._insert
        calls = []

        def flaky_insert(db, values, extra):
            calls.append(values["name"])
            if len(calls) == 2:
                raise sqlite3.OperationalError("database or disk is full")
            original_insert(db, values, extra)

        with patch.object(SettingsDatabase, "_insert", staticmethod(flaky_insert)):
            self.manager()

        self.assertTrue(os.path.isfile(self.json_file))
        self.assertFalse(os.path.exists(self.backup_file))
        self.assertEqual(len(self.db_rows()), 0)

        # Retried successfully on next start
        self.assertEqual(self.names(self.manager()), ["a", "b"])

    def test_unusable_database_falls_back_to_json(self):
        self.write_json({"connections": [_params("a")]})

        with patch(
            "src.core.db.settings_db.sqlite3.connect",
            side_effect=sqlite3.OperationalError("unable to open database file"),
        ):
            manager = self.manager()

        self.assertEqual(self.names(manager), ["a"])
        self.assertTrue(os.path.isfile(self.json_file))

    def test_corrupt_database_is_moved_aside(self):
        with open(self.db_file, "wb") as f:
            f.write(b"this is not a sqlite database" * 100)
        self.write_json({"connections": [_params("a")]})

        manager = self.manager()

        self.assertEqual(self.names(manager), ["a"])
        self.assertTrue(
            os.path.isfile(os.path.join(self.backups, "connections.corrupt.db.bk"))
        )
        self.assertEqual(
            sorted(os.listdir(self.folder)), [".backups", "connections.db"]
        )

    def test_unloadable_connection_is_not_deleted(self):
        self.write_json(
            {"connections": [_params("bad", host="invalid host"), _params("good")]}
        )
        manager = self.manager()
        self.assertEqual(self.names(manager), ["good"])

        manager.add_connection(_params("other"))
        manager.remove_connection(manager.available_connections[0])

        self.assertEqual([row["name"] for row in self.db_rows()], ["bad", "other"])

    # ------------------------------------------------------------ file shapes

    def test_empty_connections_list_is_migrated(self):
        self.write_json({"connections": []})

        self.assertEqual(self.manager().available_connections, [])
        self.assertFalse(os.path.exists(self.json_file))
        self.assertTrue(os.path.isfile(self.backup_file))

    def test_whitespace_only_file_is_migrated(self):
        self.write_json("  \n\t ")

        self.manager()

        self.assertFalse(os.path.exists(self.json_file))
        self.assertTrue(os.path.isfile(self.backup_file))

    def test_null_connections_is_migrated(self):
        self.write_json({"connections": None})

        self.manager()

        self.assertFalse(os.path.exists(self.json_file))
        self.assertTrue(os.path.isfile(self.backup_file))

    def test_connections_not_a_list_is_left_untouched(self):
        self.write_json({"connections": {"a": _params("a")}})

        manager = self.manager()

        self.assertEqual(manager.available_connections, [])
        self.assertTrue(os.path.isfile(self.json_file))
        self.assertFalse(os.path.exists(self.backup_file))

    def test_scalar_json_is_left_untouched(self):
        self.write_json("42")

        self.manager()

        self.assertTrue(os.path.isfile(self.json_file))
        self.assertFalse(os.path.exists(self.backup_file))

    def test_non_utf8_file_is_decoded(self):
        text = json.dumps({"connections": [_params("a", password="café")]})
        with open(self.json_file, "wb") as f:
            f.write(text.replace("\\u00e9", "é").encode("latin-1"))

        params = self.manager().available_connections[0].parameters

        self.assertEqual(params["password"], "café")
        self.assertFalse(os.path.exists(self.json_file))

    def test_unreadable_json_is_left_untouched(self):
        self.write_json({"connections": [_params("a")]})

        with patch.object(
            LegacyConnectionsFile, "_read_entries", side_effect=PermissionError
        ):
            manager = self.manager()

        self.assertEqual(manager.available_connections, [])
        self.assertTrue(os.path.isfile(self.json_file))
        self.assertFalse(os.path.exists(self.backup_file))

    def test_legacy_path_that_is_a_directory_is_ignored(self):
        os.mkdir(self.json_file)

        manager = self.manager()

        self.assertEqual(manager.available_connections, [])
        self.assertTrue(os.path.isdir(self.json_file))

    def test_fixed_json_is_migrated_on_refresh(self):
        self.write_json("{not-valid-json")
        manager = self.manager()
        self.write_json({"connections": [_params("a")]})

        manager.refresh_connections()

        self.assertEqual(self.names(manager), ["a"])
        self.assertFalse(os.path.exists(self.json_file))

    # ----------------------------------------------------------- entry values

    def test_boolean_stored_as_int_is_loaded_as_bool(self):
        self.write_json(
            {
                "connections": [
                    _params("on", ssh_proxy_enabled=1),
                    _params("off", ssh_proxy_enabled=0),
                ]
            }
        )

        on, off = self.manager().available_connections

        self.assertIs(on.parameters["ssh_proxy_enabled"], True)
        self.assertIs(off.parameters["ssh_proxy_enabled"], False)

    def test_numeric_name_is_stored_as_text(self):
        self.write_json({"connections": [_params(123)]})

        self.assertEqual(self.names(self.manager()), ["123"])

    def test_empty_and_null_names_get_unique_names(self):
        self.write_json({"connections": [_params(""), _params(None, host="10.0.0.2")]})

        self.assertEqual(
            self.names(self.manager()),
            ["Unnamed connection", "Unnamed connection (2)"],
        )

    def test_extra_keys_survive_restart_and_edit(self):
        self.write_json({"connections": [_params("a", custom="kept")]})
        manager = self.manager()

        manager.edit_connection(
            manager.available_connections[0], _params("a", host="10.0.0.9")
        )

        params = self.manager().available_connections[0].parameters
        self.assertEqual(params["custom"], "kept")
        self.assertEqual(params["host"], "10.0.0.9")

    # ------------------------------------------------------- name collisions

    def test_merges_into_existing_database(self):
        manager = self.manager()
        manager.add_connection(_params("a"))
        self.write_json({"connections": [_params("a", host="10.0.0.2"), _params("b")]})

        manager = self.manager()

        self.assertEqual(self.names(manager), ["a", "a (2)", "b"])
        self.assertEqual(
            manager.available_connections[0].parameters["host"], "127.0.0.1"
        )
        self.assertEqual(
            manager.available_connections[1].parameters["host"], "10.0.0.2"
        )

    def test_suffix_skips_names_already_taken(self):
        self.write_json(
            {
                "connections": [
                    _params("dupe"),
                    _params("dupe (2)", host="10.0.0.3"),
                    _params("dupe", host="10.0.0.2"),
                ]
            }
        )

        manager = self.manager()

        self.assertEqual(self.names(manager), ["dupe", "dupe (2)", "dupe (3)"])
        self.assertEqual(
            manager.available_connections[2].parameters["host"], "10.0.0.2"
        )

    def test_reimport_of_suffixed_entries_is_idempotent(self):
        data = {"connections": [_params("dupe"), _params("dupe", host="10.0.0.2")]}
        self.write_json(data)
        self.manager()
        self.write_json(data)

        manager = self.manager()

        self.assertEqual(self.names(manager), ["dupe", "dupe (2)"])
        self.assertEqual(len(self.db_rows()), 2)

    # --------------------------------------------------- failures & recovery

    def test_verification_failure_leaves_json_untouched(self):
        self.write_json({"connections": [_params("a")]})

        with patch.object(SettingsDatabase, "contains", return_value=False):
            self.manager()

        self.assertTrue(os.path.isfile(self.json_file))
        self.assertFalse(os.path.exists(self.backup_file))

        # Next start completes the migration without duplicating the connection
        manager = self.manager()
        self.assertEqual(self.names(manager), ["a"])
        self.assertEqual(len(self.db_rows()), 1)
        self.assertFalse(os.path.exists(self.json_file))

    def test_move_is_retried_after_partial_copy(self):
        self.write_json({"connections": [_params("a")]})
        with patch(
            "src.core.db.legacy_connections.os.rename", side_effect=OSError
        ), patch("src.core.db.legacy_connections.os.remove", side_effect=OSError):
            self.manager()
        self.assertTrue(os.path.isfile(self.backup_file))
        self.assertTrue(os.path.isfile(self.json_file))

        manager = self.manager()

        self.assertEqual(self.names(manager), ["a"])
        self.assertEqual(len(self.db_rows()), 1)
        self.assertFalse(os.path.exists(self.json_file))
        self.assertTrue(
            os.path.isfile(os.path.join(self.backups, "connections.old.1.json.bk"))
        )

    def test_multiple_existing_backups_are_kept(self):
        os.makedirs(self.backups)
        for name in ("connections.old.json.bk", "connections.old.1.json.bk"):
            with open(os.path.join(self.backups, name), "w", encoding="utf-8") as f:
                f.write(name)
        self.write_json({"connections": [_params("a")]})

        self.manager()

        for name in ("connections.old.json.bk", "connections.old.1.json.bk"):
            with open(os.path.join(self.backups, name), encoding="utf-8") as f:
                self.assertEqual(f.read(), name)
        self.assertTrue(
            os.path.isfile(os.path.join(self.backups, "connections.old.2.json.bk"))
        )

    def test_locked_database_is_not_moved_aside(self):
        self.manager().add_connection(_params("a"))
        self.write_json({"connections": [_params("b")]})

        with patch(
            "src.core.db.settings_db.sqlite3.connect",
            side_effect=sqlite3.OperationalError("database is locked"),
        ):
            manager = self.manager()

        self.assertEqual(self.names(manager), ["b"])
        self.assertFalse(
            os.path.exists(os.path.join(self.backups, "connections.corrupt.db.bk"))
        )
        self.assertTrue(os.path.isfile(self.json_file))

        # Once unlocked, the original data is intact and the json is migrated
        self.assertEqual(self.names(self.manager()), ["a", "b"])

    def test_corrupt_database_sidecars_do_not_affect_new_database(self):
        with open(self.db_file, "wb") as f:
            f.write(b"this is not a sqlite database" * 100)
        for sidecar in ("-journal", "-wal", "-shm"):
            with open(self.db_file + sidecar, "wb") as f:
                f.write(b"stale")
        self.write_json({"connections": [_params("a")]})

        manager = self.manager()

        self.assertEqual(self.names(manager), ["a"])
        for sidecar in ("-journal", "-wal", "-shm"):
            path = self.db_file + sidecar
            if os.path.exists(path):
                with open(path, "rb") as f:
                    self.assertNotEqual(f.read(), b"stale")
        self.assertEqual([row["name"] for row in self.db_rows()], ["a"])

    def test_unusable_database_and_corrupt_json_does_not_crash(self):
        self.write_json("{not-valid-json")

        with patch(
            "src.core.db.settings_db.sqlite3.connect",
            side_effect=sqlite3.OperationalError("unable to open database file"),
        ):
            manager = self.manager()

        self.assertEqual(manager.available_connections, [])
        self.assertTrue(os.path.isfile(self.json_file))


class TestConnectionOperations(ManagerTestCase):
    def test_add_persists(self):
        self.manager().add_connection(_params("a"))

        self.assertEqual(self.names(self.manager()), ["a"])

    def test_add_rejects_duplicate_name(self):
        manager = self.manager()
        manager.add_connection(_params("dupe"))

        with self.assertRaises(ReferenceError):
            manager.add_connection(_params("dupe"))

    def test_add_invalid_connection_is_not_persisted(self):
        manager = self.manager()

        with self.assertRaises(ValueError):
            manager.add_connection(_params("a", host="invalid host"))

        self.assertEqual(self.db_rows(), [])

    def test_edit_persists_and_keeps_position(self):
        manager = self.manager()
        manager.add_connection(_params("a"))
        manager.add_connection(_params("b"))

        manager.edit_connection(
            manager.available_connections[0], _params("renamed", host="10.0.0.9")
        )

        self.assertEqual(self.names(manager), ["renamed", "b"])
        reloaded = self.manager()
        self.assertEqual(self.names(reloaded), ["renamed", "b"])
        self.assertEqual(
            reloaded.available_connections[0].parameters["host"], "10.0.0.9"
        )

    def test_edit_rejects_duplicate_name(self):
        manager = self.manager()
        manager.add_connection(_params("a"))
        manager.add_connection(_params("b"))

        with self.assertRaises(ReferenceError):
            manager.edit_connection(manager.available_connections[0], _params("b"))

        self.assertEqual(self.names(self.manager()), ["a", "b"])

    def test_remove_persists(self):
        manager = self.manager()
        manager.add_connection(_params("a"))
        manager.add_connection(_params("b"))

        manager.remove_connection(manager.available_connections[0])

        self.assertEqual(self.names(self.manager()), ["b"])

    def test_refresh_imports_dropped_in_json(self):
        manager = self.manager()
        manager.add_connection(_params("existing"))
        self.write_json({"connections": [_params("existing"), _params("new_conn")]})

        manager.refresh_connections()

        self.assertEqual(self.names(manager), ["existing", "new_conn"])
        self.assertFalse(os.path.exists(self.json_file))

    def test_validate_parameters_casts_expected_types(self):
        validated = self.manager().validate_parameters(_params())

        self.assertIsInstance(validated["ssh_port"], int)
        self.assertIsInstance(validated["remote_port"], int)
        self.assertIsInstance(validated["local_port"], int)
        self.assertEqual(validated["host"], "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
