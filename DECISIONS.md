# Decisions

A running log of design and project decisions: what was decided, why, and what it rules out. Newest first. When a decision is reversed, add a new entry that names the one it replaces instead of editing the old one.

| # | Date | Decision | Status |
| --- | --- | --- | --- |
| 048 | 2026-10-22 | Scan for secrets with gitleaks: the whole history in CI on every push, staged changes in a pre-commit hook | Accepted |
| 047 | 2026-10-22 | The README is rewritten for a stranger, the demo GIF is recorded from a VHS tape, and Milestone 3 is done | Accepted |
| 046 | 2026-10-22 | All three workflows have passed a first run; Run 5 (on GitHub) repeats Run 4's 18/18; Grok's event-quote habit noted for after M3 | Accepted |
| 045 | 2026-10-22 | CI: three workflows (every PR offline; kind manual + weekly; live evals manual), actions pinned to commits, tests can't reach the network | Accepted |
| 044 | 2026-10-22 | Run 4 (the "after"): both models 18/18; prompt version 2 stays; the Milestone 3 "one change" is done | Accepted |
| 043 | 2026-10-22 | Prompt version 2: one-line quotes and the CrashLoop/ConfigError line, the Milestone 3 "one change" | Accepted |
| 042 | 2026-10-22 | Run 3 (the "before"): Haiku 18/18, Grok 17/18; the evals' re-check decodes JSON-string fields; prompt version 2 proposed | Accepted; prompt version 2 accepted in 043 |
| 041 | 2026-10-22 | A fix with blank YAML counts as no fix, so Unknown passes and nothing invents a placeholder | Accepted |
| 040 | 2026-10-22 | Build 039: the forced turn requires `submit_diagnosis`; `cap_rate` and `first_try_grounding` fixed; rerun the "before" as Run 3 | Accepted |
| 039 | 2026-10-22 | Run 2 (the "before"): Haiku 18/18, Grok 15/18; require the call on the forced turn and fix two metrics before prompt version 2 | Proposed, accepted in 040 |
| 038 | 2026-10-21 | Fix the two measurement flaws from Run 1: unescape `\n` in grounding; recordings hold the full namespace inventory | Accepted |
| 037 | 2026-10-21 | First real eval: Haiku 18/18, Grok 17/18; fix two measurement flaws, then prompt version 2 as the one change | Accepted |
| 036 | 2026-10-21 | `triage-eval` grades replayed scenarios against `expected.yaml`; new gate metrics replace the template's | Accepted |
| 035 | 2026-10-21 | Remove the template's calculator example and the loop's plain-text mode | Accepted |
| 034 | 2026-10-21 | Compare Claude Haiku with `grok-4.20-0309-non-reasoning` | Accepted |
| 033 | 2026-10-21 | Evals replay the recorded scenarios; live runs are an optional check | Accepted |
| 032 | 2026-10-21 | Scenario 1 waits for the BackOff event, not the CrashLoopBackOff container state | Accepted |
| 031 | 2026-10-21 | Scenarios 1 and 3 break in a way their fix can repair | Accepted |
| 030 | 2026-10-21 | Milestone 2 hand runs: 6 of 6 right; fix scenarios 1 and 3 and settle how fixes are applied before M4 | Accepted |
| 029 | 2026-10-21 | First real run: accept objects sent as JSON strings, drop `anyOf` for nullable objects, and fix three rough edges | Accepted |
| 028 | 2026-10-21 | `triage` runs on a live namespace or a recording, through the same in-process MCP server | Accepted |
| 027 | 2026-10-21 | One fixed, versioned system prompt; the namespace and any alert go in the first user message | Accepted |
| 026 | 2026-10-21 | Reject submissions with ungrounded quotes or an unsafe fix, and measure first-try grounding from the trace | Accepted |
| 025 | 2026-10-21 | Keep the template's example eval gate until Milestone 3 replaces it with the scenarios | Accepted |
| 024 | 2026-10-21 | Cap runs at 12 investigative tool calls plus one forced submission turn; a run ends only on an accepted `submit_diagnosis` | Accepted |
| 023 | 2026-10-21 | `submit_diagnosis` is an agent-side tool validated against a strict `Diagnosis` schema | Accepted |
| 022 | 2026-10-20 | Record raw API responses per scenario at the reader level and replay them offline | Accepted |
| 021 | 2026-10-20 | `describe` shows ConfigMap keys but not values, and drops ServiceAccount Secret names | Accepted |
| 020 | 2026-10-20 | Fix the namespace when the MCP server starts, and refuse to start under any identity but the agent's ServiceAccount | Accepted |
| 019 | 2026-10-20 | MCP tools use the official Kubernetes Python client behind a `KubeReader` interface | Accepted |
| 018 | 2026-10-20 | Bind the read-only role with a ClusterRoleBinding, not a RoleBinding per namespace | Accepted |
| 017 | 2026-10-20 | RBAC test checks resources against an allowlist, not just verbs | Accepted |
| 016 | 2026-10-20 | Scenario format: one namespace per scenario, `expected.yaml` with a wait condition and `also_accept` | Accepted |
| 015 | 2026-10-20 | Seeder uses `kubectl` and refuses non-kind contexts | Accepted |
| 014 | 2026-10-20 | Scenarios use pinned public images with memory limits and never create Secrets | Accepted |
| 013 | 2026-10-20 | Add PyYAML (runtime) and types-PyYAML (dev) | Accepted |
| 012 | 2026-10-20 | Defer the comparison-model API key to Milestone 3 | Accepted |
| 011 | 2026-10-20 | Use Claude Haiku as the default model while building | Accepted |
| 010 | 2026-10-20 | Keep the template's example tools and evals until M1/M2 replace them | Accepted |
| 009 | 2026-10-20 | Start from ai-project-template; rename the package to `triage` | Accepted |
| 008 | 2026-10-20 | Apache-2.0 license and an employer disclaimer from the first commit | Accepted |
| 007 | 2026-10-20 | Develop and evaluate on a local `kind` cluster | Accepted |
| 006 | 2026-10-20 | Quote evidence and check every quote against real tool output | Accepted |
| 005 | 2026-10-20 | Cap the agent at 12 tool calls; on the cap, submit with low confidence | Accepted |
| 004 | 2026-10-20 | Trim tool output before the model sees it | Accepted |
| 003 | 2026-10-20 | The caller picks the namespace, never the model | Accepted |
| 002 | 2026-10-20 | Read-only access enforced by RBAC, not by the prompt | Accepted |
| 001 | 2026-10-20 | The agent never changes the cluster; a human applies fixes | Accepted |

## Open questions

