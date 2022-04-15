import logging
import os

import pytest
import pytest_asyncio
from _pytest.config.argparsing import Parser
import random
import string
from pathlib import Path
from types import SimpleNamespace
import yaml

from lightkube import KubeConfig, Client, codecs
from lightkube.resources.core_v1 import Namespace
from lightkube.models.meta_v1 import ObjectMeta
from lightkube.resources.apps_v1 import Deployment
from lightkube.models.autoscaling_v1 import ScaleSpec

log = logging.getLogger(__name__)


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

