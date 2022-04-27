# kubernetes-metrics-server-operator

[![Test Suite](https://github.com/charmed-kubernetes/kubernetes-metrics-server-operator/workflows/Test%20Suite/badge.svg)](https://github.com/charmed-kubernetes/kubernetes-metrics-server-operator/actions)

[Metrics Server](https://github.com/kubernetes-sigs/metrics-server) exposes
core Kubernetes metrics via metrics API through a juju deployed charm into a kubernetes cluster model. 

More details can be found in [Core metrics pipeline documentation](https://kubernetes.io/docs/tasks/debug-application-cluster/resource-metrics-pipeline/).

## Metrics Server Charm

* Supports switching between releases of the metrics server based on what the charm 
has been generate with.

```bash
juju config kubernetes-metrics-server release='v0.6.1'
```

* Supports easily changing the image repository to a mirrored registry server
```bash
juju config kubernetes-metrics-server image-registry='rocks.canonical.com:443/cdk'
```