- **How a person applies a fix.** Fixes are partial objects (030). Plain client-side `kubectl apply` would delete fields the scenario's last-applied annotation still lists; `kubectl patch` (strategic merge) or `kubectl apply --server-side` would not. Decide in M4 with the dry-run check, then align the prompt, the `proposed_fix` description and the report.

---

### 048 — Scan for secrets with gitleaks: the whole history in CI on every push, staged changes in a pre-commit hook
**Why:** Before the repo goes public, its whole history has to be free of secrets, since a key deleted in a later commit is still published. A one-off scan with gitleaks v8.30.1 on 2026-10-22 covered all 25 commits and found two false positives, both from the generic API-key rule: the deliberately fake JWT that tests the recordings' secret check (`tests/test_replay.py`; it decodes to `{"sub":"x"}` and the word "signature") and a pod name in a hand-written fixture (`tests/fixtures/kube/pods.json`). Two automatic checks keep it that way, chosen 2026-10-22: CI on every push and PR, and a hook before each commit. The existing `detect-private-key` hook and `check_no_secrets` on recordings catch narrower cases.
**Consequence:**
- `.gitleaksignore` lists the two false positives by fingerprint (commit, file, rule, line), so a new finding anywhere, including a new copy of the same fake token, still fails.
- `ci.yml` gains a `secrets` job: a full-history checkout (`fetch-depth: 0`), the gitleaks v8.30.1 release binary checked against its published SHA-256, then `gitleaks git` over every commit. A binary rather than `gitleaks-action`, to keep the pinning used everywhere else and avoid that action's licence-key rule for organisations. Dependabot doesn't update a version in a `run` step, so a newer gitleaks is a deliberate edit of `VERSION` and `SHA256`.
- `.pre-commit-config.yaml` gains gitleaks' own hook, pinned to the v8.30.1 commit, which scans staged changes. pre-commit builds it with Go on the first run (a minute or two), so it needs no Homebrew install. `uv run pre-commit install` enables all the hooks, and the README's runbook now says so.
- Verified on 2026-10-22: the CI step's install and scan, run as written, passes on the current history, and a throwaway copy with a fake Anthropic key committed fails with exit 1.
- When the repo is public, GitHub's own secret scanning and push protection should be switched on too (Settings → Advanced Security). They're free for public repositories and block known provider keys at push time.

### 047 — The README is rewritten for a stranger, the demo GIF is recorded from a VHS tape, and Milestone 3 is done
**Why:** Milestone 3's last item was a README a stranger can follow, with the results table, a runbook, known failure modes and "How I built this with Claude Code", plus a demo GIF. The README had grown as a progress log, so a newcomer met the milestone history before the results. Approved on 2026-10-22 ("perform that last tick for milestone 3").
**Consequence:**
- The README now runs: demo, results (Runs 4 and 5, the current prompt, with what each column means and how to reproduce them), why this project, how it works (a Mermaid diagram), a runbook from a clean clone (offline; one recorded diagnosis; a live kind cluster; the tools from Claude; evals; re-recording; clean-up; troubleshooting from the problems actually hit while building it), CI, known failure modes (what the models get wrong, what the agent can't do yet, what the evals don't show), how it was built, then the progress log unchanged.
- The demo is `docs/demo.tape`, a [VHS](https://github.com/charmbracelet/vhs) script that records `docs/demo.gif` of `triage --replay` on scenario 6. A tape rather than a screen recording because anyone can re-record it identically after a change. It makes one real model call (about $0.002), so the GIF is real output, not the fake model. VHS is a tool for recording, installed on the machine that records, not a project dependency.
- Milestone 3 is marked done 2026-10-22: its "Done when" (a stranger can clone, follow the README and reproduce the results table) was shown by Run 5, which reproduced the table from the `eval-live.yml` workflow on a GitHub runner (046). The commit that marks it done must include `docs/demo.gif`.
- CLAUDE.md's "Coming in M3" list is replaced by a pointer to M4. ARCHITECTURE's "Built so far" says what M4 plans.

### 046 — All three workflows have passed a first run; Run 5 (on GitHub) repeats Run 4's 18/18; Grok's event-quote habit noted for after M3
**Why:** 045 said to tick the GitHub Actions item once `ci.yml` was green and each manual workflow had passed once. On 2026-10-22: `ci.yml` passed on a pull request (Dependabot's first PR, `chore(deps): bump …`); `kind.yml` passed by hand twice (runs 39828702303 and 39833628382; a third, 39835066851, was still running when this was written; about 3 minutes each, all six scenarios seeded, recorded and passing the recording tests and offline gate on GitHub's runner, live diagnosis skipped); `eval-live.yml` passed by hand (run 39835204120, 4.5 minutes, $0.50). That eval is Run 5 in evals/RESULTS.md: prompt version 2 again, both models 18/18, Haiku first-try grounding 1.0 at $0.0022 an incident, Grok 0.97 at $0.026. Grok's two quote rejections both joined an event's `type`, `reason` (and once `object`) and `message` lines into the one-line form `kubectl get events` prints; every Grok quote rejection since prompt version 2 but one has been this.
**Consequence:** The README's GitHub Actions item is ticked and Run 5's results file is committed from the run's artifact. Not done in M3, noted for later: make the event quote that models reach for a real one, either by naming the case in the prompt (it is at 498 of 500 words, so something would have to go) or by having `get_events` print one line per event (`Warning BackOff Pod/api-…: Back-off restarting …`), which changes the tool's output, the trimming tests and every recorded-output test, and needs a "before" run. Dependabot's first PR bumps a pinned action to a release from the last few days; leave it a week before merging, as with setup-uv in 045.

### 045 — CI: three workflows (every PR offline; kind manual + weekly; live evals manual), actions pinned to commits, tests can't reach the network
**Why:** Milestone 3 asks for checks on every PR and a manual workflow that spins up kind and runs the evals. The template's two workflows covered the first and half of the second: `eval-live.yml` still offered the removed `openai` path, defaulted to Anthropic only, had no kind job, and pasted inputs straight into the shell. Choices made on 2026-10-22: run the kind job weekly as well as by hand (it's free, and a red run means kind or Kubernetes has drifted from the recordings); pin actions to commit SHAs with Dependabot proposing updates (a tag can be moved by the action's owner; a commit can't); offer a live diagnosis in the kind job as an input that is off by default.
**Consequence:**
- `ci.yml` (every push to `main` and PR) adds `uv sync --locked`, a read-only token, checkout without kept credentials, a timeout, cancelling superseded runs, and shellcheck on `scripts/`.
- `tests/conftest.py` makes every connection and name lookup for a host other than this machine fail for the whole test session, with tests showing a real Anthropic client can't get through. CLAUDE.md's "tests never call a model API or need a cluster" is now enforced in every run, local or CI.
- `kind.yml` (manual, and Mondays 14:17 UTC) is its own workflow so the free weekly job never sits next to API keys it doesn't need: kind v0.33.0 with the `kindest/node:v1.37.0` image pinned by digest (the version the recordings were made on), the RBAC, the agent's kubeconfig, `triage-seed record` for all six, then the recording, CLI and eval tests plus the offline gate on the fresh recordings. They're uploaded and summarised, never committed. The optional live diagnosis gives keys only to its own step, treats "no diagnosis" (exit 1) as a result and fails only on a setup problem (exit 2).
- `eval-live.yml` (manual) defaults to `anthropic grok` and 3 repeats, accepts a scenario list, checks inputs and each chosen provider's key and model before spending anything, passes inputs to the shell only through environment variables, writes the tables to the run summary and uploads the results and run log. Model names are repository variables, not secrets; an empty `ANTHROPIC_MODEL` falls back to `claude-haiku-5-5`.
- The README's five kubeconfig commands become `scripts/agent-kubeconfig.sh`, which the README, the kind job and anyone cloning the repo all use. It removes the caller's own credentials from the copy and exits non-zero unless the result authenticates as `triage-system/triage-agent`; tests run it against a stand-in `kubectl`.
- setup-uv is pinned to v10.2.0 (2026-09-21) rather than its newest release, published the day this was written; Dependabot will propose newer ones.
- The README's GitHub Actions item is ticked once `ci.yml` is green and one manual run of each other workflow has passed.

