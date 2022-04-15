import base64
from datetime import datetime, timedelta
import logging
from pathlib import Path
from typing import Optional
import pytest
import yaml

log = logging.getLogger(__name__)


@pytest.mark.abort_on_fail
async def test_build_and_deploy_autoscaler_charm(ops_test, metadata):
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


async def test_status_autoscaler_charm(units):
    assert units[0].workload_status == "active"
    assert units[0].workload_status_message == ""
