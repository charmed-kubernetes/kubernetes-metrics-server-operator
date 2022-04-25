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

from manifests import Manifests

logger = logging.getLogger(__name__)


class KubernetesMetricsServerOperator(CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.install, self._install_or_upgrade)
        self.framework.observe(self.on.upgrade_charm, self._install_or_upgrade)
        self.framework.observe(self.on.config_changed, self._install_or_upgrade)
        self.framework.observe(self.on.leader_elected, self._set_version)
        self.framework.observe(self.on.stop, self._cleanup)

        self.framework.observe(self.on.list_versions_action, self._list_versions)
        self.framework.observe(self.on.list_resources_action, self._list_resources)
        self.framework.observe(self.on.scrub_resources_action, self._scrub_resources)
        self.framework.observe(self.on.update_status, self._update_status)

        self.manifests = Manifests(self)

    def _list_versions(self, event):
        result = {
            "versions": "\n".join(sorted(str(_) for _ in self.manifests.releases)),
        }
        event.set_results(result)

    def _list_resources(self, event):
        res_filter = [_.lower() for _ in event.params.get("resources", "").split()]
        if res_filter:
            event.log(f"Filter resource listing with {res_filter}")
        current = self.manifests.active_resources()
        expected = self.manifests.expected_resources()
        correct, extra, missing = (
            set(),
            set(),
            set(),
        )
        for kind_ns, current_set in current.items():
            if not res_filter or kind_ns.kind.lower() in res_filter:
                expected_set = expected[kind_ns]
                correct |= current_set & expected_set
                extra |= current_set - expected_set
                missing |= expected_set - current_set

        result = {
            "correct": "\n".join(sorted(str(_) for _ in correct)),
            "extra": "\n".join(sorted(str(_) for _ in extra)),
            "missing": "\n".join(sorted(str(_) for _ in missing)),
        }
        result = {k: v for k, v in result.items() if v}
        event.set_results(result)
        return correct, extra, missing

    def _scrub_resources(self, event):
        _, extra, __ = self._list_resources(event)
        if extra:
            self.manifests.delete_resources(*extra)
            self._list_resources(event)

    def _update_status(self, _):
        for resource in self.manifests.status():
            for cond in resource.status.conditions:
                if cond.status != "True":
                    self.unit.status = WaitingStatus(
                        f"Waiting for {resource} Condition:{cond.type}"
                    )
                    return
        self.unit.status = ActiveStatus("Ready")

    def _install_or_upgrade(self, _):
        """Install the manifests."""
        try:
            self.manifests.apply_manifests()
        except ConnectionError:
            self.unit.status = WaitingStatus("Waiting for API server.")
        self._update_status(_)

    def _set_version(self, _event=None):
        if self.unit.is_leader():
            self.unit.set_workload_version(self.manifests.current_release)

    def _cleanup(self, _):
        self.unit.status = WaitingStatus("Shutting down")
        self.manifests.delete_manifests(ignore_unauthorized=True)


if __name__ == "__main__":
    main(KubernetesMetricsServerOperator)
