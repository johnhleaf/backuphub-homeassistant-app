# BackupHub Home Assistant App

Public Home Assistant App repository for the BackupHub Agent.

The app connects Home Assistant OS to a BackupHub server without SSH or Docker socket access. It uses the Home Assistant Supervisor API locally and sends status and, when enabled, bounded log excerpts outbound over HTTPS.

## Install

1. In Home Assistant, open **Settings → Apps → App store**.
2. Open the repository menu and add:
   `https://github.com/johnhleaf/backuphub-homeassistant-app`
3. Install **BackupHub Agent**.
4. In BackupHub, create a fresh server pairing code.
5. Configure the app with your BackupHub HTTPS URL, the pairing code and a display name.
6. Start the app and enable start on boot.

## Security

No BackupHub, GitHub or Home Assistant secrets are stored in this repository. The Home Assistant Supervisor token is used only for requests to the local Supervisor API and is never sent to BackupHub. The BackupHub agent token is issued during pairing and stored only in the app's private `/data` volume with mode `0600`.

The app does not request Docker API access, host networking, privileged mode or full host access. It uses `hassio_role: manager` because optional log collection requires Supervisor log endpoints.

Log synchronization is optional. Logs can contain sensitive information even after best-effort redaction, so disable it if you do not want logs sent to BackupHub.
