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
    start = models.IntegerField(default=2)
    end = models.IntegerField(default=99)
    # TODO:
    #
    # ➤ annotation for evaluation at the end position (could do this for
    # the move, but the last move might have another annotation...) maybe
    # it can be a standard annotation symbol but also free text, with
    # lichess stats for the position (win/draw/loss) ...
    #
    # ➤ think about "soft" fails, or alternative moves - can improve on
    # chessable here; if a "hard fail", clearly show if the move was as
    # good or really bad, etc. UI will have a way to toggle and show more
    # (also! consider a way to track soft fails and have some stats and/or
    # some kind of practice mode for these...)
    #
    # ➤ "source" chessable course, etc, maybe a link, too?

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

    @property
    def start_index(self):
        """
        translate move numbers to index for quiz start and end

        idx  white      black      for white, e.g.:
        0    1.e4       1.d4       ➤ if start move is 2, quiz starts at idx 0,
        1    1...e5     1...d5       the white move before the opposing move
        2    2.Nf3      2.c4         that will be shown when the quiz starts
        3    2...Nc6    2...e6     ➤ if end move is 4, quiz ends at idx 6
        4    3.d4       3.Nc3
        5    3...exd4   3...Nf6    for black:
        6    4.Nxd4     4.Nf3      ➤ if start move is 2, quiz starts at idx 1
        7    4...Nf6    4...a6     ➤ if end move is 4, quiz ends at idx 7

        expecting with white to always start on at least move 2, but with black
        might want to start on move 1 and will have to revisit how js quiz
        handling works
        """
        ply = self.start * 2
        return ply - 4 if self.chapter.course.color == "white" else ply - 3

    @property
    def end_index(self):
        ply = self.end * 2
        return ply - 2 if self.chapter.course.color == "white" else ply - 1


class Move(models.Model):
    move_id = models.IntegerField(unique=True)
    move_num = models.IntegerField()
    variation = models.ForeignKey(
        Variation, on_delete=models.CASCADE, related_name="moves"
    )
    san = models.CharField(max_length=10)
    annotation = models.CharField(max_length=10, null=True, blank=True)
    text = models.TextField(null=True, blank=True)
    alt = models.JSONField(default=dict)  # e.g. {"d4": 1, "Nf3": 1, "c4": 1}
    alt_fail = models.JSONField(default=dict)
    # fen?
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
# TODO: a field to "mark" this variation from the UI after doing it, to easily find it to review something -- e.g. reviewing on the phone and you want to go back and review more and compare to similar lines... maybe it's even a text field so can add comments...  # noqa: E501
# TODO: should also show missed moves


# class MoveHistory(models.Model):
#     move_id = models.IntegerField(unique=True)
#     variation_history = models.ForeignKey(VariationHistory, on_delete=models.CASCADE)
#     datetime = models.DateTimeField(auto_now_add=True)
#     level = models.IntegerField()  # 0 start, 1 first rep (4 hours)
#     passed = models.BooleanField(default=False)
