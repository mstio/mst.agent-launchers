# AI Agent Launchers for Omarchy

A compact Omarchy Quattro bar-widget: **one** icon that opens a small context menu for **Claude Code**, **Codex**, and **Agy / Antigravity**.
The SVG mark is a monochrome mask tinted with the active bar foreground color, so it stays readable across Omarchy themes.

## Controls

| Action | Effect |
|---|---|
| Left / right click | toggle the context menu below the icon |
| Middle click | refresh local status |
| Click outside | close the menu |

Menu rows (all start in `~/Work`):

| Agent | New | Resume |
|---|---|---|
| Claude | `claude` | `claude --continue` |
| Codex | `codex` | `codex resume --last` |
| Agy | `agy` | `agy -c` |

Clicking **„… fortsetzen ▸“** expands that agent's sessions as sub-items (one agent at a time): first „Letzte Sitzung in ~/Work“ (the previous `--continue` behaviour), then its running and recent sessions (last 14 days, at most 6 per agent, running ones first, marked **●**), each with title, age or state (`arbeitet`/`wartet`) and working directory:

- running session → its window is focused (`hyprctl dispatch 'hl.dsp.focus({ window = "pid:<terminal>" })'`, Hyprland ≥ 0.56 syntax), no second client on the same transcript
- older session → resumed in its own directory: `claude --resume <id>`, `codex resume <id>`, `agy --conversation <id>`

Sources (read-only, only when the menu opens, ~0.5 s): `~/.claude/sessions/*.json` (running Claude TUIs) and `~/.claude/projects/*/*.jsonl` (title from `ai-title`/`custom-title`), `~/.codex/session_index.jsonl` plus rollout headers (internal runs such as Guardian review are skipped; running = rollout file held open by a `codex` process), Antigravity `cache/conversation_metadata.json`. Sessions in `/tmp` (e.g. curator runs) are skipped.

### All sessions (since 1.5.0)

The last menu row **„Alle Sitzungen …“** opens a floating terminal window with *every* local session of Claude Code, Codex and Agy across all folders, like the sidebar in Claude Chat. The menu itself stays small. Idea and original Claude script by bernhard2804 (proposed as `claude-sitzungen` in mstio/polaris-connector#3).

The agent choice sits at the top of the window frame: **Alle · Claude · Codex · Agy**.

| Key | Effect |
|---|---|
| Tab / Shift+Tab | next / previous agent |
| typing | filter titles (fzf) |
| Enter | resume in a new terminal in the session's folder (`claude --resume`, `codex resume`, `agy --conversation`); if it is already open, focus its window instead |
| Ctrl+F | Claude: fork for a follow-up question (`--resume --fork-session`), the original transcript stays unchanged |
| Ctrl+S | Claude: search the typed text in the **conversation content** (hit count per session) |
| Ctrl+R | reload the current view |
| Esc | close |

- Preview: for Claude folder, time span, number of prompts, first and last prompt, last answer; for Codex and Agy title, folder and last use (Agy stores its transcripts as binary data). **●** = open right now.
- Script `bin/agent-sessions`, needs `python3` and `fzf` ≥ 0.74 (tested; uses `transform`, labels and `wrap-word`), optional `rg` for faster content search. Codex and Agy sessions come from `bin/agent-launcher-status` (same rules as the menu, without the 14-day limit). The script can also be run directly or bound to a key, e.g. in `~/.config/hypr/bindings.lua`:
  `o.bind("SUPER + ALT + H", "Agenten-Sitzungen", "omarchy-launch-tui --app-id=TUI.float ~/.config/omarchy/plugins/mst.agent-launchers/bin/agent-sessions")`
- The window uses the app id `TUI.float`, which Omarchy already floats and centers (875×600); no window rule needed.
- Read-only on the agents' own session files; no network, no service, no timer. Lists only sessions whose folder still exists under `$HOME`; opens only a checked session id in such a folder, command as an argument list (no shell). Titles and texts are model output: control, C1, bidi and zero-width characters are stripped before display.
- Index cache `~/.cache/agent-sessions/index.json` (mode 0600, it contains prompt excerpts), rebuilt per file by mtime and size: first build ~2 s for ~80 Claude sessions, then < 0.1 s.
- "Open right now" for Claude comes from `~/.claude/sessions/*.json` (process checked via `/proc`, also for npm installs).
- The transcript formats are undocumented and may change with agent updates; unexpected records are skipped instead of emptying the list.
- Tests: `python3 -m unittest discover -s tests`.

A small **•** on the icon means at least one agent has a resumable `~/Work` session; in the menu, resume rows with a detected session carry a **•**, the others are dimmed (still clickable).

Since 1.3.0 the widget is a single icon to save bar width on narrow/scaled screens (e.g. 2880×1800 at scale 2 = 1440 logical px).

## Hover tooltip / quota

Hovering the icon shows, for all three agents:

- whether a resumable `~/Work` session was detected;
- locally cached quota information when available;
- the click actions (once, below the three agents).

The plugin is deliberately **read-only** for quota checks. It does not read or print OAuth tokens and does not call a quota API itself.

### Codex quota source

It reads Omarchy's standard local usage record:

`~/.local/state/omarchy/agents/usage/codex.json`

This is the same kind of record used by Omarchy's Agents panel.

### Agy quota sources

It first looks for Omarchy-style records named `agy.json`, `antigravity.json`, or `gemini.json`, then for compatible local Agy usage/quota caches (including `~/.gemini/antigravity-cli/usage-limits.json`) and relevant non-secret Omarchy cache/state JSON files.

This is designed to coexist with Agy/Gemini quota plugins such as the one already installed on the system. If no compatible cache is found, the tooltip simply says to use `/usage` inside Agy.

### Claude quota source

It reads Omarchy's standard local usage record:

`~/.local/state/omarchy/agents/usage/claude.json`

Claude therefore uses the same collector as Omarchy's built-in Agents panel. Until Claude is signed in and has recorded usage, the tooltip shows the collector's authentication status.

## Session detection

- Codex: reads recent `~/.codex/sessions/*/*/*/rollout-*.jsonl` metadata and looks for `cwd == ~/Work`.
- Agy: reads the official workspace-keyed cache `~/.gemini/antigravity-cli/cache/last_conversations.json` and checks the `~/Work` entry.
- Claude: checks Claude Code transcripts under `~/.claude/projects` for the `~/Work` workspace.

## Safety / behavior

- no automatic switching between agents;
- does not change the Omarchy default agent;
- does not pass `--dangerously-skip-permissions`;
- quota status is refreshed from local files every 60 seconds and when hovering;
- all agents always start in `~/Work`.

## Install / update manually

```bash
mkdir -p ~/.config/omarchy/plugins
rm -rf ~/.config/omarchy/plugins/mst.agent-launchers
cp -a mst.agent-launchers ~/.config/omarchy/plugins/
omarchy plugin validate ~/.config/omarchy/plugins/mst.agent-launchers
omarchy-shell shell rescanPlugins
omarchy plugin enable mst.agent-launchers
```

If version 1.0 is already enabled, replacing the files under the same plugin id normally hot-reloads it; a shell restart is only a fallback:

```bash
omarchy restart shell
```

## Remove

```bash
omarchy plugin disable mst.agent-launchers
rm -rf ~/.config/omarchy/plugins/mst.agent-launchers
omarchy-shell shell rescanPlugins
```
