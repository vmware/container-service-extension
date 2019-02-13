# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import pytest

from container_service_extension.interview.top_level_context import \
    _set_object_field, _get_object_field


def test_top_level_yaml():
    """
    Verifies basic fields work in yaml
    """
    content = {}
    _set_object_field(content, "foo", "bar")
    assert _get_object_field(content, "foo") == "bar"


def test_missing_top_level_yaml():
    """
    Verifies that missing fields return empty string
    """
    content = {}
    assert _get_object_field(content, "foo") == ""


def test_multi_level_yaml():
    """
    Verifies that multi-level fields (i.e. with dots) work
    """
    content = {}
    _set_object_field(content, "foo.bar", "baz")
    assert _get_object_field(content, "foo.bar") == "baz"


def test_adding_child_to_element_yaml():
    """
    Verifies that setting a child to an existing element causes an Exception
    """
    content = {}
    _set_object_field(content, "foo", "baz")
    assert _get_object_field(content, "foo") == "baz"

    with pytest.raises(AssertionError):
        _set_object_field(content, "foo.bar", "baz")


def test_missing_multi_level_yaml():
    """
    Test that various related values don't interfere with missing values
    """
    content = {}
    assert _get_object_field(content, "foo.bar") == ""

    _set_object_field(content, "foo", "baz")
    assert _get_object_field(content, "foo.bar") == ""

    content = {}
    _set_object_field(content, "foo.foo", "baz")
    assert _get_object_field(content, "foo.bar") == ""


def test_arrays():
    """
    Verifies basic arrays work in yaml
    """
    content = {}
    _set_object_field(content, "foo[0].bar", "baz")
    assert _get_object_field(content, "foo[0].bar") == "baz"

    array_result = _get_object_field(content, "foo")
    assert isinstance(array_result, list)
    assert len(array_result) == 1


def test_missing_arrays():
    """
    Verifies missing array entries work in yaml
    """
    content = {}
    assert _get_object_field(content, "foo[0]") == ""

    _set_object_field(content, "foo[0].bar", "baz")
    assert _get_object_field(content, "foo[0].bar") == "baz"
    assert _get_object_field(content, "foo[0].foo") == ""
    assert _get_object_field(content, "foo[1].bar") == ""