### 044 — Run 4 (the "after"): both models 18/18; prompt version 2 stays; the Milestone 3 "one change" is done
**Why:** Run 4 (evals/RESULTS.md: commit `40a407e`, prompt version 2, $0.48) against Run 3 (version 1). Haiku 18/18, first-try grounding 1.0, $0.0023 an incident; Grok 18/18, 0.98, $0.024. The CrashLoop/ConfigError wording did what it was for: Grok's scenario 1 went from 2/3 to 3/3, with no ConfigError calls (2 of 6 runs across Runs 2–3) and fewer calls (4 against 5–6). The quoting rule showed no measurable effect: Run 3 had no joined or annotated quotes left, and Run 4's one ungrounded first try was a new kind, a sentence Grok wrote itself, which grounding caught and Grok corrected in one retry after the new rejection message. The first real cap hit since 040 (`d082cccc60e9`) submitted the right diagnosis on the forced turn, where Run 2's identical path ended with none.
**Consequence:** Prompt version 2 stays as the current prompt, and the README's "one change" item is ticked. Haiku stays the default model: equal accuracy at about a tenth of Grok's cost. Not pursued in M3, noted for later: Grok's 10–12 calls on scenario 6 (an exploration budget, or a prompt line saying a `not found` Role is itself the evidence) and Haiku leaving required fields out of 1 in 6 first submissions (costs a turn, never a diagnosis). With 3 repeats per scenario, single-run differences are noise (Grok has ranged 15/18–18/18 without changes to how it diagnoses); the scenario 1 result is the clearest signal because a specific repeated mistake disappeared. Next in M3: the CI workflows, then the README for a stranger.

### 043 — Prompt version 2: one-line quotes and the CrashLoop/ConfigError line, the Milestone 3 "one change"
**Why:** Approved on 2026-10-22 as proposed in 042. Across Runs 1–3, the two failures that cost Grok diagnoses under prompt version 1 were quotes that grounding rightly rejected (joined lines or fields, words cut from the middle of a line, notes added, YAML rewritten in flow style; 2 runs lost) and scenario 1 called ConfigError (2 runs lost). Both are wording problems the prompt can address, and each leaves its own trace, so the "after" run can show which one moved.
**Consequence:** `PROMPT_VERSION` is "2". The evidence rule now says each quote is one line, or a contiguous part of one, copied exactly as shown: never join lines or fields, cut words out of the middle, add notes, or rewrite YAML in another style. That is stricter than grounding, which accepts adjacent lines (026, 038); the prompt asks for the safe form, the checker stays as it was. CrashLoop now reads "a container starts and keeps exiting with an error … even when the cause is a missing setting or env var", and ConfigError "Kubernetes can't create or start the container … If the container starts and then exits, it is CrashLoop." A rejected quote's message repeats the rule ("quote one line, or a contiguous part of one, exactly as shown; don't join lines or add notes") instead of "copy it exactly from a tool result". The prompt is 498 words against the test's 500 cap; the next addition has to replace something rather than raise the cap. Nothing else changes: same tools, schema, loop, recordings and models as Run 3, so Run 4 measures this change alone. Expected: no Grok scenario 1 ConfigError and fewer ungrounded first tries; with Run 3 already at 1.0 for Grok's grounding and 5 lost runs out of 54 across three runs, a 3-repeat "after" can confirm a large effect but not a small one, and the write-up will say so.

### 042 — Run 3 (the "before"): Haiku 18/18, Grok 17/18; the evals' re-check decodes JSON-string fields; prompt version 2 proposed
**Why:** Run 3 (evals/RESULTS.md: commit `b259251`, prompt version 1, $0.46) is the "before" for prompt version 2. Haiku 18/18, first-try grounding 0.99, $0.0024 an incident; Grok 17/18, 1.00, $0.023. No run hit the cap, so 040's required tool call wasn't exercised (the smoke test showed it works). The run exposed one more measurement bug: `submission_attempts` validated each submission without the JSON-string decoding `submit_diagnosis` applies (023), so Haiku's `b5a9e8e8cb69`, accepted with `proposed_fix` sent as a string, had no attempt to score and dropped out of the average.
Across Runs 1–3 (54 runs per model), what still goes wrong, all with prompt version 1:
- **Grok's quoting:** 5 runs with an ungrounded first try (joined, trimmed or annotated lines), 2 of them costing the run (Run 1 scenario 5, Run 2 scenario 1); none in Run 3.
- **Scenario 1 as ConfigError:** Grok, once in Run 2 and once in Run 3. The prompt defines ConfigError as a container that never starts; here it starts and exits 1.
- **Missing or extra fields:** Haiku, in 5 runs a submission left out `confidence` or `proposed_fix`, or added a field; each cost a retry, never a diagnosis.
- **Over-exploring scenario 6:** Grok, 7–12 calls where Haiku uses 4–5, after the API's `not found` for the missing Role.
**Consequence:** `decode_json_strings` and its field list move from `agent/submit.py` to `models.py`, and both `submit_diagnosis` and `submission_attempts` use them, so the evals read a submission exactly as the agent did. Run 3's saved figure stays as saved (0.988); RESULTS.md gives the corrected 0.989. Settles the scenario 1 open question: keep CrashLoop as the only accepted answer, since the prompt's own definitions decide it and accepting ConfigError would grade a misreading as right.
**Proposed (waiting for approval): prompt version 2**, one prompt change aimed at the two failures that cost diagnoses, each traceable in the "after" run's traces by its own symptom:
- Quotes: copy one line, or a contiguous part of one, exactly as shown; never join lines or fields, trim inside a line, add notes, or restyle YAML. The grounding rejection message says the same.
- The CrashLoop/ConfigError line: "a container that starts and then exits, even because a setting is missing, is CrashLoop; ConfigError is only when Kubernetes can't create or start the container."
Not in version 2: required-field reminders (they cost a turn, not a diagnosis, and the schema already enforces them) and an exploration budget for scenario 6 (a separate change with its own trade-off).

