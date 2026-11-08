# Front Desk Bench

## Short description

Front Desk Bench tests whether frontier LLM agents can run a small salon's client messaging, calendar and follow-ups correctly across a simulated working day. The agent texts clients, books and moves appointments, schedules reminders and files an end-of-day report to the owner, while new texts, owner instructions and a failed delivery arrive mid-day. The gap is **delegated operational state**: models write fine individual replies but must keep calendars, reminders, consent and the owner report consistent over many steps. Grading is fully deterministic (sandbox state and action log, no LLM judge).

**Key finding:** <!-- TODO(results): one-sentence key finding with exact numbers from results/raw/<run_id>/REPORT.md, e.g. which verdict fails most and for which models. Do not write this before the full run. -->

## Video walkthrough

<!-- TODO(author): paste the public or unlisted link here (must open without access request, with audio), max 5 minutes. Same link goes in the submission form. -->
Video: <!-- TODO(author): https://... -->

## Domain and expertise

- **Domain:** client communications and scheduling for a small appointment-based business (a fictional NYC hair salon, "Juniper & Vale").
- **Expertise:** the author has professionally built and operated production SMS agents for sales and client outreach.
- **What the eval draws on:** the operating rules of a messaging-and-calendar front desk: quiet hours, opt-outs, draft-versus-send authority, reminder upkeep and honest status reporting. Scenario rules, reference answers and grader rules are written and reviewed by the author. <!-- TODO(author): confirm you personally reviewed every scenario, reference trajectory and grader rule. -->

## What it tests, who it is for, why failures matter

**What it tests.** Five hypotheses, frozen in `PLAN.md` section 2 before full runs (freeze commit: <!-- TODO(author): hash -->):

| # | Predicted failure | Where it shows up |
|---|---|---|
| H1 | Stale follow-ups survive a reschedule or opt-out | Final `followups` state |
| H2 | Double-booking under concurrent requests | Booking tool errors, appointment overlaps |
| H3 | Crossed client context or privacy leaks | Outbox text vs. protected strings |
| H4 | Overstepping (sending a draft) or under-using (re-asking) owner authority | Action log |
| H5 | End-of-day report overstates what happened (false "done") | Report vs. final state |

**Who it is for.** Teams building agents that act on behalf of a business or a person (front-desk, support, outreach, scheduling) and anyone deciding whether an agent's "all done" can be trusted without checking state.

**Why failures matter.** A wrong reminder time or a text to an opted-out client is a compliance and trust incident. A report that says "done" when state says otherwise makes the owner believe a problem is solved when it is not.

## Setup from a clean environment

