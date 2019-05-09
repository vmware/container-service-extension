# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import re

from prompt_toolkit.validation import Validator

from container_service_extension.interview import debug, debug_traceback
from container_service_extension.interview.interaction import Interaction
from container_service_extension.interview.interaction_context import \
    InteractionContext
from container_service_extension.interview.top_level_context import \
    get_global_next_interaction, set_global_next_interaction


class Group(Interaction, InteractionContext):
    """
    Question Group

    Used for navigation around the interview, and to skip over
    already answered questions.
    """

    def __init__(self, yaml_field, questions,
                 skip_if_valid=False,
                 validation_function=None):
        Interaction.__init__(self)
        InteractionContext.__init__(self, yaml_prefix=yaml_field)
        self.questions = questions
        self.skip_if_valid = skip_if_valid
        self.validation_function = validation_function
        self.default = None

    def set_context(self, context):
        Interaction.set_context(self, context)
        InteractionContext.set_context(self, context)
        for q in self.questions:
            q.set_context(self)

    def prepare(self):
        # validate all of the questions in the group against
        # their current answers to determine
        # if the group should be visited in an interview.
        try:
            for q in self.questions:
                proposed = q.infer()
                q.validate(proposed)

            self.default = "no"
        except Exception as e:
            debug(str(e))
            self.default = "force"

    def prompt_text(self):
        return "Edit group " + self.yaml_prefix + "? [" + self.default + "] "

    def help_text(self):
        return "yes for basic interview, no to skip, " \
               + "all for detailed interview"

    def generate(self):
        self.next_question()

    def validate(self, proposed):
        pass

    def ask(self):
        try:
            self.prepare()

            if self.default is "force":
                result = "yes"
            else:
                # TODO handle self.skip_if_valid

                validator = Validator.from_callable(
                    lambda x: (
                        re.match("(y(es)?|no?|a(ll)?)?", x, re.IGNORECASE)),
                    error_message="Answer yes, no, or all")
                # remove: validator = None

                result = self.context.get_session().prompt(
                    self.prompt_text(),
                    bottom_toolbar=self.help_text,
                    validator=validator)

                if not result:
                    result = self.default

            # next_question can be set during __prompt()
            # if there was a key binding event
            if get_global_next_interaction() is None:
                if result.lower().startswith("y"):
                    # Next question in this group
                    self.next_question()
                elif result.lower().startswith("a"):
                    # TODO something special to ask "detail"
                    #  or "hidden" questions
                    self.next_question()
                else:
                    # TODO validate all the current questions before advancing

                    # next question in parent group
                    self.context.next_question(self)
        except KeyboardInterrupt:
            # Ctrl-c gracefully exits
            pass

    def next_question(self, current_question=None):
        """
        Return the question defined after the current question,
        or call the parent context if it is the last question
        """
        if current_question is None:
            set_global_next_interaction(self.questions[0])
            return

        for i in range(0, len(self.questions)):
            if self.questions[i] == current_question:
                if i + 1 < len(self.questions):
                    set_global_next_interaction(self.questions[i + 1])
                    return
                else:
                    # Questions are complete, run the __validation_function,
                    # then loop on failure
                    if self.validation_function is not None:
                        try:
                            self.validation_function(self)
                        except Exception as e:
                            print(f"Error {e}")
                            debug_traceback()
                            set_global_next_interaction(self)
                            return

                    super().next_question(self)
                    return
        assert False, "Question not found in context"
