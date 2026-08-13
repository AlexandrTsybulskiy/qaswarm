from datetime import datetime, timedelta, timezone
from pathlib import Path

import memory_schema

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = ROOT / "fixtures" / "demo-catalog" / "expected"
INCOMING = ROOT / "fixtures" / "demo-catalog" / "incoming"


def test_valid_expected_tree_has_no_errors() -> None:
    errors = memory_schema.validate_memory_tree(EXPECTED)
    assert errors == []


def test_card_missing_fetched_at_fails(tmp_path: Path) -> None:
    card = tmp_path / "user.md"
    card.write_text(
        "---\nslug: user\ntitle: User\nstatus: map\nsource: public\n"
        "product: demo\n---\n\nUser entity.\n",
        encoding="utf-8",
    )
    errors = memory_schema.validate_card(card)
    assert any("fetched_at" in e for e in errors)


def test_slug_rejects_uppercase() -> None:
    assert memory_schema.slug_ok("User") is False
    assert memory_schema.slug_ok("user") is True
    assert memory_schema.slug_ok("order-item") is True


def test_ttl_fresh_within_default_hours() -> None:
    now = datetime(2026, 8, 13, 20, 0, tzinfo=timezone.utc)
    fetched = (now - timedelta(hours=24)).isoformat()
    assert memory_schema.is_fresh(fetched, 168, now) is True


def test_ttl_expired_after_ttl_hours() -> None:
    now = datetime(2026, 8, 13, 20, 0, tzinfo=timezone.utc)
    fetched = (now - timedelta(hours=169)).isoformat()
    assert memory_schema.is_fresh(fetched, 168, now) is False


def test_incoming_without_manifest_is_incomplete(tmp_path: Path) -> None:
    incoming = tmp_path / "_incoming"
    incoming.mkdir()
    (incoming / "catalog.json").write_text("{}", encoding="utf-8")
    assert memory_schema.incoming_complete(incoming) is False


def test_demo_incoming_is_complete() -> None:
    assert memory_schema.incoming_complete(INCOMING) is True


def test_secret_like_value_in_card_fails(tmp_path: Path) -> None:
    card = tmp_path / "user.md"
    card.write_text(
        "---\nslug: user\ntitle: User\nstatus: map\nsource: public\n"
        "fetched_at: 2026-08-13T17:00:00+03:00\nproduct: demo\n---\n\n"
        "token: sk-abc123secret\n",
        encoding="utf-8",
    )
    errors = memory_schema.validate_card(card)
    assert any("secret" in e.lower() for e in errors)
