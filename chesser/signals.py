from django.core.exceptions import ValidationError
from django.db.models.signals import pre_save
from django.dispatch import receiver

from chesser.models import Variation


@receiver(pre_save, sender=Variation)
def validate_course_chapter(sender, instance, **kwargs):
    if instance.course != instance.chapter.course:
        raise ValidationError("Variation's course must match its chapter's course.")
