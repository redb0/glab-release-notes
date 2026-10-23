"""CLI commands: validate, append, promote."""

import argparse
import logging
import sys
from pathlib import Path

from glab_release_notes import constants
from glab_release_notes.append_cmd import cmd_append
from glab_release_notes.config import NotesConfig, load_config
from glab_release_notes.edit import PromoteMutator, promote_notes
from glab_release_notes.gitops import push_notes
from glab_release_notes.load import load_mr_for_validate
from glab_release_notes.models import ReleaseNotesError
from glab_release_notes.parse import validate_record

logger = logging.getLogger(__name__)


def cmd_validate(cfg: NotesConfig) -> None:
    """Validate the labels and quote of the current merge request."""
    merge_request = load_mr_for_validate()
    validate_record(labels=merge_request.labels, description=merge_request.description, cfg=cfg)
    logger.info("Release notes validation passed for MR !%s", merge_request.iid)


def _write_promoted(notes_path: Path, version: str, cfg: NotesConfig) -> None:
    current = notes_path.read_text(encoding=constants.encoding)
    updated = promote_notes(current, version, cfg)
    if updated == current:
        logger.info("Nothing to change, skipping")
        return
    notes_path.write_text(updated, encoding=constants.encoding)


def cmd_promote(*, notes_path: Path, cfg: NotesConfig, version: str, push: bool = True) -> None:
    """Promote the unreleased block under a version heading.

    With ``push=False`` the file is rewritten in place only; the release
    process owns the commit.
    """
    if not push:
        _write_promoted(notes_path, version, cfg)
        return
    message = f"chore(notes): promote {version}"
    push_notes(notes_path, message, PromoteMutator(version, cfg))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Maintain release notes from merged GitLab MRs")
    parser.add_argument(
        "--config",
        default=None,
        metavar="PATH",
        help="TOML config file; defaults to release-notes.toml in the current directory",
    )
    parser.add_argument(
        "--file",
        default=None,
        metavar="PATH",
        help="Path to the notes file; overrides 'file' from the config",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate", help="Validate the current merge request")
    append = subparsers.add_parser("append", help="Append an entry after a merge")
    append.add_argument(
        "--jira-base",
        default=None,
        help="Base URL of Jira, e.g. https://jira.mwnts.net/browse; no link without it",
    )
    promote = subparsers.add_parser("promote", help="Move unreleased entries under a version")
    promote.add_argument("--version", required=True, help="Version, e.g. 0.8.2")
    promote.add_argument(
        "--no-push",
        action="store_true",
        help="Rewrite the file only, without a commit and push",
    )
    return parser


def _dispatch(
    command: str, notes_path: Path, args: argparse.Namespace, *, cfg: NotesConfig
) -> None:
    if command == "validate":
        cmd_validate(cfg)
        return
    if command == "append":
        cmd_append(notes_path=notes_path, cfg=cfg, jira_base=args.jira_base)
        return
    if command == "promote":
        cmd_promote(notes_path=notes_path, cfg=cfg, version=args.version, push=not args.no_push)


def main(argv: list[str] | None = None) -> None:
    """Entry point for the CLI."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _build_parser().parse_args(argv)
    cfg = load_config(args.config)
    notes_path = Path(args.file) if args.file else cfg.notes_file
    try:
        _dispatch(args.command, notes_path, args, cfg=cfg)
    except ReleaseNotesError:
        logger.exception("Failed to update release notes")
        sys.exit(1)
