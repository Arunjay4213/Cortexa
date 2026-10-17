# Cortexa

Memory intelligence for AI agents. Detect ghost tokens, contradictions, and stale memories before they corrupt your agent's reasoning.

## Installation

```bash
pip install cortexa
```

With all optional features:

```bash
pip install "cortexa[all]"
```

## Quick Start

```bash
# Explore with synthetic data
cx --demo

# Launch the web dashboard
cx --web --demo

# Start the MCP server
cx --serve --demo
```

## Features

- **Ghost Token Detection** - Find memories that consume tokens but add no value
- **Contradiction Finder** - Detect conflicting memories before they cause hallucinations
- **Memory Attribution Scoring (MAS)** - Score every memory by relevance, freshness, and access patterns
- **Live Watch Mode** - Stream memory events in real-time with sparkline visualization
- **Full Audit Reports** - Health score, token waste estimates, and actionable fixes
- **Interactive TUI** - Full-screen terminal interface with animations, keyboard shortcuts, and progressive disclosure

## Slash Commands

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/audit` | Run a full memory health audit |
| `/health` | Quick health summary |
| `/watch` | Start live memory event stream |
| `/trace <text>` | Trace memory attribution for a query |
| `/search <query>` | Search the memory store |
| `/contradictions` | Find contradicting memories |
| `/ghosts` | List ghost token memories |
| `/stale` | List stale memories |
| `/memory <id>` | Inspect a specific memory |
| `/fix <id> <action>` | Apply a fix (delete/update/archive) |
| `/config` | Show current configuration |
| `/export` | Export audit report as JSON |
| `/clear` | Clear conversation |
| `/quit` | Exit |

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+H` | Health summary |
| `Ctrl+A` | Run audit |
| `Ctrl+W` | Toggle watch mode |
| `Ctrl+E` | Export audit |
| `Ctrl+L` | Clear conversation |
| `Up/Down` | Input history navigation |

## Configuration

Cortexa looks for configuration in `~/.config/cortexa/config.yml`:

```yaml
adapter: mem0
api_key: your-api-key-here
```

Supported adapters: `demo`, `mem0`, `custom`.

## Architecture

```
cx/
├── adapters/     # Memory store adapters (demo, mem0, custom)
├── agent/        # Claude-powered agent with tool use
├── core/         # Auditor, scoring, analysis
├── dashboard/    # FastAPI web dashboard
├── mcp/          # MCP server for IDE integration
├── ui/           # Formatters, animations, streaming
└── widgets/      # Textual widgets (header, input, messages, tools)
```

## Development

```bash
# Install in development mode
pip install -e ".[all,dev]"

# Run tests
pytest tests/ -v

# Lint
ruff check .

# Format
ruff format .
```

## License

MIT
