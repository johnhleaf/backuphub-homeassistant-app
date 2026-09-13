# BackupHub Agent

## Configuration

- **BackupHub URL**: HTTPS address of the BackupHub instance, normally `https://projectbackup.leafweb.se`.
- **Pairing code**: One-time server pairing code created in BackupHub. It is only used during the first successful registration.
- **Server name**: Name shown in BackupHub.
- **Log synchronization**: Sends bounded log tails from Home Assistant Core, Supervisor, host and installed apps.

After successful pairing, BackupHub issues a dedicated agent token. It is stored in the app's private `/data/backuphub.json` file with permissions `0600`.

## Security model

The app:

- does **not** use SSH;
- does **not** request Docker socket/API access;
- does **not** use host networking;
- does **not** run privileged or with full host access;
- validates BackupHub as an HTTPS URL;
- validates TLS certificates using the system trust store;
- never sends the Home Assistant `SUPERVISOR_TOKEN` to BackupHub;
- uses a separate BackupHub agent token for heartbeat/log requests.

The app requests `hassio_role: manager` because optional host/Supervisor/app log collection uses protected Supervisor log endpoints. The Supervisor token is only attached to requests whose destination is the local `http://supervisor` API.

### Logs

Log synchronization performs best-effort redaction of common bearer tokens, passwords, secrets and API keys. Redaction cannot guarantee that every application-specific secret is detected. Disable log synchronization if you do not want logs leaving Home Assistant.

## Troubleshooting

Open the app's **Log** tab. A healthy installation prints:

```text
BackupHub heartbeat/log sync OK
```

If pairing fails, create a fresh pairing code in BackupHub and save it in the app configuration before restarting the app.
