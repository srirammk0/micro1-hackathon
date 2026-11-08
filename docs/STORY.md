# The trust gap is a tier gap

Front Desk Bench drops a model into a simulated salon day: texts from several clients, a clock that moves, reminders that fire on their own, a number that bounces, and an owner who gives instructions. Grading reads only the final sandbox state and the action log: did the state end up right (Task), did the agent avoid forbidden actions (Trusted), and does its end-of-day report match reality (Report).

**What we found (run 2026-11-08, same frozen prompt and grader for every model):**

- **Frontier models nearly saturate it.** Sonnet 5.5, GPT-6.1 Sol and Gemini 4 Argon passed 71 of 72 trials. The one failure was a self-corrected slip: Sonnet scheduled a reminder for 7:30 AM in the client's timezone, told her so, then caught it an hour later.
- **The fast tier does not.** Haiku 5.5, GPT-6 Luna, DeepSeek v4.1 Flash and GLM-5.3 Flash passed 65% of 160 trials (82% best, 45% worst). This is the tier that high-volume texting actually runs on, because it costs 3 to 50 times less per trial.
- **"Right calendar, wrong day."** In 36 fast-tier trials the calendar ended correct but the agent still broke a rule or misreported its day. A check of the calendar alone would have called those passes.
- **The hardest rule is the client's clock.** A NY client texts at 9:15 PM; every Haiku trial makes his change and then texts him back at 9:15 PM. The fast tier passed that scenario 1 time in 20.
- **False claims cluster in the cheapest models.** A day report or owner message contradicting the sandbox: GLM 22% of trials, DeepSeek 8%, Haiku and Luna 2%, frontier 0%.

**The lesson.** "Can AI do this?" has two answers depending on which model you can afford to run on every message. The best models handle a front desk's bookkeeping; the models cost-sensitive deployments choose still double-book their own promises, text at night, and occasionally report things that didn't happen. And those failures hide behind a correct-looking calendar.

**What would close the gap.** Make the report a function of tool results instead of free text, enforce quiet hours and opt-outs in the send tool rather than the prompt, and grade against the same state the owner will see. Or route the stateful, rule-heavy turns to a frontier model and keep the cheap model for plain replies.

**Honest limits.** 8 scenarios, one fictional business, 3 to 5 trials per cell. The frontier result says this version is too easy for the best models, not that they're flawless; harder versions (longer days, more concurrent clients) are untested.

**Context.** micro1's PersonalAgentBench (https://www.micro1.ai/personal-agent-bench) splits task completion from trusted completion with single-trial human grading; this is a deterministic, repeated, multi-client version of that split. τ-bench grades end state for one customer at a time. The false-success problem in agents is described at https://natesnewsletter.substack.com/p/ai-agent-false-success.