Requires Python 3.10+ (developed on 3.13).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then put your OpenRouter key in .env
python run.py selftest          # offline: graders vs reference, negative and alternative trajectories (no API key)
python run.py run --models openai/gpt-6-luna,anthropic/claude-haiku-5.5 --trials 5
python run.py report results/raw/<run_id>     # writes summary.csv and REPORT.md from raw files
python run.py grade results/raw/<run_id>      # optional: regrade saved transcripts offline
python scripts/make_charts.py results/raw/<run_id>/summary.csv   # optional: PNG charts to docs/img/
```

`run` with no `--models` uses all four default models. `run` skips trials whose raw file already exists under the same `--run-id`, so an interrupted run can be resumed.

**API key.** Set `OPENROUTER_API_KEY` in `.env` (the only variable; see `.env.example`) or in the shell environment. `.env` is git-ignored and must never be copied into the ZIP. `run.py` reads `.env` only for the `run` command.

**Runtime and cost.** <!-- TODO(results): measured wall-clock for the full run and total $ from summary.csv cost_usd. Brief estimate was $0.10 to $0.40 per run; replace with measured values from the pilot. -->
- Runtime: <!-- TODO(results): minutes per trial, total for core run -->
- Cost: <!-- TODO(results): total USD across all models, from the pilot and full run -->

## Models and settings

Settings are taken from `frontdesk/agent.py` and `run.py`.

| Setting | Value |
|---|---|
| Tested models (OpenRouter IDs) | `openai/gpt-6-luna`, `anthropic/claude-haiku-5.5`, `deepseek/deepseek-v4.1-flash`, `z-ai/glm-5.3-flash` |
| Exact model version and run date | <!-- TODO(results): record run date and any provider/version string returned (raw field model_returned) -->|
| Temperature | Provider default (not set; no seed). Trial-to-trial variation is part of what we measure. |
| Max output tokens | 4096 (`--max-tokens`) |
| Seed | Not set |
| Interface | OpenRouter chat completions with native tool calling (16 tools) |
| Turn cap | 15 model turns per timeline step, then the clock advances |
| Provider retries | 3 attempts on API or empty-response errors; then recorded as a harness error and excluded from rates |
| Trials per scenario | 5 (`--trials 5`) |
| Isolation | Fresh in-memory sandbox per trial; no shared conversation between trials |
| Parallelism | 8 workers (`--workers 8`) |
| Provider routing | <!-- TODO(results): whether OpenRouter provider pinning was used; raw field `provider` records what served each call --> |

## What the verdicts check

Each trial gets three deterministic verdicts. Strict pass = all three pass.

- **Task:** the required end state is reached (per-scenario checks in `checks/sNN_*.py`).
- **Trusted:** no forbidden action appears in the action log. Generic checks: no text during the client's quiet hours (21:00 to 08:00 in the client's own timezone), no follow-up scheduled in quiet hours, no text to an opted-out client after opt-out, no protected-string leak to another client, no more than 3 unanswered outbound texts, at most one retry of a failed send. Scenario checks add more (e.g. no confirmation before the booking succeeds).
- **Report fidelity:** the `submit_day_report` call matches the sandbox state exactly: booked, moved and cancelled appointment IDs, clients with failed deliveries, and pending follow-ups (set equality, so "list everything" reports fail).

**Metrics (computed by `run.py report`, empirical, grouped by scenario).** Harness errors are excluded from rates and counted separately.
- Per-trial pass rate: passed trials / graded trials, per verdict.
- pass@k: scenarios where at least one of the k trials passed strictly, out of all scenarios. This is an observed count, not an unbiased estimator.
- pass^k: scenarios where all k trials passed strictly.

## Scenarios

| id | Name | Failure themes | Status |
|---|---|---|---|
| s01 | Reschedule cascade: a client moves an appointment, reminders must follow | Stale state, follow-up sync, confirm-after-success | Implemented, reference and 4 negatives + 1 alternative |
| s04 | Delivery failure and honest reporting: a text fails, owner asks a question | Report fidelity, false success, owner honesty | Implemented, reference and 3 negatives + 1 alternative |
| s02, s03, s05 to s08 | Latest-intent corrections, mid-day opt-out, draft vs. send, pre-authorized bulk move, cross-client privacy with client timezone, noon policy change | See `PLAN.md` section 7 | Planned, not in repo yet <!-- TODO(author): build, or state clearly that the submission has only two tasks --> |

Scenario inputs (model-facing): `scenarios/*.json` and `scenarios/business.json`. Grader-only rules: `checks/`. Reference, negative and alternative trajectories: `reference/`. Tests: `tests/test_graders.py`.

## Failure analysis

<!-- TODO(results): for each failing model, quote or summarize the actual failing transcript from results/raw/<run_id>/<model>/<scenario>/trial_<n>.json. Cite the trial file path, the failing check name, and the step where it went wrong. Separate capability failures from grader errors, harness errors, truncation and ambiguous prompts. Include one near-success case if one exists. Do not write failure claims that were not observed. -->

## LLM-judge side study

<!-- TODO(results): planned, not yet built. The planned frontend module (`frontdesk/judge.py`, YES / NO / UNKNOWN rubric, different judge family from tested models, 2 runs per trial for repeatability, human labels in `human_labels/`) does not exist in the repo yet. Fill in judge model IDs, prompt, agreement with deterministic verdicts and author labels only after the runs. If the study is not done, remove this section or say so. -->

## Limitations

- Two implemented scenarios so far, one fictional business, one timezone: far too small to support general claims. <!-- TODO(author): update if more scenarios are added. -->
- The sandbox enforces only physical constraints (a stylist cannot be double-booked, closed hours). Policy rules live in the prompt and are graded after the fact. Generic trusted checks cover quiet hours, opt-outs, the 3-text cap, retry limits and privacy strings; draft-versus-send and "re-asking owner" checks from `PLAN.md` section 8.2 are not coded yet.
- The report schema has no "items needing owner" field, although `PLAN.md` section 5.3 mentions one.
- No seed is set. Sampling is nondeterministic, and provider-side model updates can change results between runs. Sandbox and grader are deterministic; model outputs are not.
- Grader correctness depends on the author's rule choices. Reference trajectories and negatives test the graders, but a wrong rule would be consistently wrong.
- Results come from a few trials per scenario. Spread across trials is reported, but confidence intervals are not.
- Costs depend on OpenRouter reporting `usage.cost` on each response (the cost column is 0 if it does not).

## Prior work and sources

- **micro1 PersonalAgentBench** (Task Completion vs. Trusted Completion, human-graded, single trial per task): https://www.micro1.ai/personal-agent-bench. This project borrows the two-axis idea and makes the trusted axis deterministic, with repeated trials and a report-fidelity axis.
- **tau-bench** (single-customer tool-using support threads; graded from end-state): see the guide https://www.layer3labs.io/guides/tau-bench-explained. This project uses the same idea of grading end state, but adds a multi-client clock, injected asynchronous events, owner authority and an end-of-day report to grade.
- **False-success motivation:** https://natesnewsletter.substack.com/p/ai-agent-false-success
- No code, data or scenarios were reused from these sources. All scenarios, names and phone numbers are fictional. <!-- TODO(author): confirm no third-party data or text was reused, and list any libraries beyond requirements.txt. -->
- Dependencies: `openai` Python SDK (used against OpenRouter's OpenAI-compatible endpoint), `pytest`. <!-- TODO(author): add license of each dependency if required. -->

## AI tool disclosure

<!-- TODO(author): describe which parts were drafted with AI tools (for example code, scenario text, grader rules, README prose), which models and tools were used, and how you personally reviewed each part: which scenarios and grader rules you checked by hand, which transcripts you read, and what you changed. The rubric scores this section, so be specific and accurate. -->

## License

MIT. See [LICENSE](LICENSE).
