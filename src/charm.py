#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Charm the service.

Refer to the following post for a quick-start guide that will help you
develop a new k8s charm using the Operator Framework:

    https://discourse.charmhub.io/t/4208
"""

import logging
from typing import cast

import ops
from ops.manifests import Collector, ManifestClientError

from metric_server_manifests import MetricServerManifests

logger = logging.getLogger(__name__)


class KubernetesMetricsServerOperator(ops.CharmBase):
    """Charm the service."""

    stored = ops.StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.install, self._install_or_upgrade)
        self.framework.observe(self.on.upgrade_charm, self._install_or_upgrade)
        self.framework.observe(self.on.config_changed, self._install_or_upgrade)
        self.framework.observe(self.on.stop, self._cleanup)

        self.framework.observe(self.on.list_versions_action, self._list_versions)
        self.framework.observe(self.on.list_resources_action, self._list_resources)
        self.framework.observe(self.on.scrub_resources_action, self._scrub_resources)
        self.framework.observe(self.on.sync_resources_action, self._sync_resources)
        self.framework.observe(self.on.update_status, self._update_status)

        self.stored.set_default(
            config_hash=0
        )  # hashed value of the provider config once valid
        self.collector = Collector(MetricServerManifests(self))

    def _list_versions(self, event: ops.ActionEvent) -> None:
        self.collector.list_versions(event)

    def _list_resources(self, event: ops.ActionEvent) -> None:
        manifests = event.params.get("manifest", "")
        resources = event.params.get("resources", "")
        self.collector.list_resources(event, manifests, resources)

    def _scrub_resources(self, event: ops.ActionEvent) -> None:
        manifests = event.params.get("manifest", "")
        resources = event.params.get("resources", "")
        self.collector.scrub_resources(event, manifests, resources)

    def _sync_resources(self, event: ops.ActionEvent) -> None:
        manifests = event.params.get("manifest", "")
        resources = event.params.get("resources", "")
        try:
            self.collector.apply_missing_resources(event, manifests, resources)
        except ManifestClientError as e:
            msg = "Failed to sync missing resources: "
            msg += " -> ".join(map(str, e.args))
            event.set_results({"result": msg})
        else:
            self.stored.deployed = True

    def _update_status(self, _: ops.UpdateStatusEvent) -> None:
        unready = self.collector.unready
        if unready:
            self.unit.status = ops.WaitingStatus(", ".join(sorted(unready)))
        else:
            self.unit.status = ops.ActiveStatus("Ready")
            self.unit.set_workload_version(self.collector.short_version)
            self.app.status = ops.ActiveStatus(self.collector.long_version)

    def evaluate_manifests(self) -> int:
        """Evaluate all manifests."""
        self.unit.status = ops.MaintenanceStatus("Configuring metrics-server")
        new_hash = 0
        for manifest in self.collector.manifests.values():
            manifest = cast(MetricServerManifests, manifest)
            if evaluation := manifest.evaluate():
                self.unit.status = ops.BlockedStatus(evaluation)
                return -1
            new_hash += manifest.hash()
        return new_hash

    def _install_or_upgrade(self, _):
        """Install the manifests."""
        if (config_hash := self.evaluate_manifests()) < 1:
            return
        if cast(int, self.stored.config_hash) == config_hash:
            logger.info(f"No config changes detected. config_hash={config_hash}")
            return
        if self.unit.is_leader():
            self.unit.status = ops.MaintenanceStatus(
                "Deploying Kubernetes Metrics Server"
            )
            self.unit.set_workload_version("")
            for manifest in self.collector.manifests.values():
                try:
                    manifest.apply_manifests()
                except ManifestClientError as e:
                    failure_msg = " -> ".join(map(str, e.args))
                    self.unit.status = ops.WaitingStatus(failure_msg)
                    logger.warning("Encountered retryable installation error: %s", e)
                    return
        self.stored.config_hash = config_hash

    def _cleanup(self, _):
        self.unit.status = ops.MaintenanceStatus("Removing resources")
        for manifest in self.collector.manifests.values():
            manifest.delete_manifests(ignore_unauthorized=True, ignore_not_found=True)


if __name__ == "__main__":
    ops.main(KubernetesMetricsServerOperator)
