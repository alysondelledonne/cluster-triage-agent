# Decisions

A running log of design and project decisions: what was decided, why, and what it rules out. Newest first. When a decision is reversed, add a new entry that names the one it replaces instead of editing the old one.

| # | Date | Decision | Status |
| --- | --- | --- | --- |
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
