# cluster-triage-agent

[![CI](https://github.com/alysondelledonne/cluster-triage-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/alysondelledonne/cluster-triage-agent/actions/workflows/ci.yml)

An AI agent that takes a broken Kubernetes namespace and returns the root cause, the evidence it used, and a proposed YAML fix. It looks at the cluster only through read-only tools on an MCP server, enforced by RBAC, and a human decides whether to apply the fix.

**Status:** Milestone 3 (evals, CI and README) in progress. Five real evals on the recorded scenarios (36 runs each, details in [evals/RESULTS.md](evals/RESULTS.md)); the latest two, with prompt version 2, put Claude Haiku and `grok-4.20-0309-non-reasoning` both at 18/18, at about $0.0022 and $0.025 an incident. CI runs on every push and PR; the kind and live-eval workflows have passed their first runs (DECISIONS 046). Next: the README for a stranger.

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

The server reads one namespace, fixed when it starts, and refuses to start unless it is connected as the agent's ServiceAccount. Give it a kubeconfig that holds a short-lived token for that ServiceAccount and nothing else. [`scripts/agent-kubeconfig.sh`](scripts/agent-kubeconfig.sh) builds one at `~/.kube/triage-agent.yaml`: it copies the cluster from your `kind-triage` context, removes your own credentials from the copy, adds a one-hour token for `triage-system/triage-agent`, and checks the result authenticates as that ServiceAccount. Run it again to renew the token (`--context`, `--output` and `--duration` change the defaults).

```bash
scripts/agent-kubeconfig.sh
uv run triage-mcp --namespace triage-01-crashloop --kubeconfig ~/.kube/triage-agent.yaml
```

The script ends with `wrote …/triage-agent.yaml: system:serviceaccount:triage-system:triage-agent, token valid for 1h`. `triage-mcp` then waits for an MCP client on stdin and stdout; connect it to Claude Desktop or Claude Code as a stdio server with that same command.

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

## Evaluate

`triage-eval` runs every scenario from its recording, grades each run against the scenario's `expected.yaml`, and prints a summary per model (accuracy, first-try evidence grounding, tool calls, latency, cost) and a scenario-by-model grid. The offline gate uses a scripted model and is what CI runs; the real runs call the models and cost money (about $0.04 for 18 Haiku runs, about $0.45 for 18 Grok runs).

```bash
uv run triage-eval --provider fake --gate
uv run triage-eval --provider anthropic --repeats 3 --save
uv run triage-eval --provider anthropic --provider grok --repeats 3 --save
```

`--save` writes every run and the summaries to `evals/results/` and the tables to `evals/results/latest.md`. Grok needs `XAI_API_KEY` and `XAI_MODEL` in `.env` (see `.env.example`).

## CI

Three GitHub Actions workflows (DECISIONS 045). Every action is pinned to a commit, and Dependabot proposes updates weekly.

| workflow | runs | what it does | cost |
| --- | --- | --- | --- |
| [`ci.yml`](.github/workflows/ci.yml) | every push to `main` and every PR | ruff, shellcheck, mypy, pytest, the offline eval gate | free; no secrets, and the tests can't reach the network |
| [`kind.yml`](.github/workflows/kind.yml) | by hand, and Mondays | creates a kind cluster, seeds and records all six scenarios through the agent's ServiceAccount, runs the recording tests and the gate on the fresh recordings, uploads them | free; optionally diagnoses each namespace live with one model (a few cents) |
| [`eval-live.yml`](.github/workflows/eval-live.yml) | by hand only | the real evals on the committed recordings; tables in the run summary, results as an artifact | about $0.50 for both models at 3 repeats |

### Run the evals yourself

1. Fork the repo.
2. In the fork's Settings → Secrets and variables → Actions, add the secrets `ANTHROPIC_API_KEY` and `XAI_API_KEY`, and the variable `XAI_MODEL` (`grok-4.20-0309-non-reasoning` for the results here). `ANTHROPIC_MODEL` is optional and defaults to `claude-haiku-5-5`. Only the providers you run need their key.
3. Actions → **Live eval (manual)** → Run workflow. The defaults (`anthropic grok`, 3 repeats, all scenarios) reproduce the results table below.
4. The run's summary page shows the same tables as `triage-eval`; the `eval-results` artifact holds the results file and every run's trace. The workflow never commits.

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

- [x] `run_evals`: for each scenario and model, seed, triage 3 times, grade, reset (`triage-eval`, replaying the recordings instead of seeding each run: DECISIONS 033)
- [x] Accuracy, evidence grounding, p50/p95 latency, cost per incident and tool calls in a results table
- [x] Claude vs the comparison model; which wins on accuracy, cost and speed
- [x] One change made from the results, with before and after (prompt version 2: Run 3 → Run 4, DECISIONS 043–044)
- [x] GitHub Actions: checks on every PR; a manual workflow that spins up kind and runs the evals (`ci.yml`, `kind.yml`, `eval-live.yml`; first runs 2026-10-22, DECISIONS 045–046)
- [ ] README: results table, runbook, known failure modes, "How I built this with Claude Code"
- [ ] Demo GIF of the CLI diagnosing a scenario

**Done when:** a stranger can clone the repo, follow the README, and reproduce the results table.

Real evals so far, 3 runs per scenario per model, replayed from the recordings ($0.46–0.55 each). Runs 1–3 use prompt version 1, Runs 4 and 5 version 2; Run 5 ran on GitHub Actions through `eval-live.yml`. Run 2 is Run 1 rerun after fixing two flaws in the measuring tools (DECISIONS 038). Run 3 adds the loop and metric fixes (040–042) and is the "before" for prompt version 2; from Run 3 on, first-try grounding leaves out runs that never submitted. Details, per-scenario numbers and every anomaly by run: [evals/RESULTS.md](evals/RESULTS.md).

| run | model | accuracy | first-try grounding | tool calls / run | latency p50 / p95 | cost / incident |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `claude-haiku-5-5` | 18/18 (1.00) | 1.00 | 3.9 | 6.1s / 8.4s | $0.0022 |
| 1 | `grok-4.20-0309-non-reasoning` | 17/18 (0.94) | 0.92 | 5.3 | 5.0s / 15.4s | $0.028 |
| 2 | `claude-haiku-5-5` | 18/18 (1.00) | 1.00 | 4.0 | 6.5s / 9.2s | $0.0023 |
| 2 | `grok-4.20-0309-non-reasoning` | 15/18 (0.83) | 0.83 | 5.4 | 5.5s / 17.0s | $0.028 |
| 3 | `claude-haiku-5-5` | 18/18 (1.00) | 0.99 | 3.8 | 6.1s / 10.3s | $0.0024 |
| 3 | `grok-4.20-0309-non-reasoning` | 17/18 (0.94) | 1.00 | 4.8 | 6.7s / 14.8s | $0.023 |
| 4 | `claude-haiku-5-5` | 18/18 (1.00) | 1.00 | 3.8 | 5.9s / 9.5s | $0.0023 |
| 4 | `grok-4.20-0309-non-reasoning` | 18/18 (1.00) | 0.98 | 4.8 | 6.0s / 16.1s | $0.024 |
| 5 | `claude-haiku-5-5` | 18/18 (1.00) | 1.00 | 3.8 | 5.5s / 6.8s | $0.0022 |
| 5 | `grok-4.20-0309-non-reasoning` | 18/18 (1.00) | 0.97 | 4.9 | 6.1s / 16.1s | $0.026 |

Haiku wins on accuracy, evidence and cost (about 13x cheaper); Grok is faster on simple scenarios but slower on the two hardest. Grok's one miss (scenario 5) had the right fix, but its submissions kept quoting lines joined together that aren't adjacent in the output, so none was accepted. The run also exposed two flaws in the measuring tools, `\n` escapes in grounding and objects missing from the recordings, which are fixed before the before-and-after for prompt version 2 (DECISIONS 037).

Run 2 confirmed the measurement fixes (no unrecorded calls, no quote rejected for escaping; Haiku unchanged). Grok lost two scenario 6 runs in an identical way: given the API's real `not found` for the missing Role, it kept searching until the 12-call cap, then wrote the right diagnosis as plain text on the forced last turn. The loop offers only `submit_diagnosis` there but doesn't require the call, which is a gap in the loop that gets fixed before prompt version 2 (DECISIONS 039). Its scenario 1 miss was the same joined-quote habit as Run 1.

Run 3 had no cap hits and no quoting failures from Grok (first-try grounding 1.0). Its one miss was scenario 1 again, called ConfigError although the prompt defines that as a container that never starts. Haiku stayed at 18/18, with one quote missing a quote mark and two submissions that left out required fields, all corrected on retry.

**The one change: prompt version 2** (Run 3 before, Run 4 after; DECISIONS 043–044). It asks for one-line quotes, never joined or annotated, and draws the line between CrashLoop and ConfigError. Grok's scenario 1 misreading (ConfigError in 2 of 6 runs before) disappeared: 3/3 CrashLoop, in 4 calls instead of 5–6. The quoting rule showed no measurable effect, because Run 3 had no joined quotes left to fix. Both models scored 18/18 after the change. The first real cap hit since the forced-turn fix ended in a correct diagnosis instead of plain text.

| | Haiku before → after | Grok before → after |
| --- | --- | --- |
| accuracy | 18/18 → 18/18 | 17/18 → 18/18 |
| scenario 1 | 3/3 → 3/3 | 2/3 → 3/3 |
| first-try grounding | 0.99 → 1.00 | 1.00 → 0.98 |
| cost per incident | $0.0024 → $0.0023 | $0.023 → $0.024 |

Run 5 repeated Run 4 from the `eval-live.yml` workflow on a GitHub runner: both models 18/18 again. Grok's remaining quote rejections there joined an event's `type`, `reason` and `message` lines into the single line `kubectl get events` would print, which the tool doesn't; noted for after Milestone 3.

### Milestone 4: Make it stronger

- [ ] Fix validity: server-side dry run, then apply in the eval cluster and check the pod becomes Ready
- [ ] Scenarios 7 (NetworkPolicy) and 8 (red herring), plus a log-injection scenario
- [ ] Phoenix tracing and a write-up of one failed run debugged from its trace
- [ ] Optional: read-only run against the homelab cluster
- [ ] Blog post: what broke, what the evals showed, model comparison

## License

Apache-2.0. This is a personal project. It is not affiliated with, endorsed by, or representative of my employer.