### 041 — A fix with blank YAML counts as no fix
**Why:** The smoke test for 040 (both models at `MAX_TOOL_CALLS=1` on scenario 6) showed both APIs accept the required tool call, and showed a new problem. Grok's forced submission (run `74020f9e8c67`) was Unknown with `proposed_fix: {explanation, yaml: ""}` instead of null. The schema's message, "String should have at least 1 character", led it to resubmit with a placeholder `ConfigMap` named `dummy`, which every check passed. A placeholder fix is worse than none: a person might apply it. With 040 requiring a submission on every capped run, Unknown with no fix becomes a more common answer, so this matters before Run 3.
**Consequence:** `Diagnosis` treats a `proposed_fix` whose YAML is blank as null before validating. Unknown then passes with no fix, and any other category gets "required unless category is Unknown" instead of the character-count message. The tool schema the model sees is unchanged, so this doesn't change the prompt. Placeholder fixes in general (a real-looking object that changes nothing) aren't detected; M4's dry-run check is where fix validity gets tested.

### 040 — Build 039: the forced turn requires `submit_diagnosis`; `cap_rate` and `first_try_grounding` fixed; rerun the "before" as Run 3
**Why:** Approved on 2026-10-22. Settles 039's open question in favour of a Run 3: Milestone 3 asks for one change with a before and after, and with these fixes in place a rerun on prompt version 1 means the prompt version 2 comparison changes only the prompt. The alternative, one run for both, saves about $0.55 but leaves the loop fix and the prompt change to be told apart from traces.
**Consequence:** `Provider.complete` takes `require`, a tool the model must call that turn; the Claude adapter sends `tool_choice: {type: tool, name}` and the OpenAI-compatible adapter `tool_choice: {type: function, function: {name}}` (xAI documents the same form). Requiring a tool that isn't offered raises before any API call. The loop requires `submit_diagnosis` on the forced turn only; elsewhere the model still chooses freely, so nudges keep their meaning. `AgentResult.hit_cap` records that all investigative calls were used, and the evals' `at_cap` comes from it rather than from the stop reason. A run with no schema-valid submission gets `first_try_grounding: None` and is left out of the average, which is None if no run submitted (the gate treats None as a fail). Runs 1 and 2 keep the numbers they were saved with; in their saved rows a no-submission run shows 0.0. Whether Grok, required to call the tool, submits a sensible diagnosis or a forced placeholder is something Run 3 will show; the grounding and schema checks apply to it as to any submission.

### 039 — Run 2 (the "before"): Haiku 18/18, Grok 15/18; require the call on the forced turn and fix two metrics before prompt version 2
**Why:** Run 2 (evals/RESULTS.md: commit `a61b8de`, prompt version 1, recordings with the full inventory from 038, $0.55) confirmed the measurement fixes: no unrecorded calls for either model, no quote rejected for escaping, and Haiku unchanged (18/18, first-try grounding 1.00, $0.0023 an incident). Grok fell to 15/18, and its traces showed problems that would distort the prompt version 2 comparison if left in place:
- **The forced turn doesn't force.** With the API's real `not found` for Role and RoleBinding `reporter`, Grok kept looking (events for Role, ClusterRole and their bindings) until the 12-call cap in two scenario 6 runs, then answered in plain text on the last turn, with the right diagnosis. The loop offers only `submit_diagnosis` there (029) but never tells the API that a tool call is required, so a model can decline. Both APIs can require it: Anthropic's `tool_choice: {type: tool, name}` and the OpenAI-compatible `tool_choice` naming the function.
- **`cap_rate` undercounts.** It counts runs that submitted at the cap, so it read 0.0 although two runs hit the cap.
- **`first_try_grounding` mixes in runs with no submission.** A run with no schema-valid submission scores 0, so a run that never submitted lowers an evidence metric. Over the 16 Grok runs that submitted something, first tries averaged 0.94.
- **Quoting, again.** Grok's scenario 1 miss (`bf8a33de6964`) was three rejected submissions joining an event's `type` and `message` fields into one quote, the habit prompt version 2 targets. All three named ConfigError rather than CrashLoop.
**Consequence (proposed, waiting for approval):** before prompt version 2, (1) the forced turn requires the call: the `Provider.complete` interface gains a way to require a named tool, mapped to each API's `tool_choice`, and the fakes record it so tests can check it; (2) `at_cap` means the cap was reached, whatever the outcome; (3) `first_try_grounding` averages only runs with at least one schema-valid submission. Runs 1 and 2 keep the metrics they were saved with; RESULTS.md notes the change of definition. Whether to rerun the "before" after these fixes (another $0.55) or go straight to prompt version 2 is in Open questions.

### 038 — Fix the two measurement flaws from Run 1: unescape `\n` in grounding; recordings hold the full namespace inventory
**Why:** Carries out the first half of 037, so the prompt version 2 before-and-after measures the agent and not the tools. Grounding: YAML shows a multi-line string as one double-quoted line with `\n` escapes, and a model quotes it as it reads, with real line breaks (run `369e87b3bb3e`); treating `\n` and `\t` like the `\"` and `''` cases already handled (026) fixes that, while lines must still be adjacent in the output, so joined quotes like run `f740db3c3d7d`'s are still rejected (a test checks both). Replay: the recorder read every object in the scenario's manifest plus its pods and ReplicaSets, but not the two objects every namespace has, so a request for the `default` ServiceAccount or anything absent got "not in this recording" instead of the cluster's answer. Reading those two completes the inventory of what `describe` can reach, so replay can answer anything else with the API's own "not found" (or no endpoints for a Service), which is what Grok's six unrecorded calls in Run 1 would have got.
**Consequence:** `Recording` gains `inventory_complete`; recordings made before this stay False and keep the old behaviour. All six scenarios are re-recorded, and a test requires every committed recording to be complete. `kube-root-ca.crt` holds the cluster's public CA bundle, not a Secret, and `describe` shows only its key names anyway (021). "Not in this recording" remains for calls replay genuinely can't answer (other access reviews, other namespaces), and the evals keep counting those. Next: rerun both models as the "before" for prompt version 2.

