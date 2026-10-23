"""Parse GitLab API JSON into a MergeRequest."""

from glab_release_notes.models import MergeRequest, ReleaseNotesError


def _labels_from_string(raw: str) -> tuple[str, ...]:
    parts = raw.split(",")
    return tuple(part.strip() for part in parts if part.strip())


def _labels_from_list(raw: list[object]) -> tuple[str, ...]:
    return tuple(
        raw_label.strip() for raw_label in raw if isinstance(raw_label, str) and raw_label.strip()
    )


def split_labels(raw: object) -> tuple[str, ...]:
    """Normalize labels from a string or a list from the API."""
    if isinstance(raw, str):
        return _labels_from_string(raw)
    if isinstance(raw, list):
        return _labels_from_list(raw)
    return ()


def _author_map(payload: dict[str, object]) -> dict[str, object]:
    author_obj = payload.get("author")
    if isinstance(author_obj, dict):
        return author_obj
    return {}


def merge_request_from_payload(payload: dict[str, object]) -> MergeRequest:
    """Build a MergeRequest from GitLab API JSON."""
    author = _author_map(payload)
    iid_raw = payload.get("iid", payload.get("id"))
    if not isinstance(iid_raw, int):
        msg = "No MR iid in the GitLab response"
        raise ReleaseNotesError(msg)
    return MergeRequest(
        iid=iid_raw,
        description=str(payload.get("description") or ""),
        labels=split_labels(payload.get("labels")),
        web_url=str(payload.get("web_url") or ""),
        author_username=str(author.get("username") or ""),
        author_url=str(author.get("web_url") or ""),
        source_branch=str(payload.get("source_branch") or ""),
        state=str(payload.get("state") or ""),
    )
