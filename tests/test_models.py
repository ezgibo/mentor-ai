"""Schemas: rubric scoring in code and request validation."""

import pytest
from pydantic import ValidationError

from models import MessageIn, RatingsIn, RubricScores


def test_overall_score_is_rounded_average():
    assert RubricScores(accuracy=8, depth=6, structure=7, communication=9).overall() == 8
    assert RubricScores(accuracy=1, depth=1, structure=1, communication=1).overall() == 1


def test_overall_score_is_clamped_to_1_to_10():
    assert RubricScores(accuracy=0, depth=0, structure=0, communication=0).overall() == 1
    assert RubricScores(accuracy=12, depth=12, structure=12, communication=12).overall() == 10


def test_ratings_must_be_1_to_5():
    assert RatingsIn(ratings={1: 3, 2: 5}).ratings == {1: 3, 2: 5}
    with pytest.raises(ValidationError):
        RatingsIn(ratings={1: 6})
    with pytest.raises(ValidationError):
        RatingsIn(ratings={})


def test_message_cannot_be_empty():
    with pytest.raises(ValidationError):
        MessageIn(message="")
