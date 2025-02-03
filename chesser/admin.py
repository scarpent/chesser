from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Chapter, Course, Move, Variation


class ChapterInline(admin.TabularInline):
    model = Chapter
    extra = 1  # Number of empty forms to display
    readonly_fields = ("chapter_link",)

    def chapter_link(self, obj):
        link = reverse("admin:chesser_chapter_change", args=[obj.id])
        return format_html('<a href="{}">{}</a>', link, obj.title)

    chapter_link.short_description = "Chapter"


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("course_id", "title", "color")
    search_fields = ("title",)
    inlines = [ChapterInline]


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ("chapter_id", "title", "course")
    search_fields = ("title",)
    list_filter = ("course",)


@admin.register(Variation)
class VariationAdmin(admin.ModelAdmin):
    list_display = (
        "variation_id",
        "title",
        "chapter",
        "alternative",
        "informational",
        "start_move",
        "end_move",
    )
    search_fields = ("title",)
    list_filter = ("chapter", "alternative", "informational")


@admin.register(Move)
class MoveAdmin(admin.ModelAdmin):
    list_display = ("move_id", "move_num", "variation", "san", "annotation", "text")
    search_fields = ("san",)
    list_filter = ("variation",)
