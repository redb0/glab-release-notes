"""Pick the merge request from CI variables."""

import os

from glab_release_notes.api import fetch_mr, fetch_mr_for_commit
from glab_release_notes.models import MergeRequest, ReleaseNotesError


def _env_value(name: str) -> str:
    return os.environ.get(name, "").strip()


def load_mr_for_validate() -> MergeRequest:
    """MR for validation: iid from the merge request pipeline."""
    iid = _env_value("CI_MERGE_REQUEST_IID")
    if not iid:
        msg = "CI_MERGE_REQUEST_IID is required"
        raise ReleaseNotesError(msg)
    return fetch_mr(int(iid))


def load_mr_for_append() -> MergeRequest | None:
    """MR for appending: manual MR_IID or the MR of the current commit."""
    iid = _env_value("MR_IID")
    if iid:
        return fetch_mr(int(iid))
    sha = _env_value("CI_COMMIT_SHA")
    if not sha:
        return None
    return fetch_mr_for_commit(sha)
