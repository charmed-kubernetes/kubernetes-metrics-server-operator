import logging
from pathlib import Path
import lightkube.generic_resource
import pytest

log = logging.getLogger(__name__)


@pytest.fixture()
def update_status_timeout():
    return 60 * 5 + 30  # 5m 30s


@pytest.mark.abort_on_fail
async def test_charm_builds_and_deploys(ops_test, metadata, update_status_timeout):
    image = metadata["resources"]["operator-base"]["upstream-source"]
    charm_name = metadata["name"]

    # Speed up the tests
    await ops_test.model.set_config({"update-status-hook-interval": "2m"})

    charm = next(Path(".").glob(f"{charm_name}*.charm"), None)
    if not charm:
        log.info("Build Charm...")
        charm = await ops_test.build_charm(".")

    await ops_test.model.deploy(
        entity_url=charm.resolve(),
        trust=True,
        resources={"operator-base": image},
    )

    await ops_test.model.block_until(
        lambda: charm_name in ops_test.model.applications, timeout=update_status_timeout
    )
    await ops_test.model.wait_for_idle(status="active", timeout=update_status_timeout)


async def test_adjust_version(application, ops_test, update_status_timeout):
    await application.set_config(dict(release="v0.6.0"))
    await ops_test.model.wait_for_idle(status="active", timeout=update_status_timeout)
    await application.reset_config(["release"])
    await ops_test.model.wait_for_idle(status="active", timeout=update_status_timeout)


async def test_charm_status(application, units):
    latest_version = Path("upstream", "version").read_text().strip()
    assert units[0].workload_status == "active"
    assert units[0].workload_status_message == "Ready"
    assert application.status == "active"
    assert application.workload_version == latest_version


async def test_node_metrics(application, kubernetes):
    NodeMetrics = lightkube.generic_resource.create_global_resource(
        "metrics.k8s.io", "v1beta1", "NodeMetrics", "nodes"
    )
    node_metrics = kubernetes.list(NodeMetrics)
    assert all(each["usage"]["cpu"] for each in node_metrics)
