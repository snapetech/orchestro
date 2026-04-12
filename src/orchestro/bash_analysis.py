from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(slots=True)
class BashRisk:
    level: str
    reasons: list[str] = field(default_factory=list)
    command: str = ""


_DENY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\brm\s+-[^\s]*r[^\s]*f[^\s]*\s+/\s*$|\brm\s+-[^\s]*f[^\s]*r[^\s]*\s+/\s*$|\brm\s+-rf\s+/\s*$"), "rm -rf /"),
    (re.compile(r"\brm\s+-[^\s]*r[^\s]*\s+~\b"), "rm -rf ~"),
    (re.compile(r"\bmkfs\b"), "mkfs (format filesystem)"),
    (re.compile(r"\bdd\s+if="), "dd if= (raw disk write)"),
    (re.compile(r":\(\)\s*\{.*\|.*&\s*\}\s*;"), "fork bomb"),
    (re.compile(r"\bchmod\s+-R\s+777\s+/\s*$"), "chmod -R 777 /"),
    (re.compile(r">\s*/dev/sd[a-z]"), "> /dev/sda (raw disk write)"),
    (re.compile(r"\bcurl\b.*\|\s*sh\b"), "curl piped to sh"),
    (re.compile(r"\bwget\b.*\|\s*sh\b"), "wget piped to sh"),
    (re.compile(r"\bcurl\b.*\|\s*bash\b"), "curl piped to bash"),
    (re.compile(r"\bwget\b.*\|\s*bash\b"), "wget piped to bash"),
    (re.compile(r">\s*/etc/"), "write to /etc"),
    (re.compile(r">\s*/boot/"), "write to /boot"),
    (re.compile(r">\s*/usr/"), "write to /usr"),
]

_WARN_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\brm\s+-[^\s]*r"), "rm -rf (recursive delete)"),
    (re.compile(r"\bchmod\s+-R\b"), "chmod -R (recursive permission change)"),
    (re.compile(r"\bchown\s+-R\b"), "chown -R (recursive ownership change)"),
    (re.compile(r"\bkill\s+-9\b"), "kill -9 (force kill)"),
    (re.compile(r"\bpkill\b"), "pkill (pattern-based kill)"),
    (re.compile(r"\bshutdown\b"), "shutdown"),
    (re.compile(r"\breboot\b"), "reboot"),
    (re.compile(r"\bsudo\b"), "sudo (elevated privileges)"),
    (re.compile(r"\bsu\s"), "su (switch user)"),
    (re.compile(r"\|\s*sh\b"), "pipe to sh"),
    (re.compile(r"\|\s*bash\b"), "pipe to bash"),
    (re.compile(r"\beval\b"), "eval (dynamic code execution)"),
    (re.compile(r"\bgit\s+push\s+--force\b|\bgit\s+push\s+-f\b"), "git push --force"),
    (re.compile(r"\bgit\s+reset\s+--hard\b"), "git reset --hard"),
    (re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE), "DROP TABLE"),
    (re.compile(r"\bDELETE\s+FROM\b(?!.*\bWHERE\b)", re.IGNORECASE), "DELETE FROM without WHERE"),
]


def analyze_bash_command(command: str) -> BashRisk:
    deny_reasons: list[str] = []
    for pattern, reason in _DENY_PATTERNS:
        if pattern.search(command):
            deny_reasons.append(reason)

    if deny_reasons:
        return BashRisk(level="deny", reasons=deny_reasons, command=command)

    warn_reasons: list[str] = []
    for pattern, reason in _WARN_PATTERNS:
        if pattern.search(command):
            warn_reasons.append(reason)

    if warn_reasons:
        return BashRisk(level="warn", reasons=warn_reasons, command=command)

    return BashRisk(level="safe", command=command)
