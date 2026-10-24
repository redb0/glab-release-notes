"""Tests for release note generation and configuration."""

from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from glab_release_notes import cli
from glab_release_notes.config import (
    NotesConfig,
    default_config,
    load_config,
)
from glab_release_notes.edit import append_note, promote_notes
from glab_release_notes.load import load_mr_for_validate
from glab_release_notes.models import LabelDecision, MergeRequest, ReleaseNotesError, SectionSpec
from glab_release_notes.parse import (
    already_recorded,
    classify,
    parse_quote,
    parse_ticket,
    validate_record,
)
from glab_release_notes.payload import merge_request_from_payload
from glab_release_notes.render import format_entry

if TYPE_CHECKING:
    from collections.abc import Callable

_NEW_IID = 33
_RECORDED_IID = 35
_VALIDATE_IID = 42
_PAYLOAD_IID = 10
_JIRA_BASE = "https://jira.example/browse"
_CFG = default_config()

SAMPLE = """\
# Release notes

## Latest Changes

### Features

### Fixes

## 0.8.1

### Fixes {#fix_0.8.1}

* 🐛 Old fix ([#35](https://gitlab.example/merge_requests/35))
"""

CUSTOM_TOML = """\
file = "docs/notes.md"
unreleased_header = "## Upcoming"
section_prefix = "### "
skip_labels = ["release", "chore"]
always_keep = ["Highlights"]

[[section]]
label = "enhancement"
header = "Highlights"
emoji = "🚀"
anchor_prefix = "enh"

[[section]]
label = "bug"
header = "Defects"
emoji = "🐛"
"""


def _mr(**overrides: object) -> MergeRequest:
    fields = {
        "iid": _NEW_IID,
        "description": "> Support for detailed gRPC errors\n",
        "labels": ("feature",),
        "web_url": "https://gitlab.example/your/project/-/merge_requests/33",
        "author_username": "alice",
        "author_url": "https://gitlab.example/alice",
        "source_branch": "PROJ-123",
        "state": "merged",
    }
    fields.update(overrides)
    return MergeRequest(**fields)  # type: ignore[arg-type]


def _feature_entry() -> str:
    return f"* ✨ New feature ([#{_NEW_IID}](https://gitlab.example/merge_requests/{_NEW_IID}))"


def _notes_with_feature_item() -> str:
    return append_note(SAMPLE, _feature_entry(), "Features", cfg=_CFG)


def _recording_fetch(fetched: list[int], iid: int) -> MergeRequest:
    fetched.append(iid)
    return _mr(iid=iid)


def test_parse_quote_takes_last_non_empty() -> None:
    """The entry quote is the last non-empty `>` line."""
    description = "instructions\n\n> \n\n> Support for detailed gRPC errors\n"
    assert parse_quote(description) == "Support for detailed gRPC errors"


def test_parse_quote_missing() -> None:
    """Without a filled quote there is no entry text."""
    assert parse_quote("## Release notes\n\n> \n") is None


def test_parse_ticket_from_branch() -> None:
    """The Jira key is normalized from PROJ-123 and proj_123."""
    assert parse_ticket("PROJ-123") == "PROJ-123"
    assert parse_ticket("proj_123") == "PROJ-123"
    assert parse_ticket("coverage-mr") is None


def test_classify_skip_wins_over_section() -> None:
    """A skip label overrides a section label."""
    classification = classify(("feature", "release"), _CFG)
    assert classification.decision is LabelDecision.SKIP


def test_classify_first_section_label() -> None:
    """With several section labels the first one from the config wins."""
    classification = classify(("docs", "feature"), _CFG)
    assert classification.decision is LabelDecision.SECTION
    assert classification.spec is not None
    assert classification.spec.label == "feature"


def test_classify_missing() -> None:
    """Without a section or skip label the decision is missing."""
    assert classify(("foo",), _CFG).decision is LabelDecision.MISSING


def test_validate_skip_does_not_need_quote() -> None:
    """A skip label does not require a quote."""
    validate_record(labels=("refactor",), description="", cfg=_CFG)


def test_validate_missing_label() -> None:
    """Without any label the validation fails."""
    with pytest.raises(ReleaseNotesError, match="label"):
        validate_record(labels=(), description="> text", cfg=_CFG)


def test_validate_missing_quote() -> None:
    """A section label without a quote is an error."""
    with pytest.raises(ReleaseNotesError, match="quote"):
        validate_record(labels=("bug",), description="no quote", cfg=_CFG)


