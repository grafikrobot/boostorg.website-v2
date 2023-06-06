from django.contrib.auth import get_user_model
from django import forms

from .models import Preferences
from news.models import NEWS_MODELS
from news.acl import can_approve


User = get_user_model()

NEWS_ENTRY_CHOICES = [(m.news_type, m._meta.verbose_name.title()) for m in NEWS_MODELS]


class PreferencesForm(forms.ModelForm):
    allow_notification_own_news_approved = forms.MultipleChoiceField(
        choices=NEWS_ENTRY_CHOICES,
        widget=forms.widgets.CheckboxSelectMultiple,
        label="Your own news is approved after moderation",
        required=False,
    )
    allow_notification_others_news_posted = forms.MultipleChoiceField(
        choices=NEWS_ENTRY_CHOICES,
        widget=forms.widgets.CheckboxSelectMultiple,
        label="Other users publish their news",
        required=False,
    )
    allow_notification_others_news_needs_moderation = forms.MultipleChoiceField(
        choices=NEWS_ENTRY_CHOICES,
        widget=forms.widgets.CheckboxSelectMultiple,
        label="There are new entries pending moderation",
    )

    def __init__(self, *args, instance=None, **kwargs):
        if instance is not None:
            initial = kwargs.pop("initial", {})
            for field in self.Meta.fields:
                initial[field] = getattr(instance, field)
            kwargs["initial"] = initial
        super().__init__(*args, instance=instance, **kwargs)
        if not instance or not can_approve(instance.user):
            self.fields.pop("allow_notification_others_news_needs_moderation")

    def save(self, *args, **kwargs):
        for field, value in self.cleaned_data.items():
            setattr(self.instance, field, value)
        return super().save(*args, **kwargs)

    class Meta:
        model = Preferences
        fields = [
            "allow_notification_own_news_approved",
            "allow_notification_others_news_posted",
            "allow_notification_others_news_needs_moderation",
        ]


class UserProfilePhotoForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["image"]
