import logging
import json
from hashlib import sha256
import ops
from lightkube.codecs import AnyResource
from ops.manifests import ConfigRegistry, Manifests, ManifestLabel, Patch

log = logging.getLogger(__file__)


def _args_or_flags(args_list):
    """Create unique argument dict from value args or flag args."""
    return dict(arg.split("=", 1) if "=" in arg else (arg, None) for arg in args_list)


class ApplyArguments(Patch):
    """Apply extra args to the metric-server deployment."""

    def __call__(self, obj: AnyResource) -> None:
        """Update deployment arguments."""
        if not (
            obj.kind == "Deployment"
            and obj.metadata
            and obj.metadata.name == "metrics-server"
        ):
            return
        if extra_args := self.manifests.config.get("extra-args"):
            containers = obj.spec.template.spec.containers
            for container in containers:
                if container.name != "metrics-server":
                    continue
                full_args = _args_or_flags(container.args)
                full_args.update(**_args_or_flags(extra_args.split()))
                new_args = [
                    arg if value is None else f"{arg}={value}"
                    for arg, value in full_args.items()
                ]
                log.info(f"Replacing Args: {full_args} with {new_args}")
                container.args = new_args


class MetricServerManifests(Manifests):
    def __init__(self, charm: ops.CharmBase):
        super().__init__(
            "metrics-server",
            charm.model,
            "upstream/metrics-server",
            [
                ManifestLabel(self),
                ConfigRegistry(self),
                ApplyArguments(self),
            ],
        )
        self._charm = charm

    @property
    def config(self):
        """Return the config for the manifests."""
        return dict(self._charm.model.config)

    def evaluate(self) -> str:
        """Evaluate the storage class."""
        log.info("Evaluating manifests")
        return ""

    def hash(self) -> int:
        """Return a hash of the manifests."""
        return int(
            sha256(json.dumps(self.config, sort_keys=True).encode()).hexdigest(), 16
        )
