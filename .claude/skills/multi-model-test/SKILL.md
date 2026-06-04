---
name: multi-model-test
description: 'Run one prompt across every available Copilot model at once and compare the results. Use when the user wants to test a prompt against all models, benchmark or compare model outputs, see how different models answer the same question, or evaluate a prompt across the full model lineup. Includes custom (self-hosted) models when available, paces calls to stay soft on rate limits, spins up independent subagents at their highest reasoning effort, and returns a side-by-side comparison. Skips models marked internal.'
argument-hint: 'The prompt to run across all available models'
---

# Multi-Model Prompt Test

Fan a single prompt out to every model the user has access to (Copilot models plus any available custom models), run them as independent subagents at maximum reasoning, pace the calls to stay soft on rate limits, and compare the answers.

## When to Use

- The user wants to test or evaluate one prompt across all models.
- The user asks to compare, benchmark, or diff model outputs for the same input.
- The user wants to pick the best model for a task by seeing each model's answer.

## Inputs

- **Prompt**: the exact text to send to every model. Use what the user provided as the skill argument. If no prompt was given, ask the user for it before continuing.

## Procedure

### 1. Capture the prompt

Take the user's prompt verbatim. Do not rewrite, summarize, or "improve" it. Every model must receive identical input so the comparison is fair. Preserve any code blocks, formatting, and constraints exactly.

### 2. Build the model list

Enumerate every model available to the user (the same set shown in the model picker), including non-Copilot **custom models** (for example `customoai` providers) when they are present and selectable. Then filter:

- **Exclude** any model whose name or label contains `internal`, or that is otherwise marked internal/private/experimental-internal.
- **Include** every remaining user-selectable model exactly once, including custom models.
- **Deduplicate** aliases that map to the same underlying model.
- Custom models may use a non-`copilot` provider suffix (for example `"qwen/qwen3-coder-30b (customoai)"`). Use the exact label and suffix from the picker for each model.

If you cannot reliably determine the available models, ask the user to confirm or paste the list from their model picker rather than guessing. One reliable way to discover exact picker names: attempt a subagent call with a wrong model name; the error returns the full list of available models with their exact labels and provider suffixes. Use those exact labels.

Custom models may be backed by a local or self-hosted endpoint that is not always running. If a custom model is unreachable at call time, treat it as a per-model failure (see step 3) rather than aborting the run.

**Prefer explicit high-reasoning variants.** When the picker offers a reasoning-tiered variant of a model (for example `Claude Opus 4.7 (Extra high reasoning)` or `Claude Opus 4.7 (High reasoning)`), select the highest available reasoning variant and drop the plain variant of that same model so you do not test it twice. This gives a real, platform-enforced reasoning level instead of relying only on prompt wording. If no reasoning-tiered variant exists for a model, use the plain model and rely on the prompt hint in step 3.

Record the final list, and for each model note whether its reasoning level is **explicit** (a high-reasoning picker variant) or **prompt-hinted** (plain model, effort requested via wording only). The subagent `model` field uses the picker label, for example `"Claude Opus 4.8 (copilot)"`, `"GPT-5.5 (copilot)"`, or a custom model like `"openai/gpt-oss-20b (customoai)"`.

### 3. Launch subagents in rate-limit-friendly waves

Single-shot answers are stochastic, so run **3 samples per model** by default (let the user override the sample count). For each model, start a separate subagent per sample.

**Be soft on rate limits.** Do not fire every call at once. The model backends rate-limit bursts, so pace the run:

- Process the work in **small waves** of at most **4 to 5 concurrent subagent calls** at a time. Launch a wave, wait for it to return, then start the next wave.
- Leave a short pause of roughly **2 to 4 seconds between waves** so you stay under burst limits.
- If any call returns a **rate-limit error** (for example a 429 or a "rate-limited, please wait" message), do not treat it as a real model failure. Wait a few seconds longer (back off, increasing the wait on repeated hits) and **retry that specific call** up to 3 times before recording it as failed.
- Custom or self-hosted models may have tighter limits or be unreachable. Apply the same backoff, and if a custom model is plainly unreachable (for example a connection-refused error), record it as failed and move on without retrying many times.

Keep the subagents isolated from one another within a wave (no shared state, no cross-talk).

