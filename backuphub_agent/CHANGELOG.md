# Changelog

## 0.1.2

- Adds a minimal 30-second BackupHub keepalive between five-minute full status/log syncs.
- Enables faster offline detection without collecting extra system metrics.

## 0.1.1

- Hardened authentication separation between the local Supervisor API and external BackupHub requests.
- The Home Assistant `SUPERVISOR_TOKEN` can no longer be attached to BackupHub registration requests.
- Require HTTPS for the BackupHub URL.
- Atomic `0600` storage for the issued BackupHub agent token.
- Explicitly disable Docker API, full-access and host networking in app metadata.
- Updated Dockerfile for current Home Assistant App build behavior without deprecated `BUILD_FROM` dependency.
- Expanded best-effort log secret redaction.

## 0.1.0

- Initial Home Assistant App repository release.
