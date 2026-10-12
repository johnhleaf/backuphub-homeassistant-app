#!/usr/bin/env python3
import hashlib
import json
import os
import platform
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

VERSION = "0.1.2"
DATA = Path("/data/backuphub.json")
OPTIONS = Path("/data/options.json")
SUPERVISOR_BASE = "http://supervisor"
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
MAX_JSON_BYTES = 3 * 1024 * 1024
MAX_TEXT_BYTES = 3 * 1024 * 1024


def _request(url, method="GET", body=None, bearer=None, timeout=30, text=False):
    """HTTP helper. Bearer auth is explicit: never infer an external token."""
    headers = {
        "User-Agent": f"BackupHub-HA-Agent/{VERSION}",
        "Accept": "text/plain" if text else "application/json",
    }
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout,
            context=ssl.create_default_context(),
        ) as response:
            limit = MAX_TEXT_BYTES if text else MAX_JSON_BYTES
            raw = response.read(limit + 1)
            if len(raw) > limit:
                raise RuntimeError("HTTP response too large")
            if text:
                return response.status, raw.decode("utf-8", "replace")
            return response.status, json.loads(raw.decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read(1024 * 1024)
        if text:
            return exc.code, raw.decode("utf-8", "replace")
        try:
            return exc.code, json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            return exc.code, {"error": raw.decode("utf-8", "replace")[:500]}


def supervisor(path, text=False):
    if not SUPERVISOR_TOKEN:
        raise RuntimeError("SUPERVISOR_TOKEN saknas")
    status, data = _request(
        SUPERVISOR_BASE + path,
        text=text,
        bearer=SUPERVISOR_TOKEN,
    )
    if status != 200:
        raise RuntimeError(f"Supervisor {path} HTTP {status}")
    if text:
        return data
    return data.get("data", data)


def backuphub(url, method="GET", body=None, token=None, timeout=30):
    """BackupHub requests only use the explicitly supplied BackupHub token."""
    return _request(
        url,
        method=method,
        body=body,
        bearer=token,
        timeout=timeout,
        text=False,
    )


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def load_state():
    return load_json(DATA, {})


def save_state(state):
    tmp = DATA.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.chmod(tmp, 0o600)
    tmp.replace(DATA)
    os.chmod(DATA, 0o600)


def options():
    return load_json(OPTIONS, {})


def normalized_backuphub_url(value):
    value = (value or "").strip().rstrip("/")
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise RuntimeError("BackupHub-adressen måste vara en giltig HTTPS-adress")
    if parsed.username or parsed.password:
        raise RuntimeError("BackupHub-adressen får inte innehålla användarnamn/lösenord")
    return value


def register(state, opt):
    base_url = normalized_backuphub_url(opt.get("backuphub_url"))
    pairing_code = (opt.get("pairing_code") or "").strip()
    if not pairing_code:
        raise RuntimeError("pairing_code saknas")

    agent_id = state.get("agent_id") or str(uuid.uuid4())
    host = supervisor("/host/info")
    name = (opt.get("name") or host.get("hostname") or "Home Assistant").strip()
    payload = {
        "pairing_code": pairing_code,
        "agent": {
            "agent_id": agent_id,
            "agent_type": "homeassistant",
            "name": name,
            "hostname": host.get("hostname"),
            "agent_version": VERSION,
            "os_name": host.get("operating_system") or "Home Assistant OS",
            "kernel": host.get("kernel"),
            "architecture": platform.machine(),
        },
    }

    # Intentionally no Supervisor token on this external request.
    status, data = backuphub(
        base_url + "/api/server-agent/v1/register",
        method="POST",
        body=payload,
        token=None,
    )
    if status not in (200, 201):
        raise RuntimeError(f"BackupHub register HTTP {status}: {data}")
    agent_token = data.get("agent_token")
    if not agent_token:
        raise RuntimeError("BackupHub register svarade utan agent_token")

    state = {
        "backuphub_url": base_url,
        "agent_id": agent_id,
        "name": name,
        "token": agent_token,
        "seen": {},
    }
    save_state(state)
    print("BackupHub pairing klar; agent-token sparad lokalt", flush=True)
    return state


def collect(state):
    host = supervisor("/host/info")
    core = supervisor("/core/info")
    supervisor_info = supervisor("/supervisor/info")
    addons = supervisor("/addons").get("addons", [])
    try:
        stats = supervisor("/core/stats")
    except Exception:
        stats = {}

    total = int(float(host.get("disk_total") or 0) * 1024**3)
    used = int(float(host.get("disk_used") or 0) * 1024**3)
    free = int(float(host.get("disk_free") or 0) * 1024**3)

    boot = host.get("boot_timestamp")
    uptime = None
    if boot:
        try:
            # Supervisor boot_timestamp is microseconds since Unix epoch.
            uptime = max(0, int(time.time() - float(boot) / 1_000_000))
        except Exception:
            pass

    mem_used = stats.get("memory_usage")
    mem_limit = stats.get("memory_limit")
    memory_available = None
    if isinstance(mem_limit, (int, float)) and isinstance(mem_used, (int, float)):
        memory_available = mem_limit - mem_used

    installed_addons = [a for a in addons if a.get("installed")]
    return {
        "agent_id": state["agent_id"],
        "name": state["name"],
        "hostname": host.get("hostname"),
        "agent_version": VERSION,
        "server_type": "homeassistant",
        "os_name": host.get("operating_system") or "Home Assistant OS",
        "os_version": host.get("operating_system"),
        "kernel": host.get("kernel"),
        "architecture": platform.machine(),
        "cpu_percent": stats.get("cpu_percent"),
        "memory_total_bytes": mem_limit,
        "memory_used_bytes": mem_used,
        "memory_available_bytes": memory_available,
        "disk_total_bytes": total,
        "disk_used_bytes": used,
        "disk_free_bytes": free,
        "uptime_seconds": uptime,
        "updates_available": (
            sum(1 for a in installed_addons if a.get("update_available"))
            + (1 if core.get("update_available") else 0)
            + (1 if supervisor_info.get("update_available") else 0)
        ),
        "security_updates_available": 0,
        "reboot_required": False,
        "ha_core_version": core.get("version"),
        "ha_supervisor_version": supervisor_info.get("version"),
        "ha_os_version": host.get("operating_system"),
        "ha_healthy": bool(supervisor_info.get("healthy", True)),
        "ha_addons_count": len(installed_addons),
        "ha_addons_updates": sum(
            1 for a in installed_addons if a.get("update_available")
        ),
    }


def redact(text):
    patterns = [
        (r"(?i)(authorization\s*[:=]\s*bearer\s+)[A-Za-z0-9._~+/-]+", r"\1[REDACTED]"),
        (r"(?i)(supervisor_token\s*[:=]\s*)[^\s,;]+", r"\1[REDACTED]"),
        (r"(?i)((?:access[_-]?token|refresh[_-]?token|token|password|passwd|secret|api[_-]?key)\s*[:=]\s*)[^\s,}\]]{8,}", r"\1[REDACTED]"),
    ]
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text)
    return text


