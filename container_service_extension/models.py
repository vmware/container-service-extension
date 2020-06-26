# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from dataclasses import dataclass
from typing import List

from dataclasses import dataclass

@dataclass()
class Ovdc:
    """Represents OVDC instance (with respect to CSE K8s runtimes).

    If dictionaries are passed as arguments, the constructor auto-converts
    them into the expected class instances.
    """

    id: str
    k8s_runtime: List[str]
    name: str = None
    remove_compute_policy_from_vms: bool = None

    def __post_init__(self):
        # Validate the input values for k8s_runtimes
        if set(self.k8s_runtime) - set(CLUSTER_RUNTIME_PLACEMENT_POLICIES): # noqa: E501
            msg = "Cluster providers should have one of the follwoing values:" \
                f" {', '.join(CLUSTER_RUNTIME_PLACEMENT_POLICIES)}."
            raise cse_exception.BadRequestError(msg)