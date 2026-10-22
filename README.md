# cluster-triage-agent

An AI agent that takes a broken Kubernetes namespace and returns the root cause, the evidence it used, and a proposed YAML fix. It looks at the cluster only through read-only tools on an MCP server, enforced by RBAC, and a human decides whether to apply the fix.

**Status:** Milestone 2 done (2026-10-21): `triage` diagnosed all six scenarios correctly with Claude Haiku, for about $0.002 a run (results below). Milestone 3 (evals, CI and README) in progress: evals will replay the recordings (DECISIONS 033) and compare Haiku with `grok-4.20-0309-non-reasoning` (DECISIONS 034); next is moving `triage-eval` onto the scenarios.

- How it works: [ARCHITECTURE.md](ARCHITECTURE.md)
- Why it works that way: [DECISIONS.md](DECISIONS.md)

## Why another triage tool

[k8sgpt](https://github.com/k8sgpt-ai/k8sgpt) and [HolmesGPT](https://github.com/robusta-dev/holmesgpt) already use LLMs to explain cluster problems. This project is narrower and focuses on two things:

- **Read-only by construction.** Every capability is an MCP tool running under a ServiceAccount with `get`, `list` and `watch` only (plus `create` on `subjectaccessreviews`), and a test fails CI if the role ever gains a write verb or Secrets access.
- **Measured.** A suite of seeded failure scenarios on a `kind` cluster scores root-cause accuracy, evidence grounding, latency and cost per incident, comparing two models.

## Quick start

```bash
uv sync
cp .env.example .env            # add an API key and model ID
uv run pytest                   # offline, no API calls
uv run triage-eval --provider fake --gate
kind create cluster --name triage
uv run triage-seed list          # the six failure scenarios
uv run triage-seed check         # seed each one, wait for the failure, clean up
kubectl --context kind-triage apply -f deploy/rbac/   # the agent's read-only ServiceAccount
kubectl --context kind-triage auth can-i --list \
  --as=system:serviceaccount:triage-system:triage-agent   # reads only; no secrets, no writes
```

## Run the MCP server

The server reads one namespace, fixed when it starts, and refuses to start unless it is connected as the agent's ServiceAccount. Give it a kubeconfig that holds a short-lived token for that ServiceAccount and nothing else. The token lasts an hour; run these again to renew it.

```bash
kubectl --context kind-triage config view --minify --raw > ~/.kube/triage-agent.yaml
chmod 600 ~/.kube/triage-agent.yaml
kubectl --kubeconfig ~/.kube/triage-agent.yaml config unset users.kind-triage
kubectl --kubeconfig ~/.kube/triage-agent.yaml config set-credentials triage-agent --token="$(kubectl --context kind-triage -n triage-system create token triage-agent --duration=1h)"
kubectl --kubeconfig ~/.kube/triage-agent.yaml config set-context --current --user=triage-agent
kubectl --kubeconfig ~/.kube/triage-agent.yaml auth whoami
uv run triage-mcp --namespace triage-01-crashloop --kubeconfig ~/.kube/triage-agent.yaml
```

`auth whoami` should print `system:serviceaccount:triage-system:triage-agent`. `triage-mcp` then waits for an MCP client on stdin and stdout; connect it to Claude Desktop or Claude Code as a stdio server with that same command.

### Record the scenarios for offline tests

`triage-seed record` seeds each scenario with your context, waits for the failure plus 15 seconds, reads everything the tools could ask for through the agent's kubeconfig above, saves the raw API responses to `tests/fixtures/scenarios/NN-name/recording.json`, and deletes the scenario. The tests replay these through the real tools. Run it again after changing a scenario.

```bash
uv run triage-seed record
```

## Diagnose a namespace

`triage` runs the agent: the five read-only tools, the triage prompt, and `submit_diagnosis` as the only way to finish. With `--namespace` it reads the live cluster through the agent's kubeconfig above and refuses to run as anyone else. With `--replay` it reads a recording instead, so no cluster is needed. Both call the model, so both cost a little; set `ANTHROPIC_API_KEY` in `.env` first.

```bash
uv run triage-seed apply 1
uv run triage --namespace triage-01-crashloop
uv run triage --replay tests/fixtures/scenarios/06-rbac-denied/recording.json
uv run triage --namespace triage-01-crashloop --alert "api pods keep restarting" --json
```

It prints the category and affected object, the root cause, each evidence quote with the tool it came from, and the proposed fix as YAML, then one line with the run's tool calls, tokens, time and cost. Exit code 0 means a diagnosis was submitted, 1 that the agent didn't submit one, 2 a setup problem. Every run is also appended to `runs/runs.jsonl` with the namespace, prompt version and the full trace.

## Progress

Milestones 1–3 are the MVP. Each milestone ends in something that runs and is committed.

### Milestone 0: Setup — done 2026-10-20

- [x] Policy check, personal Anthropic API key with a monthly spend cap (comparison-model key deferred to M3)
- [x] Repo created from ai-project-template; package renamed to `triage`
- [x] Docker, `kind` and `kubectl` installed; `kind-triage` cluster running (Kubernetes v1.37.0)
- [x] CLAUDE.md with the goal, the read-only rule, "write tests first", and the commands

**Done when:** CI is green on an empty project and `kubectl get nodes` works against kind. ✅

### Milestone 1: Broken cluster and read-only tools — done 2026-10-20

- [x] Scenarios 1–6 as manifests plus `expected.yaml`, each in its own namespace
- [x] Script that applies a scenario, waits until the failure shows, and deletes it afterward (`triage-seed`)
- [x] All six scenarios verified on `kind-triage` with `triage-seed check` (2026-10-20)
- [x] RBAC manifests and a test that fails if the ClusterRole gains a write verb or Secrets access
- [x] MCP server with the five read tools, running under that ServiceAccount
- [x] Output trimming (log line cap, managed fields removed)
- [x] Each tool's real output per scenario recorded into `tests/fixtures/` (`triage-seed record`)
- [x] Server connected to Claude and one scenario triaged by chatting, as a sanity check (scenario 6, Claude desktop app)

**Done when:** all six scenarios seed reliably, every tool has tests, and a scenario can be diagnosed by hand through the MCP server. ✅

### Milestone 2: The agent — done 2026-10-21

- [x] `Diagnosis` Pydantic model and the `submit_diagnosis` tool
- [x] Loop calling tools through the MCP client, with the tool-call cap and a required submission
- [x] System prompt with the triage order (pods, events, logs, config, permissions)
- [x] Every run logged to JSON lines: tool calls, tokens, latency, cost
- [x] CLI: `triage --namespace demo-crashloop` prints a readable report
- [x] Evidence quotes checked against the real tool output
- [x] At least 4 of 6 scenarios right by hand; misses noted

**Done when:** one command diagnoses any scenario and prints root cause, evidence and a proposed fix. ✅

Hand runs, 2026-10-21, `claude-haiku-5-5`, prompt version 1, one run each (scenario 1 live, the rest replayed from recordings):

| Scenario | Diagnosis | Right? | Confidence | Tool calls | Cost |
| --- | --- | --- | --- | --- | --- |
| 01-crashloop | CrashLoop, Deployment/api | ✅ | 0.80 | 4 | $0.0020 |
| 02-imagepull | ImagePull, Deployment/web | ✅ | 0.95 | 3 | $0.0020 |
| 03-oomkilled | OOMKilled, Deployment/worker | ✅ | 0.90 | 3 | $0.0018 |
| 04-missing-config | ConfigError, Deployment/billing | ✅ | 0.93 | 4 | $0.0019 |
| 05-failing-probe | ProbeFailure, Deployment/frontend | ✅ | 0.90 | 4 | $0.0020 |
| 06-rbac-denied | RBACDenied, ServiceAccount/reporter | ✅ | 0.93 | 5 | $0.0027 |

No misses. One run each is not a measurement; Milestone 3 runs each scenario 3 times per model. What the runs did show is in DECISIONS 030: the scenario 1 and 3 fixes can't work as the scenarios are written, and partial-object fixes need a safer way to apply than plain `kubectl apply`.

### Milestone 3: Evals, CI and README — ship and apply

- [ ] `run_evals`: for each scenario and model, seed, triage 3 times, grade, reset
- [ ] Accuracy, evidence grounding, p50/p95 latency, cost per incident and tool calls in a results table
- [ ] Claude vs the comparison model; which wins on accuracy, cost and speed
- [ ] One change made from the results, with before and after
- [ ] GitHub Actions: checks on every PR; a manual workflow that spins up kind and runs the evals
- [ ] README: results table, runbook, known failure modes, "How I built this with Claude Code"
- [ ] Demo GIF of the CLI diagnosing a scenario

**Done when:** a stranger can clone the repo, follow the README, and reproduce the results table.

### Milestone 4: Make it stronger

- [ ] Fix validity: server-side dry run, then apply in the eval cluster and check the pod becomes Ready
- [ ] Scenarios 7 (NetworkPolicy) and 8 (red herring), plus a log-injection scenario
- [ ] Phoenix tracing and a write-up of one failed run debugged from its trace
- [ ] Optional: read-only run against the homelab cluster
- [ ] Blog post: what broke, what the evals showed, model comparison

## License

Apache-2.0. This is a personal project. It is not affiliated with, endorsed by, or representative of my employer.
