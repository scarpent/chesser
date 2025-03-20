from django.db import models
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
    """

    title = models.CharField(max_length=100)
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)  # Denormalized field
    start_move = models.IntegerField(
        default=2, help_text="Reviews start at this move number"
    )
    level = models.IntegerField(default=0, db_index=True)
    next_review = models.DateTimeField(default=timezone.now, db_index=True)
    source = models.JSONField(null=True, blank=True, default=dict)
    mainline_moves_str = models.TextField(null=True, blank=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["course", "mainline_moves_str"],
                name="unique_moves_string_per_course",
            ),
        ]

    def __str__(self):
        course_title = self.course.title if self.course_id else "(no course)"
        chapter_title = self.chapter.title if self.chapter_id else "(no chapter)"
        return f"{course_title}: {chapter_title}: {self.title} ({self.id})"

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

    def get_latest_quiz_result(self):
        return self.quiz_results.order_by("-datetime").first()

    def get_latest_quiz_result_datetime(self):
        latest_result = self.get_latest_quiz_result()
        return latest_result.datetime if latest_result else None

    @classmethod
    def due_for_review(cls):
        now = timezone.now()
        return cls.objects.filter(next_review__lte=now).order_by("next_review").first()

    @classmethod
    def due_counts(cls):
        """Returns a tuple of (total due now, total due soon)

        Soon will vary depending on the number due now, e.g. if
        only 1 review is due now, very soon might be 1 minute, since
        it will come up as we finish the current review. Reviews can
        vary quite a bit in how long to do, say 10 seconds to 5 minutes,
        depending on length/lookups/analysis.

        We'll not look too far ahead, we want this to be fairly immediate.
        """
        now = timezone.now()
        total_due_now = cls.objects.filter(next_review__lte=now).count()

        if total_due_now < 5:
            relatively_soon = 2
        if total_due_now < 10:
            relatively_soon = 5
        else:
            relatively_soon = 10

        soon = now + timezone.timedelta(minutes=relatively_soon)
        total_due_soon = cls.objects.filter(
            next_review__gte=now, next_review__lte=soon
        ).count()

        return total_due_now, total_due_soon


class Move(models.Model):
    move_num = models.IntegerField()
    sequence = models.IntegerField()  # expected to be in order from 0 to n
    variation = models.ForeignKey(
        Variation, on_delete=models.CASCADE, related_name="moves"
    )
    san = models.CharField(max_length=10)
    annotation = models.CharField(max_length=10, default="", blank=True)
    text = models.TextField(null=True, blank=True)
    alt = models.TextField(null=True, blank=True)  # e.g. d4, Nf3, c4
    alt_fail = models.TextField(null=True, blank=True)  # ["f4", "b3", "g3"]
    # chessground drawable shapes (arrows/circles are implied by origin/dest)
    # e.g. [{"orig":"f4","brush":"green"},{"orig":"c5","dest":"d3","brush":"red"}]
    shapes = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ("variation", "sequence")
        ordering = ["sequence"]

    def __str__(self):
        return (
            f"{self.variation.title} ({self.variation_id}): "
            f"{self.move_num} {self.san}"
        )

    @property
    def move_verbose(self):
        white_to_move = self.sequence % 2 == 0
        dots = "." if white_to_move else "..."
        return f"{self.move_num}{dots}{self.san}{self.annotation}"


class QuizResult(models.Model):
    variation = models.ForeignKey(
        Variation, on_delete=models.CASCADE, related_name="quiz_results"
    )
    datetime = models.DateTimeField(auto_now_add=True, db_index=True)
    level = models.IntegerField()  # 0 unlearned, 1 first rep (4 hours)
    passed = models.BooleanField(default=False)
