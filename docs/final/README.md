# Running the final evaluation

This page is for whoever runs the final evaluation or checks how it was run. It covers what has to be true before
the run, the commands in order, what each one writes, and how a run that was cut short continues. What the results
mean is in the report the last command writes; what counts as good enough is in the [quality
targets](../quality-targets.md).

## Before the run

The command checks each of these itself and refuses to start otherwise:

| Condition | Why |
|---|---|
| The held-out files match `scenarios/held-out/FROZEN` | The scenarios are the ones frozen on 2026-10-19 |
| `docs/quality-targets.md` and `docs/final/predictions.md` are committed and unchanged | Targets and predictions are written before the results exist |
| No tracked file has uncommitted changes | The run belongs to one identified revision, recorded in its manifest |
| `OPENAI_API_KEY` is in the environment | Only its presence is checked; it is never read or printed |
| `--prices-checked` gives the date the prices of `gpt-6-luna` and `gpt-6.1-sol` were checked | The costs in the report rest on those prices (`refund_agent/agent/costs.py`) |
| `--budget-usd` is above 0 and at most 15 | The plan's limit for the first final batch (section 12) |

Check by hand, before the first run: the account's access to `gpt-6.1-sol`, and its rate limits for both models.

## Commands

All run from the repository's root in Git Bash.

1. **Dry run.** Writes the first request of each configuration's agent and of the simulated customer to
   `runs/final-dry-run/`, built from a development scenario, and prints an upper estimate of the cost. Sends
   nothing.

   ```bash
   uv run python -m refund_agent.evaluation.final --dry-run
   ```

2. **The run.** 180 conversations; each line it prints is one try and its machine items.

   ```bash
   uv run --env-file .env python -m refund_agent.evaluation.final --budget-usd 5 --prices-checked YYYY-MM-DD
   ```

3. **If the run was cut short** (Ctrl+C, a closed terminal, a crash), the same command with the run's folder
   continues it. Tries that finished or crashed are not run again; a try that was cut short is moved aside to
   `try<n>-cut-short-<k>/` and run again. A resume refuses if the code or the settings changed, and its budget
   includes what the run spent before.

   ```bash
   uv run --env-file .env python -m refund_agent.evaluation.final --resume runs/final-<time> --budget-usd 5 --prices-checked YYYY-MM-DD
   ```

4. **Transcripts**, one file per configuration, for the dialogue audit:

   ```bash
   uv run python -m refund_agent.evaluation.transcripts runs/final-<time>/A
   ```

5. **Dialogue audit.** Claude's audit is written into `audit-claude.toml` in each configuration's folder (`audit
   new ... --file audit-claude.toml`). The user's share follows from it:

   ```bash
   uv run python -m refund_agent.evaluation.audit sample runs/final-<time>
   ```

   The user's verdicts go into `audit.toml` in each configuration's folder; `audit compare` shows where the two
   readers disagree, and the user settles each disagreement.

6. **Report.** Writes `report.md` and `report.json` into the run's folder.

   ```bash
   uv run python -m refund_agent.evaluation.report runs/final-<time>
   ```

## What a run writes

```text
runs/final-<time>/
  manifest.json            what ran: configurations, models, prices, prompt and policy hashes, the freeze's hash,
                           the commits of the targets and predictions, the code's fingerprint and commit
  invocations.jsonl        each start and resume, with its budget
  A/  B/  C/               one folder per configuration
    manifest.json          the configuration's part, read by the transcripts and the audit
    H01/try1/
      started.json         written first
      agent-requests.jsonl every request and answer of the agent, with each attempt's cost
      simulator-requests.jsonl
      result.json          the verdict and the evidence: refused attempts, handoffs, agent run times, cost
      crash.json           instead of result.json, if the try crashed; its database is kept
```

## Limits

- `gpt-6.1-sol` is an alias without a fixed snapshot; the report lists the model IDs that answered and when.
- A new run with the same manifest need not give the same answers: the models are not deterministic. The report is
  reproducible from the saved results.
- The configuration's label is visible in the folders; Claude's audit is therefore not blind to it.
