from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Chapter, Course, Move, QuizResult, Variation


class ChapterInline(admin.TabularInline):
    model = Chapter
    extra = 0  # Number of empty forms to display
    readonly_fields = ("chapter_link",)

    @admin.display(description="Chapter")
    def chapter_link(self, obj):
        link = reverse("admin:chesser_chapter_change", args=[obj.id])
        return format_html('<a href="{}">{}</a>', link, obj.title)


class MoveInlineForm(forms.ModelForm):
    class Meta:
        model = Move
        fields = "__all__"
        widgets = {
            "text": forms.Textarea(attrs={"rows": 3, "cols": 40}),
            "alt": forms.Textarea(attrs={"rows": 1, "cols": 20}),
            "alt_fail": forms.Textarea(attrs={"rows": 1, "cols": 20}),
        }


class MoveInline(admin.TabularInline):
    model = Move
    form = MoveInlineForm
    extra = 0  # Number of empty forms to display


class VariationInline(admin.TabularInline):
    model = Variation
    extra = 0  # Number of empty forms to display
    readonly_fields = ("mainline_moves_display",)
    ordering = ("title",)

    @admin.display(description="Mainline Moves")
    def mainline_moves_display(self, obj):
        link = reverse("admin:chesser_variation_change", args=[obj.id])
        return format_html('<a href="{}">{}</a>', link, obj.mainline_moves)


class QuizResultInline(admin.TabularInline):
    model = QuizResult
    extra = 0  # Number of empty forms to display
    readonly_fields = ("datetime", "level", "passed")
    ordering = ("-datetime",)  # datetime descending


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "color")
    search_fields = ("title",)
    inlines = [ChapterInline]


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ("title", "course")
    search_fields = ("title",)
    list_filter = ("course",)
    inlines = [VariationInline]


@admin.register(Variation)
class VariationAdmin(admin.ModelAdmin):
    list_display = ("id", "clickable_title", "chapter", "start", "level", "next_review")
    search_fields = ("title",)
    list_filter = ("chapter",)
    inlines = [MoveInline, QuizResultInline]

    @admin.display(description="Title")
    def clickable_title(self, obj):
        link = reverse("admin:chesser_variation_change", args=[obj.id])
        return format_html('<a href="{}">{}</a>', link, obj.title)


@admin.register(Move)
class MoveAdmin(admin.ModelAdmin):
    list_display = ("sequence", "move_num", "variation", "san", "annotation", "text")
    search_fields = ("san",)
    list_filter = ("variation",)


@admin.register(QuizResult)
class QuizResultAdmin(admin.ModelAdmin):
    list_display = ("variation", "datetime", "level", "passed")
    search_fields = ("variation__title",)
    list_filter = ("variation", "passed", "level")
