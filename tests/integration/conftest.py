import logging

import pytest
import pytest_asyncio
from pathlib import Path
import random
import string
import yaml

from lightkube import KubeConfig, Client
from lightkube.resources.core_v1 import Namespace
from lightkube.models.meta_v1 import ObjectMeta

log = logging.getLogger(__name__)


@pytest_asyncio.fixture(scope="module")
async def kubernetes(charmed_kubernetes, request, module_name):
    rand_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
    namespace = f"{module_name}-{rand_str}"
    config = KubeConfig.from_file(charmed_kubernetes.kubeconfig)
    client = Client(
        config=config.get(context_name="juju-context"),
        namespace=namespace,
        trust_env=False,
    )
    namespace_obj = Namespace(metadata=ObjectMeta(name=namespace))
    client.create(namespace_obj)
    yield client
    client.delete(Namespace, namespace)


@pytest.fixture
def metadata():
    metadata = Path("./metadata.yaml")
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
