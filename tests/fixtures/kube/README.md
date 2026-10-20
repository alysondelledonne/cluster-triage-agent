# Kubernetes fixtures

Hand-written payloads in the shape the Kubernetes API returns (camelCase, as
`kubectl get -o json` prints), modeled on the seeded scenarios. The offline tool
tests in `tests/test_kube_tools.py` serve these through a fake reader instead of
a cluster.

They include the noise real objects carry (`managedFields`, the
`last-applied-configuration` annotation, `resourceVersion`, `uid`) so the tests
prove trimming removes it.

The Milestone 1 item "record each tool's real output per scenario" adds captured
output next to these.
