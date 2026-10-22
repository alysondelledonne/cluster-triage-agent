# Eval results

Every real eval run, newest first: what was run, the numbers, and what each
anomaly turned out to be. The raw rows for each run are in `evals/results/`;
the per-run traces (every tool call and submission) are in the run log
(`runs/runs.jsonl`, git-ignored), found by run ID.

How to read the metrics: see ARCHITECTURE.md, "Evals". How to rerun:

```bash
uv run triage-eval --provider anthropic --provider grok --repeats 3 --save
```

---

## Run 1: 2026-10-21, prompt version 1

**Setup**

| | |
| --- | --- |
| When | 2026-10-21 20:55–21:02 PT (2026-10-22 03:55 UTC) |
| Code | commit `0c533fe` (scenario evals, DECISIONS 036) |
| Prompt | version 1 (DECISIONS 027) |
| Cluster data | the six recordings in `tests/fixtures/scenarios/`, replayed (DECISIONS 033); scenarios 1 and 3 re-recorded on 2026-10-21 after DECISIONS 031–032 |
| Models | `claude-haiku-5-5` ($0.10 / $0.50 per million tokens in / out) and `grok-4.20-0309-non-reasoning` ($1.25 / $2.50) (DECISIONS 034) |
| Runs | 3 per scenario per model, 36 in total, one at a time |
| Results file | `evals/results/20261022T035920Z-claude-haiku-5-5+grok-4.20-0309-non-reasoning.json` |
| Total cost | $0.55: Haiku $0.04 (298K tokens in, 20K out), Grok $0.51 (386K in, 10K out) |

**Summary**

| model | runs | accuracy | category_accuracy | submitted_rate | first_try_grounding | avg_tool_calls | cap_rate | unrecorded_call_rate | latency_p50_s | latency_p95_s | cost_per_incident_usd |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| claude-haiku-5-5 | 18 | 1.0 | 1.0 | 1.0 | 1.0 | 3.89 | 0.0 | 0.0 | 6.08 | 8.44 | 0.00222 |
| grok-4.20-0309-non-reasoning | 18 | 0.944 | 0.944 | 0.944 | 0.917 | 5.33 | 0.056 | 0.062 | 5.0 | 15.43 | 0.02816 |

**Per scenario** (correct runs; tool calls, latency and confidence for each of the three runs; mean cost per run)

| scenario | Haiku correct | Haiku tool calls | Haiku latency (s) | Haiku cost | Grok correct | Grok tool calls | Grok latency (s) | Grok cost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 01-crashloop | 3/3 | 5, 5, 5 | 7.9, 7.6, 10.2 | $0.0027 | 3/3 | 10, 9, 8 | 16.7, 10.5, 15.4 | $0.0542 |
| 02-imagepull | 3/3 | 3, 3, 3 | 6.1, 5.6, 5.2 | $0.0020 | 3/3 | 3, 3, 3 | 3.9, 4.6, 4.3 | $0.0152 |
| 03-oomkilled | 3/3 | 4, 3, 3 | 6.4, 8.4, 5.6 | $0.0023 | 3/3 | 3, 3, 3 | 4.2, 5.5, 3.9 | $0.0145 |
| 04-missing-config | 3/3 | 4, 4, 4 | 6.5, 5.8, 5.5 | $0.0019 | 3/3 | 4, 4, 4 | 5.2, 4.7, 5.0 | $0.0184 |
| 05-failing-probe | 3/3 | 3, 3, 3 | 5.7, 5.4, 4.9 | $0.0019 | **2/3** | 3, 5, 3 | 5.0, 10.5, 4.0 | $0.0232 |
| 06-rbac-denied | 3/3 | 5, 5, 5 | 6.6, 7.1, 7.4 | $0.0027 | 3/3 | 9, 7, 12 | 10.7, 5.7, 10.9 | $0.0434 |

Confidence: Haiku 0.85–0.95 on every run. Grok 0.90–0.95 on every run that submitted, including the ones that needed corrections.

**Which wins**

