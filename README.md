# my-project

## Claude Code plugins

This repository ships the [Superpowers](https://github.com/obra/superpowers)
plugin as a project-scoped Claude Code plugin. It's declared in
[`.claude/settings.json`](.claude/settings.json) via `extraKnownMarketplaces`
(pointing at `obra/superpowers-marketplace`) and `enabledPlugins`.

When you open this repo in Claude Code and trust the folder, you'll be
prompted to install the marketplace and plugin. To install it manually:

```
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers@superpowers-marketplace
```

Then run `/reload-plugins` to activate it.
