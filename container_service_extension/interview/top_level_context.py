# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings

from container_service_extension.interview.interaction_context import \
    InteractionContext

global next_question
global question_stack


def get_global_next_interaction():
    global next_question
    return next_question


def set_global_next_interaction(interaction):
    global next_question
    next_question = interaction


def perform_interview(content, questions):
    """
    Performs an interactive interview.

    :param str content: config contents (as array of objects).
    :param str questions: array of questions.

    :return: sample config as dict.
    :rtype: dict
    """

    interview = TopLevelContext(content, questions)
    interview.set_shared_value("mode", "interview")
    interview.run()

    return interview.get_content()


bindings = KeyBindings()


@bindings.add('up')
def _go_to_previous_question(event):
    """
    Go to previous question when the `up arrow` is pressed.

    Pop the last two items off of the question stack,
    configure the next question global variables, then
    exit the current question.
    """
    global next_question
    global question_stack
    next_question = question_stack[-2]
    del question_stack[-1]
    del question_stack[-1]

    event.app.exit()


@bindings.add('c-j')
def _suppress_carriage_return(_):
    """ Ignore CR events.  This was necessary to run in PyCharm. """
    pass


class TopLevelContext(InteractionContext):
    """
    Top level context for editing a configuration file
    """

    def __init__(self, questions, session=None, content=None):
        InteractionContext.__init__(self)
        self.__content = content if content else [{}]
        self.__shared_values = {}
        self.__failed = False

        if session is None:
            self.session = PromptSession(key_bindings=bindings)  # style=style
        else:
            self.session = session

        self.questions = questions
        for q in questions:
            q.set_context(self)

    def get_top_context(self):
        return self

    def get_session(self):
        return self.session

    def get_shared_value(self, key):
        return self.__shared_values[key]

    def set_shared_value(self, flag, value):
        self.__shared_values[flag] = value

    def get_content(self):
        return self.__content

    def get_failed(self):
        return self.__failed

    def get_yaml_value(self, yaml_field):
        """
        Get the yaml field value.

        The yaml_field should be a dot-separated value, like "foo.bar",
        and can contain array indexes, like "foo[4].bar"
        """
        try:
            return _get_object_field(self.__content[0], yaml_field)
        except Exception as e:
            raise IndexError("Error looking for " + str(yaml_field)) from e

    def set_yaml_value(self, yaml_field, value):
        """
        Set a yaml field value.

        The yaml_field should be a dot-separated value, like "foo.bar"
        """
        try:
            _set_object_field(self.__content[0], yaml_field, value)
        except Exception as e:
            raise IndexError(f"Error setting {yaml_field} to {value}") from e

    def set_yaml_value_default(self, yaml_field, value):
        """
        Set a yaml field value if a value is not already defined.

        The yaml_field should be a dot-separated value, like "foo.bar",
        and can contain array indexes, like "foo[4].bar"
        """
        try:
            if _get_object_field(self.__content[0], yaml_field) is "":
                _set_object_field(self.__content[0], yaml_field, value)
        except Exception as e:
            raise IndexError("Error looking for " + str(yaml_field)) from e

    def next_question(self, current_question):
        global next_question

        if current_question is None:
            return self.questions[0]

        for i in range(0, len(self.questions)):
            if self.questions[i] == current_question:
                if i + 1 < len(self.questions):
                    next_question = self.questions[i + 1]
                    return
                else:
                    return  # No more questions

    def generate_content(self):
        """
        Loop through all of the questions, and generate values as
        they are visited
        """
        question = self.next_question(None)

        # Main repl loop
        while question is not None:
            question.generate()

    def validate_content(self):
        """
        Loop through all of the questions, and validate values as
        they are visited
        """
        question = self.next_question(None)

        # Main repl loop
        while question is not None:
            value = question.context.get_yaml_value(question.yaml_field)
            question.validate(value)

    def run(self):
        """
        Loop through all of the questions, and return the top level context
        """
        global question_stack
        global next_question

        question_stack = []
        next_question = self.next_question(None)

        # Main repl loop
        while next_question is not None:
            # if the question is already in the stack, delete it
            # and everything after it, before appending.
            try:
                i = question_stack.index(next_question)
                question_stack = question_stack[:i]
            except ValueError:
                pass

            question_stack.append(next_question)

            # prepare the current question
            current_interaction = next_question
            next_question = None

            try:
                result = current_interaction.ask()

                # next_question can be set during ask() if there was a
                # key binding event (up-arrow), or as a result of failed
                # validations
                if next_question is None:
                    try:
                        current_interaction.validate(result)
                        current_interaction.set_value(result)
                    except AssertionError as e:
                        print(str(e))
                        next_question = current_interaction

                # next_question can be set during set_value for groups
                if next_question is None:
                    current_interaction.context.next_question(
                        current_interaction)

            except KeyboardInterrupt:
                # Ctrl-c gracefully exits by not setting next question
                self.__failed = True
                pass


