import logging

from pathlib import Path
from typing import Dict, Optional

import yaml
from jinja2 import Template
from lightkube import Client, codecs
from lightkube.core.exceptions import ApiError

log = logging.getLogger(__file__)


class Manifests:
    def __init__(self, charm):
        self.namespace = charm.model.name
        self.application = charm.model.app.name
        self.client = Client(namespace=self.namespace, field_manager=self.application)

    @property
    def version(self):
        return Path("upstream", "version").read_text(encoding="utf-8").strip()

    def charm_resources(self, *components: str):
        return (
            (res, current)
            for component in components
            for manifest in Path("upstream", "manifests", component).glob("*.yaml")
            for res, current in self._list_manifest(
                manifest,
                labels={self.application: "true"},
            )
        )

    def apply_manifests(self, context: Dict[str, str], *components: str):
        for component in components:
            for manifest in Path("upstream", "manifests", component).glob("*.yaml"):
                self._apply_manifest(manifest, context)

    def delete_manifests(self, *components: str, **kwargs):
        for component in components:
            for manifest in Path("upstream", "manifests", component).glob("*.yaml"):
                self._delete_manifest(manifest, **kwargs)

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

    def _list_manifest(self, filepath: Path, **selectors):
        text = filepath.read_text()
        thing = [
            (res, res.metadata.name == obj.metadata.name)
            for obj in codecs.load_all_yaml(text)
            for res in self.client.list(
                type(obj), namespace=obj.metadata.namespace, **selectors
            )
        ]
        return thing

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

    def _delete_manifest(
        self,
        filepath: Path,
        namespace: Optional[str] = None,
        **kwargs,
    ):
        text = filepath.read_text()
        for obj in codecs.load_all_yaml(text):
            self.delete_resources(
                obj,
                namespace=obj.metadata.namespace or namespace,
                **kwargs,
            )

    def delete_resources(
        self,
        *resources,
        namespace: Optional[str] = None,
        ignore_not_found: bool = False,
        ignore_unauthorized: bool = False,
    ):
        """Delete named resources."""
        for obj in resources:
            try:
                namespace = obj.metadata.namespace or namespace
                log.info(
                    f"Deleting {type(obj).__name__}/{obj.metadata.name}"
                    + (f" to {namespace}" if namespace else "")
                )
                self.client.delete(type(obj), obj.metadata.name, namespace=namespace)
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
