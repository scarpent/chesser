from datetime import timedelta

from django import forms
from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from djangoql.admin import DjangoQLSearchMixin

from .models import Chapter, Course, Move, QuizResult, SharedMove, Variation


class RecentVariationFilter(SimpleListFilter):
    title = "recent variations"
    parameter_name = "variation"

    def lookups(self, request, model_admin):
        recent_threshold = timezone.now() - timedelta(days=30)
        recent = Variation.objects.filter(created_at__gte=recent_threshold).order_by(
            "-created_at"
        )
        return [(v.id, f"{v.chapter.title}: {v.title}") for v in recent]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(variation__id=self.value())
        return queryset


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


class MoveForm(forms.ModelForm):
    class Meta:
        model = Move  # or SharedMove — use the same class for both
        fields = "__all__"
        widgets = {
            "fen": forms.TextInput(attrs={"size": 80}),
            "san": forms.TextInput(attrs={"size": 7}),
            "annotation": forms.TextInput(attrs={"size": 7}),
            "alt": forms.Textarea(attrs={"rows": 1, "cols": 40}),
            "alt_fail": forms.Textarea(attrs={"rows": 1, "cols": 40}),
        }


class RegularMoveForm(MoveForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        instance = self.instance
        if (
            instance
            and instance.pk
            and instance.fen
            and instance.san
            and instance.variation
            and instance.variation.chapter
            and instance.variation.chapter.course
        ):
            color = instance.variation.chapter.course.color
            self.fields["shared_move"].queryset = SharedMove.objects.filter(
                fen=instance.fen,
                san=instance.san,
                opening_color=color,
            )
        else:
            self.fields["shared_move"].queryset = SharedMove.objects.none()


class MoveInline(admin.TabularInline):
    model = Move
    form = MoveInlineForm
    extra = 0  # Number of empty forms to display
    readonly_fields = ("move_id", "shared_link")
    fields = (
        "move_id",
        "shared_link",
        "sequence",
        "move_num",
        "san",
        "annotation",
        "text",
        "alt",
        "alt_fail",
        "shapes",
    )

    @admin.display(description="ID")
    def move_id(self, obj):
        if not obj.id:
            return ""

        url = reverse("admin:chesser_move_change", args=[obj.id])
        return format_html('<a href="{}">{}</a>', url, obj.id)

    @admin.display(description="Shared")
    def shared_link(self, obj):
        shared = obj.shared_move
        if not shared:
            return "-"
        url = reverse("admin:chesser_sharedmove_change", args=[shared.id])
        preview = shared.text.strip().replace("\n", " ")
        preview = preview[:40] + "…" if len(preview) > 40 else preview
        return format_html('<a href="{}" title="{}">#{}</a>', url, preview, shared.id)


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
    readonly_fields = ("created_at", "view_on_site_link")

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

    @admin.display(description="View on site")
    def view_on_site_link(self, obj):
        if not obj.id:
            return ""
        url = reverse("variation", args=[obj.id])
        return format_html(
            '<a href="{}" target="_blank">Variation #{}</a>', url, obj.id
        )


@admin.register(Move)
class MoveAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
    form = RegularMoveForm
    list_display = (
        "san",
        "shared_move_link",
        "move_num",
        "has_text",
        "has_annotation",
        "has_alt",
        "has_alt_fail",
        "has_shapes",
        "variation",
    )
    list_filter = (RecentVariationFilter,)
    readonly_fields = ("view_on_site_link", "matching_moves_link")

    @admin.display(description="Text?", boolean=True)
    def has_text(self, obj):
        return bool(obj.text)

    @admin.display(description="Ann?", boolean=True)
    def has_annotation(self, obj):
        return bool(obj.annotation)

    @admin.display(description="Alt?", boolean=True)
    def has_alt(self, obj):
        return bool(obj.alt)

    @admin.display(description="Alt Fail?", boolean=True)
    def has_alt_fail(self, obj):
        return bool(obj.alt_fail)

    @admin.display(description="Shapes?", boolean=True)
    def has_shapes(self, obj):
        return bool(obj.shapes)

    @admin.display(description="View on site")
    def view_on_site_link(self, obj):
        if not obj.id:
            return ""

        variation_id = obj.variation.id
        idx = obj.sequence
        url = reverse("variation", args=[variation_id]) + f"?idx={idx}"

        return format_html(
            '<a href="{}" target="_blank">Variation #{}</a>', url, variation_id
        )

    @admin.display(description="Matching Moves")
    def matching_moves_link(self, obj):
        fen = obj.fen
        san = obj.san
        color = obj.variation.chapter.course.color
        query = (
            f'fen="{fen}" and san="{san}" and variation.chapter.course.color="{color}"'
        )
        url = reverse("admin:chesser_move_changelist") + f"?q={query}"
        return format_html('<a href="{}">Find matching fen/san/color</a>', url)

    @admin.display(description="Shared")
    def shared_move_link(self, obj):
        if not obj.shared_move_id:
            return "-"
        url = reverse("admin:chesser_sharedmove_change", args=[obj.shared_move_id])
        return format_html(
            '<a href="{}" target="_blank">#{}</a>', url, obj.shared_move_id
        )


@admin.register(QuizResult)
class QuizResultAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
    list_display = ("variation", "datetime", "level", "passed")
    list_filter = (RecentVariationFilter, "passed", "level")
    readonly_fields = ("variation", "datetime", "level", "passed")
    fields = ("variation", "datetime", "level", "passed")


@admin.register(SharedMove)
class SharedMoveAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
    form = MoveForm
    list_display = ("san", "fen", "short_text")
    inlines = [MoveInline]

    def short_text(self, obj):
        return obj.text.strip()[:60] + "..." if obj.text else ""

    short_text.short_description = "Text Preview"
