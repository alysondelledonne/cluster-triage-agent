# Decisions

A running log of design and project decisions: what was decided, why, and what it rules out. Newest first. When a decision is reversed, add a new entry that names the one it replaces instead of editing the old one.

| # | Date | Decision | Status |
| --- | --- | --- | --- |
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

- **Comparison model.** Grok (the portfolio plan's original default) or an OpenAI model. Decide in Milestone 3 when the second key is created (012).

---

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
