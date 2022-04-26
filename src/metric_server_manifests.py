import logging
from manifests import Manifests

log = logging.getLogger(__file__)


class MetricServerManifests(Manifests):
    def __init__(self, charm):
        manipulations = [self.add_label, self.apply_registry, self.apply_arguments]
        super().__init__(charm, manipulations)

    @staticmethod
    def _args_or_flags(args_list):
        """Create unique argument dict from value args or flag args."""
        return dict(
            arg.split("=", 1) if "=" in arg else (arg, None) for arg in args_list
        )

    def apply_registry(self, obj):
        registry = self.config.get("registry-server")
        if not registry:
            return
        spec = obj.get("spec") or {}
        template = spec and spec.get("template") or {}
        inner_spec = template and template.get("spec") or {}
        containers = inner_spec and inner_spec.get("containers") or {}
        for container in containers:
            if full_image := container.get("image"):
                _, image = full_image.split("/", 1)
                new_full_image = f"{registry}/{image}"
                container["image"] = new_full_image
                log.info(f"Replacing Image: {full_image} with {new_full_image}")

    def apply_arguments(self, obj):
        """Append the extra-args to the metric-server deployment."""
        if not (
            obj.get("kind") == "Deployment"
            and obj["metadata"]["name"] == "metrics-server"
        ):
            return
        extra_args = self.config.get("extra-args")
        if not extra_args:
            return
        containers = obj["spec"]["template"]["spec"]["containers"]
        for container in containers:
            if container["name"] != "metrics-server":
                continue
            full_args = self._args_or_flags(container["args"])
            full_args.update(**self._args_or_flags(extra_args.split()))
            new_args = [
                arg if value is None else f"{arg}={value}"
                for arg, value in full_args.items()
            ]
            log.info(f"Replacing Args: {full_args} with {new_args}")
            container["args"] = new_args
