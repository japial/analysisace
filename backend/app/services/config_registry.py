"""Keeps a stored copy of every config/*.yaml version that has been in use.

Results such as `shariah_result` record the config version they were computed with, so the
exact rules behind any number can be recovered (PRD section 0, rule 3).
"""

import hashlib
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.app_config import DOMAINS, ConfigError, load_config_file
from app.models import ConfigVersion


def sync_config_versions(session: Session, config_dir: Path) -> list[tuple[str, str]]:
    """Store any config version not yet in the database. Returns the (domain, version) added.

    Raises ConfigError if a file changed without its `version` being bumped.
    """
    added: list[tuple[str, str]] = []
    for domain in DOMAINS:
        loaded = load_config_file(domain, config_dir)
        checksum = hashlib.sha256(loaded.raw_yaml.encode("utf-8")).hexdigest()
        stored = session.scalar(
            select(ConfigVersion).where(
                ConfigVersion.domain == domain, ConfigVersion.version == loaded.version
            )
        )
        if stored is None:
            session.add(
                ConfigVersion(
                    domain=domain, version=loaded.version, yaml=loaded.raw_yaml, checksum=checksum
                )
            )
            added.append((domain, loaded.version))
        elif stored.checksum != checksum:
            raise ConfigError(
                f"config/{domain}.yaml changed but still says version {loaded.version}. "
                "Bump `version` in the file."
            )
    session.flush()
    return added
