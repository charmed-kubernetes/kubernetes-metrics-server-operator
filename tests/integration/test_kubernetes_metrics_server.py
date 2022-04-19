import logging
from pathlib import Path

import lightkube.generic_resource
from lightkube.resources.core_v1 import Pod
from tenacity import retry, wait_exponential, stop_after_delay, before_log

import pytest

log = logging.getLogger(__name__)


@pytest.mark.abort_on_fail
async def test_charm_builds_and_deploys(ops_test, metadata):
    image = metadata["resources"]["operator-base"]["upstream-source"]
    charm_name = metadata["name"]

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
        lambda: charm_name in ops_test.model.applications, timeout=60
    )

    await ops_test.model.wait_for_idle(status="active")


async def test_charm_status(application, units):
    version = Path("upstream", "version").read_text().strip()
    assert units[0].workload_status == "active"
    assert units[0].workload_status_message == "Ready"
    assert application.status == "active"
    assert application.workload_version == version


async def test_node_metrics(application, kubernetes: lightkube.Client):
    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_delay(120),
        reraise=True,
        before=before_log(log, logging.INFO),
    )
    def wait_for_ready():
        ns = "kube-system"
        labels = {application.name: "true"}
        pods = kubernetes.list(Pod, namespace=ns, labels=labels)
        assert all(cont.ready for pod in pods for cont in pod.status.containerStatuses)

    wait_for_ready()
    NodeMetrics = lightkube.generic_resource.create_global_resource(
        "metrics.k8s.io", "v1beta1", "NodeMetrics", "nodes"
    )
    node_metrics = kubernetes.list(NodeMetrics)
    assert all(each["usage"]["cpu"] for each in node_metrics)
