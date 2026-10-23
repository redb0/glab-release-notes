# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.1.0

Initial release.

- `validate`, `append`, `promote` commands driven by the GitLab MR API.
- Configurable wording (notes file, `Latest Changes` header, sections, labels, skip labels, section prefix) via a `release-notes.toml` file; built-in team defaults when absent.
- `--file`, `--config`, `--version`, `--no-push`, `--jira-base` options.
