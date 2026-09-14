# First-time user validation

[中文试用表](adoption-validation.zh-CN.md) · [Documentation](README.md)

Status: **pending real users**. Automated walkthroughs and agent reviews are engineering
checks; they do not demonstrate adoption, usability for humans, or willingness to reuse.

Ask three developers who have not used this project to try the README without coaching.
They should use disposable Git projects, not production repositories. They choose the
agent they normally use; a terminal-only attempt is also useful.

## Tasks

1. Install the runtime and reach the first successful acceptance and completion.
2. Add one acceptance for a small task in their own disposable project.
3. Change code after a passing check and explain the resulting report.
4. Start a fresh agent session using the handoff and identify the next action.

## Record for each participant

Copy the table for each participant. Record actual observations and leave untried
items as "Not collected."

| Observation | Result |
| --- | --- |
| OS, Python version, agent or terminal | Not collected |
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

Do not collect secrets, source code, screenshots, or telemetry without the participant's
agreement. There is no automatic telemetry in the runtime. No participants have been
contacted as part of implementation.