def test_validate_message_lists_configured_labels() -> None:
    """The validation error names the labels of the active config."""
    cfg = NotesConfig(
        notes_file=Path("docs/notes.md"),
        unreleased_header="## Upcoming",
        section_prefix="### ",
        skip_labels=frozenset({"skip-me"}),
        always_keep=(),
        sections=(SectionSpec("enhancement", "Highlights", "🚀", "enh"),),
    )
    with pytest.raises(ReleaseNotesError, match="enhancement"):
        validate_record(labels=(), description="> text", cfg=cfg)
    with pytest.raises(ReleaseNotesError, match="skip-me"):
        validate_record(labels=(), description="> text", cfg=cfg)


def test_format_entry_with_jira() -> None:
    """An entry contains the emoji, the IID, the Jira link, and the author."""
    spec = _CFG.by_label["feature"]
    line = format_entry(
        text="gRPC support",
        spec=spec,
        mr=_mr(),
        ticket="PROJ-123",
        jira_base=_JIRA_BASE,
    )
    assert line.startswith("* ✨ gRPC support ")
    assert "[#33](https://gitlab.example/your/project/-/merge_requests/33)" in line
    assert "[PROJ-123](https://jira.example/browse/PROJ-123)" in line
    assert "[@alice](https://gitlab.example/alice)" in line


def test_format_entry_without_ticket() -> None:
    """Without a ticket key there is no Jira link."""
    spec = _CFG.by_label["bug"]
    line = format_entry(text="Fix", spec=spec, mr=_mr(), ticket=None, jira_base=_JIRA_BASE)
    assert "jira.example" not in line
    assert "[#33](" in line


def test_format_entry_without_jira_base() -> None:
    """Without jira_base there is no Jira link, even if a ticket is present."""
    spec = _CFG.by_label["feature"]
    line = format_entry(
        text="gRPC support",
        spec=spec,
        mr=_mr(),
        ticket="PROJ-123",
        jira_base=None,
    )
    assert "jira.example" not in line
    assert "[PROJ-123]" not in line
    assert "[#33](" in line


def test_format_entry_empty_jira_base() -> None:
    """An empty jira_base (unset CI variable) behaves the same as absent."""
    spec = _CFG.by_label["feature"]
    line = format_entry(
        text="gRPC support",
        spec=spec,
        mr=_mr(),
        ticket="PROJ-123",
        jira_base="",
    )
    assert "[PROJ-123]" not in line
    assert "[#33](" in line


def test_format_entry_without_emoji() -> None:
    """A section without an emoji produces a plain entry."""
    spec = SectionSpec("bug", "Defects", "", "bug")
    line = format_entry(text="Fix", spec=spec, mr=_mr(), ticket=None, jira_base=_JIRA_BASE)
    assert line.startswith("* Fix ")
    assert "  " not in line.split(" (")[0]


def test_append_note_prepends_feature() -> None:
    """A new entry goes to the top of the Features section."""
    updated = append_note(SAMPLE, _feature_entry(), "Features", cfg=_CFG)
    unreleased = updated.split("## 0.8.1")[0]
    assert "* ✨ New feature" in unreleased
    assert unreleased.index("### Features") < unreleased.index("* ✨ New feature")
    assert unreleased.index("* ✨ New feature") < unreleased.index("### Fixes")
    assert "* 🐛 Old fix" in updated.split("## 0.8.1")[1]


def test_append_note_creates_docs_section() -> None:
    """The Documentation section appears only when it has an entry."""
    entry = "* 📝 Docs ([#40](https://gitlab.example/merge_requests/40))"
    updated = append_note(SAMPLE, entry, "Documentation", cfg=_CFG)
    unreleased = updated.split("## 0.8.1")[0]
    assert "### Documentation" in unreleased
    assert "* 📝 Docs" in unreleased


def test_already_recorded() -> None:
    """A repeated IID is not written again."""
    assert already_recorded(SAMPLE, _RECORDED_IID)
    assert not already_recorded(SAMPLE, _NEW_IID)


def test_promote_moves_item_under_version() -> None:
    """Promotion moves the entry under the version heading."""
    promoted = promote_notes(_notes_with_feature_item(), "0.8.2", _CFG)
    rest = promoted.split("## 0.8.2", 1)[1]
    assert "### Features {#feat_0.8.2}" in rest
    assert "* ✨ New feature" in rest.split("## 0.8.1")[0]
    assert "## 0.8.1" in rest


