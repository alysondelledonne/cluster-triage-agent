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

## Run 3: 2026-10-22, prompt version 1, after the loop and metric fixes

The "before" for prompt version 2 (DECISIONS 040). Same models, prompt, recordings and 3 runs per scenario as Run 2. What changed since Run 2: the forced last turn requires the `submit_diagnosis` call (040), `cap_rate` counts every run that used all 12 calls and `first_try_grounding` leaves out runs with no submission (040), and a blank fix counts as no fix (041).

**Setup**

| | |
| --- | --- |
| When | 2026-10-22 10:17–10:22 PT (17:22 UTC) |
| Code | commit `b259251` (DECISIONS 041) |
| Prompt | version 1 (DECISIONS 027), unchanged |
| Cluster data | the six recordings from 038, unchanged since Run 2 |
| Models | `claude-haiku-5-5` and `grok-4.20-0309-non-reasoning`, prices as in Run 1 |
| Runs | 3 per scenario per model, 36 in total, one at a time |
| Results file | `evals/results/20261022T172216Z-claude-haiku-5-5+grok-4.20-0309-non-reasoning.json` |
| Total cost | $0.46: Haiku $0.04 (311K tokens in, 23K out), Grok $0.41 (317K in, 7K out) |

**Summary**

| model | runs | accuracy | category_accuracy | submitted_rate | first_try_grounding | avg_tool_calls | cap_rate | unrecorded_call_rate | latency_p50_s | latency_p95_s | cost_per_incident_usd |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| claude-haiku-5-5 | 18 | 1.0 | 1.0 | 1.0 | 0.988 | 3.78 | 0.0 | 0.0 | 6.07 | 10.3 | 0.00236 |
| grok-4.20-0309-non-reasoning | 18 | 0.944 | 0.944 | 1.0 | 1.0 | 4.83 | 0.0 | 0.0 | 6.74 | 14.79 | 0.02298 |

Haiku's saved `first_try_grounding` (0.988) leaves out one run by mistake: `b5a9e8e8cb69` sent `proposed_fix` as a JSON string, which `submit_diagnosis` decodes and accepted, but the evals' re-check didn't decode it and found no attempt to score. Fixed in DECISIONS 042; with that run counted (its first try was fully grounded), Haiku's figure is 0.989. Grok's figure is unaffected.

**Per scenario** (correct runs; tool calls, latency and confidence for each of the three runs; mean cost per run)

| scenario | Haiku correct | Haiku tool calls | Haiku latency (s) | Haiku cost | Grok correct | Grok tool calls | Grok latency (s) | Grok cost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 01-crashloop | 3/3 | 4, 5, 5 | 14.8, 6.4, 7.5 | $0.0033 | **2/3** | 6, 5, 5 | 11.6, 10.3, 11.4 | $0.0250 |
| 02-imagepull | 3/3 | 3, 3, 3 | 5.6, 5.5, 5.8 | $0.0019 | 3/3 | 3, 3, 3 | 6.1, 6.4, 5.9 | $0.0152 |
| 03-oomkilled | 3/3 | 3, 3, 3 | 10.3, 5.7, 9.2 | $0.0026 | 3/3 | 3, 4, 3 | 5.3, 5.8, 7.5 | $0.0159 |
| 04-missing-config | 3/3 | 4, 4, 4 | 6.1, 6.0, 5.2 | $0.0019 | 3/3 | 4, 4, 4 | 6.5, 11.0, 8.1 | $0.0172 |
| 05-failing-probe | 3/3 | 3, 4, 3 | 6.0, 6.4, 5.8 | $0.0019 | 3/3 | 3, 3, 3 | 5.7, 5.7, 6.7 | $0.0145 |
| 06-rbac-denied | 3/3 | 5, 4, 5 | 7.2, 6.3, 6.8 | $0.0026 | 3/3 | 11, 11, 9 | 14.8, 18.2, 13.4 | $0.0502 |

Confidence: Haiku 0.80–0.95, Grok 0.90–0.95 on every run.

**Every anomaly, by run**

