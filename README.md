# Agent Profiles Defaults

Three VS Code Copilot agents that create an automated code review loop between two different models.

| Agent | Model | Role |
|-------|-------|------|
| `reviewer` | Claude Opus 4.7 | Read-only code review (security, performance, quality) |
| `implementer` | GPT-5.5 | Applies fixes and writes code |
| `conductor` | Claude Opus 4.7 | Orchestrates review → implement → re-review loops |

## Quick Install

Run this from the root of your project:

```bash
curl -fsSL https://raw.githubusercontent.com/appatalks/agent-profiles-defaults/main/.github/agents/{reviewer,implementer,conductor}.agent.md -o .github/agents/#1.agent.md --create-dirs
```

Or clone and copy:

```bash
git clone https://github.com/appatalks/agent-profiles-defaults.git /tmp/apd && cp -r /tmp/apd/.github/agents .github/ && rm -rf /tmp/apd
```

Or if you just want to copy from a local clone:

```bash
cp -r path/to/agent-profiles-defaults/.github/agents .github/
```



## Usage

In VS Code Copilot Chat, select an agent from the agent picker:

- **@reviewer** — Review code for security, performance, and quality issues
- **@implementer** — Write or fix code based on feedback
- **@conductor** — Run the full review-implement-re-review loop automatically (max 3 cycles)

## Customization

Edit the `model:` field in any `.agent.md` frontmatter to swap models. The model format is `"Model Name (copilot)"`. You can also use an array for fallback:

```yaml
model: ['Claude Opus 4.7 (copilot)', 'Claude Sonnet 4 (copilot)']
```
