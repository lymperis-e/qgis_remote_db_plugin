# QGIS Plugin: Remote DB

[![CodeQL](https://github.com/lymperis-e/qgis_remote_db_plugin/actions/workflows/codeql.yml/badge.svg)](https://github.com/lymperis-e/qgis_remote_db_plugin/actions/workflows/codeql.yml) [![Code Style](https://github.com/lymperis-e/qgis_remote_db_plugin/actions/workflows/code-style.yml/badge.svg)](https://github.com/lymperis-e/qgis_remote_db_plugin/actions/workflows/code-style.yml)
[![security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)

![Plugin logo](img/logo_50.png)

The Remote DB plugin for QGIS allows users to establish SSH tunnels to remote database servers, which can then be used for querying or other database operations within QGIS.

#### Usage

1. Install the `remote_db` plugin in QGIS.
2. Open the plugin menu and click "Add Connection".
3. Enter a name for the connection and fill in the required connection parameters such as host, ssh_port, remote_port, local_port, username, and password.
4. Click "OK" to save the connection.
5. To connect to the remote machine, select the connection from the list of connections and click the "Connect" button.
6. Once the connection is established, you can access the remote database through the forwarded local port.

Note that it is the responsibility of the user to manage their local ports, ensuring that different database connections in their QGIS browser use different local ports.

## Add a new connection

Let's say you want to connect to a remote PostgreSQL database server with the following connection parameters:

- Host: `example.com`
- SSH port: `22`
- PostgeSQL service port: `5432` , this is the port that the database server is listening to.
- Local port: `5433` , this is the local port to which the remote port will be forwarded. In your local machine, you can access the remote DB server in this port.
- Username: `john_doe` , a user on the remote machine, with ssh privileges
- Password: `my_password` , user's password

To set up a connection with the `remote_db` plugin in QGIS:

1. Open QGIS and go to the "Plugins" menu.
2. Click "remote_db" to open the plugin menu.
3. Click "Add Connection".
4. Enter a name for the connection, e.g. "Example Database". This is just a label for you to known which connection is which.
5. Enter the host name or IP address of the remote server, e.g. `example.com`.
6. Enter the SSH port number, e.g. `22`. Most machines listen for ssh connections in port 22. Server admins may change this setting for security reasons
7. Enter the remote port number, e.g. `5432`.
8. Enter the local port number, e.g. `5433`. This will forward `example.com:5432` to `127.0.0.1:5433`
9. Add the Database connection from the **QGIS Browser Panel**, like you normally would. The host address should be `127.0.0.1` , and the port should be the `local_port` you selected previously. **Attention**, **YOU** are responsible for managing your local ports. If you want to have many ssh connections to different servers open **at the same time**, you should configure them to use different local ports. You have to make sure that the local ports defined in the plugin's connections match the ports that are specified in QGIS's database connections parameters.
10. Enter the SSH username, e.g. `john_doe`.
11. Enter the SSH password, e.g. `my_password`.
12. Click "OK" to save the connection.
13. The new connection should now appear in the list. Click `Connect` and you are good to go!

## Import from SSH config

Click **Import SSH Config** to list the hosts of your OpenSSH client config: `~/.ssh/config` on Linux and macOS, `%USERPROFILE%\.ssh\config` on Windows. All importable hosts are checked by default. Uncheck the ones you don't want and click **Import**. Hosts that already exist or can't be imported are shown greyed out; hover over a host for details.

- **What is imported:** `HostName`, `User`, `Port`, the first existing `IdentityFile`, and the first `LocalForward`. `Host *` defaults, multiple aliases per `Host` line, negated patterns, `Match all` and `Include` are supported.
- **Ports:** a host without a `LocalForward` gets remote port `5432` and the next free local port, starting at `5433`. Review the ports before connecting.
- **Skipped hosts:** wildcard patterns, hosts that already exist as connections, and aliases without a valid `HostName` are not imported.
- **Not supported:** `ProxyJump` and `ProxyCommand`. Hosts that use them are imported without the proxy, and you get a warning. Nothing in the config is ever executed.
- **Passwords:** none are imported. Authentication uses your keys or SSH agent, and you can add a password by editing the connection.

## Advanced usage

Connections are stored in a SQLite database, _connections.db_, inside the settings folder. Click the button **'Open Settings Folder'** from the top of the plugin panel to open it.

Older versions of the plugin stored connections in _connections.json_. On startup, this file is automatically imported into _connections.db_ and then moved to _.backups/connections.old.json.bk_. All backups (including unreadable databases) are kept in the _.backups_ subfolder, so the settings folder only contains your current settings. If the file cannot be read, it is left untouched and the error is written to the QGIS message log.

For bulk imports, advanced users can place a _connections.json_ file (`{"connections": [ ... ]}`) in the settings folder and press **refresh**. Connections that already exist unchanged are skipped. If a name is already used by a different connection, the imported one gets a numbered suffix, for example `name (2)`. Available parameters are:

| Parameter                      | Description                                                      |
| ------------------------------ | ---------------------------------------------------------------- |
| `name`                         | Name of the connection, displayed in the list                    |
| `host`                         | IP or domain name of the remote host                             |
| `ssh_port`                     | Port listening for SSH                                           |
| `username`                     | Username on the remote host                                      |
| `password` (optional)          | Password for the username on the remote host (optional)          |
| `id_file` (optional)           | SSH identity file (optional)                                     |
| `pkey_password` (optional)     | Passphrase for the SSH identity file (optional)                  |
| `ssh_proxy` (optional)         | Proxy server to use for connecting to the remote host (optional) |
| `ssh_proxy_enabled` (optional) | Use the proxy server (optional)                                  |
| `remote_port`                  | Port on the remote host to forward to localhost                  |
| `local_port`                   | Local port to expose the remote service on                       |

## Requirements

- QGIS 3.0 or later
- Python 3.6 or later

## Issues

This is a new plugin. Although it has been tested in several machines, it is still very likely that bugs may arise, especially in **installation**. Please report any issues you have in the repository's **Issues** , or send me an [e-mail](mailto:geo.elymperis@gmail.com) .I ;ll be more than happy to troubleshoot with you!

Suggestions & pull requests are more than welcome.

## Development

### Security audit

Docker is required to run the Bandit security scan. From the repository root, run:

```bash
python scripts/run_security_audit.py
```

The scan writes its JSON report to `audit/bandit-report.json`. Bandit findings produce a nonzero exit code.

To render the existing JSON report as HTML without rerunning the scan, run:

```bash
python scripts/run_security_audit.py --beautify
```

The HTML report is saved to `audit/bandit-report.html`.

## Tests

Run the unit tests from the repository root:

```bash
python -m unittest discover -s tests -v
```

Expected result: all tests pass with `OK`.

### Using `scripts/export.py`:

You can create a release _.zip_ file with the plugin's code, ready to be installed in QGIS, by running:

```bash
python scripts/export.py
```

You can create a release and install in your QGIS by running:

```bash
python scripts/export.py --install-dev
```

### Format all py files with `black`:

```bash
python -m black .
```

### Publishing the Plugin

To publish a new version of the plugin, create a new tag following the format `vX.Y.Z` and push it to the repository. The GitHub Actions workflow will automatically build and publish the plugin.
