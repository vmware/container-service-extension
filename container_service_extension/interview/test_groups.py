# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from prompt_toolkit import PromptSession
from prompt_toolkit.input.defaults import create_pipe_input

from container_service_extension.interview.group import Group
from container_service_extension.interview.indexed_group import IndexedGroup
from container_service_extension.interview.question import Question
from container_service_extension.interview.top_level_context import \
    TopLevelContext


class MemoryContext(TopLevelContext):
    def __init__(self, questions, input_pipe, seed_data=None):
        session = PromptSession(input=input_pipe)
        TopLevelContext.__init__(self, questions, content=seed_data,
                                 session=session)


def feed_session_with_input(questions, input_text, seed_data=None):
    """
    Runs a test session.

    For safety, always ends the input with a Ctrl-C.  If the
    session reads past the end of the input text, it will be
    detected by the run loop, and session.get_failed() will be True

    :param questions:
    :param input_text:
    :param seed_data:
    :rtype: TopLevelContext
    """
    input_pipe = create_pipe_input()
    input_pipe.send_text(input_text)
    input_pipe.send_text("\x03")
    return MemoryContext(questions, input_pipe, seed_data=seed_data)


def test_group():
    """
    Just verify that the simplest use case passes.
    :return:
    """

    questions = [
        Question("one", validation=r"ONE"),
        Question("two", validation=r"TWO")
    ]
    g = Group("", questions)
    s = feed_session_with_input([g], "ONE\nTWO\n")
    s.run()
    print(s.get_content())
    assert not s.get_failed()


def test_group_update():
    """
    Just verify that the simplest use case passes.
    :return:
    """

    questions = [
        Question("one", validation=r"ONE"),
        Question("two", validation=r"TWO")
    ]
    g = Group("", questions)
    s = feed_session_with_input([g], "yes\n\n\n",
                                seed_data=[{"one": "ONE", "two": "TWO"}])
    s.run()
    print(s.get_content())
    assert not s.get_failed()


def test_group_failure():
    """
    Just verify that the simplest use case passes.
    :return:
    """

    questions = [
        Question("one", validation=r"ONE"),
        Question("two", validation=r"TWO")
    ]
    g = Group("", questions)
    s = feed_session_with_input([g], "\n\n")
    s.run()
    print(s.get_content())
    assert s.get_failed()


def test_indexed_group():
    """
    Just verify that the simplest use case passes.
    :return:
    """

    g = IndexedGroup("group",
                     questions=[
                         Question("one"),
                         Question("two")
                     ])
    s = feed_session_with_input([g], "add\nalpha\nbeta\n\n")
    s.run()
    print(s.get_content())

    assert str(s.get_content()) \
        == "[{'group': [{'one': 'alpha', 'two': 'beta'}]}]"
    assert not s.get_failed()


def test_multi_indexed_group():
    """
    Verify multiples add and edit functions work.
    :return:
    """

    g = IndexedGroup("group",
                     questions=[
                         Question("one"),
                         Question("two")
                     ])
    s = feed_session_with_input([g],
                                "add\nalpha\nbeta\n"
                                "add\ngamma\nomega\n"
                                "0\nuno\ndos\n\n")
    s.run()
    print(s.get_content())

    assert str(s.get_content()) == \
        "[{'group': [{'one': 'uno', 'two': 'dos'}, " \
        "{'one': 'gamma', 'two': 'omega'}]}]"
    assert not s.get_failed()
