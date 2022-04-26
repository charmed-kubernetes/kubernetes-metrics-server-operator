from metric_server_manifests import MetricServerManifests
from pathlib import Path
import pytest
from unittest.mock import MagicMock


def test_labeled_objects(request):
    charm = MagicMock()
    charm.model.name = "ns:" + request.node.name
    charm.model.app.name = "app:" + request.node.name
    charm.config = {}
    manifests = MetricServerManifests(charm)
    latest = Path("upstream", "version").read_text().strip()
    original = Path("upstream", "manifests", latest, "components.yaml").read_text()
    modified = manifests.modify(original)
    assert charm.model.app.name not in original
    assert charm.model.app.name in modified, "Expected adjustments with labels"
    assert charm.model.name not in modified, "Unexpected adjustment with namespaces"


@pytest.mark.parametrize(
    "args",
    [
        "--kubelet-insecure-tls",
        "--kubelet-preferred-address-types="
        "InternalIP,Hostname,InternalDNS,ExternalDNS,ExternalIP",
    ],
)
def test_deployment_arguments(request, args):
    charm = MagicMock()
    charm.model.name = "ns:" + request.node.name
    charm.model.app.name = "app:" + request.node.name
    charm.config = {"extra-args": args}
    manifests = MetricServerManifests(charm)
    latest = Path("upstream", "version").read_text().strip()
    original = Path("upstream", "manifests", latest, "components.yaml").read_text()
    modified = manifests.modify(original)
    assert args not in original
    assert args in modified


@pytest.mark.parametrize("registry", ["my.server", "my.server:443/library"])
def test_deployment_registry(request, registry):
    charm = MagicMock()
    charm.model.name = "ns:" + request.node.name
    charm.model.app.name = "app:" + request.node.name
    charm.config = {"registry-server": registry}
    manifests = MetricServerManifests(charm)
    latest = Path("upstream", "version").read_text().strip()
    original = Path("upstream", "manifests", latest, "components.yaml").read_text()
    modified = manifests.modify(original)
    assert registry not in original
    assert registry in modified
