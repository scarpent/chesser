from django import forms
from django.contrib import admin
from django.db import models
from django.urls import reverse
from django.utils.html import format_html
from djangoql.admin import DjangoQLSearchMixin

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
            "san": forms.TextInput(attrs={"size": 7}),
            "annotation": forms.TextInput(attrs={"size": 7}),
            "text": forms.Textarea(attrs={"rows": 3, "cols": 40}),
            "alt": forms.Textarea(attrs={"rows": 1, "cols": 15}),
            "alt_fail": forms.Textarea(attrs={"rows": 1, "cols": 15}),
            "shapes": forms.Textarea(attrs={"rows": 3, "cols": 15}),
        }


class MoveInline(admin.TabularInline):
    model = Move
    form = MoveInlineForm
    extra = 0  # Number of empty forms to display


class VariationInline(admin.TabularInline):
    model = Variation
    extra = 0  # Number of empty forms to display
    fields = (
        "title",
        "course",
        "start_move",
        "level",
        "next_review",
        "mainline_moves_display",
    )
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
class CourseAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
    list_display = ("title", "color")
    inlines = [ChapterInline]


@admin.register(Chapter)
class ChapterAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
    list_display = ("title", "course")
    list_filter = ("course",)
    inlines = [VariationInline]


@admin.register(Variation)
class VariationAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "clickable_title",
        "chapter",
        "ply",
        "start_move",
        "level",
        "next_review",
    )
    list_filter = ("chapter",)
    inlines = [MoveInline, QuizResultInline]
    readonly_fields = ("created_at",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_ply=models.Count("moves"))

    @admin.display(ordering="_ply")
    def ply(self, obj):
        return obj._ply

    @admin.display(description="Title")
    def clickable_title(self, obj):
        link = reverse("admin:chesser_variation_change", args=[obj.id])
        return format_html('<a href="{}">{}</a>', link, obj.title)


@admin.register(Move)
class MoveAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
    list_display = ("san", "annotation", "move_num", "variation")
    list_filter = ("variation",)


@admin.register(QuizResult)
class QuizResultAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
    list_display = ("variation", "datetime", "level", "passed")
    list_filter = ("variation", "passed", "level")
    readonly_fields = ("variation", "datetime", "level", "passed")
    fields = ("variation", "datetime", "level", "passed")
