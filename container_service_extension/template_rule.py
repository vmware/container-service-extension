# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.server_constants import LocalTemplateKey


class TemplateRule:
    def __init__(self, definition, logger=None, msg_update_callback=None):
        """."""
        self.name = definition.get('name')
        self.target = definition.get('target')
        self.action = definition.get('action')
        self.logger = logger
        self.msg_update_callback = msg_update_callback

    def __str__(self):
        redacted_action = dict(self.action)
        if 'admin_password' in redacted_action:
            redacted_action['admin_password'] = "[REDCATED]"
        return f"{self.name} : ({self.target.get('name')} at rev {self.target.get('revision')}) -> {redacted_action}" # noqa: E501

    def validate(self, template_table):
        """."""
        if self.target:
            target_name = self.target.get('name')
            target_revision = self.target.get('revision')
        else:
            msg = f"Rule : {self.name}'s target is not defined."
            if self.logger:
                self.logger.warning(msg)
            if self.msg_update_callback:
                self.msg_update_callback.info(msg)
            return False

        if not target_name:
            msg = f"Rule : {self.name}'s target name is not defined."
            if self.logger:
                self.logger.warning(msg)
            if self.msg_update_callback:
                self.msg_update_callback.info(msg)
            return False

        if not target_revision:
            msg = f"Rule : {self.name}'s target revision is not defined."
            if self.logger:
                self.logger.warning(msg)
            if self.msg_update_callback:
                self.msg_update_callback.info(msg)
            return False

        if target_name not in template_table:
            msg = f"Rule : {self.name}'s target template : {target_name} is " \
                  "not a known k8s template."
            if self.logger:
                self.logger.warning(msg)
            if self.msg_update_callback:
                self.msg_update_callback.info(msg)
            return False

        if str(target_revision) not in template_table[target_name]:
            msg = f"Rule : {self.name}'s target template : {target_name} at " \
                  f"revision : {target_revision} is not a known k8s template."
            if self.logger:
                self.logger.warning(msg)
            if self.msg_update_callback:
                self.msg_update_callback.info(msg)
            return False

        if not self.action:
            msg = f"Rule : {self.name} has no action"
            if self.logger:
                self.logger.warning(msg)
            if self.msg_update_callback:
                self.msg_update_callback.info(msg)
            return False

        all_actions = set(self.action.keys())
        invalid_actions = list(
            all_actions - set([
                LocalTemplateKey.ADMIN_PASSWORD,
                LocalTemplateKey.COMPUTE_POLICY,
                LocalTemplateKey.CPU,
                LocalTemplateKey.MEMORY
            ]))

        if invalid_actions:
            msg = f"Rule : {self.name}'s specifies invalid action(s) : " \
                  f"{invalid_actions}"
            if self.logger:
                self.logger.warning(msg)
            if self.msg_update_callback:
                self.msg_update_callback.info(msg)
            # the rule is still valid, so don't fail the validation.

        return True

    def apply_on(self, target_template):
        """."""
        new_admin_password = self.action.get(LocalTemplateKey.ADMIN_PASSWORD) # noqa: E501
        if new_admin_password and new_admin_password != target_template[LocalTemplateKey.ADMIN_PASSWORD]: # noqa: E501
            target_template[LocalTemplateKey.ADMIN_PASSWORD] = new_admin_password # noqa: E501

        new_compute_profile = self.action.get(LocalTemplateKey.COMPUTE_POLICY) # noqa: E501
        if new_compute_profile and new_compute_profile != target_template[LocalTemplateKey.COMPUTE_POLICY]: # noqa: E501
            target_template[LocalTemplateKey.COMPUTE_POLICY] = new_compute_profile # noqa: E501
            # TODO: Update the compute policy of the template right away!

        new_cpu = self.action.get(LocalTemplateKey.CPU)
        if new_cpu and new_cpu != target_template[LocalTemplateKey.CPU]: # noqa: E501
            target_template[LocalTemplateKey.CPU] = new_cpu

        new_memory = self.action.get(LocalTemplateKey.MEMORY)
        if new_memory and new_memory != target_template[LocalTemplateKey.MEMORY]: # noqa: E501
            target_template[LocalTemplateKey.MEMORY] = new_memory
