# GitHub Dashboard — cmux Dock extension

[gh-dash](https://github.com/dlvhdr/gh-dash) (a PR/issue dashboard TUI for the
GitHub CLI) running as a pane in the [cmux](https://github.com/manaflow-ai/cmux)
Dock.

## Install

```
cmux extension install manaflow-ai/cmux-gh-dash
```

Requires the [GitHub CLI](https://cli.github.com) (`gh auth login` first). The
consent preview shows the one build step (`gh extension install dlvhdr/gh-dash`,
runs once at install) and the pane command (`gh dash`) before anything runs.
