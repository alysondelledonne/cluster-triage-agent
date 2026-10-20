# cluster-triage-agent

An AI agent that takes a broken Kubernetes namespace and returns the root cause, the evidence it used, and a proposed YAML fix. It looks at the cluster only through read-only tools on an MCP server, enforced by RBAC, and a human decides whether to apply the fix.

> **Status:** Milestone 0 (setup). The repo is the project template with the package renamed; the Kubernetes tools, scenarios and evals arrive in Milestones 1–3.

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
```

## Planned

- Read-only tools: `list_pods`, `get_events`, `get_logs`, `describe`, `can_i`
- Structured diagnosis: category, affected resource, root cause, quoted evidence, YAML patch, confidence
- Scenarios: CrashLoop, ImagePull, OOMKilled, missing config, failing probe, RBAC denial
- Results table, runbook and known failure modes in this README

## License

Apache-2.0. This is a personal project. It is not affiliated with, endorsed by, or representative of my employer.
