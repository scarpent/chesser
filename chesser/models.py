from django.db import models
from django.utils import timezone

# short intervals for early prototyping and testing...
REPETITION_INTERVALS = {  # level: hours
    1: 1,  # 4, or maybe try 6? or...?
    2: 2,  # 1 * 24,
    3: 4,  # 3 * 24,
    4: 8,  # 7 * 24,
    5: 1 * 24,  # 14 * 24,
    6: 2 * 24,  # 30 * 24,
    7: 3 * 24,  # 60 * 24,
    8: 4 * 24,  # 120 * 24,
    9: 7 * 24,  # 180 * 24,
}


class Course(models.Model):
    title = models.CharField(max_length=100)
    color = models.CharField(max_length=5)

    def __str__(self):
        return self.title


class Chapter(models.Model):
    title = models.CharField(max_length=100)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.course.title}: {self.title}"


class Variation(models.Model):
    """
    level 0 = "unlearned" / never reviewed - it's one time only, and we
    move on to 1 from there, and return to 1 when we fail a review
    """

    title = models.CharField(max_length=100)
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE)
    start = models.IntegerField(
        default=2, help_text="Reviews start at this move number"
    )
    level = models.IntegerField(default=0)
    next_review = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.chapter.course.title}: {self.chapter.title}: {self.title}"

    @property
    def mainline_moves(self):
        white_to_move = True
        move_string = ""
        for move in self.moves.iterator():
            if white_to_move:
                prefix = f"{move.move_num}."
                white_to_move = False
            else:
                prefix = ""
                white_to_move = True
            move_string += f"{prefix}{move.san} "

        return move_string

    @property
    def start_index(self):
        """
        translate move numbers to index

        idx  white      black      for white, e.g.:
        0    1.e4       1.d4       ➤ if start move is 2, quiz starts at idx 0,
        1    1...e5     1...d5       the white move before the opposing move
        2    2.Nf3      2.c4         that will be shown when the quiz starts
        3    2...Nc6    2...e6
        4    3.d4       3.Nc3
        5    3...exd4   3...Nf6    for black:
        6    4.Nxd4     4.Nf3      ➤ if start move is 2, quiz starts at idx 1
        7    4...Nf6    4...a6

        expecting with white to always start on at least move 2,
        but with black might want to start on move 1
        """
        ply = self.start * 2
        return ply - 4 if self.chapter.course.color == "white" else ply - 3

    def handle_quiz_result(self, passed):
        previous_level = self.level
        new_level = previous_level + 1 if passed else 1
        self.level = new_level
        self.next_review = timezone.now() + timezone.timedelta(
            hours=REPETITION_INTERVALS[self.level]
        )
        self.save()

        QuizResult.objects.create(
            variation=self,
            passed=passed,
            level=previous_level,
        )

    @classmethod
    def due_for_review(cls):
        now = timezone.now()
        return cls.objects.filter(next_review__lte=now).order_by("next_review").first()


class Move(models.Model):
    move_num = models.IntegerField()
    sequence = models.IntegerField()
    variation = models.ForeignKey(
        Variation, on_delete=models.CASCADE, related_name="moves"
    )
    san = models.CharField(max_length=10)
    annotation = models.CharField(max_length=10, null=True, blank=True)
    text = models.TextField(null=True, blank=True)
    alt = models.JSONField(default=list, blank=True)  # e.g. ["d4", "Nf3", "c4"]
    alt_fail = models.JSONField(default=list, blank=True)  # ["f4", "b3", "g3"]

    class Meta:
        unique_together = ("variation", "sequence")
        ordering = ["sequence"]

    def __str__(self):
        return (
            f"{self.variation.id}: {self.variation.title}: "
            f"{self.move_num} {self.san}"
        )


class QuizResult(models.Model):
    variation = models.ForeignKey(Variation, on_delete=models.CASCADE)
    datetime = models.DateTimeField(auto_now_add=True)
    level = models.IntegerField()  # 0 unlearned, 1 first rep (4 hours)
    passed = models.BooleanField(default=False)
