#!/usr/bin/env bash
# Build the kubeconfig the agent uses: the cluster from your context, a short-lived
# token for the agent's ServiceAccount, and none of your own credentials.
# Used by the README, the kind workflow (.github/workflows/kind.yml) and anyone
# cloning the repo (DECISIONS.md 045). Run it again to renew the token.
#
#   scripts/agent-kubeconfig.sh [--context kind-triage] [--output ~/.kube/triage-agent.yaml] [--duration 1h]
set -euo pipefail

context="kind-triage"
output="${HOME}/.kube/triage-agent.yaml"
duration="1h"
expected="system:serviceaccount:triage-system:triage-agent"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --context) context="$2"; shift 2 ;;
    --output) output="$2"; shift 2 ;;
    --duration) duration="$2"; shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

mkdir -p "$(dirname "$output")"
# The file holds a token, so only its owner may read it, from the moment it exists.
umask 077
kubectl --context "$context" config view --minify --raw > "$output"
chmod 600 "$output"

# Drop your own user (on kind, an admin client certificate) from the copy.
admin_user="$(kubectl --kubeconfig "$output" config view --minify -o 'jsonpath={.contexts[0].context.user}')"
kubectl --kubeconfig "$output" config unset "users.${admin_user}" > /dev/null

token="$(kubectl --context "$context" -n triage-system create token triage-agent --duration="$duration")"
kubectl --kubeconfig "$output" config set-credentials triage-agent --token="$token" > /dev/null
kubectl --kubeconfig "$output" config set-context --current --user=triage-agent > /dev/null

who="$(kubectl --kubeconfig "$output" auth whoami -o 'jsonpath={.status.userInfo.username}')"
if [[ "$who" != "$expected" ]]; then
  echo "error: $output authenticates as '$who', not $expected" >&2
  exit 1
fi
echo "wrote $output: $who, token valid for $duration"
