"""Build the markdown sections of the release notes."""

from glab_release_notes import constants
from glab_release_notes.config import NotesConfig
from glab_release_notes.models import MergeRequest, SectionSpec

type Sections = dict[str, str]


def format_entry(
    *,
    text: str,
    spec: SectionSpec,
    mr: MergeRequest,
    ticket: str | None,
    jira_base: str | None = None,
) -> str:
    """Build a single list item for the release notes."""
    links = [f"[#{mr.iid}]({mr.web_url})"]
    if ticket is not None and jira_base is not None:
        links.append(f"[{ticket}]({jira_base}/{ticket})")
    emoji = f"{spec.emoji} " if spec.emoji else ""
    return f"* {emoji}{text} ({', '.join(links)}) by [@{mr.author_username}]({mr.author_url})"


def render_unreleased(sections: Sections, cfg: NotesConfig) -> str:
    """Build the unreleased block.

    The ``always_keep`` sections are always present; other sections only when non-empty.
    """
    blocks: list[str] = []
    for header in cfg.section_order:
        _append_section_block(blocks, sections, header, cfg=cfg)
    return constants.double_newline.join(blocks)


def _append_section_block(
    blocks: list[str],
    sections: Sections,
    header: str,
    *,
    cfg: NotesConfig,
) -> None:
    body = sections.get(header, "")
    keep_empty = header in cfg.always_keep
    if not body and not keep_empty:
        return
    prefix = f"{cfg.section_prefix}{header}"
    if body:
        blocks.append(f"{prefix}{constants.double_newline}{body}")
        return
    blocks.append(prefix)


def assemble(prefix: str, unreleased: str, postfix: str) -> str:
    """Join the file parts with a single trailing newline."""
    chunks = [prefix.rstrip(), unreleased.strip()]
    post_stripped = postfix.strip()
    if post_stripped:
        chunks.append(post_stripped)
    joined = constants.double_newline.join(chunks)
    return f"{joined}\n"


def prepend_entry(sections: Sections, header: str, entry: str) -> Sections:
    """Add an entry at the top of a section."""
    current = sections.get(header, "")
    if not current:
        sections[header] = entry
        return sections
    combined = f"{entry}\n{current}"
    sections[header] = combined.strip()
    return sections
