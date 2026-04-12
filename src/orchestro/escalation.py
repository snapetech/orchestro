from __future__ import annotations

import json
import logging
import os
import subprocess
import urllib.request
import urllib.error
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from orchestro.paths import data_dir

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class EscalationEvent:
    run_id: str
    reason: str
    category: str
    channel: str
    timestamp: str


class EscalationChannel(ABC):
    @abstractmethod
    def send(self, event: EscalationEvent) -> bool: ...


class ShellChannel(EscalationChannel):
    def send(self, event: EscalationEvent) -> bool:
        print(f"[ESCALATION] [{event.category}] run={event.run_id} {event.reason}")
        return True


class FileChannel(EscalationChannel):
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or data_dir() / "escalations.log"

    def send(self, event: EscalationEvent) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a") as fh:
                fh.write(json.dumps(asdict(event)) + "\n")
            return True
        except OSError:
            logger.exception("FileChannel failed to write escalation")
            return False


class WebhookChannel(EscalationChannel):
    def __init__(self, url: str, *, timeout: float = 10.0) -> None:
        self.url = url
        self.timeout = timeout

    def send(self, event: EscalationEvent) -> bool:
        payload = json.dumps(asdict(event)).encode()
        req = urllib.request.Request(
            self.url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return 200 <= resp.status < 300
        except (urllib.error.URLError, OSError):
            logger.exception("WebhookChannel failed to POST escalation")
            return False


class CommandChannel(EscalationChannel):
    def __init__(self, command: str) -> None:
        self.command = command

    def send(self, event: EscalationEvent) -> bool:
        env = {
            **os.environ,
            "ESCALATION_RUN_ID": event.run_id,
            "ESCALATION_REASON": event.reason,
            "ESCALATION_CATEGORY": event.category,
            "ESCALATION_CHANNEL": event.channel,
            "ESCALATION_TIMESTAMP": event.timestamp,
        }
        try:
            subprocess.run(
                self.command,
                shell=True,
                env=env,
                timeout=30,
                check=False,
            )
            return True
        except (OSError, subprocess.TimeoutExpired):
            logger.exception("CommandChannel failed to run escalation command")
            return False


CHANNEL_TYPES: dict[str, type[EscalationChannel]] = {
    "shell": ShellChannel,
    "file": FileChannel,
    "webhook": WebhookChannel,
    "command": CommandChannel,
}


def _build_channel(spec: dict[str, Any]) -> EscalationChannel | None:
    channel_type = spec.get("type", "shell")
    if channel_type == "shell":
        return ShellChannel()
    if channel_type == "file":
        path = Path(spec["path"]) if "path" in spec else None
        return FileChannel(path=path)
    if channel_type == "webhook":
        url = spec.get("url")
        if not url:
            logger.warning("webhook channel missing 'url'")
            return None
        return WebhookChannel(url)
    if channel_type == "command":
        cmd = spec.get("command")
        if not cmd:
            logger.warning("command channel missing 'command'")
            return None
        return CommandChannel(cmd)
    logger.warning("unknown escalation channel type: %s", channel_type)
    return None


def load_escalation_config(dd: Path | None = None) -> dict[str, EscalationChannel]:
    dd = dd or data_dir()
    config_path = dd / "escalation.json"
    channels: dict[str, EscalationChannel] = {"default": ShellChannel()}
    if not config_path.exists():
        return channels
    try:
        raw = json.loads(config_path.read_text())
    except (OSError, json.JSONDecodeError):
        logger.exception("failed to load escalation config from %s", config_path)
        return channels
    for name, spec in raw.get("channels", {}).items():
        ch = _build_channel(spec)
        if ch is not None:
            channels[name] = ch
    default_name = raw.get("default", "shell")
    if default_name in channels:
        channels["default"] = channels[default_name]
    elif default_name == "shell":
        channels["default"] = ShellChannel()
    return channels


class Escalator:
    def __init__(
        self,
        channels: dict[str, EscalationChannel] | None = None,
        default: str = "default",
    ) -> None:
        self.channels = channels or {"default": ShellChannel()}
        self.default = default

    def escalate(
        self,
        *,
        run_id: str,
        reason: str,
        category: str,
        channel: str | None = None,
    ) -> None:
        target = channel or self.default
        ch = self.channels.get(target) or self.channels.get(self.default)
        if ch is None:
            ch = ShellChannel()
        event = EscalationEvent(
            run_id=run_id,
            reason=reason,
            category=category,
            channel=target,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        try:
            ch.send(event)
        except Exception:
            logger.exception("escalation channel %s failed for run %s", target, run_id)


def read_escalation_log(dd: Path | None = None, *, limit: int = 50) -> list[dict[str, Any]]:
    dd = dd or data_dir()
    log_path = dd / "escalations.log"
    if not log_path.exists():
        return []
    lines: list[str] = []
    try:
        lines = log_path.read_text().splitlines()
    except OSError:
        return []
    entries: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries[-limit:]