### 037 — First real eval: Haiku 18/18, Grok 17/18; fix two measurement flaws, then prompt version 2 as the one change
**Why:** Run 1 (evals/RESULTS.md: commit `0c533fe`, prompt version 1, 3 runs per scenario per model, $0.55) gave Claude Haiku 18/18, first-try grounding 1.00, 3.9 tool calls and $0.0022 an incident; `grok-4.20-0309-non-reasoning` 17/18, 0.92, 5.3 calls and $0.028. Reading every anomaly by run ID showed three kinds of problem:
- **Grok's quoting.** It joined non-adjacent lines into one quote, trimmed lines, and added notes inside quotes. Grounding (026) rightly rejected these; the scenario 5 miss came from resending the same joined quote after being told it wasn't found. Its diagnoses were all right.
- **A grounding false negative.** A script quoted with real line breaks didn't match `describe` output that shows it as a YAML string with `\n` escapes. Same text, different escaping, like the `\"` case 026 already handles.
- **A replay gap.** Grok asked to describe objects the recorder never read: Role and RoleBinding `reporter`, ConfigMap `api`, ServiceAccount `default` (6.2% of its calls). A real cluster answers "not found", or with the object for `default`; replay answered "not in this recording", which is less faithful and tells the model it is being evaluated.
**Consequence:** Haiku stays the default model: it matched or beat Grok on every measure except p50 latency, at a thirteenth of the cost. Before the Milestone 3 "one change", the two measurement flaws are fixed so the before-and-after compares like with like: grounding treats `\n` and `\t` escapes as line breaks and tabs, and the recorder reads the namespace's built-in objects (the `default` ServiceAccount and the `kube-root-ca.crt` ConfigMap) so a recording holds everything `describe` can reach, letting replay answer anything else with the API's own "not found". The scenarios are then re-recorded and rerun as the "before". The one change is prompt version 2, aimed at the quoting failures: quote one line or part of a line exactly, never join lines or add notes, keep quotes short, and a rejection message that says the same. Run 1's results file is committed as the record.

### 036 — `triage-eval` grades replayed scenarios against `expected.yaml`; new gate metrics replace the template's
**Why:** The evals should measure what matters for a diagnosis: the right category and object (with `also_accept` counting), whether the run ended in an accepted submission, and whether the first submission's evidence was real (first-try grounding, from the trace, since rejected quotes are corrected before a person sees them). Tool calls, cap hits, latency and cost show what it took; the share of calls the recording couldn't answer shows whether replay still stands in for the cluster (033). Runs go through the same `diagnose()` as `triage`, so the evals test the real path. The offline gate needs a model that gets every scenario right for free, so a scripted golden model follows each scenario's signal and quotes the real line it finds.
**Consequence:** `evals/baseline.json` now holds `accuracy`, `submitted_rate` and `first_try_grounding` (all 1.0 for the golden model). That replaces the calculator's `answer_accuracy`, `tool_accuracy` and `answered_rate`: a change of metrics, not a lowering. Results are saved only with `--save`; the manual workflow passes it. The gate checks minimums only, so `unrecorded_call_rate` is reported but not gated.

### 035 — Remove the template's calculator example and the loop's plain-text mode
**Why:** 025 kept them only so CI had an eval gate until the scenarios replaced it, which 036 does in the same commit. Nothing else used them.
**Consequence:** Supersedes 025. Gone: `mcp_server/server.py`, `evals/cases.jsonl`, their tests, `run_agent`'s plain-text mode and its `max_steps` (every run now needs a finish tool), and the `MAX_STEPS` setting. The loop's basic tests now use a tiny finish tool of their own.

### 034 — Compare Claude Haiku with `grok-4.20-0309-non-reasoning`
**Why:** Settles the open question from 012. Grok was the portfolio plan's original choice, and xAI's API is OpenAI-compatible, so the existing provider works unchanged. Of xAI's models, `grok-4.20-0309-non-reasoning` ($1.25 in / $2.50 out per million tokens under 200K) is the closest match to Haiku's fast, cheap tier; `grok-4.7` costs $2 / $6. One replay of scenario 6 on 2026-10-21 got it right (RBACDenied, ServiceAccount/reporter, 0.90) in 11 tool calls and 15.9s for about $0.049, against Haiku's 5 calls, 6.8s and $0.0027.
**Consequence:** Setup is easy to get wrong, so `.env.example` spells it out: the key must be a "Grok Interface" key from console.x.ai's API Keys page, with prepaid credits on the same team; a key from the grok.com consumer app is rejected with "Incorrect API key provided". `config/pricing.json` has the model's price. `triage` now reports a refused model call as one line (`the model API refused the request (grok/<model>): ...`, exit code 2) instead of a traceback.

### 033 — Evals replay the recorded scenarios; live runs are an optional check
**Why:** Milestone 3 is done when a stranger can reproduce the results table. Replaying the six recordings needs only the repo and an API key, gives every model the same cluster output, and costs cents; seeding a cluster for every run needs kind, takes minutes per scenario, and lets the cluster's timing change what the agent sees. The trade-off is that the agent can only see what was recorded, so the evals count calls the recording doesn't have; if that number grows, the recorder's sweep (022) is missing something.
**Consequence:** `triage-eval` will run the scenarios from `tests/fixtures/scenarios/` (step 1b). A live mode and an optional kind job in the manual workflow (step 4) check that recordings still match a real cluster. The offline gate no longer writes result files; the five committed from local gate runs of the template's fake model are removed, since they weren't real results.

### 032 — Scenario 1 waits for the BackOff event, not the CrashLoopBackOff container state
**Why:** Seeding scenario 1 took 6 seconds the first time, then 84 to 164 seconds, then timed out at 180 seconds while re-recording for 031. The recordings show the container as `terminated: Error` rather than `waiting: CrashLoopBackOff` at the moment it was read, so the kubelet only sometimes reports the waiting state during back-off and a poll every 3 seconds can keep missing it. Exactly why wasn't pinned down. The kubelet's `BackOff` event ("Back-off restarting failed container") is emitted when back-off starts and stays in the event list, so polling can't miss it, and it means the same thing.
**Consequence:** Only `expected.yaml` changes; the category and expected answer don't. The recording check for scenario 1 now looks for `reason: BackOff` in `get_events` instead of a pod state. The seeding tests that used scenario 1 as their container-state example now use scenario 2.

