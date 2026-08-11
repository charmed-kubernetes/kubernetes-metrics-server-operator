import logging

import pytest
import pytest_asyncio
from pathlib import Path
import yaml

from lightkube import Client

log = logging.getLogger(__name__)


@pytest_asyncio.fixture(scope="module")
async def kubernetes():
    client = Client()
    yield client


@pytest.fixture
def metadata():
    metadata = Path("./charmcraft.yaml")
    data = yaml.safe_load(metadata.read_text())
    return data


@pytest.fixture
def application(ops_test, metadata):
    model = ops_test.model
    charm_name = metadata["name"]
    return model.applications[charm_name]


@pytest.fixture
def units(application):
    return application.units
