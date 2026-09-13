<!-- minimal-harness:start -->
## Minimal Harness workflow

At session start run `python3 .harness/harness.py doctor` and `python3 .harness/harness.py status`, then read `.harness/HANDOFF.md`.
Keep one task active. Define tasks with `task add --from SPEC.json`; use `task revise ID --from SPEC.json --note TEXT` for explicit changes. Do not edit runtime status or evidence fields by hand.
Use `next` to select work, `verify` for command acceptance, and `record` for browser/manual observations. `run check` alone is not task evidence. Save browser artifacts in `.harness/artifacts/`.
Run `report ID` to inspect readiness and evidence, and `complete ID` only after every acceptance passes against the current code and definition. An unavailable tool means `unverified`; browser/manual records are attestations.
Respect configured allowed paths and approval operations. Stop at the configured failure limit; do not bypass a blocked task. Run `handoff` before ending the session.
<!-- minimal-harness:end -->
