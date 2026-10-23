"""Low-level HTTP client for the GitLab API."""

import json
import os
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from glab_release_notes import constants
from glab_release_notes.models import ReleaseNotesError

type Payload = dict[str, object]


def api_url(path: str) -> str:
    """Build a GitLab API URL for the current project."""
    base = os.environ["CI_API_V4_URL"].rstrip("/")
    project = quote(str(os.environ["CI_PROJECT_ID"]), safe="")
    return f"{base}/projects/{project}/{path}"


def gitlab_json(path: str) -> object:
    """GET JSON with the CI job token."""
    url = api_url(path)
    headers = {"PRIVATE-TOKEN": os.environ["GITLAB_API_TOKEN"]}
    http_request = Request(url, headers=headers)  # noqa: S310
    try:
        with urlopen(http_request, timeout=constants.http_timeout) as response:  # noqa: S310
            return json.loads(response.read().decode())
    except HTTPError as exc:
        msg = f"GitLab API {url} -> HTTP {exc.code}"
        raise ReleaseNotesError(msg) from exc


def payload_list(raw: object) -> list[Payload]:
    """Keep only dict objects from an API response."""
    if not isinstance(raw, list):
        return []
    return [payload for payload in raw if isinstance(payload, dict)]
