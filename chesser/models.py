from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import UniqueConstraint
from django.utils import timezone

REPETITION_INTERVALS = {  # Level value is hours
    1: 4,  # Or maybe try 6? or...?
    2: 1 * 24,
    3: 3 * 24,
    4: 7 * 24,
    5: 14 * 24,
    6: 30 * 24,
    7: 60 * 24,
    8: 120 * 24,
    9: 180 * 24,
}
# chessable: 4h, 19h, 2d23h, 6d23h, 13d23h, 29d23h, 89d23h, 179d23h


class Course(models.Model):
    title = models.CharField(max_length=100)
    color = models.CharField(max_length=5)

    def __str__(self):
        return self.title


class Chapter(models.Model):
    title = models.CharField(max_length=100)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)

    def __str__(self):
        course_title = self.course.title if self.course_id else "(no course)"
        return f"{course_title}: {self.title}"


class Variation(models.Model):
    """
    Level 0 = "unlearned" / never reviewed - it's one time only, and we
    move on to 1 from there, and return to 1 when we fail a review

    source structure:
    {
        "my_course": {
            "course": course,
            "chapter": chapter,
            "variation_title": variation_title,
            "variation_id": variation_id,
        },
        "original_course": {},  # same as above
    }

    Why include a denormalized `course` field when `chapter` already links to it?

    * Faster queries: avoids joins when checking e.g. variation uniqueness in a course
    * Efficient indexing: enables direct index on (course, move_sequence), etc.
    * Simpler code: fewer joins in filters, easier filtering in templates & serializers
    * Still safe: `chapter.course_id == variation.course_id` is enforced in validation
    """

    title = models.CharField(max_length=100)
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)  # Denormalized field
    is_intro = models.BooleanField(default=False)
    start_move = models.IntegerField(
        default=2, help_text="Reviews start at this move number"
    )
    level = models.IntegerField(default=0, db_index=True)
    next_review = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    source = models.JSONField(null=True, blank=True, default=dict)
    mainline_moves_str = models.TextField(null=True, blank=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["course", "mainline_moves_str"],
                name="unique_moves_string_per_course",
            ),
        ]

    def clean(self):
        if self.chapter.course != self.course:
            raise ValidationError(
                "Variation's denormalized course must match its chapter's course."
            )

    def __str__(self):
        # beware: keep this simple -- ran into all kinds of django admin
        # list issues in prod when trying to reference course/chapter,
        # probably having to do with lazy loading, yada yada
        # (dev sqlite more forgiving than prod postgres)
        # specifically: QuizResult and Move list views were getting 500s
        return f"{self.title} ({self.id})"

    @property
    def mainline_moves(self):  # TODO: maybe don't need this anymore...
        if not self.mainline_moves_str:
            white_to_move = True
            move_string = ""
            for move in self.moves.iterator():
                prefix = f"{move.move_num}." if white_to_move else ""
                white_to_move = not white_to_move
                move_string += f"{prefix}{move.san} "
            self.mainline_moves_str = move_string.strip()
            self.save(update_fields=["mainline_moves_str"])
        return self.mainline_moves_str

    @property
    def start_index(self):
        """
        Translate move numbers to index of array of moves sent to client

        idx  white      black      for white, e.g.:
        0    1.e4       1.d4       ➤ move 2 = 2 * 2 - 2 = 2
        1    1...e5     1...d5     ➤ move 4 = 4 * 2 - 2 = 6
        2    2.Nf3      2.c4
        3    2...Nc6    2...e6
        4    3.d4       3.Nc3
        5    3...exd4   3...Nf6    for black:
        6    4.Nxd4     4.Nf3      ➤ move 2 = 2 * 2 - 1 = 3
        7    4...Nf6    4...a6     ➤ move 4 = 4 * 2 - 1 = 7
        """
        ply = self.start_move * 2
        return ply - 2 if self.chapter.course.color == "white" else ply - 1

    @transaction.atomic
    def handle_quiz_result(self, passed):
        previous_level = self.level if self.level >= 0 else 0
        new_level = previous_level + 1 if passed else 1
        self.level = new_level

        max_level = max(REPETITION_INTERVALS.keys())
        hours = REPETITION_INTERVALS.get(new_level, REPETITION_INTERVALS[max_level])
        self.next_review = timezone.now() + timezone.timedelta(hours=hours)

        self.save()

        QuizResult.objects.create(
            variation=self,
            passed=passed,
            level=previous_level,
        )

    def get_latest_quiz_result_datetime(self):
        latest_result = self.quiz_results.order_by("-datetime").first()
        return latest_result.datetime if latest_result else None

    @classmethod
    def due_for_review(cls):
        return (
            cls.objects.filter(next_review__lte=timezone.now())
            .order_by("next_review")
            .first()
        )

    @classmethod
    def due_counts(cls):
        """Returns a tuple of (total due now, total due soon)

        Soon will vary depending on the number due now, e.g. if
        only 1 review is due now, soon might be 1 minute since
        it will come up as we finish the current review. Reviews
        can vary quite a bit in how long to do, say 15 seconds to
        5 minutes, depending on length/lookups/analysis.

        We'll not look too far ahead, we want this to be fairly immediate.
        """
        now = timezone.now()
        total_due_now = cls.objects.filter(next_review__lte=now).count()

        if total_due_now < 5:
            relatively_soon = 2
        elif total_due_now < 10:
            relatively_soon = 5
        else:
            relatively_soon = 8

        soon = now + timezone.timedelta(minutes=relatively_soon)
        total_due_soon = cls.objects.filter(
            next_review__gte=now, next_review__lte=soon
        ).count()

        return total_due_now, total_due_soon


