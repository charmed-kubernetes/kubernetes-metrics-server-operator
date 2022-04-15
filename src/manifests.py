import logging
from pathlib import Path

from lightkube import Client, codecs
from lightkube.core.exceptions import ApiError

log = logging.getLogger(__file__)


class Manifests:
    def __init__(self, charm):
        self.namespace = charm.model.name
        self.application = charm.model.app.name
        self.client = Client(namespace=self.namespace, field_manager="lightkube")

    @property
    def version(self):
        return Path("upstream", "version").read_text(encoding="utf-8")

    def apply_manifests(self, component):
        manifests = Path("upstream", "manifests", component).glob("*.yaml")
        for manifest in manifests:
            self.apply_manifest(manifest)

    def delete_manifests(self, component):
        manifests = Path("upstream", "manifests", component).glob("*.yaml")
        for manifest in manifests:
            self.delete_manifest(manifest)

    def apply_manifest(self, filepath):
        with filepath.open() as f:
            text = f.read()
            text = text.replace("juju-application-placeholder", self.application)
            text = text.replace("juju-namespace-placeholder", self.namespace)
        for obj in codecs.load_all_yaml(text):
            self.delete_resource(
                type(obj),
                obj.metadata.name,
                ignore_not_found=True,
            )
            self.client.create(obj)

    def delete_manifest(
        self,
        filepath,
        namespace=None,
        ignore_not_found=False,
        ignore_unauthorized=False,
    ):
        with filepath.open() as f:
            text = f.read()
        for obj in codecs.load_all_yaml(text):
            self.delete_resource(
                type(obj),
                obj.metadata.name,
                namespace=namespace,
                ignore_not_found=ignore_not_found,
                ignore_unauthorized=ignore_unauthorized,
            )

    def delete_resource(
        self,
        resource_type,
        name,
        namespace=None,
        ignore_not_found=False,
        ignore_unauthorized=False,
    ):
        """Delete a resource."""
        try:
            self.client.delete(resource_type, name, namespace=namespace)
        except ApiError as err:
            if err.status.message is not None:
                err_lower = err.status.message.lower()
                if "not found" in err_lower and ignore_not_found:
                    log.warning(f"Ignoring not found error: {err.status.message}")
                elif "(unauthorized)" in err_lower and ignore_unauthorized:
                    # Ignore error from https://bugs.launchpad.net/juju/+bug/1941655
                    log.warning(f"Ignoring unauthorized error: {err.status.message}")
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
