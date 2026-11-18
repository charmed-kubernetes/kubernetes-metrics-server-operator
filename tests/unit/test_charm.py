# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
#
from pathlib import Path

import pytest
import yaml


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


def test_refresh_applies_new_default_release(lightkube_client):
    """An unpinned deployment re-applies manifests when the release default changes."""
    root = Path(__file__).parents[2]
    previous = yaml.safe_load((root / "charmcraft.yaml").read_text())["config"]
    previous["options"]["release"].pop("default", None)

    # Deploy the previous revision: release unset, manifests applied, hash stored.
    old = Harness(KubernetesMetricsServerOperator, config=yaml.safe_dump(previous))
    old.set_leader(True)
    old.begin()
    old.charm.on.install.emit()
    previous_hash = old.charm.stored.config_hash
    assert previous_hash > 0
    old.cleanup()

    # Refresh to this revision with no config change.
    new = Harness(KubernetesMetricsServerOperator)
    new.set_leader(True)
    new.begin()
    new.charm.stored.config_hash = previous_hash
    lightkube_client.apply.reset_mock()
    new.charm.on.upgrade_charm.emit()

    release = new.model.config["release"]
    version = (root / "upstream" / "metrics-server" / "version").read_text().strip()
    assert release == version, "schema default and version file must match"
    applied = [c.args[0] for c in lightkube_client.apply.call_args_list]
    (deployment,) = [r for r in applied if r.kind == "Deployment"]
    image = deployment.spec.template.spec.containers[0].image
    assert image.endswith(f":{release}")
    assert new.charm.stored.config_hash != previous_hash
    new.cleanup()
