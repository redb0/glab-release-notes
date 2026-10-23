"""Fetch merge requests from the GitLab API."""

from urllib.parse import quote

from glab_release_notes.http import Payload, gitlab_json, payload_list
from glab_release_notes.models import MergeRequest, ReleaseNotesError
from glab_release_notes.payload import merge_request_from_payload


def fetch_mr(iid: int) -> MergeRequest:
    """Load a merge request by iid."""
    raw = gitlab_json(f"merge_requests/{iid}")
    if not isinstance(raw, dict):
        msg = f"Invalid GitLab response for MR !{iid}"
        raise ReleaseNotesError(msg)
    return merge_request_from_payload(raw)


def _first_or_none(payloads: list[Payload]) -> Payload | None:
    if payloads:
        return payloads[0]
    return None


def _pick_payload(payloads: list[Payload]) -> Payload | None:
    merged = [payload for payload in payloads if payload.get("state") == "merged"]
    chosen = _first_or_none(merged)
    if chosen is not None:
        return chosen
    return _first_or_none(payloads)


def fetch_mr_for_commit(sha: str) -> MergeRequest | None:
    """Find the merged merge request for a commit SHA."""
    encoded = quote(sha, safe="")
    path = f"repository/commits/{encoded}/merge_requests"
    chosen = _pick_payload(payload_list(gitlab_json(path)))
    if chosen is None:
        return None
    return merge_request_from_payload(chosen)
