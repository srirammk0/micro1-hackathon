# Submission checklist: Front Desk Bench

[x] done in repo, [ ] still to do. **You** = must be done personally.

## Still to do (you)

- [ ] Write what you personally reviewed in README "Sources and AI use" (only you can say it truthfully).
- [ ] Record the video (`docs/VIDEO_SCRIPT.md`), upload unlisted, test the link in a private window with audio.
- [ ] Paste the video link into README (`**Video:** TODO`) and the submission form.
- [ ] Rebuild the ZIP after those README edits (command below) and upload it.
- [ ] Paste the short description into the form.
- [ ] Accept the micro1 Participant Agreement yourself.
- [ ] Submit before 9:15 PM PT, Nov 8. Only the latest complete submission counts.

## Deliverables in the repo

- [x] README with description, domain/expertise, who it's for, run steps, key handling, runtime/cost, model IDs, settings, trials, scores, failure analysis, audit history, limitations, sources, AI use.
- [x] 8 scenarios (`scenarios/`), grader rules (`checks/`, `frontdesk/grade.py`), all rules stated in the prompt (`frontdesk/agent.py`).
- [x] Reference, alternative and negative solutions (`reference/`), 51 grader tests (`python run.py selftest`).
- [x] Raw transcripts and scores: `results/raw/final` (fast tier, 160), `results/raw/frontier` (72), plus `pilot1` and `main1` audit runs.
- [x] Results page generated from raw data (`docs/index.html`).
- [x] `requirements.txt`, `.env.example` (names only), MIT `LICENSE`.
- [x] No LLM judge in the score, so no judge validation needed. The judge side study was not built; README doesn't claim it.

## Build and check the ZIP

```bash
cd "/Users/sriram.mk/Documents/Personal/Side Projects/Hackathons/micro1"
rm -f front-desk-bench.zip && zip -qr front-desk-bench.zip . -x ".env" ".git/*" ".venv/*" "*/.pytest_cache/*" ".pytest_cache/*" "*/__pycache__/*" "*.DS_Store" "*.zip" ".claude/*"
unzip -l front-desk-bench.zip | grep -E " README.md$|\.env" ; ls -lh front-desk-bench.zip
```

README.md must appear at the top level, `.env.example` only (no `.env`), size under 50 MB.

## Short description (for the form)

Front Desk Bench: an agent runs a small salon's client texting, calendar and reminders for a simulated day, graded deterministically on final sandbox state, the action log and whether its end-of-day report is true (no LLM judge). Frontier models (Sonnet 5.5, GPT-6.1 Sol, Gemini 4 Argon) passed 71 of 72 trials; the fast tier used for high-volume texting passed 65% of 160, often with a correct calendar hiding a broken rule or a false report.
