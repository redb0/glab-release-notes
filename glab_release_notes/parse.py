"""Parse the quote, ticket key, and labels of a merge request."""

from glab_release_notes import constants
from glab_release_notes.config import NotesConfig
from glab_release_notes.models import Classification, LabelDecision, ReleaseNotesError


def parse_quote(description: str) -> str | None:
    """Return the last non-empty quote from the MR description."""
    matches: list[str] = [line.strip() for line in constants.quote_re.findall(description)]
    if not matches:
        return None
    return matches[-1]


def parse_ticket(branch: str) -> str | None:
    """Extract a Jira ticket key from a branch name."""
    match = constants.ticket_re.search(branch)
    if match is None:
        return None
    prefix = match.group(1).upper()
    number = match.group(2)
    return f"{prefix}-{number}"


def classify(labels: tuple[str, ...], cfg: NotesConfig) -> Classification:
    """Determine skip / missing / section from labels."""
    label_set = set(labels)
    if label_set & cfg.skip_labels:
        return Classification(LabelDecision.SKIP)
    for spec in cfg.sections:
        if spec.label in label_set:
            return Classification(LabelDecision.SECTION, spec)
    return Classification(LabelDecision.MISSING)


def validate_record(*, labels: tuple[str, ...], description: str, cfg: NotesConfig) -> None:
    """Check that the MR is ready to be recorded in the release notes."""
    classification = classify(labels, cfg)
    if classification.decision is LabelDecision.SKIP:
        return
    if classification.decision is LabelDecision.MISSING:
        section_labels = ", ".join(spec.label for spec in cfg.sections)
        skip_labels = ", ".join(sorted(cfg.skip_labels))
        msg = f"A section label ({section_labels}) or a skip label ({skip_labels}) is required"
        raise ReleaseNotesError(msg)
    if parse_quote(description) is None:
        msg = "The MR description has no entry text (a `> …` quote)"
        raise ReleaseNotesError(msg)


def already_recorded(notes_markdown: str, iid: int) -> bool:
    """Check whether a link to this MR is already present."""
    marker = f"/merge_requests/{iid})"
    return marker in notes_markdown
