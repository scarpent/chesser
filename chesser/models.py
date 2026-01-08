from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import UniqueConstraint
from django.utils import timezone


class Chapter(models.Model):
    COLOR_CHOICES = [("white", "White"), ("black", "Black")]

    title = models.CharField(max_length=100)
    color = models.CharField(
        max_length=5, choices=COLOR_CHOICES, null=False, blank=False
    )

    def __str__(self):
        return f"{self.color.title()}: {self.title}"


class Variation(models.Model):
    """
    Level 0 = "unlearned" / never reviewed - it's one time only, and we
    move on to 1 from there, and return to 1 when we fail a review.
    (We can manually reset to 0 if we want to reset our reviews for a line.)

    source structure:
    {
        "my_course": {
            "course": course,
            "chapter": chapter,
            "variation_title": variation_title,
            "variation_id": variation_id,
            "note": note,  # optional
        },
        "original_course": {},  # same as above
        "link": [
            {
                "url": url,
                "text": link text,
            }
        ]  # array is optional
    }

    The `source` field is intentionally flexible. It is stored as JSON to avoid
    prematurely committing to a rigid schema. Conventions may be added over time,
    but existing data should remain backward-compatible.

    Source was originally intended to link Chessable courses, where I often had
    both an original version and a modified personal version of a line. This data
    was imported automatically, and no dedicated UI was initially planned for
    editing it (the Django admin is sufficient if needed).

    The `link` key was added later as a general-purpose attribution/reference
    mechanism (videos, studies, articles). It may eventually warrant a small UI,
    but is currently rendered read-only.
    """

    title = models.CharField(max_length=100)
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE)
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
                fields=["chapter", "mainline_moves_str"],
                name="unique_moves_string_per_chapter",
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.id})"

    @property
    def mainline_moves(self):
        if not self.mainline_moves_str:
            # TODO: maybe don't need this anymore, since we should be
            # able to count on the model being initialized with main
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
        Return the 0-based index into the client ply array corresponding
        to this starting move number and color. FEN plies are 1-based,
        but the client array is 0-based.

        The client represents moves as a flat list of plies:
        [1w, 1b, 2w, 2b, 3w, 3b, ...]

        For a given move number N:
        • White starts at index (N * 2) - 2
        • Black starts at index (N * 2) - 1

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
        return ply - 2 if self.chapter.color == "white" else ply - 1

    @transaction.atomic
    def handle_quiz_result(self, passed):
        previous_level = self.level if self.level >= 0 else 0
        new_level = previous_level + 1 if passed else 1
        self.level = new_level

        max_level = max(settings.REPETITION_INTERVALS.keys())
        hours = settings.REPETITION_INTERVALS.get(
            new_level, settings.REPETITION_INTERVALS[max_level]
        )
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

    def clean(self):
        super().clean()
        if self.shared_move_id:
            if self.fen != self.shared_move.fen:
                raise ValidationError(
                    f"SharedMove FEN mismatch: {self.fen} != {self.shared_move.fen}"
                )
            if self.san != self.shared_move.san:
                raise ValidationError(
                    f"SharedMove SAN mismatch: {self.san} != {self.shared_move.san}"
                )
            if self.variation.chapter.color != self.shared_move.opening_color:
                raise ValidationError(
                    f"SharedMove color mismatch: {self.shared_move.opening_color} "
                    f"!= {self.variation.chapter.color}"
                )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

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
        """
        Canonical move identifier: move number + dots + SAN.

        Annotations like "!" are intentionally excluded because they're
        editorial metadata, not identity. When comparing mainline/root
        moves to subvar moves, compare (num, dots, san) rather than the
        full MoveParts (which includes annotation).
        """
        dots = "." if self.white_to_move else "..."
        return f"{self.move_num}{dots}{self.san}"

    @property
    def opening_color(self):
        return self.variation.chapter.color


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
        variation__chapter__color=color,
    )
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    return qs
