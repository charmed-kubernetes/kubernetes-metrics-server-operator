import logging

from collections import defaultdict, namedtuple
from functools import cached_property
from itertools import islice
from pathlib import Path
from typing import Dict, Mapping, Optional, Set, Union

import yaml
from jinja2 import Template
from lightkube import Client, codecs
from lightkube.core.client import NamespacedResource, GlobalResource
from lightkube.core.exceptions import ApiError

log = logging.getLogger(__file__)
AnyResource = Union[NamespacedResource, GlobalResource]


class NamespaceKind(namedtuple("NamespaceKind", "kind, namespace")):
    def __str__(self):
        if self.namespace:
            return "/".join(self)
        return self.kind


class HashableResource:
    def __init__(self, rsc):
        self.rsc = rsc

    def uniq(self):
        kind = type(self.rsc).__name__
        ns = self.metadata.namespace
        name = self.metadata.name
        return kind, ns, name

    def __str__(self):
        return "/".join(filter(None, self.uniq()))

    def __hash__(self):
        return hash(self.uniq())

    def __eq__(self, other):
        return other.uniq() == self.uniq()

    def __getattr__(self, item):
        return getattr(self.rsc, item)


class Manifests:
    def __init__(self, charm, *components: str):
        self.namespace = charm.model.name
        self.application = charm.model.app.name
        self.components = components
        self.client = Client(namespace=self.namespace, field_manager=self.application)

    @property
    def version(self) -> str:
        return Path("upstream", "version").read_text(encoding="utf-8").strip()

    @cached_property
    def resources(self) -> Mapping[NamespaceKind, Set[HashableResource]]:
        """All component resource sets subdivided by kind and namespace."""
        result: Mapping[NamespaceKind, Set[HashableResource]] = defaultdict(set)
        for component in self.components:
            for manifest in Path("upstream", "manifests", component).glob("*.yaml"):
                for obj in codecs.load_all_yaml(manifest.read_text()):
                    kind_ns = NamespaceKind(obj.kind, obj.metadata.namespace)
                    result[kind_ns].add(HashableResource(obj))
        return result

    def status(self) -> Set[HashableResource]:
        """Returns all objects which have a `.status.conditions` attribute."""
        objects = (
            self.client.get(
                type(obj.rsc),
                obj.metadata.name,
                namespace=obj.metadata.namespace,
            )
            for resources in self.resources.values()
            for obj in resources
        )
        return set(
            HashableResource(obj)
            for obj in objects
            if hasattr(obj, "status") and obj.status.conditions
        )

    def expected_resources(self) -> Mapping[NamespaceKind, Set[HashableResource]]:
        """All currently installed resources expected by this charm."""
        result: Mapping[NamespaceKind, Set[HashableResource]] = defaultdict(set)
        for key, resources in self.resources.items():
            for obj in resources:
                result[key].add(
                    HashableResource(
                        self.client.get(
                            type(obj.rsc),
                            obj.metadata.name,
                            namespace=obj.metadata.namespace,
                        )
                    )
                )
        return result

    def active_resources(self) -> Mapping[NamespaceKind, Set[HashableResource]]:
        """All currently installed resources ever labeled by this charm."""
        return {
            key: set(
                HashableResource(rsc)
                for rsc in self.client.list(
                    type(obj.rsc),
                    namespace=obj.metadata.namespace,
                    labels={self.application: "true"},
                )
            )
            for key, resources in self.resources.items()
            for obj in islice(resources, 1)  # take the first element if it exists
        }

    def apply_manifests(self, context: Dict[str, str]):
        for component in self.components:
            for manifest in Path("upstream", "manifests", component).glob("*.yaml"):
                self._apply_manifest(manifest, context)

    def delete_manifests(self, **kwargs):
        for resources in self.resources.values():
            for obj in resources:
                self.delete_resource(obj, **kwargs)

    def _apply_manifest(self, filepath: Path, context: Dict[str, str]):
        template = Template(filepath.read_text())
        content = template.render(**context)
        text = self._modifications(content)
        for obj in codecs.load_all_yaml(text):
            name = obj.metadata.name
            namespace = obj.metadata.namespace
            log.info(
                f"Adding {obj.kind}/{name}" + (f" to {namespace}" if namespace else "")
            )
            self.client.apply(obj, name)

    def _modifications(self, content: str) -> str:
        def _add_label(obj):
            obj["metadata"].setdefault("labels", {})
            obj["metadata"].setdefault("name", "")
            obj["metadata"]["labels"][self.application] = "true"

        data = [_ for _ in yaml.safe_load_all(content) if _]
        for part in data:
            if part["kind"] == "List":
                for item in part["items"]:
                    _add_label(item)
            else:
                _add_label(part)
        return yaml.safe_dump_all(data)

    def delete_resources(
        self,
        *resources: HashableResource,
        namespace: Optional[str] = None,
        ignore_not_found: bool = False,
        ignore_unauthorized: bool = False,
    ):
        """Delete named resources."""
        for obj in resources:
            try:
                namespace = obj.metadata.namespace or namespace
                log.info(f"Deleting {obj}")
                self.client.delete(
                    type(obj.rsc), obj.metadata.name, namespace=namespace
                )
            except ApiError as err:
                if err.status.message is not None:
                    err_lower = err.status.message.lower()
                    if "not found" in err_lower and ignore_not_found:
                        log.warning(f"Ignoring not found error: {err.status.message}")
                    elif "(unauthorized)" in err_lower and ignore_unauthorized:
                        # Ignore error from https://bugs.launchpad.net/juju/+bug/1941655
                        log.warning(f"Unauthorized error ignored: {err.status.message}")
                    else:
                        log.exception(
                            "ApiError encountered while attempting to delete resource: "
                            + err.status.message
                        )
                        raise
                else:
                    log.exception(
                        "ApiError encountered while attempting to delete resource."
                    )
                    raise

    delete_resource = delete_resources
