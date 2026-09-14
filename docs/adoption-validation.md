# Maintainer worksheet for first-time user validation

[中文试用表](adoption-validation.zh-CN.md) · [Participant start page](../START-HERE.md) ·
[Documentation](README.md)

Status: **pending real users**. Automated walkthroughs and agent reviews are engineering
checks; they do not demonstrate adoption, usability for humans, or willingness to reuse.

This worksheet is for the maintainer. **Do not send it or the full README to a participant.**
Send only the platform page that matches their computer:

- [macOS participant page](first-use-macos.md)
- [Windows PowerShell participant page](first-use-windows.md)

For an actual trial, replace `DOC_COMMIT` in the URL below with the merge commit that
contains the guide. This keeps the instructions fixed while the participant works:

```text
https://github.com/denggui-ai/minimal-harness/blob/DOC_COMMIT/docs/first-use-macos.md
https://github.com/denggui-ai/minimal-harness/blob/DOC_COMMIT/docs/first-use-windows.md
```

Ask three developers who have not used this project to follow the selected page without
coaching. Do not explain a stale-evidence result until their own answer is recorded. They
must use disposable Git projects, not production repositories. Stage 1 is terminal-only;
an AI agent is not required.

Only participants who already have Git and Python 3.9+ count toward the three-person
sample. Record a missing prerequisite as onboarding attrition, then recruit a replacement;
do not turn this trial into an operating-system installation session.

## Tasks

1. Follow the fixed platform demo through its first successful acceptance.
2. Change the demo source after the pass and explain the resulting report without hints.
3. Restore, reverify, complete, and explain the handoff's next action.
4. Optionally install the release in a disposable project copy and add one existing test
   command as acceptance.

## Record for each participant

Copy the table for each participant. Record actual observations and leave untried
items as "Not collected."

| Observation | Result |
| --- | --- |
| OS, Python version, agent or terminal | Not collected |
| Git/Python prerequisite attrition before the timed trial | Not collected |
| Exact release tag or development commit; documentation language used | Not collected |
| Time to first valid completion | Not collected |
| Steps requiring help or manual JSON repair | Not collected |
| Can explain command evidence vs browser/manual attestation | Not collected |
| Can explain why stale evidence cannot complete | Not collected |
| Unexpected rejection or false completion | Not collected |
| Would use it again; reason in participant's own words | Not collected |

Acceptance target: all three finish the first workflow without maintainer intervention
and correctly explain a stale-evidence report. Record failures as findings, not as user
error. Prioritize repeat blockers before adding integrations or new orchestration.

Collect the six participant answers in the platform page verbatim: environment, elapsed
time, first blocker and raw output, stale-evidence explanation, disposable-project result,
and willingness to reuse. Moderator notes belong here, not in the participant guide.

Do not collect secrets, source code, screenshots, or telemetry without the participant's
agreement. There is no automatic telemetry in the runtime. No participants have been
contacted as part of implementation.
