# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
#
import pytest


from charm import KubernetesMetricsServerOperator
from ops.model import ActiveStatus, MaintenanceStatus
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
    assert harness.model.unit.status == ActiveStatus("Ready")
    lightkube_client.create.assert_called()