### 031 — Scenarios 1 and 3 break in a way their fix can repair
**Why:** 030 found that no fix could make either scenario healthy: scenario 1's script exited 1 unconditionally, and scenario 3's `tail /dev/zero` grew without bound. A scenario whose correct fix can't work would fail the M4 fix-validity check for the scenario's sake, not the agent's. Scenario 1 now exits only when `LISTEN_PORT` is unset and otherwise keeps running; scenario 3 now reads one 40 MiB block with `dd` and holds it by blocking on a pipe to `sleep` (about 41.7 MiB resident, measured), well over its 16Mi limit and under the 64Mi the agent proposed.
**Consequence:** Same failure signals, categories and expected answers, so `expected.yaml` doesn't change, but both scenarios are re-recorded. Tests now run scenario 1's script with and without `LISTEN_PORT`, and check scenario 3's fixed size sits between its limit and 64Mi. This supersedes the first two findings in 030.

### 030 — Milestone 2 hand runs: 6 of 6 right; fix scenarios 1 and 3 and settle how fixes are applied before M4
**Why:** The bar was 4 of 6. With `claude-haiku-5-5` and prompt version 1, one run each (scenario 1 live, the rest replayed), all six got the right category and affected object, in 3 to 5 tool calls, at about $0.002 a run, every one accepted on its first submission once 029 was in. Three things came out of reading the fixes, not just the categories:
- **Scenario 1's fix can't work as written.** The container's script exits 1 unconditionally, so setting `LISTEN_PORT`, which the agent rightly proposed, would not make it Ready. The agent noticed and said so in its explanation. The scenario should exit only when `LISTEN_PORT` is unset.
- **Scenario 3 has the same problem.** `tail /dev/zero` grows without bound, so no memory limit is enough, and raising it to 64Mi (the proposed fix) would still be OOMKilled. The scenario should allocate a fixed amount above 16Mi (for example 40Mi) and then sleep.
- **Partial-object fixes and `kubectl apply`.** Fixes name the object and only the fields that change (026). The scenarios were created with client-side `kubectl apply`, so applying scenario 4's fix (a ConfigMap with only `LOG_LEVEL`) the same way would delete `LOG_FORMAT`, and a partial Deployment patch would drop fields like `image`. `kubectl patch` or server-side apply keeps them. The prompt and the field description still say "`kubectl apply`".
**Consequence:** Milestone 2 is done. Before the M4 fix-validity check: change scenarios 1 and 3 and re-record them, and decide how fixes are applied (now an open question). Weaker evidence picks (`ready: 1/1`, an nginx start-up line) are grounded and harmless; the M3 evals will show whether they matter. One run per scenario says the agent works, not how reliably: that is M3's job.

### 029 — First real run: accept objects sent as JSON strings, drop `anyOf` for nullable objects, and fix three rough edges
**Why:** The first `triage --replay` of scenario 6 with Claude Haiku found the right answer (RBACDenied, ServiceAccount/reporter, grounded quotes, a namespaced Role and RoleBinding) but ended `no_submission`: in all three tries it sent `proposed_fix` as a JSON-encoded string, once with `confidence` folded inside it, and the rejection message ("Input should be a valid dictionary") didn't say what was wrong. Nullable nested objects, which Pydantic writes as `anyOf: [object, null]`, are a known trigger for this. Replaying that run's own arguments with the fixes below, the second try is accepted.
**Consequence:**
- The schema writes a nullable object as the object with `type: ["object", "null"]`.
- `parse_submission` decodes `affected_resource`, `evidence` or `proposed_fix` when they arrive as a JSON string; text after the JSON is dropped, so a field folded into it is reported as missing. A non-JSON string gets `send an object with ..., not a string`. Grounding still applies to whatever is decoded.
- The MCP server is built with `log_level="WARNING"`: the SDK configures root logging, and at INFO every model HTTP request was printed inside the report.
- A 401 from the API server now says the agent's one-hour token has probably expired and points to the README to renew it, instead of a bare "Unauthorized".
- `config/pricing.json` has `claude-haiku-5-5` at $0.10 / $0.50 per million tokens (the rate for prompts up to 100K tokens; every triage request is far below that). Taken from a third-party summary of Anthropic's docs on 2026-10-21; to confirm against the console.

### 028 — `triage` runs on a live namespace or a recording, through the same in-process MCP server
**Why:** One command for both the real thing and offline development: `--namespace` reads the cluster through the agent's kubeconfig after the same identity check as `triage-mcp`, and `--replay` reads a recording, so prompt changes can be tried on all six scenarios without a cluster. Both build the same MCP server in-process and connect to it with the MCP client, so the agent sees exactly the tools an external client would. Exit codes (0 diagnosed, 1 not, 2 setup) make it scriptable, and `--json` gives the diagnosis for other tools.
**Consequence:** Each run's log line gains `info` (namespace, prompt version, source, alert) next to the trace and the diagnosis, which is what the M3 evals will read. The report strips terminal control characters from model and cluster text, since quotes come from logs. `MAX_TOOL_CALLS` (default 12) is now a setting, and the `MAX_OUTPUT_TOKENS` default goes from 1024 to 2048, because a diagnosis with a Role and RoleBinding fix runs to several hundred tokens and a reply cut off at the limit loses its tool call. The template's question-answering `triage` command is gone; its prompt moved into the eval runner until M3.

### 027 — One fixed, versioned system prompt; the namespace and any alert go in the first user message
**Why:** A prompt that never changes between runs is one text to reason about and compare across eval runs, and the API can cache it. The namespace is per-run input, so it belongs in the user message, alongside an optional alert from the caller, which is labelled a hint rather than proof so the agent still checks it. The prompt lists the signs of every category, built from the `Category` enum, says which object counts as "affected" (the Deployment, or the ServiceAccount for RBACDenied), and repeats the rules the grounding check enforces (exact quotes; named, namespaced, non-Secret fixes) so most submissions pass the first time.
**Consequence:** Changing the prompt means bumping `PROMPT_VERSION`; runs will record it from step 5. Tests check the rules and the triage order are present, not the prompt's quality; that is what the hand runs and M3 evals measure. The NetworkPolicy signs describe symptoms only, because the tools can't read NetworkPolicies yet (an M4 change to the tools and the RBAC allowlist).

