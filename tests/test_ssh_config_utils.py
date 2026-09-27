import importlib
import os
import tempfile
import textwrap
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

ssh_config = importlib.import_module("src.core.utils.ssh_config")
ConnectionManager = importlib.import_module(
    "src.core.ConnectionManager"
).ConnectionManager


class SSHConfigTestCase(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.ssh_dir = self._temp.name
        self.config_path = os.path.join(self.ssh_dir, "config")
        patcher = patch.object(ssh_config, "ssh_directory", return_value=self.ssh_dir)
        patcher.start()
        self.addCleanup(patcher.stop)
        user_patcher = patch.object(
            ssh_config, "_local_username", return_value="localuser"
        )
        user_patcher.start()
        self.addCleanup(user_patcher.stop)

    def tearDown(self):
        self._temp.cleanup()

    def write(self, text, name="config", encoding="utf-8", newline=None):
        path = os.path.join(self.ssh_dir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding=encoding, newline=newline) as f:
            f.write(textwrap.dedent(text))
        return path

    def load(self, used_ports=()):
        return {
            params["name"]: (params, warnings)
            for params, warnings in ssh_config.load_from_ssh_config(
                self.config_path, used_ports
            )
        }


class TestParsing(SSHConfigTestCase):
    def test_missing_config_returns_nothing(self):
        self.assertEqual(ssh_config.load_from_ssh_config(self.config_path), [])

    def test_basic_host(self):
        self.write("""
            Host dev-db
                HostName 10.0.0.5
                User alice
                Port 2200
            """)

        params, warnings = self.load()["dev-db"]

        self.assertEqual(params["host"], "10.0.0.5")
        self.assertEqual(params["username"], "alice")
        self.assertEqual(params["ssh_port"], 2200)
        self.assertEqual(params["password"], "")
        self.assertIs(params["ssh_proxy_enabled"], False)
        self.assertEqual(warnings, [])

    def test_defaults(self):
        self.write("Host db.example.com\n")

        params, _ = self.load()["db.example.com"]

        self.assertEqual(params["host"], "db.example.com")
        self.assertEqual(params["username"], "localuser")
        self.assertEqual(params["ssh_port"], 22)
        self.assertEqual(params["remote_bind_address"], "127.0.0.1")
        self.assertEqual(params["remote_port"], 5432)
        self.assertEqual(params["local_port"], 5433)

    def test_keywords_are_case_insensitive_and_accept_equals(self):
        self.write("""
            HOST=dev
              hostname = 10.0.0.5
              USER=alice
              port    2200
            """)

        params, _ = self.load()["dev"]

        self.assertEqual(
            (params["host"], params["username"], params["ssh_port"]),
            ("10.0.0.5", "alice", 2200),
        )

    def test_comments_blank_lines_crlf_and_bom(self):
        self.write(
            "# comment\r\n\r\nHost dev # trailing\r\n  HostName 10.0.0.5\r\n",
            encoding="utf-8-sig",
            newline="",
        )

        self.assertEqual(list(self.load()), ["dev"])
        self.assertEqual(self.load()["dev"][0]["host"], "10.0.0.5")

    def test_quoted_values_and_windows_paths(self):
        key = os.path.join(self.ssh_dir, "my key")
        open(key, "w").close()
        self.write(f'Host dev\n  HostName 10.0.0.5\n  IdentityFile "{key}"\n')

        self.assertEqual(self.load()["dev"][0]["id_file"], os.path.normpath(key))

    def test_multiple_aliases_on_one_host_line(self):
        self.write("Host a.example.com b.example.com\n  User alice\n")

        hosts = self.load()

        self.assertEqual(list(hosts), ["a.example.com", "b.example.com"])
        self.assertEqual(hosts["b.example.com"][0]["username"], "alice")

    def test_wildcards_and_negations_are_not_imported(self):
        self.write("""
            Host *
                User everyone
            Host *.corp !bastion.corp
                Port 2222
            Host web?.example.com
                Port 1
            """)

        self.assertEqual(self.load(), {})

    def test_first_obtained_value_wins(self):
        self.write("""
            Host dev
                HostName 10.0.0.5
            Host dev
                HostName 10.0.0.6
                User second
            Host *
                User fallback
                Port 2022
            """)

        params, _ = self.load()["dev"]

        self.assertEqual(params["host"], "10.0.0.5")
        self.assertEqual(params["username"], "second")
        self.assertEqual(params["ssh_port"], 2022)

    def test_global_options_before_first_host_apply(self):
        self.write("User globaluser\nHost dev\n  HostName 10.0.0.5\n")

        self.assertEqual(self.load()["dev"][0]["username"], "globaluser")

    def test_wildcard_defaults_and_negation(self):
        self.write("""
            Host a.corp b.corp
                HostName %h
            Host *.corp !b.corp
                User corpuser
            """)

        hosts = self.load()

        self.assertEqual(hosts["a.corp"][0]["username"], "corpuser")
        self.assertEqual(hosts["b.corp"][0]["username"], "localuser")
        self.assertEqual(hosts["a.corp"][0]["host"], "a.corp")

    def test_square_brackets_are_literal(self):
        self.write("Host [x].example.com\n  User alice\nHost x.example.com\n")

        self.assertEqual(self.load()["x.example.com"][0]["username"], "localuser")

    def test_match_all_applies_and_other_match_blocks_are_ignored(self):
        self.write("""
            Host dev
                HostName 10.0.0.5
            Match exec "touch /tmp/pwned"
                User matched
            Match all
                Port 2022
            """)

        params, _ = self.load()["dev"]

        self.assertEqual(params["username"], "localuser")
        self.assertEqual(params["ssh_port"], 2022)

    def test_hostname_token_expansion(self):
        self.write("Host dev\n  HostName %h.example.com\n")

        self.assertEqual(self.load()["dev"][0]["host"], "dev.example.com")

    def test_invalid_port_falls_back_to_22_with_warning(self):
        self.write("Host dev.example.com\n  Port abc\n")

        params, warnings = self.load()["dev.example.com"]

        self.assertEqual(params["ssh_port"], 22)
        self.assertEqual(len(warnings), 1)


class TestInclude(SSHConfigTestCase):
    def test_relative_include_with_glob(self):
        self.write("Host one.example.com\n", name="config.d/1.conf")
        self.write("Host two.example.com\n", name="config.d/2.conf")
        self.write("Include config.d/*.conf\nHost three.example.com\n")

        self.assertEqual(
            list(self.load()),
            ["one.example.com", "two.example.com", "three.example.com"],
        )

    def test_absolute_include(self):
        included = self.write("Host inc.example.com\n", name="other/inc")
        self.write(f'Include "{included}"\n')

        self.assertEqual(list(self.load()), ["inc.example.com"])

    def test_missing_include_is_ignored(self):
        self.write("Include does-not-exist\nHost dev.example.com\n")

        self.assertEqual(list(self.load()), ["dev.example.com"])

    def test_include_inside_host_block_keeps_condition(self):
        self.write("  User included\n", name="user.conf")
        self.write("""
            Host dev.example.com
                Include user.conf
                Port 2022
            Host other.example.com
            """)

        hosts = self.load()

        self.assertEqual(hosts["dev.example.com"][0]["username"], "included")
        self.assertEqual(hosts["dev.example.com"][0]["ssh_port"], 2022)
        self.assertEqual(hosts["other.example.com"][0]["username"], "localuser")

    def test_recursive_include_does_not_loop(self):
        self.write("Include config\nHost dev.example.com\n")

        self.assertEqual(list(self.load()), ["dev.example.com"])


class TestIdentityFile(SSHConfigTestCase):
    def test_first_existing_identity_file_is_used(self):
        key = os.path.join(self.ssh_dir, "id_dev")
        open(key, "w").close()
        self.write(f"""
            Host dev.example.com
                IdentityFile {os.path.join(self.ssh_dir, "missing")}
                IdentityFile {key}
            """)

        params, warnings = self.load()["dev.example.com"]

        self.assertEqual(params["id_file"], os.path.normpath(key))
        self.assertEqual(warnings, [])

    def test_identity_file_tokens(self):
        key = os.path.join(self.ssh_dir, "dev.example.com-alice")
        open(key, "w").close()
        self.write(f"""
            Host dev.example.com
                User alice
                IdentityFile {self.ssh_dir}/%h-%r
            """)

        self.assertEqual(
            self.load()["dev.example.com"][0]["id_file"], os.path.normpath(key)
        )

    def test_missing_identity_files_warn(self):
        self.write("Host dev.example.com\n  IdentityFile /nope/id_rsa\n")

        params, warnings = self.load()["dev.example.com"]

        self.assertEqual(params["id_file"], "")
        self.assertEqual(len(warnings), 1)


class TestForwarding(SSHConfigTestCase):
    def test_local_forward_sets_ports(self):
        self.write("Host db.example.com\n  LocalForward 6543 db.internal.lan:5433\n")

        params, _ = self.load()["db.example.com"]

        self.assertEqual(params["local_port"], 6543)
        self.assertEqual(params["remote_bind_address"], "db.internal.lan")
        self.assertEqual(params["remote_port"], 5433)

    def test_local_forward_variants(self):
        self.write("""
            Host a.example.com
                LocalForward 127.0.0.1:6001 localhost:5432
            Host b.example.com
                LocalForward [::1]:6002 [::1]:5432
            Host c.example.com
                LocalForward 6003 10.0.0.9/5432
            Host d.example.com
                LocalForward /tmp/local.sock /tmp/remote.sock
            """)

        hosts = self.load()

        self.assertEqual(hosts["a.example.com"][0]["local_port"], 6001)
        self.assertEqual(hosts["a.example.com"][0]["remote_bind_address"], "127.0.0.1")
        self.assertEqual(hosts["b.example.com"][0]["local_port"], 6002)
        self.assertEqual(hosts["b.example.com"][0]["remote_bind_address"], "127.0.0.1")
        self.assertEqual(hosts["c.example.com"][0]["remote_bind_address"], "10.0.0.9")
        # Unix sockets are unsupported: defaults are used instead
        self.assertEqual(hosts["d.example.com"][0]["remote_port"], 5432)

    def test_auto_local_ports_are_unique_and_skip_used_ones(self):
        self.write("""
            Host a.example.com
            Host b.example.com
                LocalForward 5435 localhost:5432
            Host c.example.com
            """)

        hosts = self.load(used_ports={5433})

        self.assertEqual(hosts["a.example.com"][0]["local_port"], 5434)
        self.assertEqual(hosts["b.example.com"][0]["local_port"], 5435)
        self.assertEqual(hosts["c.example.com"][0]["local_port"], 5436)

    def test_proxies_are_reported(self):
        self.write("""
            Host a.example.com
                ProxyJump bastion
            Host b.example.com
                ProxyCommand ssh -W %h:%p bastion
            Host c.example.com
                ProxyJump none
            """)

        hosts = self.load()

        self.assertEqual(len(hosts["a.example.com"][1]), 1)
        self.assertEqual(len(hosts["b.example.com"][1]), 1)
        self.assertEqual(hosts["c.example.com"][1], [])
        self.assertEqual(hosts["b.example.com"][0]["ssh_proxy"], "")


class FakeConnection:
    def __init__(self, parameters):
        if "." not in parameters.get("host", ""):
            raise ValueError(f"invalid host {parameters.get('host')}")
        self.parameters = parameters
        self.name = parameters.get("name", "")
        self.local_port = parameters.get("local_port", 0)


class TestManagerImport(SSHConfigTestCase):
    def setUp(self):
        super().setUp()
        self.settings = os.path.join(self.ssh_dir, "settings")
        patcher = patch("src.core.ConnectionManager.Connection", FakeConnection)
        patcher.start()
        self.addCleanup(patcher.stop)

    def manager(self):
        return ConnectionManager(settings_folder=self.settings)

    def detect(self, manager):
        return {
            h.parameters["name"]: h
            for h in manager.detect_ssh_config_hosts(self.config_path)
        }

    def test_detection_does_not_import(self):
        self.write("Host a.example.com\n")
        manager = self.manager()

        hosts = self.detect(manager)

        self.assertTrue(hosts["a.example.com"].importable)
        self.assertEqual(manager.available_connections, [])
        self.assertEqual(self.manager().available_connections, [])

    def test_import_selected_adds_and_persists_only_those(self):
        self.write("Host a.example.com\nHost b.example.com\nHost c.example.com\n")
        manager = self.manager()
        hosts = self.detect(manager)

        imported, skipped = manager.import_connections(
            [hosts["a.example.com"].parameters, hosts["c.example.com"].parameters]
        )

        self.assertEqual(imported, ["a.example.com", "c.example.com"])
        self.assertEqual(skipped, [])
        names = [conn.name for conn in self.manager().available_connections]
        self.assertEqual(names, ["a.example.com", "c.example.com"])

    def test_import_nothing_selected(self):
        self.write("Host a.example.com\n")
        manager = self.manager()

        self.assertEqual(manager.import_connections([]), ([], []))
        self.assertEqual(self.manager().available_connections, [])

    def test_existing_connections_are_flagged(self):
        self.write("Host a.example.com\nHost b.example.com\n")
        manager = self.manager()
        manager.import_connections([self.detect(manager)["a.example.com"].parameters])

        hosts = self.detect(manager)

        self.assertFalse(hosts["a.example.com"].importable)
        self.assertEqual(hosts["a.example.com"].problem, "already exists")
        self.assertTrue(hosts["b.example.com"].importable)

    def test_invalid_hosts_are_flagged(self):
        self.write("Host myalias\nHost good.example.com\n")

        hosts = self.detect(self.manager())

        self.assertFalse(hosts["myalias"].importable)
        self.assertIn("invalid host", hosts["myalias"].problem)
        self.assertTrue(hosts["good.example.com"].importable)

    def test_import_reports_failures_without_stopping(self):
        self.write("Host a.example.com\nHost b.example.com\n")
        manager = self.manager()
        hosts = self.detect(manager)
        manager.import_connections([hosts["a.example.com"].parameters])

        imported, skipped = manager.import_connections(
            [hosts["a.example.com"].parameters, hosts["b.example.com"].parameters]
        )

        self.assertEqual(imported, ["b.example.com"])
        self.assertEqual([name for name, _ in skipped], ["a.example.com"])

    def test_local_ports_of_existing_connections_are_avoided(self):
        manager = self.manager()
        manager.add_connection(
            {
                "name": "existing",
                "host": "x.example.com",
                "ssh_port": 22,
                "remote_bind_address": "127.0.0.1",
                "remote_port": 5432,
                "local_port": 5433,
                "username": "u",
                "password": "",
                "id_file": "",
                "pkey_password": "",
                "ssh_proxy": "",
                "ssh_proxy_enabled": False,
            }
        )
        self.write("Host a.example.com\n")

        hosts = self.detect(manager)

        self.assertEqual(hosts["a.example.com"].parameters["local_port"], 5434)

    def test_warnings_are_attached_to_hosts(self):
        self.write("Host a.example.com\n  ProxyJump bastion\n")

        hosts = self.detect(self.manager())

        self.assertEqual(len(hosts["a.example.com"].warnings), 1)
        self.assertTrue(hosts["a.example.com"].importable)

    def test_missing_config_detects_nothing(self):
        self.assertEqual(self.manager().detect_ssh_config_hosts(self.config_path), [])


if __name__ == "__main__":
    unittest.main()