class QuizResult(models.Model):
    variation = models.ForeignKey(
        Variation, on_delete=models.CASCADE, related_name="quiz_results"
    )
    datetime = models.DateTimeField(default=timezone.now, editable=False, db_index=True)
    level = models.IntegerField()  # 0 unlearned, 1 first rep. interval, etc
    passed = models.BooleanField(default=False)


class AnnotatedMove(models.Model):
    fen = models.CharField(db_index=True)
    san = models.CharField(max_length=10)
    annotation = models.CharField(max_length=10, default="", blank=True)
    text = models.TextField(default="", blank=True)
    alt = models.TextField(default="", blank=True)  # e.g. d4, Nf3, c4
    alt_fail = models.TextField(default="", blank=True)
    # chessground drawable shapes (arrows/circles are implied by origin/dest)
    # e.g. [{"orig": "f4", "brush":"green"},
    #       {"orig": "c5", "dest": "d3", "brush": "red"}]
    shapes = models.TextField(default="", blank=True)

    class Meta:
        abstract = True

    def shareable_fields_match(self, other_move: "AnnotatedMove") -> bool:
        """
        Check if the shareable fields of this move are equal to another move.
        """
        shareable_fields = ["annotation", "text", "alt", "alt_fail", "shapes"]
        return all(
            getattr(self, field) == getattr(other_move, field)
            for field in shareable_fields
        )


class Move(AnnotatedMove):
    move_num = models.IntegerField()
    sequence = models.IntegerField()  # expected to be in order from 0 to n
    variation = models.ForeignKey(
        Variation, on_delete=models.CASCADE, related_name="moves"
    )
    shared_move = models.ForeignKey(
        "SharedMove",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="moves",
    )

    class Meta:
        unique_together = ("variation", "sequence")
        ordering = ["sequence"]

    def __str__(self):
        return (
            f"{self.variation.title} ({self.variation_id}): "
            f"{self.move_num} {self.san}"
        )

    def get_resolved_field(self, field_name: str) -> str:
        field_defaults = {
            "text": "",
            "annotation": "",
            "alt": "",
            "alt_fail": "",
            "shapes": "[]",
        }
        assert (
            field_name in field_defaults
        ), f"Field '{field_name}' is not resolvable via shared_move"
        default = field_defaults[field_name]

        if self.shared_move:
            return getattr(self.shared_move, field_name) or default
        return getattr(self, field_name) or default

    @property
    def white_to_move(self):
        return self.sequence % 2 == 0

    @property
    def move_verbose(self):
        dots = "." if self.white_to_move else "..."
        return f"{self.move_num}{dots}{self.san}"

    @property
    def opening_color(self):
        return self.variation.chapter.course.color


class SharedMove(AnnotatedMove):
    opening_color = models.CharField(max_length=5)

    def __str__(self):
        assert self.fen, "SharedMove must have a FEN string"

        try:
            fields = self.fen.split(" ")
            move_number = int(fields[5])
            dots = "." if fields[1] == "b" else "..."
        except Exception:
            return f"? {self.san}"

        return f"{move_number}{dots}{self.san} #{self.id}"


def get_shared_candidates(fen, san, opening_color):
    candidates = SharedMove.objects.filter(
        fen=fen, san=san, opening_color=opening_color
    ).order_by("id")
    return {
        str(shared_move.id): {
            "annotation": shared_move.annotation,
            "text": shared_move.text,
            "alt": shared_move.alt,
            "alt_fail": shared_move.alt_fail,
            "shapes": shared_move.shapes,
        }
        for shared_move in candidates
    }


def get_matching_moves(fen, san, color, exclude_id=None):
    qs = Move.objects.filter(
        fen=fen,
        san=san,
        variation__chapter__course__color=color,
    )
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    return qs
