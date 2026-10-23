"""Release notes for GitLab projects, generated from merged merge requests."""

from glab_release_notes.config import NotesConfig, default_config, load_config
from glab_release_notes.edit import append_note, promote_notes
from glab_release_notes.models import LabelDecision, MergeRequest, ReleaseNotesError
from glab_release_notes.parse import (
    already_recorded,
    classify,
    parse_quote,
    parse_ticket,
    validate_record,
)
from glab_release_notes.payload import merge_request_from_payload
from glab_release_notes.render import format_entry

__all__ = (
    "LabelDecision",
    "MergeRequest",
    "NotesConfig",
    "ReleaseNotesError",
    "already_recorded",
    "append_note",
    "classify",
    "default_config",
    "format_entry",
    "load_config",
    "merge_request_from_payload",
    "parse_quote",
    "parse_ticket",
    "promote_notes",
    "validate_record",
)
