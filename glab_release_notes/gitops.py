"""Commit and push the updated release notes."""

import logging
import subprocess
from collections.abc import Callable
from pathlib import Path

from glab_release_notes import constants
from glab_release_notes.models import ReleaseNotesError

logger = logging.getLogger(__name__)


def _run_git(args: list[str], *, check: bool) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=check, text=True)  # noqa: S603


def _commit_notes(path: Path, message: str, updated: str) -> subprocess.CompletedProcess[str]:
    encoding = constants.encoding
    git = constants.git_bin
    path.write_text(updated, encoding=encoding)
    _run_git([git, "add", str(path)], check=True)
    _run_git([git, "commit", "-m", message], check=True)
    return _run_git([git, "push"], check=False)


def _reset_notes(path: Path) -> None:
    git = constants.git_bin
    _run_git([git, "reset", "HEAD^"], check=True)
    _run_git([git, "checkout", "--", str(path)], check=True)


def _try_push(path: Path, message: str, mutate: Callable[[str], str]) -> bool:
    git = constants.git_bin
    encoding = constants.encoding
    _run_git([git, "pull", "--rebase"], check=False)
    current = path.read_text(encoding=encoding)
    updated = mutate(current)
    if updated == current:
        logger.info("Nothing to change, skipping")
        return True
    pushed = _commit_notes(path, message, updated)
    if pushed.returncode == 0:
        return True
    _reset_notes(path)
    return False


def push_notes(path: Path, message: str, mutate: Callable[[str], str]) -> None:
    """Commit the notes, retrying on a push race."""
    for trial in range(constants.push_retries):
        logger.info("Push attempt %s/%s", trial + 1, constants.push_retries)
        if _try_push(path, message, mutate):
            return
    msg = f"Could not push the notes after {constants.push_retries} attempts"
    raise ReleaseNotesError(msg)
