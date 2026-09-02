# GitHub Dashboard — cmux Dock extension

[gh-dash](https://github.com/dlvhdr/gh-dash) (a PR/issue dashboard TUI for the
GitHub CLI) running as a pane in the [cmux](https://github.com/manaflow-ai/cmux)
Dock.

## Install

```
cmux extension install manaflow-ai/cmux-gh-dash
```

Requires the [GitHub CLI](https://cli.github.com) (`gh auth login` first). The
consent preview shows one macOS build step before anything runs. That step
downloads the audited `gh-dash` v4.25.2 asset by its immutable GitHub release
asset ID and checks its SHA-256 digest before placing it in the extension
checkout. The pane executes that verified local binary, so the install never
resolves a mutable branch, latest release, or global `gh extension` directory.

`gh-dash` can read GitHub data and perform the actions offered by its upstream
TUI using the user's existing `gh` authentication. cmux does not mint a token
or copy the GitHub credential store. During the download, the installer reads
the existing `gh` token and briefly writes it to a mode-0600 temporary netrc
inside `.gh-dash-download.*`; its exit trap removes that directory. A forced
termination or power loss can leave it behind, so remove that directory and
rotate the token if one remains. Use a least-privilege GitHub token and review
actions before confirming them. Update `third_party/gh-dash.lock` only after
auditing the signed upstream tag, release asset IDs, and published digests,
then run `python3 scripts/check-manifest.py`.
