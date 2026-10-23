"""Data models for release notes."""

from dataclasses import dataclass
from enum import Enum


class LabelDecision(Enum):
    """Result of analyzing a merge request's labels."""

    SKIP = "skip"
    MISSING = "missing"
    SECTION = "section"


class ReleaseNotesError(Exception):
    """Error while validating or updating release notes."""


@dataclass(frozen=True, slots=True)
class SectionSpec:
    """A GitLab label and its section header, emoji, and anchor prefix."""

    label: str
    header: str
    emoji: str
    anchor_prefix: str


@dataclass(frozen=True, slots=True)
class Classification:
    """Classification of a merge request by its labels."""

    decision: LabelDecision
    spec: SectionSpec | None = None


@dataclass(frozen=True, slots=True)
class MergeRequest:
    """Merge request data needed to record an entry."""

    iid: int
    description: str
    labels: tuple[str, ...]
    web_url: str
    author_username: str
    author_url: str
    source_branch: str
    state: str