| run ID | model | scenario | what happened | verdict |
| --- | --- | --- | --- | --- |
| `a06fee764eb3` | Grok | 01 | **Wrong category**: ConfigError on Deployment/api, confidence 0.95, accepted first time. The evidence and fix (set `LISTEN_PORT`) were right. The prompt defines ConfigError as a container that never starts (CreateContainerConfigError or a missing ConfigMap, key or volume); here it starts, prints `fatal: required setting LISTEN_PORT is missing` and exits 1, which is CrashLoop. Run 2's `bf8a33de6964` made the same call. | A real misclassification against the prompt's own definitions |
| `5b896ee50087` | Grok | 06 | Right answer after 11 calls and one nudge. Got `not found` for Role and RoleBinding `reporter`, looked at events for those kinds, then guessed a Role name (`configmap-reader`, also `not found`) before submitting. | Correct, but explored well past what it needed, as in Run 2 |
| `13c26bf9365c` | Haiku | 03 | One grounding rejection, then accepted: a `describe` quote of the container's script dropped the closing `"` after `loading cache into memory`. Haiku's first ungrounded quote in three runs. | Correct rejection |
| `b4431258895e` | Haiku | 01 | Two schema rejections (first `proposed_fix` and `confidence` missing, then `confidence` missing), then accepted. It read only `previous=true` logs, which in this recording say `unable to retrieve container logs for containerd://…`, and said so in its root cause. | Schema working as designed. The log text is what the kubelet returned when the scenario was recorded, so replay is faithful |
| `f956d9b18f35` | Haiku | 03 | One schema rejection (`proposed_fix` and `confidence` missing), then accepted. | Schema working as designed |
| `b5a9e8e8cb69` | Haiku | 01 | Accepted first time with `proposed_fix` sent as a JSON string, which `submit_diagnosis` decodes. The evals' re-check didn't, so the run got no `first_try_grounding`. | **A measurement bug**, fixed in DECISIONS 042 |

**What this says**

1. **The forced turn wasn't needed this time.** No run hit the cap (`cap_rate` 0.0 under its corrected definition), so the `tool_choice` fix from 040 didn't come into play; Grok's scenario 6 runs ended on their own after 9–11 calls. Its recovery from 1/3 to 3/3 there is variance, not the fix. The smoke test before this run is what showed the fix works.
2. **Grok quoted cleanly.** First-try grounding 1.0, against 0.92 and 0.94 (on comparable terms) in Runs 1 and 2. Over the three runs, 5 of Grok's 54 runs had an ungrounded first try, all from joining, trimming or annotating lines; in Run 3, none. Haiku had its first, a dropped quote mark.
3. **Scenario 1's CrashLoop/ConfigError boundary is now Grok's only miss, twice in two runs.** The prompt's definitions already put this case in CrashLoop, and Grok picked ConfigError anyway.
4. **Haiku leaves out required fields.** 2 of 18 runs (and 2 in Run 2) sent a submission without `confidence` or `proposed_fix`. The schema catches it and the retry costs one turn; it never cost a diagnosis.
5. **Cost and the choice of model are unchanged.** Haiku: 18/18 at $0.0024 an incident. Grok: 17/18 at $0.023, about 10x more; cheaper than before because it made fewer calls.

**Caveats:** 3 runs per scenario. Grok's 15/18 in Run 2 and 17/18 here differ by two runs, with no change that touched how it diagnoses, which is a fair picture of the run-to-run noise at this size.

**What changes next** (DECISIONS 042): fix the re-check's decoding. Prompt version 2 is proposed there and waiting for approval.

---

## Run 2: 2026-10-21, prompt version 1, after the measurement fixes

The "before" for prompt version 2, rerun after DECISIONS 038 fixed grounding of `\n` escapes and gave replay the namespace's full inventory. Same models, same prompt, same 3 runs per scenario.

**Setup**