def send_logs(state):
    if not options().get("logs_enabled", True):
        return

    sources = [
        ("core", "/core/logs?lines=500&no_colors"),
        ("supervisor", "/supervisor/logs?lines=500&no_colors"),
        ("host", "/host/logs?lines=500&no_colors"),
    ]
    try:
        addons = supervisor("/addons").get("addons", [])
        for addon in addons:
            slug = addon.get("slug")
            if addon.get("installed") and slug and slug != "backuphub_agent":
                sources.append(
                    (f"app:{slug}", f"/addons/{slug}/logs?lines=300&no_colors")
                )
    except Exception:
        pass

    seen = state.setdefault("seen", {})
    batches = []
    for name, path in sources[:30]:
        try:
            text = redact(supervisor(path, text=True))
        except Exception:
            continue
        if len(text) > 2 * 1024 * 1024:
            text = text[-2 * 1024 * 1024 :]
        lines = text.splitlines()
        hashes = [
            hashlib.sha256(line.encode("utf-8", "replace")).hexdigest()[:16]
            for line in lines
        ]
        previous = seen.get(name)
        if not isinstance(previous, list):
            previous = []

        max_overlap = min(len(previous), len(hashes), 500)
        overlap = 0
        for count in range(max_overlap, 0, -1):
            if previous[-count:] == hashes[:count]:
                overlap = count
                break

        fresh = lines[overlap:]
        seen[name] = hashes[-500:]
        if fresh:
            batches.append({"source": name, "text": "\n".join(fresh) + "\n"})

    if batches:
        status, data = backuphub(
            state["backuphub_url"] + "/api/server-agent/v1/logs",
            method="POST",
            body={"agent_id": state["agent_id"], "batches": batches},
            token=state["token"],
            timeout=60,
        )
        if status != 200:
            raise RuntimeError(f"log sync HTTP {status}: {data}")
        save_state(state)


def heartbeat(state):
    status, data = backuphub(
        state["backuphub_url"] + "/api/server-agent/v1/heartbeat",
        method="POST",
        body=collect(state),
        token=state["token"],
        timeout=30,
    )
    if status != 200:
        raise RuntimeError(f"heartbeat HTTP {status}: {data}")

def ping(state):
    status, data = backuphub(
        state["backuphub_url"] + "/api/server-agent/v1/ping",
        method="POST",
        body={"agent_id": state["agent_id"], "agent_version": VERSION, "reported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
        token=state["token"],
        timeout=15,
    )
    if status != 200:
        raise RuntimeError(f"ping HTTP {status}: {data}")


def main():
    if not SUPERVISOR_TOKEN:
        raise SystemExit("SUPERVISOR_TOKEN saknas")

    opt = options()
    state = load_state()
    if not state.get("token"):
        state = register(state, opt)

    print(
        f"BackupHub Agent {VERSION} startad för {state.get('name', 'Home Assistant')}",
        flush=True,
    )
    next_full = 0.0
    while True:
        try:
            now = time.monotonic()
            if now >= next_full:
                heartbeat(state)
                send_logs(state)
                print("BackupHub heartbeat/log sync OK", flush=True)
                next_full = time.monotonic() + 300
            else:
                ping(state)
                print("BackupHub ping OK", flush=True)
        except Exception as exc:
            print(f"BackupHub sync failed: {exc}", flush=True)
        time.sleep(30)


if __name__ == "__main__":
    main()
