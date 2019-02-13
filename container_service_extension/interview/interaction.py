# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from prompt_toolkit import print_formatted_text
from prompt_toolkit.validation import DummyValidator

from container_service_extension.interview import debug


class Interaction:
    """
    Basic class to handle the lifecycle of a single
    parameter in the YAML file.

    For an interactive session, callers should make two calls to this class:
     - user_answer = interaction.ask()
     - if interaction.validate(user_answer):
        interaction.set_value(user_answer)

    For an non-interactive session, it is almost the same:
     - suggestion = interaction.ask()
     - if interaction.validate(suggestion):
         <respond somehow>


    Implementers should override the following methods:
     - initialize()
     - comment()
     - validation_function()
     - choices()
     - suggestion()
     - help_text()

    """

    def __init__(self,
                 required=True):
        self.context = None
        self.initialized = False
        self.__required = required

    def set_context(self, context):
        """
        Must be called by the interview controller to set the backing
        context for this question.
        :param context:
        """
        self.context = context

    def ask(self):
        """
        Ask this question to an interactive user.

        This method will use the following helper methods to
        display the question:

        - prompt_text: return the prompt string
        - choices: return a list of allowed values
        - help_text: return the help text (displayed in the bottom bar)
        - suggestion: suggested answer (current value or default if there
            isn't one), will be used if no value is entered (user presses Enter)

        Note: this method can also use the global method `set_global_next_interaction`,
              if it does, then the response is ignored, and the interview
              will advance to the specified question.
        :rtype: str
        """
        self.prepare()

        comment = self.comment()
        if comment:
            print_formatted_text(comment)

        result = self.context.get_session() \
            .prompt(self.get_prompt_text(),
                    bottom_toolbar=self.get_help_text(),
                    validator=self.get_validator())

        return result or self.get_suggestion()

    def infer(self):
        """
        Infer an answer to this question in a non-interactive scenario.

        This method will use the following helper methods to
        display the question:

        - choices: return a list of allowed values
        - suggestion: suggested answer (current value or default if there
            isn't one)

        :rtype: str
        :raises: Exception if there is no way to guess an answer.
        """
        self.prepare()
        return self.get_suggestion()

    def validate(self, proposed_value):
        """
        Validate the answer entered by the user.

        This is done by looking at the following fields:
            * choices_value (array or callable)
            * __required (boolean)
            * __validation_function

        :param proposed_value: proposed answer
        :rtype: None
        :raises Exception if the proposed_value is not valid
        """
        choices_value = self.choices()

        if isinstance(choices_value, str):
            assert proposed_value is choices_value, \
                f"{self.yaml_field} has an invalid value: {proposed_value}. " \
                f"Should be {choices_value}"
        elif isinstance(choices_value, list) and len(choices_value) > 0:
            assert proposed_value in choices_value, \
                f"{self.yaml_field} has an invalid value: {proposed_value}. " \
                f"Should be one of {str(choices_value[:5])}"
        else:
            assert proposed_value is not None or not self.__required, \
                f"A value is required for {self.yaml_field}. "

        # if callable(self.__validation_function):
        #    self.__validation_function(self, proposed_value)

    def prepare(self):
        """
        Call the initialize routine once per prompt to get defaults and choices.
        Ignore any errors.

        :rtype: None
        """
        try:
            self.initialize()
        except Exception as e:
            debug(str(e))

    def get_validator(self):
        """
        Get a validator.  If none is implemented, then use a DummyValidator
        because prompt toolkit seems to want one once one has been set.
        :return:
        """
        validator = self.validator()
        if not validator:
            validator = DummyValidator()
        return validator

    def get_prompt_text(self):
        """
        Get the interactive prompt string for this field.

        :rtype: str
        """
        choices = self.choices()
        if choices is not None:
            print("Options are " + str(choices))

        prompt_text = self.prompt()
        suggestion = self.get_suggestion()
        return f"{prompt_text} [{suggestion}] "

    def get_suggestion(self):
        """
        Get the suggested value for this field as a string.

        :return: suggested value
        :rtype: str
        """
        suggestion = self.suggestion()
        if suggestion is None:
            suggestion = ""
        return suggestion

    def get_help_text(self):
        """
        Get the signpost help for this field.  In an
        interactive session, this will be displayed in
        a bottom-bar.

        :rtype: str
        """
        return " " + str(self.help_text())

    #
    # Override these methods in implementations
    #

    def initialize(self):
        """
        Override to do any one-time initialization for this object.
        :rtype: None
        """
        pass

    def prompt(self):
        """
        Override to set the short __description of this question.
        :return: formatted text string
        """
        raise Exception("'prompt' must be defined")

    def comment(self):
        """
        Override to print a comment in interactive sessions before
        the prompt.  It will not be repeated if there is a validation
        error.
        :return: formatted text string
        """
        return None

    def validator(self):
        """
        Override to return a response validator.  This validator
        should accept all legal values.

        Any values failing the validator will be re-prompted in
        an interactive session or cause a failure in non-interactive
        ones.
        :return: Subclass of Validator or None
        """
        return None

    def choices(self):
        """
        Override to return a set of choices, one of which must be the answer.

        If set, this will augment any returned validator to verify
        the response is one of the choices.
        :return:
        """
        return None

    def suggestion(self):
        """
        Override to the suggested value for this field.
        Usually this is the current value, but if one hasn't been
        entered, then the default is returned.

        :return: suggested value
        :rtype: str
        """
        return None

    def help_text(self):
        """
        Override to set the signpost help for this field.  In an
        interactive session, this will be displayed in
        a bottom-bar.

        :rtype: str
        """
        return None
