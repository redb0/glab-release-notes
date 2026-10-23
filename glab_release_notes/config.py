"""Configuration for release note generation."""

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from glab_release_notes.models import ReleaseNotesError, SectionSpec

#: The config file looked up in the current directory by default.
DEFAULT_CONFIG_FILE = "release-notes.toml"

_DEFAULT_NOTES_FILE = "docs/release-notes.md"
_DEFAULT_UNRELEASED_HEADER = "## Latest Changes"
_DEFAULT_SECTION_PREFIX = "### "
_DEFAULT_SKIP_LABELS = ("release", "refactor", "test", "chore", "style")
_DEFAULT_ALWAYS_KEEP = ("Features", "Fixes")
_DEFAULT_SECTIONS = (
    SectionSpec("feature", "Features", "✨", "feat"),
    SectionSpec("bug", "Fixes", "🐛", "fix"),
    SectionSpec("docs", "Documentation", "📝", "docs"),
    SectionSpec("ci", "CI", "👷", "ci"),
)

_TOP_LEVEL_KEYS = (
    "file",
    "unreleased_header",
    "section_prefix",
    "skip_labels",
    "always_keep",
    "section",
)
_SECTION_KEYS = ("label", "header", "emoji", "anchor_prefix")


@dataclass(frozen=True, slots=True)
class NotesConfig:
    """The configurable text of the release notes."""

    notes_file: Path
    unreleased_header: str
    section_prefix: str
    skip_labels: frozenset[str]
    always_keep: tuple[str, ...]
    sections: tuple[SectionSpec, ...]

    @property
    def section_order(self) -> tuple[str, ...]:
        """Section headers in display order."""
        return tuple(spec.header for spec in self.sections)

    @property
    def by_header(self) -> Mapping[str, SectionSpec]:
        """Sections indexed by header."""
        return MappingProxyType({spec.header: spec for spec in self.sections})

    @property
    def by_label(self) -> Mapping[str, SectionSpec]:
        """Sections indexed by label."""
        return MappingProxyType({spec.label: spec for spec in self.sections})


def default_config() -> NotesConfig:
    """The built-in defaults (the team convention)."""
    return NotesConfig(
        notes_file=Path(_DEFAULT_NOTES_FILE),
        unreleased_header=_DEFAULT_UNRELEASED_HEADER,
        section_prefix=_DEFAULT_SECTION_PREFIX,
        skip_labels=frozenset(_DEFAULT_SKIP_LABELS),
        always_keep=_DEFAULT_ALWAYS_KEEP,
        sections=_DEFAULT_SECTIONS,
    )


def load_config(path: str | Path | None = None) -> NotesConfig:
    """Load the config from a TOML file, or from the built-in defaults.

    An explicit ``path`` must exist. Without one, ``release-notes.toml`` from the
    current directory is used if present.
    """
    if path is not None:
        config_path = Path(path)
        if not config_path.is_file():
            msg = f"Config file not found: {config_path}"
            raise ReleaseNotesError(msg)
        return _config_from_data(_read_toml(config_path))
    config_path = Path(DEFAULT_CONFIG_FILE)
    if config_path.is_file():
        return _config_from_data(_read_toml(config_path))
    return default_config()


def _read_toml(config_path: Path) -> dict[str, object]:
    try:
        with config_path.open("rb") as handle:
            data = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        msg = f"Invalid TOML in {config_path}: {exc}"
        raise ReleaseNotesError(msg) from exc
    return data


def _config_from_data(data: dict[str, object]) -> NotesConfig:
    unknown = sorted(set(data) - set(_TOP_LEVEL_KEYS))
    if unknown:
        msg = f"Unknown config keys: {', '.join(unknown)}"
        raise ReleaseNotesError(msg)

    sections = _parse_sections(data.get("section"))
    always_keep = _str_list(data.get("always_keep", list(_DEFAULT_ALWAYS_KEEP)), "always_keep")
    skip_labels = _str_list(data.get("skip_labels", list(_DEFAULT_SKIP_LABELS)), "skip_labels")
    known_headers = {spec.header for spec in sections}
    unknown_kept = [header for header in always_keep if header not in known_headers]
    if unknown_kept:
        msg = f"always_keep references unknown sections: {', '.join(unknown_kept)}"
        raise ReleaseNotesError(msg)

    return NotesConfig(
        notes_file=Path(str(data.get("file", _DEFAULT_NOTES_FILE))),
        unreleased_header=str(data.get("unreleased_header", _DEFAULT_UNRELEASED_HEADER)),
        section_prefix=str(data.get("section_prefix", _DEFAULT_SECTION_PREFIX)),
        skip_labels=frozenset(skip_labels),
        always_keep=tuple(always_keep),
        sections=sections,
    )


def _parse_sections(raw: object) -> tuple[SectionSpec, ...]:
    if not isinstance(raw, list) or not raw:
        msg = "At least one [[section]] is required"
        raise ReleaseNotesError(msg)
    sections: list[SectionSpec] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw):
        spec = _parse_section(entry, index)
        if spec.label in seen:
            msg = f"Duplicate section label: {spec.label}"
            raise ReleaseNotesError(msg)
        seen.add(spec.label)
        sections.append(spec)
    return tuple(sections)


def _parse_section(entry: object, index: int) -> SectionSpec:
    if not isinstance(entry, dict):
        msg = f"[[section]] #{index + 1} must be a table"
        raise ReleaseNotesError(msg)
    unknown = sorted(set(entry) - set(_SECTION_KEYS))
    if unknown:
        msg = f"[[section]] #{index + 1}: unknown keys {', '.join(unknown)}"
        raise ReleaseNotesError(msg)
    label = _required_str(entry, "label", index)
    header = _required_str(entry, "header", index)
    emoji = entry.get("emoji", "")
    if not isinstance(emoji, str):
        msg = f"[[section]] #{index + 1}: 'emoji' must be a string"
        raise ReleaseNotesError(msg)
    anchor = _required_str(entry, "anchor_prefix", index, default=label)
    return SectionSpec(label=label, header=header, emoji=emoji, anchor_prefix=anchor)


def _required_str(
    entry: dict[str, object], key: str, index: int, *, default: str | None = None
) -> str:
    value = entry.get(key, default)
    if not isinstance(value, str) or not value:
        required = "' is required" if default is None else "' must be a non-empty string"
        msg = f"[[section]] #{index + 1}: '{key}{required}"
        raise ReleaseNotesError(msg)
    return value


def _str_list(raw: object, name: str) -> list[str]:
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        msg = f"'{name}' must be a list of strings"
        raise ReleaseNotesError(msg)
    return raw
