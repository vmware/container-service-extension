# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from prompt_toolkit import PromptSession
from prompt_toolkit.input.defaults import create_pipe_input
from pytest import raises

from container_service_extension.interview.comment import Comment
from container_service_extension.interview.confirmation import Confirmation
from container_service_extension.interview.question import Question
from container_service_extension.interview.top_level_context import \
    TopLevelContext


class MemoryContext(TopLevelContext):
    def __init__(self, questions, input_pipe, seed_data=None):
        session = PromptSession(input=input_pipe)
        TopLevelContext.__init__(self, questions, content=seed_data,
                                 session=session)


def feed_session_with_input(questions, input_text, seed_data=None):
    input_pipe = create_pipe_input()
    input_pipe.send_text(input_text)
    return MemoryContext(questions, input_pipe, seed_data=seed_data)


def test_positive_case():
    """
    Just verify that the simplest use case passes.
    :return:
    """
    q = Question("question", validation=r"answer")
    feed_session_with_input([q], "answer\n")

    response = q.ask()
    q.validate(response)
    q.set_value(response)

    assert response == "answer"


def test_existing_value_passes():
    """
    Verify that no answer works if there was a saved value.
    :return:
    """
    q = Question("question", validation=r"previous")
    feed_session_with_input([q], "\n", seed_data=[{"question": "previous"}])

    response = q.ask()
    assert response == "previous"

    q.validate(response)
    q.set_value(response)


def test_existing_value_is_validated():
    """
    Verify that no answer works if there was a saved value.
    :return:
    """
    q = Question("question", validation="answer")
    feed_session_with_input([q], "\n", seed_data=[{"question": "previous"}])

    response = q.ask()
    assert response == "previous"

    with raises(AssertionError):
        q.validate(response)


def test_invalid_response():
    q = Question("question", validation=r"answer")
    feed_session_with_input([q], "not-answer\n")

    response = q.ask()
    assert response == "not-answer"

    with raises(AssertionError):
        q.validate(response)


def test_response_is_choice_string():
    q = Question("question", choices="answer")
    feed_session_with_input([q], "answer\n")

    response = q.ask()
    assert response == "answer"

    q.validate(response)
    q.set_value(response)


def test_response_is_not_choice_string():
    q = Question("question", choices="answer")
    feed_session_with_input([q], "not-answer\n")

    response = q.ask()
    assert response == "not-answer"

    with raises(AssertionError):
        q.validate(response)


def test_response_in_choice_array():
    q = Question("question", choices=["nope", "answer", "nada"])
    feed_session_with_input([q], "answer\n")

    response = q.ask()
    assert response == "answer"

    q.validate(response)
    q.set_value(response)


def test_response_not_in_choice_array():
    q = Question("question", choices=["nope", "nada"])
    feed_session_with_input([q], "answer\n")

    response = q.ask()
    assert response == "answer"

    with raises(AssertionError):
        q.validate(response)


def test_comment_takes_no_input():
    c = Comment("comment")
    q = Question("question", validation="answer")
    feed_session_with_input([c, q], "answer\n")

    response = q.ask()
    q.validate(response)
    q.set_value(response)
    assert response == "answer"


def test_confirmation_yes():
    q = Confirmation()
    feed_session_with_input([q], "\n")

    response = q.ask()
    q.validate(response)
    q.set_value(response)
    assert q.is_done()


def test_confirmation_no():
    q = Confirmation()
    feed_session_with_input([q], "\x03\n")

    response = q.ask()
    q.validate(response)
    q.set_value(response)
    assert not q.is_done()
