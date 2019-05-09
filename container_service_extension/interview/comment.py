# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import re

from prompt_toolkit import print_formatted_text

from container_service_extension.interview.interaction import Interaction


class Comment(Interaction):
    """
    Basic question class to (optionally) print a comment during the interview
    """

    def __init__(self, description,
                 skip_function=None):
        Interaction.__init__(self, required=False)
        self.description = description
        self.skip_function = skip_function

    def generate(self):
        """
        Do nothing unless we are interactive
        """
        pass

    def ask(self):
        """
        Show the message to the interactive user
        """
        self.prepare()

        expanded = self.description
        # Expand {} using the global context
        # TODO: expand {{}} using local context, {shared.} as shared variables
        while True:
            m = re.search('{(.*?)}', expanded)
            if not m:
                break

            value = self.context.get_top_context().get_yaml_value(m.group(1))
            if not value:
                # If the value cannot be found, replace with parens and keep searching
                value = "(" + m.group(1) + ")"

            expanded = expanded[:m.start()] + value + expanded[m.end():]

        if not self.skip_function or not self.skip_function(self):
            print_formatted_text(expanded)

    def set_value(self, answer):
        """
        The interview always sets the user entered value, so we ignore it
        """
        pass