| | |
| --- | --- |
| When | 2026-10-21 21:38–21:43 PT (2026-10-22 04:43 UTC) |
| Code | commit `a61b8de` (DECISIONS 038) |
| Prompt | version 1 (DECISIONS 027), unchanged |
| Cluster data | all six scenarios re-recorded on 2026-10-21 with the full namespace inventory (038), replayed |
| Models | `claude-haiku-5-5` and `grok-4.20-0309-non-reasoning`, prices as in Run 1 |
| Runs | 3 per scenario per model, 36 in total, one at a time |
| Results file | `evals/results/20261022T044311Z-claude-haiku-5-5+grok-4.20-0309-non-reasoning.json` |
| Total cost | $0.55: Haiku $0.04 (304K tokens in, 21K out), Grok $0.51 (386K in, 9K out) |

**Summary**

| model | runs | accuracy | category_accuracy | submitted_rate | first_try_grounding | avg_tool_calls | cap_rate | unrecorded_call_rate | latency_p50_s | latency_p95_s | cost_per_incident_usd |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| claude-haiku-5-5 | 18 | 1.0 | 1.0 | 1.0 | 1.0 | 4.0 | 0.0 | 0.0 | 6.53 | 9.21 | 0.00228 |
| grok-4.20-0309-non-reasoning | 18 | 0.833 | 0.833 | 0.833 | 0.833 | 5.44 | 0.0 | 0.0 | 5.51 | 16.98 | 0.02808 |

Against Run 1: Haiku is unchanged within noise (18/18 both times, 4.0 calls against 3.9, $0.0023 against $0.0022). Grok fell from 17/18 to 15/18. `unrecorded_call_rate` is 0 for both models, so the replay fix worked: every call got the answer a real cluster would give.

**Per scenario** (correct runs; tool calls, latency and confidence for each of the three runs; mean cost per run)

| scenario | Haiku correct | Haiku tool calls | Haiku latency (s) | Haiku cost | Grok correct | Grok tool calls | Grok latency (s) | Grok cost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 01-crashloop | 3/3 | 5, 5, 5 | 8.1, 7.7, 8.2 | $0.0027 | **2/3** | 11, 7, 5 | 19.8, 17.0, 9.5 | $0.0491 |
| 02-imagepull | 3/3 | 3, 3, 3 | 5.8, 5.2, 5.7 | $0.0019 | 3/3 | 3, 3, 3 | 5.6, 5.5, 7.1 | $0.0152 |
| 03-oomkilled | 3/3 | 4, 3, 3 | 9.9, 9.2, 5.8 | $0.0026 | 3/3 | 4, 3, 3 | 5.5, 4.3, 4.1 | $0.0160 |
| 04-missing-config | 3/3 | 4, 4, 4 | 8.0, 6.6, 5.6 | $0.0019 | 3/3 | 4, 4, 4 | 4.8, 4.8, 5.9 | $0.0157 |
| 05-failing-probe | 3/3 | 4, 4, 3 | 5.2, 5.9, 5.0 | $0.0019 | 3/3 | 3, 3, 3 | 3.9, 4.2, 4.0 | $0.0145 |
| 06-rbac-denied | 3/3 | 5, 5, 5 | 6.5, 6.8, 6.9 | $0.0026 | **1/3** | 11, 12, 12 | 14.3, 14.0, 13.9 | $0.0580 |

Confidence: Haiku 0.85–0.95 on every run. Grok 0.90–0.95 on every run that submitted.

**Every anomaly, by run**

