# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import re

from container_service_extension.interview.interaction import Interaction
from container_service_extension.interview.interaction_context import \
    InteractionContext
from container_service_extension.interview.top_level_context import \
    set_global_next_interaction


class IndexedGroup(Interaction, InteractionContext):
    """
    Indexed Question Group

    Used for asking questions about an array of objects
    """

    def __init__(self, yaml_field, questions,
                 description=None,
                 item_prompt="",
                 required=0):
        Interaction.__init__(self)
        InteractionContext.__init__(self)
        self.yaml_field = yaml_field
        self.description = description
        self.__item_prompt = item_prompt
        self.__questions = questions
        self.required = required
        self.overview = []
        self.__index = None
        self.__max_index = None
        self.__prompt = None
        self.__default = None
        self.__validation = None
        self.__validation_message = None

    def set_context(self, context):
        Interaction.set_context(self, context)
        InteractionContext.set_context(self, context)
        for q in self.__questions:
            q.set_context(self)

    def get_yaml_value(self, key):
        assert self.__index >= 0
        return self.parent_context.get_yaml_value(
            self.yaml_field + "[" + str(self.__index) + "]." + key)

    def set_yaml_value(self, key, value):
        assert self.__index >= 0
        return self.parent_context.set_yaml_value(
            self.yaml_field + "[" + str(self.__index) + "]." + key, value)

    def prepare(self):
        # find number of indexed elements
        array = self.context.get_yaml_value(self.yaml_field)
        self.__max_index = len(array)
        self.__prompt = f"Found {self.__max_index} " \
                        + str(self.yaml_field) + " elements\n"

        if len(array) > 0:
            self.__prompt += "Enter the number to edit, " \
                             + "'d' to delete, 'a' to add, or Enter to skip"
            self.__default = ""
            self.__validation = "(a.*|d.*|\\d+)?"
            self.__validation_message = "Please enter a valid value"
        else:
            self.__prompt += "Enter 'a' to add, or Enter to skip"
            self.__default = "a"
            self.__validation = "(a.*)?"
            self.__validation_message = "Please enter a valid value"

    def next_question(self, current_question=None):
        """
        Return the question defined after the current question,
        or call the parent context if it is the last question
        """

        if current_question is None:
            set_global_next_interaction(self.__questions[0])
            return

        for i in range(0, len(self.__questions)):
            if self.__questions[i] == current_question:
                if i + 1 < len(self.__questions):
                    set_global_next_interaction(self.__questions[i + 1])
                    return
                else:
                    # Go back to top level
                    # TODO post_validation stuff
                    set_global_next_interaction(self)
                    return
        assert False, "Question not found in context"

    def prompt(self):
        return self.__prompt

    def default(self):
        return self.__default

    def validate(self, proposed_value):
        """
        Validate the answer entered by the user.

        This is done by looking at the following fields:
            * validation (although this is also checked by prompt_toolkit)
            * choices_value (array or callable)
            * required (boolean)
            * validation_function

        :param proposed_value: proposed answer
        :rtype: None
        :raises Exception if the proposed_value is not valid
        """
        if self.__validation:
            assert re.match(self.__validation, proposed_value), \
                f"{self.yaml_field} has an invalid value: {proposed_value}. " \
                f"{self.__validation_message}"

        # TODO
        # Test Numbers to be in range

    def set_value(self, proposed_value):
        if proposed_value is None or len(proposed_value) == 0:
            # go to the next question
            # TODO validate should ensure that 1 exists
            pass
        else:
            if proposed_value.startswith("a"):
                self.__index = self.__max_index
                self.__max_index = self.__max_index + 1
                set_global_next_interaction(self.__questions[0])
            elif proposed_value.startswith("d"):
                # TODO confirm deletion
                set_global_next_interaction(self)
            else:
                self.__index = int(proposed_value)
                set_global_next_interaction(self.__questions[0])
