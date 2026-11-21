"""Versioned rule files (PRD section 0, rule 3) and their stored copies."""

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.app_config import DOMAINS, ConfigError, get_config, load_config_file
from app.core.config import get_settings
from app.models import ConfigVersion
from app.services.config_registry import sync_config_versions


@pytest.mark.parametrize("domain", DOMAINS)
def test_every_repo_config_file_loads_with_a_version(domain: str) -> None:
    assert get_config(domain).version


def test_shariah_config_matches_prd_7_1_defaults() -> None:
    cfg = get_config("shariah").data
    assert cfg["default_method"] == "aaoifi"  # Q1 default
    assert cfg["review_margin_pts"] == 2.0
    assert cfg["methods"]["aaoifi"]["ratios"]["debt_to_market_cap"]["max_pct"] == 30.0
    assert cfg["methods"]["sp"]["ratios"]["receivables_to_market_cap"]["max_pct"] == 49.0
    assert "receivables_to_market_cap" not in cfg["methods"]["aaoifi"]["ratios"]


def test_zakat_config_matches_fr13_2() -> None:
    cfg = get_config("zakat").data
    assert cfg["rate_pct"] == 2.5
    assert cfg["nisab"] == {"gold_grams": 87.48, "silver_grams": 612.36}
    assert cfg["shares_method"] == "MARKET_VALUE"  # Q2 default


def test_file_without_version_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "zakat.yaml").write_text("rate_pct: 2.5\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="version"):
        load_config_file("zakat", tmp_path)


def test_unknown_domain_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="Unknown"):
        load_config_file("nope", tmp_path)


def _copy_configs(dest: Path) -> None:
    for domain in DOMAINS:
        source = get_settings().config_dir / f"{domain}.yaml"
        (dest / f"{domain}.yaml").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def test_sync_stores_each_version_once(session: Session, tmp_path: Path) -> None:
    _copy_configs(tmp_path)
    assert len(sync_config_versions(session, tmp_path)) == len(DOMAINS)
    assert sync_config_versions(session, tmp_path) == []
    assert len(session.scalars(select(ConfigVersion)).all()) == len(DOMAINS)


def test_sync_rejects_a_change_without_a_version_bump(session: Session, tmp_path: Path) -> None:
    _copy_configs(tmp_path)
    sync_config_versions(session, tmp_path)
    path = tmp_path / "zakat.yaml"
    path.write_text(
        path.read_text(encoding="utf-8").replace("rate_pct: 2.5", "rate_pct: 3"), encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="Bump"):
        sync_config_versions(session, tmp_path)
