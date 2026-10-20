# Decisions

A running log of design and project decisions: what was decided, why, and what it rules out. Newest first. When a decision is reversed, add a new entry that names the one it replaces instead of editing the old one.

| # | Date | Decision | Status |
| --- | --- | --- | --- |
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

- **Step cap value.** The template's `MAX_STEPS` defaults to 8; the design says 12 tool calls. Settle in Milestone 2 when the loop is wired to the Kubernetes tools.
- **Comparison model.** Grok (the portfolio plan's original default) or an OpenAI model. Decide in Milestone 3 when the second key is created (012).

---

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
