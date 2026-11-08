# Video script: Front Desk Bench (5 minutes max)

Target runtime: 4:40, leaving buffer under the 5:00 limit. Narration in the script is a draft; numbers are placeholders until the full run exists. Do not read placeholder numbers aloud.

## Recording tips

- Screen recording with narration. AI-generated voice is allowed; facecam is optional.
- Export MP4 at 1080p. Check audio before upload.
- Upload to a host that gives a public or unlisted link that plays without sign-in (for example YouTube unlisted or Google Drive "anyone with the link"). Test the link in a private browser window with audio on.
- Keep the video under 5:00 on the player's counter. Speak at a steady pace (about 130 words per minute), so ~600 words is about 4:40.
- Show the actual terminal commands and actual output files. Do not show `.env` or any key; keep the terminal window clear of it.
- Re-check that every number on screen matches `results/raw/<run_id>/REPORT.md`.

## Timeline

| Time | Segment | Shot list (what is on screen) | Narration (draft) |
|---|---|---|---|
| 0:00 to 0:30 | Problem hook | Title card "Front Desk Bench". Cut to a text thread on a phone mockup: two clients, one reschedule. | "A salon front desk runs on texts and a calendar. Agents can write a nice reply. The hard part is keeping the calendar, reminders and the owner report consistent across a whole day. And agents tend to say 'done' whether or not it is." |
| 0:30 to 1:20 | The sandbox and one live scenario | Repo tree in editor (`frontdesk/`, `scenarios/`, `checks/`). Open `scenarios/s01_reschedule.json`, scroll the timeline. Run `python run.py run --scenarios s01_reschedule --models <one model> --trials 1` (or show a pre-recorded terminal capture if the live run is slow). | "The world is an in-memory salon with a fixed clock. Between steps, new texts arrive, a reminder fires automatically, and at the end the agent must file a structured report. Each trial starts from a fresh sandbox." |
| 1:20 to 2:10 | The three verdicts | Split screen: `checks/s01_reschedule.py` task checks on the left; `grade.py` trusted rules on the right. Show the `grade` output dict for one trial with each verdict highlighted. | "Three deterministic verdicts. Task: is the final state right? Trusted: did the agent do anything forbidden, like texting during the client's quiet hours? Report fidelity: does the end-of-day report match the state? No LLM judge is in the score." |
| 2:10 to 3:00 | Results charts | `docs/img/pass_rates_by_model.png`, then `docs/img/heatmap_scenario_by_model.png`. | "Across [N] trials per scenario and [M] models, [TODO(results): headline number]. The heatmap shows where each model fails. [TODO(results): one sentence on the pattern.]" |
| 3:00 to 3:50 | One failure transcript | Open the failing trial JSON, scroll to the tool calls around the failing step, highlight the report fields that disagree with the final state. | "Here is a real failure, trial [TODO(results): path]. At [TODO(results): step], the agent [TODO(results): exact action]. The report then says [TODO(results): quote]. The state says [TODO(results): quote]." |
| 3:50 to 4:20 | LLM-judge hot take | Slide with the question "Would a judge reading the transcript catch this?". Show judge agreement numbers if the study was run. | "A natural shortcut is to have a model read the transcript and grade it. [TODO(results): what the judge study found, or if not run, remove this segment and say 'future work'.] Sandbox state is the ground truth that the transcript can hide." |
| 4:20 to 4:40 | How to reproduce | Terminal: `python run.py selftest`, then `python run.py run ...` and `python run.py report ...` (show, do not run the paid run live). Show README "Setup" section. | "Everything reruns from a clean environment with one key. Offline grading and the selftest need no key." |
| 4:40 to 4:55 | Limits and close | Slide: limitations list (scenario count, fictional business, nondeterministic sampling). | "This is two [TODO(results): or more] scenarios, one fictional salon, and a few trials per model. Treat it as a method you can extend, not a leaderboard. Thanks for watching." |

## Narration word budget

- Total draft narration: about 600 words for 4:40 at 130 wpm. Cut the judge segment first if over time.

## Placeholders to fill after the full run

- `[N]` trials per scenario, `[M]` models: from `results/raw/<run_id>/REPORT.md`.
- Headline number and the heatmap pattern: from `REPORT.md` and the chart.
- Failure transcript path, step, and quoted report and state text: from the trial file. Quote only what is in the file.
- Judge study result: only if run. Otherwise remove the segment.
