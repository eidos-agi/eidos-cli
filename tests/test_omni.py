"""Unit tests for eidos omni tenant targeting and row shape."""

from __future__ import annotations

from eidos_cli.omni import (
    INDEX_KEY,
    OmniError,
    ROW_FIELDS,
    build_row,
    pair_for,
    parse_data,
)


def test_reeves_pair_is_hostkey_prove_target() -> None:
    pair = pair_for("reeves")
    assert pair.container == "reeves-omni"
    assert pair.host == "127.0.0.1"
    assert pair.port == 16772


def test_other_tenant_pairs() -> None:
    assert pair_for("eidos").port == 16773
    assert pair_for("aic").container == "aic-omni"
    assert pair_for("aic").port == 16774
    assert pair_for("arp").port == 16775
    assert pair_for("gmw").port == 16776
    assert pair_for("GMW").container == "gmw-omni"


def test_kai_has_no_omni() -> None:
    try:
        pair_for("kai")
    except OmniError as exc:
        assert "no paired Omni" in str(exc)
    else:
        raise AssertionError("kai must be refused")


def test_unknown_tenant_is_refused() -> None:
    try:
        pair_for("tabletop")
    except OmniError as exc:
        assert "unknown tenant" in str(exc)
    else:
        raise AssertionError("unknown tenant must be refused")


def test_row_has_exactly_four_fields() -> None:
    row = build_row(tenant="reeves", kind="probe")
    assert tuple(row) == ROW_FIELDS
    assert row["kind"] == "probe"
    assert row["id"]
    assert row["data"]["tenant"] == "reeves"
    assert row["emb"] == []


def test_parse_data_json_or_text() -> None:
    assert parse_data('{"a": 1}') == {"a": 1}
    assert parse_data("plain") == "plain"


def test_index_key() -> None:
    assert INDEX_KEY == "omni:index"
