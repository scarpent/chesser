import pytest

from chesser.importer import NORMALIZED_ANNOTATIONS, normalize_annotation


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, ""),
        ("", ""),
        ("   ", ""),
        ("\n\t", ""),
    ],
)
def test_normalize_annotation_blankish_returns_empty_string(value, expected):
    assert normalize_annotation(value) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        # Counterplay
        ("⇆", "⇄"),
        ("  ⇆  ", "⇄"),
        # Winning advantage
        ("+-", "±"),
        ("-+", "∓"),
        # Slight advantage
        ("+=", "⩲"),
        ("+/=", "⩲"),
        ("=+/", "⩲"),
        ("=+", "⩱"),
        ("=/+", "⩱"),
        # Equality
        ("==", "="),
        # Checkmate
        ("++", "#"),
        # With the idea (delta variants)
        ("Δ", "△"),
        # Only move
        ("[]", "□"),
        # Zugzwang
        ("ZZ", "⊙"),
        # Unclear
        ("~", "∞"),
    ],
)
def test_normalize_annotation_normalizes_known_variants(raw, expected):
    assert normalize_annotation(raw) == expected


def test_normalize_annotation_leaves_unknown_tokens_unchanged():
    assert normalize_annotation("?!") == "?!"
    assert normalize_annotation("foo") == "foo"
    assert normalize_annotation("±") == "±"  # already canonical
    assert normalize_annotation("⇄") == "⇄"  # already canonical


def test_normalize_annotation_matches_defined_mapping_completely():
    """
    Guard against forgetting to add a test case when the mapping dict changes.

    This ensures every key in NORMALIZED_ANNOTATIONS is exercised at least once,
    and that whitespace trimming doesn't affect correctness.
    """
    for k, v in NORMALIZED_ANNOTATIONS.items():
        assert normalize_annotation(k) == v
        assert normalize_annotation(f"  {k}  ") == v


def test_normalize_annotation_does_not_replace_inside_longer_strings():
    """
    It's a token normalizer, not a text replacer.
    """
    assert normalize_annotation("x+-y") == "x+-y"
    assert normalize_annotation("mate++!") == "mate++!"
    assert normalize_annotation("maybe~unclear") == "maybe~unclear"