def test_promote_restores_empty_unreleased() -> None:
    """After promotion the unreleased block is empty Features/Fixes again."""
    promoted = promote_notes(_notes_with_feature_item(), "0.8.2", _CFG)
    after_header, rest = promoted.split("## 0.8.2", 1)
    unreleased = after_header.split("## Latest Changes")[1]
    assert "### Features" in after_header
    assert "* ✨ New feature" not in unreleased
    assert "### Fixes {#fix_0.8.2}" not in rest
    assert "### Documentation" not in unreleased


def test_promote_noop_when_empty() -> None:
    """An empty unreleased block creates no version section."""
    assert promote_notes(SAMPLE, "0.8.2", _CFG) == SAMPLE


def test_load_mr_for_validate_requires_iid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without CI_MERGE_REQUEST_IID validation is not skipped."""
    monkeypatch.delenv("CI_MERGE_REQUEST_IID", raising=False)
    with pytest.raises(ReleaseNotesError, match="CI_MERGE_REQUEST_IID"):
        load_mr_for_validate()


def test_load_mr_for_validate_fetches_by_iid(monkeypatch: pytest.MonkeyPatch) -> None:
    """The MR for validation is fetched by iid from the pipeline."""
    fetched: list[int] = []
    monkeypatch.setenv("CI_MERGE_REQUEST_IID", str(_VALIDATE_IID))
    monkeypatch.setattr(
        "glab_release_notes.load.fetch_mr",
        partial(_recording_fetch, fetched),
    )
    merge_request = load_mr_for_validate()
    assert fetched == [_VALIDATE_IID]
    assert merge_request.iid == _VALIDATE_IID


def test_cmd_promote_pushes_commit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Promotion goes through push_notes, not separate git calls in CI."""
    notes_path = tmp_path / "release-notes.md"
    seen: list[str] = []

    def _push(path: Path, message: str, mutate: Callable[[str], str]) -> None:
        seen.append(message)
        current = path.read_text(encoding="utf-8")
        path.write_text(mutate(current), encoding="utf-8")

    monkeypatch.setattr("glab_release_notes.cli.push_notes", _push)
    notes_path.write_text(_notes_with_feature_item(), encoding="utf-8")
    cli.cmd_promote(notes_path=notes_path, cfg=_CFG, version="0.8.2")
    assert seen == ["chore(notes): promote 0.8.2"]
    assert "## 0.8.2" in notes_path.read_text(encoding="utf-8")


def test_cmd_promote_no_push(tmp_path: Path) -> None:
    """--no-push rewrites the file without touching git."""
    notes_path = tmp_path / "release-notes.md"
    notes_path.write_text(_notes_with_feature_item(), encoding="utf-8")
    cli.cmd_promote(notes_path=notes_path, cfg=_CFG, version="0.8.2", push=False)
    assert "## 0.8.2" in notes_path.read_text(encoding="utf-8")


def test_merge_request_from_payload() -> None:
    """Parsing GitLab JSON into a MergeRequest."""
    payload: dict[str, object] = {
        "iid": _PAYLOAD_IID,
        "description": "> Text",
        "labels": ["bug", "ci"],
        "web_url": "https://example/merge_requests/10",
        "author": {"username": "ann", "web_url": "https://example/ann"},
        "source_branch": "fix-log",
        "state": "merged",
    }
    merge_request = merge_request_from_payload(payload)
    assert merge_request.iid == _PAYLOAD_IID
    assert merge_request.labels == ("bug", "ci")
    assert merge_request.author_username == "ann"
    assert merge_request.source_branch == "fix-log"


# --- Configuration ---------------------------------------------------------


