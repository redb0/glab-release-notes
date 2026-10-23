"""Insert an entry and promote unreleased entries under a version."""

from glab_release_notes import constants
from glab_release_notes.config import NotesConfig
from glab_release_notes.parse import already_recorded
from glab_release_notes.render import assemble, prepend_entry, render_unreleased
from glab_release_notes.split import parse_sections, split_unreleased


def has_items(body: str) -> bool:
    """Whether a section has any list items."""
    return constants.item_re.search(body) is not None


def append_note(notes_markdown: str, entry: str, header: str, *, cfg: NotesConfig) -> str:
    """Insert an entry into the right section of the unreleased block."""
    prefix, unreleased, postfix = split_unreleased(notes_markdown, cfg)
    sections = prepend_entry(parse_sections(unreleased, cfg), header, entry)
    return assemble(prefix, render_unreleased(sections, cfg), postfix)


def _version_blocks(sections: dict[str, str], version: str, cfg: NotesConfig) -> list[str]:
    blocks: list[str] = []
    for header in cfg.section_order:
        body = sections.get(header, "")
        if not has_items(body):
            continue
        spec = cfg.by_header[header]
        title = f"{cfg.section_prefix}{header} {{#{spec.anchor_prefix}_{version}}}"
        blocks.append(f"{title}{constants.double_newline}{body}")
    return blocks


def _assemble_promoted(
    *,
    prefix: str,
    postfix: str,
    version: str,
    blocks: list[str],
    cfg: NotesConfig,
) -> str:
    emptied: dict[str, str] = dict.fromkeys(cfg.always_keep, "")
    joined = constants.double_newline.join(blocks)
    heading = f"## {version}{constants.double_newline}{joined}"
    new_post = f"{heading}{constants.double_newline}{postfix.strip()}"
    return assemble(prefix, render_unreleased(emptied, cfg), new_post.strip())


def promote_notes(notes_markdown: str, version: str, cfg: NotesConfig) -> str:
    """Move non-empty unreleased sections under a version heading."""
    prefix, unreleased, postfix = split_unreleased(notes_markdown, cfg)
    blocks = _version_blocks(parse_sections(unreleased, cfg), version, cfg)
    if not blocks:
        return notes_markdown
    return _assemble_promoted(
        prefix=prefix, postfix=postfix, version=version, blocks=blocks, cfg=cfg
    )


class AppendMutator:
    """Re-inserts the entry after a git pull."""

    def __init__(self, entry: str, header: str, iid: int, *, cfg: NotesConfig) -> None:
        """Keep the entry text, the section, the MR iid, and the config."""
        self._entry = entry
        self._header = header
        self._iid = iid
        self._cfg = cfg

    def __call__(self, notes_markdown: str) -> str:
        """Return the markdown with the entry, if not already present."""
        if already_recorded(notes_markdown, self._iid):
            return notes_markdown
        return append_note(notes_markdown, self._entry, self._header, cfg=self._cfg)


class PromoteMutator:
    """Re-promotes the unreleased block after a git pull."""

    def __init__(self, version: str, cfg: NotesConfig) -> None:
        """Keep the version number and the config."""
        self._version = version
        self._cfg = cfg

    def __call__(self, notes_markdown: str) -> str:
        """Return the markdown with the promoted entries."""
        return promote_notes(notes_markdown, self._version, self._cfg)
