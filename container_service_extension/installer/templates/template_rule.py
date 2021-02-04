# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.common.constants.server_constants import LocalTemplateKey  # noqa: E501
from container_service_extension.common.utils.core_utils import NullPrinter
from container_service_extension.logging.logger import NULL_LOGGER


class TemplateRule:
    """Represents a template rule object.

    Rules can be defined to override template definitions as defined by remote
    template cookbook. Each rule acts on 'target' viz. a template, and can have
    only one target. Matching is driven by name and revision of the template.
    If only name is specified without the revision or vice versa, the rule will
    not be processed. And once a match is found, as an 'action' the following
    attributes can be overriden.
        * compute_policy
        * cpu
        * memory
    """

    def __init__(self, name, target, action, logger=NULL_LOGGER,
                 msg_update_callback=NullPrinter()):
        """Initialize TemplateRule object.

        :param str name: name of the rule.
        :param dict target: target template of the rule. The keys 'name' and
            'revision' should be present in the dictionary.
        :param dict action: attributes of the target template to update,
            accepted keys are 'compute_policy', 'cpu' and 'memory'.
        :param logging.Logger logger: logger to log with.
        :param utils.ConsoleMessagePrinter msg_update_callback: Callback.
        """
        self.name = name
        self.target = target
        self.action = action
        self.logger = logger
        self.msg_update_callback = msg_update_callback

    def __str__(self):
        return f"{self.name} : ({self.target.get('name')} at rev {self.target.get('revision')}) -> {self.action}" # noqa: E501

    def _validate(self, template_table):
        """."""
        if self.target:
            target_name = self.target.get('name')
            target_revision = self.target.get('revision')
        else:
            msg = f"Rule : {self.name}'s target is not defined."
            self.logger.warning(msg)
            self.msg_update_callback.error(msg)
            return False

        if not target_name:
            msg = f"Rule : {self.name}'s target name is not defined."
            self.logger.warning(msg)
            self.msg_update_callback.error(msg)
            return False

        if not target_revision:
            msg = f"Rule : {self.name}'s target revision is not defined."
            self.logger.warning(msg)
            self.msg_update_callback.error(msg)
            return False

        if target_name not in template_table:
            msg = f"Rule : {self.name}'s target template : {target_name} is " \
                  "not a known k8s template."
            self.logger.warning(msg)
            self.msg_update_callback.error(msg)
            return False

        if str(target_revision) not in template_table[target_name]:
            msg = f"Rule : {self.name}'s target template : {target_name} at " \
                  f"revision : {target_revision} is not a known k8s template."
            self.logger.warning(msg)
            self.msg_update_callback.error(msg)
            return False

        if not self.action:
            msg = f"Rule : {self.name} has no action"
            self.logger.warning(msg)
            self.msg_update_callback.error(msg)
            return False

        all_actions = set(self.action.keys())
        invalid_actions = list(
            all_actions - set([
                LocalTemplateKey.COMPUTE_POLICY,
                LocalTemplateKey.CPU,
                LocalTemplateKey.MEMORY
            ]))

        if invalid_actions:
            msg = f"Rule : {self.name}'s specifies invalid action(s) : " \
                  f"{invalid_actions}"
            self.logger.warning(msg)
            self.msg_update_callback.error(msg)
            # the rule is still valid, so don't fail the validation.

        return True

    def apply(self, templates):
        """Validate and apply a rule on templates.

        If the rule validation fails, appropriate message will be logged and
        updated via msg_update_callback. If validation goes through, an
        in-place updation of template deifintion will occur. Unknown action
        keys will be ignored.

        :param list templates: list of local template defintions
        """
        # Arrange the k8s templates by name and revision for ease of querying.
        # The resulting data srtucture is a 3 level dictionary, where
        # first level dictionary is key-ed by the template name, while the
        # second level dictionary is keyed by the various revisions of the
        # template in question. And as value corresponding to each second level
        # dictionary key, we have local k8s template definition represented as
        # a dictionary.
        template_table = {}
        for template in templates:
            template_name = template[LocalTemplateKey.NAME]
            template_revision = str(template[LocalTemplateKey.REVISION])
            if template_name not in template_table:
                template_table[template_name] = {}
            template_table[template_name][template_revision] = template

        if not self._validate(template_table):
            return

        target_template = template_table[self.target['name']][str(self.target['revision'])] # noqa: E501

        new_compute_policy = \
            self.action.get(LocalTemplateKey.COMPUTE_POLICY)
        if new_compute_policy is not None:
            target_template[LocalTemplateKey.COMPUTE_POLICY] = \
                new_compute_policy

        new_cpu = self.action.get(LocalTemplateKey.CPU)
        if new_cpu is not None:
            target_template[LocalTemplateKey.CPU] = new_cpu

        new_memory = self.action.get(LocalTemplateKey.MEMORY)
        if new_memory is not None:
            target_template[LocalTemplateKey.MEMORY] = new_memory
