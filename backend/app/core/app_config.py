"""Loader for the versioned rule files in config/*.yaml.

Thresholds, Zakat rules, schedules and excluded periods are never constants in code
(PRD section 0, rule 3). Every file must carry a `version`.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.core.config import get_settings

DOMAINS = (
    "shariah",
    "zakat",
    "regime",
    "schedules",
    "excluded_periods",
    "trading_calendar",
)


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class LoadedConfig:
    domain: str
    version: str
    data: dict[str, Any]
    raw_yaml: str


def load_config_file(domain: str, config_dir: Path) -> LoadedConfig:
    if domain not in DOMAINS:
        raise ConfigError(f"Unknown config domain: {domain}")
    path = config_dir / f"{domain}.yaml"
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ConfigError(f"Missing config file: {path}") from exc
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a mapping at the top level")
    version = data.get("version")
    if not isinstance(version, str) or not version:
        raise ConfigError(f"{path} must set a non-empty string `version`")
    return LoadedConfig(domain=domain, version=version, data=data, raw_yaml=raw)


@lru_cache
def get_config(domain: str) -> LoadedConfig:
    """Cached config for the running process. Restart to pick up a new version."""
    return load_config_file(domain, get_settings().config_dir)
