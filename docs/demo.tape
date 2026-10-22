# Records docs/demo.gif: the triage CLI diagnosing the RBAC scenario from its
# recording, so no cluster is needed (DECISIONS.md 047).
# Needs VHS (https://github.com/charmbracelet/vhs) and ANTHROPIC_API_KEY in .env.
# It makes one real model call with the default model: about $0.002.
# Run from the repo root:  vhs docs/demo.tape
Output docs/demo.gif

Require uv

Set Shell "bash"
Set FontSize 13
Set Width 1200
Set Height 900
Set Padding 16
Set TypingSpeed 40ms

Hide
Type "export PS1='$ ' && uv sync -q && clear"
Enter
Sleep 5s
Show

Type "uv run triage --replay tests/fixtures/scenarios/06-rbac-denied/recording.json"
Sleep 600ms
Enter
Wait+Screen@90s /stopped: /
Sleep 8s
