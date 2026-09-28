"""Agent configuration loaded from a JSON file, with sane defaults for a
small clinic deployment (single server, handful of workstations)."""
import json
import os
import socket
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_CONFIG_PATH = os.environ.get(
    "RWT_AGENT_CONFIG", "/etc/ransomware-toolkit/agent.json"
)

# Extensions commonly appended by ransomware to encrypted files.
SUSPICIOUS_EXTENSIONS = [
    ".locked", ".encrypted", ".crypt", ".crypted", ".enc", ".ransom",
    ".wcry", ".wncry", ".locky", ".cerber", ".zzz", ".micro", ".ryk",
]

# Filenames commonly dropped as ransom notes.
RANSOM_NOTE_PATTERNS = [
    "readme_to_decrypt", "decrypt_instructions", "how_to_decrypt",
    "help_decrypt", "your_files_are_encrypted", "recovery_instructions",
]


@dataclass
class AgentConfig:
    agent_id: str = field(default_factory=lambda: socket.gethostname())
    server_url: str = "http://127.0.0.1:8080"
    api_key: str = "change-me"
    watch_paths: list = field(default_factory=lambda: [str(Path.home())])
    canary_dir_name: str = ".rwt_canary"
    canary_files_per_dir: int = 5
    heartbeat_interval_seconds: int = 60
    # Sliding-window heuristic: this many file modifications with high
    # entropy / suspicious extensions inside this many seconds trips a
    # "mass encryption" alert.
    mass_change_count_threshold: int = 20
    mass_change_window_seconds: int = 30
    entropy_threshold: float = 7.5
    # Autonomous response is OFF by default. A small clinic should turn
    # this on only after testing, since isolating a host is disruptive.
    autonomous_response_enabled: bool = False
    dry_run: bool = True

    @classmethod
    def load(cls, path: str = DEFAULT_CONFIG_PATH) -> "AgentConfig":
        if not os.path.exists(path):
            return cls()
        with open(path, "r") as fh:
            data = json.load(fh)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
