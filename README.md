# Agent Profiles Defaults

Two VS Code Copilot agents for a lead-builder workflow with mandatory reviewer approval.

| Agent | Model | Role |
|-------|-------|------|
| `builder` | GPT-5.5 | Lead agent for planning, editing, testing, and shipping work |
| `reviewer` | Claude Opus 4.6 | Equal partner for comprehensive review, test design, test execution, and approval |

## Quick Install

Run this from the root of your project:

```bash
curl -fsSL https://raw.githubusercontent.com/appatalks/agent-profiles-defaults/main/.github/agents/{builder,reviewer}.agent.md -o .github/agents/#1.agent.md --create-dirs
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

> Add agents to this project following https://github.com/appatalks/agent-profiles-defaults, then customize them for this project's goals, stack, and conventions.

Copilot will pull the agent definitions, place them in `.github/agents/`, and adapt Builder's workflow, review dimensions, and implementation standards to fit your project.

### Role-Based Customization (Optional)

Append your role or job title to the prompt and Copilot will tune Builder's workflow and the reviewer's approval criteria to match your domain:

> Add agents to this project following https://github.com/appatalks/agent-profiles-defaults, customize them for this project, and optimize Builder and reviewer for my role as a **{your role}**.

Replace `{your role}` with whatever fits. For example:

| Role | What changes |
|------|-------------|
| Teacher | Builder prioritizes readable examples and clear naming; reviewer checks pedagogical fit |
| Security Researcher | Builder treats exploitability as a first-class design concern; reviewer adds threat modeling and CVE-aware checks |
| Accountant | Builder enforces data integrity, auditability, and decimal precision; reviewer tests financial edge cases |
| Secretary / Admin | Builder focuses on workflow automation quality and PII handling; reviewer checks permissions and input validation |
| GitHub Customer Reliability Engineer | Builder adds SLO-aware changes and observability; reviewer checks incident-readiness and diagnostics |
| GitHub Sales | Builder emphasizes demo-readiness and customer-facing polish; reviewer checks examples and presentation risk |
| Microsoft Support | Builder prioritizes compatibility and diagnostic clarity; reviewer checks supportability and error messages |

Any job title or domain works. The prompt is freeform.

## Usage

In VS Code Copilot Chat, select an agent from the agent picker:

- **@builder**: Lead implementation agent. Plans, edits, tests, and requests reviewer approval before closing every task
- **@reviewer**: Comprehensive review partner. Reviews plans and diffs, designs and runs tests, rubber-ducks decisions, and returns APPROVE / REQUEST CHANGES / NEEDS DISCUSSION

## Workflow

1. Start with **@builder** for most tasks.
2. Builder reads the code, plans the work, implements changes, and runs focused verification.
3. Builder sends the result to **@reviewer** for approval.
4. Reviewer examines all relevant angles, runs or designs tests, and returns a verdict.
5. Builder addresses requested changes until reviewer approves or the user explicitly overrides the gate.

For high-risk or ambiguous work, Builder can also ask reviewer to rubber-duck the plan before editing.

User-confirmed direction should steer the workflow. Builder and reviewer should surface tradeoffs, but they should not refuse or repeatedly relitigate a reasonable request after the user has accepted the risk. For example, if the user asks to remove legacy code, compatibility paths, or safety gates and confirms the tradeoff, Builder should make the removal and reviewer should check for concrete regressions rather than blocking the request by default.

## Customization

Edit the `model:` field in any `.agent.md` frontmatter to swap models. The model format is `"Model Name (copilot)"`. You can also use an array for fallback:

```yaml
model: ['GPT-5.5 (copilot)', 'Claude Opus 4.6 (copilot)']
```

### Reasoning Effort

Each agent has a **Reasoning Discipline** section in its body that primes the model to deliberate at the appropriate level for its role:

| Agent | Level | Rationale |
|-------|-------|-----------|
| `builder` | extra-high | Leads execution, plans changes, reasons through risks, and coordinates approval |
| `reviewer` | high | Performs comprehensive review, designs and runs tests, and approves or requests changes |

VS Code's agent frontmatter does not currently expose a per-agent reasoning knob, so these levels are enforced via in-prompt instructions. Adjust the **Reasoning Discipline** section in any `.agent.md` body to retune.

### Approval Gate

Builder must obtain reviewer approval for every ask before presenting the task as complete. Reviewer should approve only when the work satisfies the request, the verification is adequate for the risk level, and any remaining concerns are clearly non-blocking.

The approval gate is a quality loop, not a veto over confirmed user direction. Accepted tradeoffs should be documented as notes or suggestions unless they introduce concrete unaccepted breakage, security exposure, or policy violations.
