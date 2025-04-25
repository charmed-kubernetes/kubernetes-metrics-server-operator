# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
#
import pytest


from charm import KubernetesMetricsServerOperator
from ops.model import MaintenanceStatus
from ops.testing import Harness


@pytest.fixture(scope="function")
def harness(request):
    harness = Harness(KubernetesMetricsServerOperator)
    harness.set_leader(True)
    harness.begin()
    harness._backend.model_name = request.node.originalname
    yield harness
    harness.cleanup()


def test_metrics_server_after_config_minimal(lightkube_client, harness):
    assert harness.model.unit.status == MaintenanceStatus("")
    harness.update_config({})
    assert harness.model.unit.status == MaintenanceStatus(
        "Deploying Kubernetes Metrics Server"
    )
    lightkube_client.apply.assert_called()


def test_metrics_server_after_config_extra_args(harness):
    assert harness.model.unit.status == MaintenanceStatus("")
    harness.update_config({"extra-args": "--testable=1 --metric-resolution=30s"})
    assert harness.model.unit.status == MaintenanceStatus(
        "Deploying Kubernetes Metrics Server"
    )
    for manifests in harness.charm.collector.manifests.values():
        deployment = [r for r in manifests.resources if r.kind == "Deployment"][0]
        args = deployment.resource.spec.template.spec.containers[0].args
        assert "--testable=1" in args, "Should add a new arg"
        assert "--metric-resolution=30s" in args, "Should replace args"