def _get_object_field(container, yaml_field):
    """
    Parse the yaml_field value as a path, then
    get the value from the corresponding entry
    in the container object using recursion.

    :param container: dictionary containing dictionary and array
                      values.
    :param yaml_field: path specification for an entry in the container
                      dictionary
    :return: Value from container at the path, or None
    """
    assert type(yaml_field) is str
    if not type(container) is dict:
        return ""

    parts = yaml_field.split('.', 1)
    if len(parts) > 1:
        array_marker = parts[0].find('[')
        if array_marker >= 0:
            array_name = parts[0][:array_marker].strip()
            array_spec = parts[0][array_marker:].strip()
            if array_name not in container:
                return ""
            return _get_array_field(container[array_name], array_spec,
                                    parts[1])

        if not parts[0] in container:
            return ""
        return _get_object_field(container[parts[0]], parts[1])
    else:
        if yaml_field in container:
            return container[yaml_field]
        return ""


def _get_array_field(container, array_spec, yaml_field):
    """
    Parse the yaml_field value as a path, then
    set the value of the corresponding entry
    in the container object.

    :param container: dictionary containing dictionary and array
                      values.
    :param array_spec specification for array (e.g. '[3]')
    :param yaml_field: path specification for an entry in the container
                      dictionary
    :return: value at the specified array_spec in the container
    """
    assert type(container) is list
    assert type(array_spec) is str
    assert array_spec[0] == '['
    assert type(yaml_field) is str

    array_end_marker = array_spec.find(']')
    assert array_end_marker > 1, f"misformed array specification: {array_spec}"

    # Today we don't deal with multi-variant arrays, but we could in the future
    assert array_end_marker == len(array_spec) - 1

    array_index = int(array_spec[1: array_end_marker])
    if array_index < len(container):
        return _get_object_field(container[array_index], yaml_field)

    return ""


def _set_object_field(container, yaml_field, value):
    """
    Parse the yaml_field value as a path, then
    set the value of the corresponding entry
    in the container object.

    :param container: dictionary containing dictionary and array
                      values.
    :param yaml_field: path specification for an entry in the container
                      dictionary
    :param value:     value to create or update at the specified
                      path in the container
    :return: None
    """
    assert type(container) is dict
    assert type(yaml_field) is str

    parts = yaml_field.split('.', 1)
    if len(parts) > 1:
        array_marker = parts[0].find('[')
        if array_marker >= 0:
            array_name = parts[0][:array_marker].strip()
            array_spec = parts[0][array_marker:].strip()
            if array_name not in container:
                container[array_name] = []
            _set_array_field(container[array_name], array_spec, parts[1],
                             value)

        else:
            if not parts[0] in container:
                container[parts[0]] = {}
            _set_object_field(container[parts[0]], parts[1], value)
    else:
        assert yaml_field.find(
            '[') < 0, "Array must not be last element in field"
        container[yaml_field] = value


def _set_array_field(container, array_spec, yaml_field, value):
    """
    Parse the yaml_field value as a path, then
    set the value of the corresponding entry
    in the container object.

    :param container: dictionary containing dictionary and array
                      values.
    :param array_spec specification for array (e.g. '[3]')
    :param yaml_field: path specification for an entry in the container
                      dictionary
    :param value:     value to create or update at the specified
                      path in the container
    :return: None
    """
    assert type(container) is list
    assert type(array_spec) is str
    assert array_spec[0] == '['
    assert type(yaml_field) is str

    array_end_marker = array_spec.find(']')
    assert array_end_marker > 1, f"misformed array specification: {array_spec}"

    # Today we don't deal with multi-variant arrays, but we could in the future
    assert array_end_marker == len(array_spec) - 1

    array_index = int(array_spec[1: array_end_marker])
    if len(container) == array_index:
        container.append(dict())

    if len(container) < array_index:
        raise Exception("Too few items in array")

    _set_object_field(container[array_index], yaml_field, value)
