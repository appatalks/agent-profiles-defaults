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



## Use Copilot to Install & Customize

Already using VS Code Copilot? Paste this prompt into Copilot Chat and it will fetch the agents, add them to your project, and tailor them to your codebase:

> Add agents to this project following https://github.com/appatalks/agent-profiles-defaults — then customize them for this project's goals, stack, and conventions.

Copilot will pull the agent definitions, place them in `.github/agents/`, and adapt the instructions, review dimensions, and implementation standards to fit your project.

### Role-Based Customization (Optional)

Append your role or job title to the prompt and Copilot will tune the conductor's workflow, review priorities, and implementation standards to match your domain:

> Add agents to this project following https://github.com/appatalks/agent-profiles-defaults — customize them for this project and optimize the conductor for my role as a **{your role}**.

Replace `{your role}` with whatever fits — for example:

| Role | What changes |
|------|-------------|
| Teacher | Conductor prioritizes readability, clear naming, and documentation; reviewer flags pedagogical anti-patterns |
| Security Researcher | Conductor escalates all OWASP findings to Critical; reviewer adds threat-modeling and CVE-reference checks |
| Accountant | Conductor enforces data-integrity checks, audit logging, and decimal-precision validation |
| Secretary / Admin | Conductor focuses on workflow automation quality, input validation, and PII handling |
| GitHub Customer Reliability Engineer | Conductor adds SLO-aware review gates, incident-response patterns, and observability checks |
| GitHub Sales | Conductor emphasizes demo-readiness, API usage examples, and customer-facing polish |
| Microsoft Support | Conductor prioritizes backward compatibility, diagnostic logging, and error-message clarity |

Any job title or domain works — the prompt is freeform.

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
