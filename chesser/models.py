from django.db import models


class Course(models.Model):
    course_id = models.IntegerField(unique=True)
    title = models.CharField(max_length=100)
    color = models.CharField(max_length=5)

    def __str__(self):
        return self.title


class Chapter(models.Model):
    chapter_id = models.IntegerField(unique=True)
    title = models.CharField(max_length=100)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.course.title}: {self.title}"


class Variation(models.Model):
    variation_id = models.IntegerField(unique=True)
    title = models.CharField(max_length=100)
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE)
    alternative = models.BooleanField(default=False)
    informational = models.BooleanField(default=False)
    start_move = models.IntegerField(default=1)
    end_move = models.IntegerField(default=99)
    # TODO: annotation for evaluation at the end position (could do this for
    # the move, but the last move might have another annotation...)

    def __str__(self):
        return f"{self.chapter.course.title}: {self.chapter.title}: {self.title}"

    @property
    def mainline_moves(self):
        moves = self.moves.order_by("move_id")
        white_to_move = True
        move_string = ""
        for move in moves:
            if white_to_move:
                prefix = f"{move.move_num}."
                white_to_move = False
            else:
                prefix = ""
                white_to_move = True
            move_string += f"{prefix}{move.san} "

        return move_string


class Move(models.Model):
    move_id = models.IntegerField(unique=True)
    move_num = models.IntegerField()
    variation = models.ForeignKey(
        Variation, on_delete=models.CASCADE, related_name="moves"
    )
    san = models.CharField(max_length=10)
    annotation = models.CharField(max_length=10, null=True, blank=True)
    text = models.TextField(null=True, blank=True)
    # TODO: draw/arrows/circles...

    def __str__(self):
        return (
            f"{self.variation.variation_id}: {self.variation.title}: "
            f"{self.move_num} {self.san}"
        )


# class VariationHistory(models.Model):
#     variation_id = models.IntegerField(unique=True)
#     datetime = models.DateTimeField(auto_now_add=True)
#     level = models.IntegerField()  # 0 start, 1 first rep (4 hours)
#     passed = models.BooleanField(default=False)


# class MoveHistory(models.Model):
#     move_id = models.IntegerField(unique=True)
#     variation_history = models.ForeignKey(VariationHistory, on_delete=models.CASCADE)
#     datetime = models.DateTimeField(auto_now_add=True)
#     level = models.IntegerField()  # 0 start, 1 first rep (4 hours)
#     passed = models.BooleanField(default=False)
