| model | runs | accuracy | category_accuracy | submitted_rate | first_try_grounding | avg_tool_calls | cap_rate | unrecorded_call_rate | latency_p50_s | latency_p95_s | cost_per_incident_usd |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| claude-haiku-5-5 | 18 | 1.0 | 1.0 | 1.0 | 1.0 | 4.0 | 0.0 | 0.0 | 6.53 | 9.21 | 0.00228 |
| grok-4.20-0309-non-reasoning | 18 | 0.833 | 0.833 | 0.833 | 0.833 | 5.44 | 0.0 | 0.0 | 5.51 | 16.98 | 0.02808 |

| scenario | claude-haiku-5-5 | grok-4.20-0309-non-reasoning |
| --- | --- | --- |
| 01-crashloop | 3/3 | 2/3 |
| 02-imagepull | 3/3 | 3/3 |
| 03-oomkilled | 3/3 | 3/3 |
| 04-missing-config | 3/3 | 3/3 |
| 05-failing-probe | 3/3 | 3/3 |
| 06-rbac-denied | 3/3 | 1/3 |
