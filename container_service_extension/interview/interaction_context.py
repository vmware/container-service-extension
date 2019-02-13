# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause


class InteractionContext:
    """Context that a question is being asked in.

    Contains the __prompt environment any yaml prefix.
    """

    def __init__(self, yaml_prefix=''):
        self.yaml_prefix = yaml_prefix

        # Ensure that if there is a prefix then ends with a dot
        if yaml_prefix and not yaml_prefix.endswith('.'):
            self.yaml_prefix += '.'

        self.parent_context = None

    def set_context(self, context):
        self.parent_context = context

    def get_top_context(self):
        return self.parent_context.get_top_context()

    def get_session(self):
        """
        Returns the prompt_toolkit session object to use
        """
        return self.parent_context.get_session()

    def get_shared_value(self, key):
        """
        Returns a globally shared value related to the interview
        instance (not part of the configuration file.

        :param key: key to look up in top level context
        :return: value of key or None
        """
        return self.parent_context.get_shared_value(key)

    def get_yaml_value(self, key):
        """
        Get the value of a yaml key in this context
        from the underlying configuration file
        """
        return self.parent_context.get_yaml_value(self.yaml_prefix + key)

    def set_yaml_value(self, key, value):
        """
        Set the value of a yaml key in this context
        in the underlying configuration file
        """
        self.parent_context.set_yaml_value(self.yaml_prefix + key, value)

    def set_yaml_value_default(self, key, value):
        """
        Set the value of a yaml key in this context
        in the underlying configuration file
        """
        self.parent_context.set_yaml_value_default(self.yaml_prefix + key,
                                                   value)

    def next_question(self, current_question):
        """
        Advance to the next question in the context
        """
        self.parent_context.next_question(self)