| run ID | model | scenario | what happened | verdict |
| --- | --- | --- | --- | --- |
| `ff4411967fd0` | Grok | 06 | **No diagnosis.** Read logs, the Deployment and ServiceAccount, ran `can_i` (allowed: false), then asked for Role and RoleBinding `reporter` and got the API's `not found`. Then spent its last four calls on `get_events` for kinds Role, RoleBinding, ClusterRole and ClusterRoleBinding, reaching the 12-call cap. On the forced last turn, where `submit_diagnosis` is the only tool offered, it wrote the right diagnosis (RBACDenied, missing Role/RoleBinding) as plain text instead of calling the tool. | **A gap in the agent loop:** the forced turn offers only the finish tool but doesn't require a tool call, so a model can still answer in text |
| `b6399304a283` | Grok | 06 | Identical path, the same 12 calls in the same order, the same plain-text answer on the forced turn. | Same gap |
| `79bd8223680f` | Grok | 06 | Same path to the two `not found`s, then two `get_events` and a second `list_pods` (11 calls), one nudge, then submitted. Right answer, confidence 0.95. | Correct, but explored far past what it needed |
| `bf8a33de6964` | Grok | 01 | **No diagnosis.** Three submissions rejected, so the run ended. All three named **ConfigError** on Deployment/api, not CrashLoop, so even an accepted one would have been graded wrong. Rejected quotes: `Warning Back-off restarting failed container ...` (the event's `type: Warning` field joined to its `message`, which are separate lines), then the same joined quote twice more with the full message. Also, on the first attempt, the container's `args` rewritten in flow style (`args: ["echo ..."]`) where `describe` shows a block list. | Correct rejections; the same joined-quote habit as Run 1's scenario 5 miss |
| `6ca572090b46` | Grok | 01 | One rejection, then accepted. Rejected quotes: `state: 'terminated: Error, exit code 1', restarts: 2, ready: 0/1` (three separate `list_pods` fields stitched into one line, the first one trimmed) and the `args` again in flow style with a note appended (`, command: [sh, -c], no env section`). | Correct rejections |
| `9246c6bc9baa` | Haiku | 03 | One rejection: an evidence item carried an extra `reason` field (as in Run 1's `5907d32dcaad`). Corrected on the next submission. | Schema working as designed |
| `ea579f0a2c1d` | Haiku | 03 | One rejection: `confidence` missing. Corrected on the next submission. | Schema working as designed |

No grounding rejection in this run was a false negative: every rejected quote was checked against the tool output in the trace.

**What this says**

1. **The measurement fixes did what they were for.** No unrecorded calls, and no quote rejected for escaping. Haiku's results barely moved, which is what a fix to the measuring tools should look like for a model that wasn't affected.
2. **A realistic "not found" made scenario 6 harder for Grok, and exposed a gap in the loop.** In Run 1 replay answered "not in this recording" for the Role and RoleBinding, and two of Grok's three runs submitted after 7 and 9 calls. Now it gets the API's `not found`, which is real evidence for RBACDenied, but it keeps searching, including events for cluster-wide kinds, until the cap. Twice it then answered in plain text on the forced turn. The loop offers only `submit_diagnosis` on that turn but doesn't tell the API that a tool call is required (`tool_choice`), so the model can still decline. Both APIs document a way to require one (Anthropic's `tool_choice` of type `tool`; xAI's OpenAI-compatible `tool_choice` naming a function, or `"required"`). This is a gap in my loop, not only in the model.
3. **Grok's quoting habit is unchanged.** Joining separate fields or lines into one quote, rewriting YAML in another style, and appending notes caused both scenario 1 problems, as in Run 1. This is what prompt version 2 is aimed at.
4. **Two metrics undercount.** `cap_rate` counts only runs that *submitted* at the cap, so it reads 0.0 although two Grok runs hit it. `first_try_grounding` scores a run with no submission at all as 0, which mixes "never submitted" into an evidence metric: of the 16 Grok runs that submitted something, first tries averaged 0.94 grounded.
5. **Cost and the choice of model are unchanged.** Haiku: 18/18 at $0.0023 an incident. Grok: 15/18 at $0.028, about 12x more.

**Caveats:** 3 runs per scenario is still small; Grok's drop from 17/18 to 15/18 is two runs, and both scenario 6 failures followed an identical path, so they are less independent than they look. Scenario 1's grading accepts only CrashLoop; `bf8a33de6964` argued ConfigError (the crash is caused by a missing setting), which is defensible but would have been graded wrong; whether to accept it is an open question in DECISIONS.md, not changed here.

**What changes next** (DECISIONS 039, built in 040): fix the loop so the forced turn requires the `submit_diagnosis` call, and fix the two metrics, before prompt version 2, so the before-and-after measures the prompt and not the loop. From Run 3 on, `cap_rate` counts every run that used all 12 calls and `first_try_grounding` averages only runs that submitted something; the Run 1 and Run 2 numbers above use the old definitions.

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
