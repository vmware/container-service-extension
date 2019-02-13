# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause


import re

from prompt_toolkit.validation import Validator

from container_service_extension.interview.interaction import Interaction


class Question(Interaction):

    def __init__(self, yaml_field,
                 prompt=None,
                 required=True,
                 initialize=None,
                 choices=None,
                 default=None,
                 example=None,
                 description=None,
                 validation=None, validation_function=None,
                 validation_message=None,
                 skip_function=None):
        Interaction.__init__(self)
        self.yaml_field = yaml_field
        self.__prompt = prompt
        self.__required = required
        self.__initialize = initialize
        self.__choices = choices
        self.__default = default
        self.__example = example
        self.__description = description
        self.__validation = validation
        self.__validation_function = validation_function
        self.__validation_message = validation_message
        self.__skip_function = skip_function

    def initialize(self):
        if self.__initialize is not None:
            (self.__initialize)(self)

    def comment(self):
        return None

    def validator(self):
        """
        Override to return a response validator.
        :return:
        """
        if self.__validation and self.__validation_message:
            return Validator.from_callable(
                lambda x: (re.match(self.__validation, x)),
                error_message=self.__validation_message)

        return None

    def prompt(self):
        if self.__prompt:
            return self.__prompt
        else:
            return self.yaml_field

    def choices(self):
        # Materialize the __choices if we have a lambda
        if callable(self.__choices):
            return self.__choices()
        return self.__choices

    def set_choices(self, choices):
        """ Set the choices from an external function """
        self.__choices = choices

    def default(self):
        return self.__default

    def set_default(self, value):
        """ Set the default value from an external function """
        self.__default = value

    def generate(self):
        """
        TODO- refactor
        Create a sample value and set the field in the
        result without human interaction.

        :rtype: None
        """
        # Materialize the __choices if we have a lambda
        if callable(self.__choices):
            choices_value = self.__choices(self)
        else:
            choices_value = self.__choices

        if isinstance(choices_value, str):
            self.context.set_yaml_value(self.yaml_field, choices_value)
        elif isinstance(choices_value, list) and len(self.__choices) > 0:
            self.context.set_yaml_value(self.yaml_field, choices_value[0])
        elif len(self.sample) > 0:
            self.context.set_yaml_value(self.yaml_field, self.sample)
        elif len(self.__default) > 0:
            self.context.set_yaml_value(self.yaml_field, self.__default)
        else:
            assert not self.__required, \
                f"no generated value determined for ${self.yaml_field}" \
                    f"set a __default or sample value."

        self.context.next_question(self)

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
        choices_value = self.choices()

        if self.__validation:
            assert re.match(self.__validation, proposed_value), \
                f"{self.yaml_field} has an invalid value: {proposed_value}. " \
                f"Doesn't match pattern' {self.__validation}"

        if isinstance(choices_value, str):
            assert proposed_value == choices_value, \
                f"{self.yaml_field} has an invalid value: {proposed_value}. " \
                f"Should be {choices_value}"
        elif isinstance(choices_value, list) and len(choices_value) > 0:
            assert proposed_value in choices_value, \
                f"{self.yaml_field} has an invalid value: {proposed_value}. " \
                f"Should be one of {str(choices_value[:5])}"
        else:
            assert proposed_value or not self.__required, \
                f"A value is required for {self.yaml_field}. "

        if callable(self.__validation_function):
            self.__validation_function(self, proposed_value)

    def suggestion(self):
        """
        Get the suggested value for this field.
        Usually this is the current value, but if one hasn't been
        entered, then the __default is returned.

        :return: suggested value
        :rtype: str
        """
        suggestion = self.get_value()
        if not suggestion:
            suggestion = self.__default
        return suggestion

    def help_text(self):
        return None

    def get_value(self):
        """
        Get the current value defined in the YAML
        :return: value or None if one hasn't been set
        :rtype: str
        """
        return self.context.get_yaml_value(self.yaml_field)

    def set_value(self, answer):
        """
        Set the current value defined in the YAML
        :param answer: value or None to update the field value
        :type answer: str
        """
        return self.context.set_yaml_value(self.yaml_field, answer)
