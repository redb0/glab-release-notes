"""The append command: record a merged merge request."""

import logging
from pathlib import Path

from glab_release_notes import constants
from glab_release_notes.config import NotesConfig
from glab_release_notes.edit import AppendMutator
from glab_release_notes.gitops import push_notes
from glab_release_notes.load import load_mr_for_append
from glab_release_notes.models import Classification, LabelDecision, MergeRequest, ReleaseNotesError
from glab_release_notes.parse import (
    already_recorded,
    classify,
    parse_quote,
    parse_ticket,
    validate_record,
)
from glab_release_notes.render import format_entry

logger = logging.getLogger(__name__)


def _build_entry(
    merge_request: MergeRequest,
    classification: Classification,
    *,
    cfg: NotesConfig,
    jira_base: str | None,
) -> tuple[str, str]:
    validate_record(labels=merge_request.labels, description=merge_request.description, cfg=cfg)
    if classification.spec is None:
        msg = "No section after a successful validation"
        raise ReleaseNotesError(msg)
    quote = parse_quote(merge_request.description)
    if quote is None:
        msg = "No entry text"
        raise ReleaseNotesError(msg)
    entry = format_entry(
        text=quote,
        spec=classification.spec,
        mr=merge_request,
        ticket=parse_ticket(merge_request.source_branch),
        jira_base=jira_base,
    )
    return entry, classification.spec.header


def _is_skipped(
    merge_request: MergeRequest,
    notes_path: Path,
    classification: Classification,
) -> bool:
    if merge_request.state and merge_request.state != "merged":
        logger.info("MR !%s is in state %s, skipping", merge_request.iid, merge_request.state)
        return True
    if classification.decision is LabelDecision.SKIP:
        logger.info("Skip label on MR !%s, skipping", merge_request.iid)
        return True
    notes_markdown = notes_path.read_text(encoding=constants.encoding)
    if already_recorded(notes_markdown, merge_request.iid):
        logger.info("MR !%s is already recorded, skipping", merge_request.iid)
        return True
    return False


def cmd_append(*, notes_path: Path, cfg: NotesConfig, jira_base: str | None = None) -> None:
    """Record a merged merge request and push the commit."""
    merge_request = load_mr_for_append()
    if merge_request is None:
        logger.info("No merge request found, skipping")
        return
    classification = classify(merge_request.labels, cfg)
    if _is_skipped(merge_request, notes_path, classification):
        return
    entry, header = _build_entry(merge_request, classification, cfg=cfg, jira_base=jira_base)
    push_notes(
        notes_path,
        f"chore(notes): add entry for MR !{merge_request.iid}",
        AppendMutator(entry, header, merge_request.iid, cfg=cfg),
    )
