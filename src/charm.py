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

from ops.charm import CharmBase
from ops.main import main
from ops.model import ActiveStatus, WaitingStatus

from charms.prometheus_k8s.v0.prometheus_scrape import MetricsEndpointProvider
from manifests import Manifests

logger = logging.getLogger(__name__)


class KubernetesMetricsServerOperator(CharmBase):
    METRICS_PARAMETERS = {
        "base-metrics-server-cpu",
        "base-metrics-server-memory",
        "metrics-server-memory-per-node",
        "metrics-server-min-cluster-size",
    }
    """Charm the service."""

    def __init__(self, *args):
        super().__init__(*args)
        jobs = [
            {
                "scrape_interval": self.config["scrape-interval"],
                "static_configs": [
                    {
                        "targets": ["*:8080", "*:8081"],
                    }
                ],
            }
        ]

        self.monitoring = MetricsEndpointProvider(self, jobs=jobs)

        self.framework.observe(self.on.install, self._install_or_upgrade)
        self.framework.observe(self.on.upgrade_charm, self._install_or_upgrade)
        self.framework.observe(self.on.config_changed, self._install_or_upgrade)
        self.framework.observe(self.on.leader_elected, self._set_version)
        self.framework.observe(self.on.stop, self._cleanup)

    def _install_or_upgrade(self, _):
        """Install the manifests."""
        manifests = Manifests(self)

        try:
            context = {
                k.replace("-", "_"): v
                for k, v in self.config.items()
                if k in self.METRICS_PARAMETERS
            }
            manifests.apply_manifests(context, "metrics-server")
            self.unit.status = ActiveStatus("Ready")
        except ConnectionError:
            self.unit.status = WaitingStatus("Waiting for API server.")

    def _set_version(self, _event=None):
        if self.unit.is_leader():
            manifests = Manifests(self)
            self.unit.set_workload_version(manifests.version)

    def _cleanup(self, _):
        self.unit.status = WaitingStatus("Shutting down")
        manifests = Manifests(self)
        manifests.delete_manifests("metrics-server", ignore_unauthorized=True)


if __name__ == "__main__":
    main(KubernetesMetricsServerOperator)