Each subagent call must set:

- `model`: the target model picker label. Use the explicit high-reasoning variant chosen in step 2 when one exists.
- `description`: a short label like `Run prompt on <Model Name> (sample 2/3)`.
- `prompt`: the wrapper below, with the user's prompt embedded unchanged.

Wrapper prompt for each subagent:

```
You are one model in a multi-model comparison. Use your HIGHEST / MAXIMUM
reasoning effort and extended thinking for this task. Think deeply before
answering.

Answer the following prompt on its own merits. Do not mention that you are
part of a comparison in your final answer.

=== BEGIN USER PROMPT ===
<the user's prompt, verbatim>
=== END USER PROMPT ===

Return only your best final answer to the prompt above.
```

For models running as an **explicit** high-reasoning variant, the platform enforces the reasoning level. For **prompt-hinted** models, the wording ("highest / maximum reasoning effort, extended thinking, think deeply") is only a request, not a guarantee, because plain agent frontmatter does not expose a per-model reasoning knob. Track which mode each model used so you can report it honestly in step 5.

### 4. Record results to CSV

After every subagent returns, write the rows to a timestamped file `./tmp/multi-model-output-<timestamp>.csv` (relative to the workspace root), where `<timestamp>` is the run start time in UTC, formatted `YYYYMMDDTHHMMSSZ` (e.g. `./tmp/multi-model-output-20260604T143000Z.csv`). Use a colon-free, filename-safe format so it works on every OS. Each run creates its own file. Create the `./tmp/` directory if it does not exist.

Write this exact header as the first line:

```
timestamp,model,reasoning_mode,sample,prompt,response
```

Formatting rules (RFC 4180):

- One row per sample (so 3 rows per model when running 3 samples).
- `timestamp`: ISO 8601 UTC, e.g. `2026-06-04T14:30:00Z`.
- `model`: the model name, e.g. `Claude Opus 4.8`.
- `reasoning_mode`: `explicit` if the model ran as a high-reasoning picker variant, or `prompt-hinted` if effort was only requested via wording.
- `sample`: which sample this row is, e.g. `1/3`.
- `prompt`: the user's prompt, identical for every row.
- `response`: that model's full final answer for this sample.
- Wrap every field in double quotes. Escape any literal double quote inside a field by doubling it (`"` becomes `""`). This keeps commas, newlines, and quotes inside prompts and responses from breaking the CSV.
- Each run writes a fresh timestamped file with its own header. Do not append to a previous run's file.

### 5. Collect and compare

After writing the CSV, present a side-by-side comparison:

- One clearly labeled section per model, in a stable order.
- For each model, show its samples and a **consistency note**: whether the samples agreed, and if they diverged, what the majority answer was. Flag any model whose samples disagreed with each other as unstable on this prompt.
- State each model's `reasoning_mode` (`explicit` vs `prompt-hinted`) so the user knows where the reasoning level was enforced versus merely requested.
- A short closing summary that highlights where the models agreed, where they diverged, and any notable differences in correctness, depth, or approach.
- Tell the user the exact path of the timestamped results file (e.g. `./tmp/multi-model-output-20260604T143000Z.csv`).

Do not declare a single "winner" unless the user asks. Surface the differences and let the user judge.

## Constraints

- Send the same prompt, unchanged, to every model.
- Never include models marked internal.
- Include every other available model, including custom (self-hosted) models, using the exact picker label and provider suffix.
- Prefer the highest available explicit reasoning variant of a model; fall back to prompt-hinted effort only when no reasoning variant exists.
- Run multiple samples per model (default 3) and report cross-sample consistency, since single runs are stochastic.
- Be soft on rate limits: launch in small waves (4 to 5 concurrent), pause briefly between waves, and back off and retry on rate-limit errors rather than recording them as failures.
- Record every sample to a timestamped `./tmp/multi-model-output-<timestamp>.csv` file with proper RFC 4180 quoting and escaping.
- Be honest about reasoning: label each model `explicit` or `prompt-hinted`. Do not claim a guaranteed reasoning level for prompt-hinted models.
- If a subagent fails or a model is unavailable after retries, note it in the results and continue with the rest rather than aborting the whole run.
