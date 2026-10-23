"""Format constants for the release notes (regexes and tool settings)."""

import re

push_retries = 10
http_timeout = 30
double_newline = "\n\n"
encoding = "utf-8"
git_bin = "git"

quote_re = re.compile(r"^> ?(.*\S.*)$", re.MULTILINE)
ticket_re = re.compile(r"(?i)\b([a-z]{2,})[-_](\d+)\b")
version_line_re = re.compile(r"^## ", re.MULTILINE)
anchor_re = re.compile(r"\s*\{#.*\}\s*$")
item_re = re.compile(r"^\* ", re.MULTILINE)
