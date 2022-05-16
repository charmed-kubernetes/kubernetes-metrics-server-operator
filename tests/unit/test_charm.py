# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
#
from pathlib import Path
import pytest


from charm import KubernetesMetricsServerOperator
from ops.model import WaitingStatus, MaintenanceStatus
from ops.testing import Harness


@pytest.fixture(scope="function")
def harness(request):
    harness = Harness(KubernetesMetricsServerOperator)
    harness.begin()
    harness._backend.model_name = request.node.originalname
    yield harness
    harness.cleanup()


def test_metrics_server_after_config_minimal(lightkube_client, harness):
    assert harness.model.unit.status == MaintenanceStatus("")
    harness.update_config({})
    latest_version = Path("upstream", "version").read_text().strip()
    assert harness.model.unit.status == WaitingStatus(
        f"Configuring metrics-server {latest_version}"
    )
    lightkube_client.apply.assert_called()