def test_load_config_defaults_without_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without a config file the built-in defaults are used."""
    monkeypatch.chdir(tmp_path)
    assert load_config() == default_config()


def test_load_config_autodetects_config_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A release-notes.toml in the current directory is picked up."""
    (tmp_path / "release-notes.toml").write_text(CUSTOM_TOML, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert cfg.unreleased_header == "## Upcoming"
    assert cfg.notes_file == Path("docs/notes.md")
    assert cfg.skip_labels == frozenset({"release", "chore"})
    assert cfg.always_keep == ("Highlights",)
    assert cfg.section_order == ("Highlights", "Defects")
    assert cfg.by_label["bug"].emoji == "🐛"


def test_load_config_explicit_path(tmp_path: Path) -> None:
    """An explicit --config path is used as-is."""
    config_path = tmp_path / "custom.toml"
    config_path.write_text(CUSTOM_TOML, encoding="utf-8")
    cfg = load_config(config_path)
    assert cfg.unreleased_header == "## Upcoming"


def test_load_config_explicit_path_missing(tmp_path: Path) -> None:
    """A missing explicit config file is an error."""
    with pytest.raises(ReleaseNotesError, match="Config file not found"):
        load_config(tmp_path / "nope.toml")


def test_load_config_unknown_top_level_key(tmp_path: Path) -> None:
    """Unknown top-level keys are rejected."""
    config_path = tmp_path / "bad.toml"
    config_path.write_text(
        'prefix = "### "\n'
        'file = "docs/notes.md"\n'
        '\n[[section]]\nlabel = "feature"\nheader = "Features"\n',
        encoding="utf-8",
    )
    with pytest.raises(ReleaseNotesError, match="Unknown config keys: prefix"):
        load_config(config_path)


def test_load_config_unknown_section_key(tmp_path: Path) -> None:
    """Unknown keys in a [[section]] table are rejected."""
    config_path = tmp_path / "bad.toml"
    config_path.write_text(
        CUSTOM_TOML + '\n[[section]]\nlabel = "x"\nheader = "X"\nicon = "i"\n',
        encoding="utf-8",
    )
    with pytest.raises(ReleaseNotesError, match="unknown keys icon"):
        load_config(config_path)


def test_load_config_requires_section(tmp_path: Path) -> None:
    """A config without any [[section]] is rejected."""
    config_path = tmp_path / "bad.toml"
    config_path.write_text('file = "docs/notes.md"\n', encoding="utf-8")
    with pytest.raises(ReleaseNotesError, match="At least one \\[\\[section\\]\\]"):
        load_config(config_path)


def test_load_config_duplicate_label(tmp_path: Path) -> None:
    """Duplicate section labels are rejected."""
    config_path = tmp_path / "bad.toml"
    config_path.write_text(
        CUSTOM_TOML + '\n[[section]]\nlabel = "bug"\nheader = "Other"\n',
        encoding="utf-8",
    )
    with pytest.raises(ReleaseNotesError, match="Duplicate section label: bug"):
        load_config(config_path)


def test_load_config_always_keep_unknown_header(tmp_path: Path) -> None:
    """always_keep must reference a configured section header."""
    config_path = tmp_path / "bad.toml"
    config_path.write_text(
        'file = "docs/notes.md"\n'
        'always_keep = ["Features"]\n'
        '\n[[section]]\nlabel = "feature"\nheader = "Highlights"\n',
        encoding="utf-8",
    )
    with pytest.raises(ReleaseNotesError, match="unknown sections: Features"):
        load_config(config_path)


def test_main_uses_config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI wires a custom config file into promote end to end."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").mkdir()
    notes_path = tmp_path / "docs" / "notes.md"
    notes_path.write_text(
        "# Notes\n\n## Upcoming\n\n### Highlights\n\n"
        "* 🚀 Shiny ([#7](https://gitlab.example/merge_requests/7)) by [@ann](https://gitlab.example/ann)\n\n"
        "### Defects\n",
        encoding="utf-8",
    )
    config_path = tmp_path / "release-notes.toml"
    config_path.write_text(CUSTOM_TOML, encoding="utf-8")

    cli.main(["--config", str(config_path), "promote", "--version", "1.0.0", "--no-push"])

    updated = notes_path.read_text(encoding="utf-8")
    assert "## 1.0.0" in updated
    assert "### Highlights {#enh_1.0.0}" in updated
    assert "* 🚀 Shiny" in updated
    assert "## Upcoming" in updated


def test_custom_section_prefix_roundtrip() -> None:
    """A non-default section prefix is written and re-parsed."""
    cfg = NotesConfig(
        notes_file=Path("notes.md"),
        unreleased_header="## Upcoming",
        section_prefix="#### ",
        skip_labels=frozenset({"release"}),
        always_keep=("Highlights",),
        sections=(SectionSpec("feature", "Highlights", "✨", "feat"),),
    )
    notes = "# Notes\n\n## Upcoming\n\n#### Highlights\n"
    updated = append_note(
        notes, "* ✨ One ([#1](https://gitlab.example/merge_requests/1))", "Highlights", cfg=cfg
    )
    assert "#### Highlights\n\n* ✨ One" in updated

    promoted = promote_notes(updated, "2.0.0", cfg)
    assert "#### Highlights {#feat_2.0.0}" in promoted
