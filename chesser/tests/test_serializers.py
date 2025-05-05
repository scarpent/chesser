import pytest

from chesser import serializers


@pytest.mark.parametrize(
    "upcoming_text, expected",
    [
        ("1. e4 {Strong opening move} e5", False),
        ("opening move} e5 {is a good response...}", True),
        ("opening move} e5", True),
        ("no context so no brackets", False),
        ("{something", False),
        ("still {something", False),
    ],
)
def test_is_in_comment(upcoming_text, expected):
    assert serializers.is_in_comment(upcoming_text) == expected
