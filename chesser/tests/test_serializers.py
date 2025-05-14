import pytest

from chesser import serializers
from chesser.models import Chapter, Course, Move, Variation


@pytest.mark.django_db
def test_exercise_serializers():
    """
    just to exercise things a bit until we write proper tests...
    """
    course = Course.objects.create(title="Test Course", color="white")
    chapter = Chapter.objects.create(title="Test Chapter", course=course)
    variation = Variation.objects.create(
        title="Test Variation",
        course=course,
        chapter=chapter,
        start_move=2,
        mainline_moves_str="1.e4 e5",
    )
    Move.objects.create(
        variation=variation,
        move_num=1,
        sequence=0,
        san="e4",
        text="(1...d5 2.exd5 {Lorem ipsum}) (1.d4 d5 (1...c5))",
    )
    fen = "r1bqkbnr/pp1ppp1p/2n3p1/2p5/2P5/2N3P1/PP1PPPBP/R1BQK1NR b KQkq - 1 4"
    Move.objects.create(
        variation=variation,
        move_num=1,
        sequence=1,
        san="e5",
        text="check, mate " + f'<fenseq data-fen="{fen}">4...bg7</fenseq>',
    )
    serializers.serialize_variation(variation, all_data=False)
    serializers.serialize_variation(variation, all_data=True)
    serializers.get_final_move_simple_subvariations_html(variation)
