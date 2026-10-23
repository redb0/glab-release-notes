# Glab Release Notes

Automatically add the changes from each merged merge request to human-readable release notes in a file.

This is a GitLab-oriented take on [latest-changes](https://github.com/tiangolo/latest-changes): a small, dependency-free CLI that runs in your GitLab CI and keeps a `release-notes.md` up to date as merge requests get merged.

Unlike tools that scrape `git log` or conventional-commit messages, it reads the data **from the merge request itself**:

* a **label** decides which section the entry lands in,
* a **one-line quote** (`> …`) in the MR description is the entry text,
* a **ticket key** in the source-branch name (e.g. `FMT-1110`) becomes an optional Jira link.

So the person writing the MR writes the one sentence that matters, and CI takes care of the formatting, links, author, and ordering.

## How it works

A release notes file is plain Markdown with an `## Latest Changes` block at the top and versioned blocks below it:

```Markdown
# Release notes

## Latest Changes

### Features

### Fixes

## 0.8.1

### Fixes {#fix_0.8.1}

* 🐛 Fixed a crash on empty input ([#35](https://gitlab.example/your/project/-/merge_requests/35)) by [@alice](https://gitlab.example/alice)
```

After a merge request is merged, the `append` command finds the `## Latest Changes` block and adds a new list item to the section chosen by the MR's label:

> ## Latest Changes
>
> ### Features
>
> * ✨ Add support for detailed gRPC errors ([#123](https://gitlab.example/your/project/-/merge_requests/123), [FMT-1110](https://jira.example/browse/FMT-1110)) by [@bob](https://gitlab.example/bob)

The entry is built from:

* the **label** → section and emoji (see [Using labels](#using-labels)),
* the **last non-empty `> …` quote** in the MR description → the entry text,
* the **ticket key** parsed from the source branch name → a Jira link (only when a `--jira-base` is given),
* the MR **author** and **URL** → trailing `by [@author](…)`.

The entry is prepended to the top of the section so the newest change reads first. Because the notes are just a file in your repo, you can later tweak, reorder, or extend any entry by hand.

## Using labels

A merge request is routed to a section by its labels. The built-in default mapping is:

| Label       | Section         | Emoji |
| ----------- | --------------- | ----- |
| `feature`   | `Features`      | ✨    |
| `bug`       | `Fixes`         | 🐛    |
| `docs`      | `Documentation` | 📝    |
| `ci`        | `CI`            | 👷    |

Labels that are never recorded into the notes:

* `release`, `refactor`, `test`, `chore`, `style`

Rules:

* A merge request must carry **either** a section label **or** a skip label.
* A **skip label wins** if both a section label and a skip label are present.
* With several section labels, the first one in the configured order wins.
* A section label **requires** a `> …` quote in the description; a skip label does not.

`Features` and `Fixes` always exist (even when empty). The other sections appear only once they have at least one entry.

## Getting started

1. **Add the notes file** (if you don't have one), e.g. `docs/release-notes.md`:

   ```Markdown
   # Release notes

   ## Latest Changes

   ### Features

   ### Fixes
   ```

2. **Add a merge-request template** that asks authors to set a label and write a one-line quote. A minimal `Default.md`:

   ```Markdown
   /label ~feature

   ## Release notes

   One line in a quote. No emojis and no links — CI adds those after the merge.

   >
   ```

3. **Add the CI jobs** (see [CI wiring](#ci-wiring)).

That's enough for `validate` and `append` to work. `promote` is what your release job calls.

## Commands

```
glab-release-notes [--config PATH] [--file PATH] <command>
```

* `validate` — a gate for the MR pipeline. Fails the pipeline when the MR has neither a section label nor a skip label, or has a section label but no `> …` quote.
* `append` — after a merge, appends the entry to the `## Latest Changes` block and pushes a `chore(notes): add entry for MR !<iid>` commit. It retries on a push race and is idempotent: an already-recorded MR is skipped.
* `promote` — moves the non-empty sections of `## Latest Changes` under a new `## <version>` heading with anchors, then empties the block back to the always-kept sections. `--version` is required; `--no-push` rewrites the file only so your release process can own the commit.

## CI wiring

The tool talks to the GitLab API using CI variables, so it is bound to whichever project's pipeline runs it:

* `CI_API_V4_URL`, `CI_PROJECT_ID`, `GITLAB_API_TOKEN` — API endpoint and auth;
* `CI_MERGE_REQUEST_IID` — used by `validate`;
* `CI_COMMIT_SHA` — used by `append` to find the MR of the current commit.

A typical `.gitlab-ci.yml`:

```yaml
validate-release-notes:
  stage: linter
  script:
    - uv run glab-release-notes validate
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"

append-release-notes:
  stage: linter
  variables:
    GIT_DEPTH: 0
  before_script:
    - !reference [.base_git_pre_settings, script]   # git credentials for the push
  script:
    - uv run glab-release-notes append --jira-base https://jira.example/browse
  rules:
    - if: $CI_COMMIT_TAG || $CI_PIPELINE_SOURCE == "merge_request_event"
      when: never
    - if: '$CI_COMMIT_MESSAGE =~ /^chore\(notes\)/'
      when: never
    - if: $CI_COMMIT_BRANCH == "main" && $CI_PIPELINE_SOURCE == "push"
```

The `chore(notes)` rule prevents the job from re-running on its own commits, and `GIT_DEPTH: 0` gives `append` a full history. The `before_script` must configure git with credentials able to push to the target branch (see [Pushing to a protected branch](#pushing-to-a-protected-branch)).

### Promoting on release

Call `promote` in your release job, right before (and, with `--no-push`, folded into) the release commit:

```yaml
    - uv run glab-release-notes promote --version "${version}" --no-push
```

## Existing MRs — running manually

`append` resolves the MR from `CI_COMMIT_SHA` by default. To record a specific merge request by hand — for example one that was merged before you added this — run `append` on the target branch with the `MR_IID` variable set:

```
MR_IID=123 uv run glab-release-notes append --jira-base https://jira.example/browse
```

This is also the escape hatch for any MR the automatic run skipped.

## Configuration

The wording of the release notes — the file, the `Latest Changes` header, the sections, the labels, and the skip labels — is configurable, in the same spirit as [latest-changes](https://github.com/tiangolo/latest-changes). Put a `release-notes.toml` in the repo root and it is picked up automatically; pass `--config PATH` to point at a different file. Without a config file, the built-in defaults from [Using labels](#using-labels) apply.

Precedence: CLI flags (`--file`) > config file > built-in defaults.

```toml
# release-notes.toml
file = "docs/release-notes.md"        # the notes file (CLI --file wins)
unreleased_header = "## Latest Changes"
section_prefix = "### "
skip_labels = ["release", "refactor", "test", "chore", "style"]
always_keep = ["Features", "Fixes"]

[[section]]
label = "feature"
header = "Features"
emoji = "✨"
anchor_prefix = "feat"

[[section]]
label = "bug"
header = "Fixes"
emoji = "🐛"
anchor_prefix = "fix"

[[section]]
label = "docs"
header = "Documentation"
emoji = "📝"
anchor_prefix = "docs"

[[section]]
label = "ci"
header = "CI"
emoji = "👷"
anchor_prefix = "ci"
```

Keys:

* `file` — the notes file to update. Defaults to `docs/release-notes.md`.
* `unreleased_header` — the header of the accumulating block. Defaults to `## Latest Changes`.
* `section_prefix` — the prefix of the section headers inside the block. Defaults to `### `.
* `skip_labels` — labels that are never recorded. A skip label also wins over a section label.
* `always_keep` — section headers that are always rendered, even when empty. Defaults to `["Features", "Fixes"]`; use `[]` to render a section only once it has an entry (the latest-changes behavior).
* `[[section]]` — one table per section:
    * `label` (required) — the GitLab label that routes an MR to this section.
    * `header` (required) — the section header text.
    * `emoji` (optional) — the emoji prefixed to entries in this section. Omit it for a plain entry.
    * `anchor_prefix` (optional) — the anchor prefix used when promoting, e.g. `{#feat_1.0.0}`. Defaults to the label.

The order of `[[section]]` tables matters in both directions: it is the display order of the sections, and the first matching label wins when an MR carries several section labels.

The entry line format itself is fixed: `* <emoji> <text> (links) by <author>`. It is not a template.

## Pushing to a protected branch

`append` and `promote` (without `--no-push`) `git commit` and `git push` the updated notes. If your target branch is protected against direct pushes, the CI job must be running with credentials that can push to it.

In GitLab that usually means one of:

* the job runs as a user/role allowed to push to the branch, or
* you pass a token to the git setup (the `!reference [.base_git_pre_settings, script]` pattern above) that can push.

The commits are attributed to the CI identity, not to any individual author.

## Development

```
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy glab_release_notes tests
uv run pytest
```

Releases are managed with [commitizen](https://github.com/commitizen/commitizen): `uv run cz bump` updates the version and `CHANGELOG.md` and tags the commit. A GitHub Release on that tag publishes the package to PyPI via trusted publishing (`.github/workflows/publish.yaml`).

## License

This project is licensed under the terms of the MIT license.