- **Accuracy:** Haiku, 18/18 against 17/18. Grok's miss was not a wrong diagnosis (below).
- **Evidence:** Haiku. Every first submission quoted real output. Grok's first submissions in three runs contained quotes that weren't in the output.
- **Cost:** Haiku, by about 13x per incident ($0.0022 against $0.028). Grok's input price is 12.5x Haiku's, and it also read more on the two hardest scenarios.
- **Speed:** mixed. Grok is faster on simple scenarios (p50 5.0s against 6.1s) but much slower on scenarios 1 and 6, where it made 8–12 tool calls (p95 15.4s against 8.4s).
- **Effort:** Haiku is steady (3–5 calls on every scenario). Grok matches it on scenarios 2–4 but explores far more on 1 and 6, and hit the 12-call cap once.

**Every anomaly, by run**

| run ID | model | scenario | what happened | verdict |
| --- | --- | --- | --- | --- |
| `f740db3c3d7d` | Grok | 05 | Right fix (readiness probe to port 80) but **no diagnosis**: three submissions rejected, all naming ProbeFailure on Deployment/frontend at confidence 0.95. First, one quote was 622 characters, over the 500 limit. Then twice the same `list_pods` quote, which joins lines that aren't next to each other: `ready: 0/1` + `failing_conditions:` + `- 'ContainersReady: ContainersNotReady containers with unready status: [frontend]'`. Each line exists, but not together. Grok resent it unchanged after being told it wasn't found. | Correct rejections; model didn't act on the feedback |
| `369e87b3bb3e` | Grok | 01 | One nudge, one rejection, then accepted. Rejected quotes: `state: 'terminated: Error, exit code 1'` (the real line continues `, finished 2026-…'`; Grok cut it and added a closing quote mark), and the scenario's script quoted with real line breaks where `describe` shows it as one YAML string with `\n` escapes. | First: correct rejection. Second: **the checker's fault** (same text, different escaping) |
| `d281ac41e772` | Grok | 01 | One nudge, one rejection, then accepted. Rejected quotes had notes added inside them: `... finished 2026-10-21T23:10:34+00:00' (repeated for restarts: 2)` and `args: - "...exec sleep 2147483647\n" (no env section)`. | Correct rejections |
| `cac338c87692` | Grok | 01 | Asked to describe ConfigMap `api` and ServiceAccount `default`; replay answered "not in this recording" (2 of 9 calls). | **Replay gap**: on a real cluster the ConfigMap would be "not found" and `default` exists |
| `6a160c52ffdf` | Grok | 06 | One nudge. Asked to describe Role `reporter` and RoleBinding `reporter`; replay answered "not in this recording" (2 of 9 calls). | **Replay gap**: a real cluster says "not found", which is itself evidence for RBACDenied |
| `2d65a137e741` | Grok | 06 | Same two unrecorded calls; used all 12 tool calls and submitted on the forced last turn (right answer, confidence 0.90). | Replay gap, and the cap working as designed |
| `5907d32dcaad` | Haiku | 03 | One rejection: an evidence item carried an extra `reason` field. Corrected on the next submission. | Schema working as designed |

**What this says**

1. **Both models diagnose all six failures.** Every submission named the right category and object; the only miss was a run that never got a submission accepted.
2. **Grok's evidence habits are the weak point.** It joins lines, trims them or annotates them, which grounding (DECISIONS 026) catches and rejects. Twice that cost extra turns, and once it lost the run because Grok repeated the same quote. The rejection message ("copy it exactly from a tool result") wasn't enough to change its behaviour.
3. **The measuring tools have two flaws, both mine.** Grounding treats `\"` as `"` but not `\n` as a line break, so one real quote was rejected. Replay can't answer a `describe` for an object the recorder didn't read: on a real cluster those calls get "not found" (or, for `default`, the object), while replay gets "not in this recording", which also tells the model it's in an eval.
4. **Cost is the clearest difference.** At about 13x the cost per incident and no accuracy advantage, Grok isn't the better choice for this agent at these prices.

**Caveats:** 3 runs per scenario is small; one run more or less changes Grok's accuracy by 5.6 points. All runs used replayed recordings, so the cluster's output was identical every time. Latency includes network time to each provider from one laptop.

**What changes next** (DECISIONS 037): fix the two measurement flaws (unescape `\n` and `\t` in grounding; record the namespace's full inventory so replay answers unknown objects with the API's own "not found"), re-record, rerun as the "before". Then make one change, prompt version 2 (quote one line or part of a line exactly; never join lines or add notes; a rejection message that says so), and rerun as the "after".