### 026 — Reject submissions with ungrounded quotes or an unsafe fix, and measure first-try grounding from the trace
**Why:** 006 says every quote is checked against real tool output; this decides what happens when one fails. Rejecting it and letting the model retry means a person never sees an invented quote in a report, and the trace still holds every attempt, so `submission_attempts` can report the first-try hallucination rate for the evals. The other option, accepting the submission and marking quotes as unverified, measured the same thing but showed made-up evidence to the reader. Matching ignores whitespace and two escaping differences (`\"` in JSON logs, `''` in YAML) but nothing else, and a quote counts only for the tool it names. The fix gets the same treatment: it must parse, each object must name its `apiVersion`, `kind` and `metadata.name` (so it's clear what it applies to and can be dry-run in M4), and a Secret, a cluster-wide kind or another namespace sends it back rather than reaching a human.
**Consequence:** Grounding failures use the same 2 retries as schema errors. A quote must come from a call made before the submission, so submitting before looking always fails. `Finish.parse` now receives the run's tool records. The cluster-wide list is a fixed set of common kinds, not a lookup against the API.

### 025 — Keep the template's example eval gate until Milestone 3 replaces it with the scenarios
**Why:** Milestone 3 is where the evals are rebuilt around the six scenarios and their recordings. Moving the gate now would mean writing it twice. Keeping the old "stop at the first plain-text answer" behaviour when no finish tool is given lets the calculator cases keep checking the loop, provider and grading plumbing in CI meanwhile.
**Consequence:** `run_agent` has two modes for now. `server.py` and `evals/cases.jsonl` stay until Milestone 3, which removes them along with the plain-text mode if nothing else needs it.

### 024 — Cap runs at 12 investigative tool calls plus one forced submission turn; a run ends only on an accepted `submit_diagnosis`
**Why:** Settles the open question on the step cap: the design said 12 tool calls, the template counted 8 model turns. Counting tool calls rather than turns measures how much the agent looked, whatever it batches per turn. 005 says the agent must submit rather than guess silently at the cap, so the last turn offers only `submit_diagnosis` and asks for confidence below 0.5 if unsure. Ending only on a submission means every run produces something gradeable, and the stop reason (`submitted_at_cap`, `no_submission`) shows when it didn't go well.
**Consequence:** Nudges for plain-text answers (2) and retries for rejected submissions (2) are limited, so every run ends. Confidence at the cap is asked for, not enforced; the stop reason is the flag. The Anthropic adapter now puts a note that follows tool results into the same user turn, since turns must alternate. The cap is a default of `run_agent` for now; step 5 exposes it as a setting.

### 023 — `submit_diagnosis` is an agent-side tool validated against a strict `Diagnosis` schema
**Why:** Submitting a diagnosis doesn't read the cluster, so it doesn't belong on the MCP server, which stays only about looking at Kubernetes. A Pydantic model gives one definition for the tool schema the model sees and the validation of what it sends. Unknown fields are rejected and every error names its field, so the model can correct a bad call. `proposed_fix` may be null only for Unknown, so a confident category always comes with a fix. Evidence must name one of the five MCP tools, which is what lets step 3 check each quote against that tool's real output.
**Consequence:** The schema is inlined (no `$ref`) for portability across model APIs. The limits (1–8 evidence items, quotes up to 500 characters, YAML up to 5,000) are first guesses, to revisit after the hand runs at the end of Milestone 2. The loop that offers this tool and retries rejected submissions is step 2.

### 022 — Record raw API responses per scenario at the reader level and replay them offline
**Why:** Tests and CI must not need a cluster, but they should run on what a real cluster says. Recording the raw responses under the `KubeReader` interface, rather than the tools' text, keeps the full trail of what the API returned and keeps recordings valid when trimming changes: the real tools and `trim.py` run over them on every test. The other option, saving each tool's final text, would go stale with every trimming change. Recording is an action of `triage-seed` because it already seeds, waits and deletes; the reads in between go through the agent's kubeconfig, never the admin context.
**Consequence:** `ReplayReader` lives in `src/` so the M2 offline agent runs and M3 eval gate can use the same recordings. Recordings keep `managedFields` and are tens to hundreds of KB each. They must be re-recorded when a scenario changes, and an agent call the sweep didn't record replays as a "not in this recording" error, so the sweep grows if the agent needs more. Saving refuses token- or key-shaped text.

### 021 — `describe` shows ConfigMap keys but not values, and drops ServiceAccount Secret names
**Why:** ConfigMap values can hold anything, including things that should have been Secrets. The failures here only need to know which keys exist (scenario 4 is a missing key), so the model gets key names and sizes. A ServiceAccount lists the names of its token and pull Secrets; the agent never looks at Secrets, so those go too.
**Consequence:** If a future scenario hinges on a wrong ConfigMap value, this needs revisiting with a new entry; for now a diagnosis that needs a value says so.

### 020 — Fix the namespace when the MCP server starts, and refuse to start under any identity but the agent's ServiceAccount
**Why:** 003 says the caller picks the namespace. Taking it as a startup argument and closing every tool over it means no tool has a namespace parameter, so the model can't ask for another one at all. RBAC (002) only keeps the agent read-only if the server actually runs as the agent's ServiceAccount; with your own kubeconfig it would have admin rights. A SelfSubjectReview at startup turns that mistake into a refusal.
**Consequence:** One server process per namespace; the M2 agent and evals start a server per run. Running the server needs a kubeconfig with a ServiceAccount token (README, "Run the MCP server"); tokens last an hour.

### 019 — MCP tools use the official Kubernetes Python client behind a `KubeReader` interface
**Why:** It returns structured objects, so there's no parsing of `kubectl` output, and `can_i` is one explicit `create_subject_access_review` call rather than a generic `kubectl create -f -` inside a read-only server. Version 37 ships type hints, so mypy checks the calls. A small `KubeReader` protocol keeps the client out of the tools, so unit tests serve fixtures through a fake. The seeder keeps using `kubectl` (015).
**Consequence:** Adds the `kubernetes` package (approved 2026-10-20) and its dependencies. Fixtures are the API's camelCase JSON, the same shape `kubectl get -o json` prints.

### 018 — Bind the read-only role with a ClusterRoleBinding, not a RoleBinding per namespace
**Why:** Every scenario runs in its own namespace (016), so per-namespace RoleBindings would mean seeding creates a binding each time and the agent can't run against a namespace nobody prepared. The tools are still limited to the one namespace the caller passes in (003), and the role is read-only with no Secrets (017).
**Consequence:** The ServiceAccount `triage-system/triage-agent` can read the allowed resources in every namespace, including `kube-system`. Tightening to per-namespace RoleBindings stays an option for M4, when the threat-model scenarios land.

### 017 — RBAC test checks resources against an allowlist, not just verbs
**Why:** Banning write verbs isn't enough: some read verbs are dangerous on subresources (`get pods/exec` can open a shell over WebSockets, `get nodes/proxy` reaches the kubelet API). `tests/test_rbac.py` lists every (apiGroup, resource) the agent may read and fails on anything else, plus wildcards, Secrets, `escalate`/`bind`/`impersonate`, `nonResourceURLs` and `aggregationRule`. It also checks the role grants exactly the allowlist, and runs a set of deliberately bad changes to prove each check fires.
**Consequence:** Any new permission the MCP tools need is a two-line, reviewed change: the ClusterRole and the allowlist. The role reads EndpointSlices rather than the deprecated core Endpoints API, and Roles and RoleBindings so the agent can explain RBAC denials.

### 016 — Scenario format: one namespace per scenario, `expected.yaml` with a wait condition and `also_accept`
**Why:** A namespace per scenario keeps them independent and makes cleanup one `kubectl delete namespace`. Each `expected.yaml` holds the right answer plus how to tell the failure has actually shown (a container waiting or terminated reason, an event, or text in the logs), so seeding waits on the real signal instead of a fixed sleep. Some failures have more than one fair answer (the ServiceAccount or the Deployment using it), so `also_accept` lists the alternatives for grading in M3.
**Consequence:** Scenario 6 keeps running and logs its 403 instead of exiting, so it reads as RBACDenied rather than CrashLoop. `Category` and `ResourceRef` live in `src/triage/models.py` now, ahead of the `Diagnosis` model in M2, so scenarios and diagnoses share one category list.

### 015 — Seeder uses `kubectl` and refuses non-kind contexts
**Why:** Seeding creates and deletes resources, which the agent must never do, so it stays separate from the agent's read-only path and runs with your own kube context. `kubectl apply -f` handles multi-document manifests with no extra code, and the Kubernetes Python client is a separate decision for the M1 tools. Every call passes `--context` explicitly (default `kind-triage`) so a changed default context can't send scenarios to another cluster.
**Consequence:** `triage-seed` exits with an error for any context not starting with `kind-` unless `--allow-any-context` is passed. Unit tests use a fake `Kubectl`; nothing in CI touches a cluster.

### 014 — Scenarios use pinned public images with memory limits and never create Secrets
**Why:** Pinned tags make runs reproducible; memory limits keep a laptop kind cluster healthy (and scenario 3 needs one to fail); no Secrets keeps the "agent never sees Secrets" rule simple to test.
**Consequence:** Images are limited to busybox, nginx and curlimages/curl, checked by `tests/test_scenarios.py` along with namespaces, limits, privileged mode and Secrets.

### 013 — Add PyYAML (runtime) and types-PyYAML (dev)
**Why:** Scenario manifests and `expected.yaml` are YAML. PyYAML was already in the lockfile through pre-commit at the same version; approved 2026-10-20.
**Consequence:** Always `yaml.safe_load`, never `yaml.load`.

### 012 — Defer the comparison-model API key to Milestone 3
**Why:** Nothing before the M3 evals calls a second model, and an unused key is one more thing to secure and pay for.
**Consequence:** M0 is done with only the Anthropic key. The provider adapter already supports OpenAI-compatible APIs, so adding the key later is a config change.

### 011 — Use Claude Haiku as the default model while building
**Why:** Cheapest Claude model; good enough to exercise the loop during M1–M2. Larger models get compared in M3 on accuracy, cost and latency.
**Consequence:** `.env.example` sets `ANTHROPIC_MODEL=claude-haiku-5-5`. The Anthropic account has a monthly spend cap with auto-reload off.

### 010 — Keep the template's example tools and evals until M1/M2 replace them
**Why:** They keep CI green and the eval gate working from day one, so every later change is checked against something.
**Consequence:** The example MCP tools and `evals/cases.jsonl` are placeholders; they are removed as the Kubernetes tools and scenarios land.

### 009 — Start from ai-project-template; rename the package to `triage`
**Why:** The template already has the provider adapter, agent loop, MCP server, eval harness with a CI gate, and run logging, all tested. Reusing it puts the effort into the triage problem.
**Consequence:** Commands are `triage`, `triage-mcp` and `triage-eval`. The template lives in its own private repo for later projects.

### 008 — Apache-2.0 license and an employer disclaimer from the first commit
**Why:** Red Hat's public guidelines allow personal open source work but don't cover unlicensed code, so the license goes in before anything else. The disclaimer makes clear this is a personal project.
**Consequence:** No Red Hat or client code, data or environments; public images and synthetic scenarios only. The repo stays private until it's ready to publish.

### 007 — Develop and evaluate on a local `kind` cluster
**Why:** Free, disposable and identical in CI, so scenarios are reproducible by anyone who clones the repo. Not tied to OpenShift.
**Consequence:** The cluster is `kind-triage`. The homelab is an optional live demo in M4, never presented as production.

### 006 — Quote evidence and check every quote against real tool output
**Why:** A diagnosis is only useful if a human can verify it. Checking quotes against the actual tool output catches made-up evidence, the same grounding idea as the reconciliation pipeline.
**Consequence:** "Evidence grounding" is an eval metric alongside root-cause accuracy.

### 005 — Cap the agent at 12 tool calls; on the cap, submit with low confidence
**Why:** Bounds cost and latency per incident, and forces an answer instead of an open-ended search. Submitting with low confidence is more honest than guessing silently.
**Consequence:** The eval reports how often the cap is hit. See the open question on the template's default of 8.

### 004 — Trim tool output before the model sees it
**Why:** Raw `kubectl` output is long and repetitive (managed fields, full logs). Trimming lowers cost and latency, and the effect is measurable.
**Consequence:** Log line cap (default 100), managed fields dropped from `describe`, long event lists summarized. Trimming could hide a clue; the red-herring scenario in M4 tests that.

### 003 — The caller picks the namespace, never the model
**Why:** Limits the blast radius of a confused or manipulated model to the namespace a human asked about.
**Consequence:** Every tool is scoped to the namespace passed in by the CLI or eval harness.

### 002 — Read-only access enforced by RBAC, not by the prompt
**Why:** Prompts can be ignored or overridden (for example by instructions hidden in logs); the API server can't. A ServiceAccount with `get`, `list` and `watch` only, plus `create` on `subjectaccessreviews` for `can_i`, makes writes impossible.
**Consequence:** No access to Secrets. A test fails CI if the ClusterRole gains a write verb or Secrets access. All cluster output is treated as untrusted data.

### 001 — The agent never changes the cluster; a human applies fixes
**Why:** Triage agents earn trust slowly. Proposing a YAML patch keeps a human in the loop and keeps the project's risk near zero.
**Consequence:** No auto-apply. M4 checks fix validity with a server-side dry run, then applies the patch only in the throwaway eval cluster.
