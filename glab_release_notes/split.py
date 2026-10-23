"""Split the release notes markdown into sections."""

import re

from glab_release_notes import constants
from glab_release_notes.config import NotesConfig
from glab_release_notes.models import ReleaseNotesError


def _find_unreleased(notes_markdown: str, cfg: NotesConfig) -> re.Match[str]:
    header = cfg.unreleased_header
    match = re.search(rf"^{re.escape(header)}\s*$", notes_markdown, re.MULTILINE)
    if match is None:
        msg = f"Header {header!r} not found"
        raise ReleaseNotesError(msg)
    return match


def _cut_after_header(prefix: str, rest: str) -> tuple[str, str, str]:
    next_version = constants.version_line_re.search(rest)
    if next_version is None:
        return prefix, rest, ""
    start = next_version.start()
    return prefix, rest[:start], rest[start:]


def split_unreleased(notes_markdown: str, cfg: NotesConfig) -> tuple[str, str, str]:
    """Cut the file into a header, the unreleased block, and the rest."""
    match = _find_unreleased(notes_markdown, cfg)
    prefix = notes_markdown[: match.end()]
    rest = notes_markdown[match.end() :]
    return _cut_after_header(prefix, rest)


def _header_name(raw: str) -> str:
    return constants.anchor_re.sub("", raw).strip()


def _section_end(matches: list[re.Match[str]], index: int, unreleased: str) -> int:
    if index + 1 < len(matches):
        return matches[index + 1].start()
    return len(unreleased)


def _fill_sections(matches: list[re.Match[str]], unreleased: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        title = _header_name(match.group(1))
        end = _section_end(matches, index, unreleased)
        sections[title] = unreleased[match.end() : end].strip()
    return sections


def parse_sections(unreleased: str, cfg: NotesConfig) -> dict[str, str]:
    """Parse the section lines of the unreleased block."""
    section_re = re.compile(rf"^{re.escape(cfg.section_prefix)}(.+)$", re.MULTILINE)
    matches = list(section_re.finditer(unreleased))
    return _fill_sections(matches, unreleased)
