from django import forms
from poetry.models import Poem, Verse
from .models import MemorizationItem, ReviewLog

class MemorizationItemForm(forms.Form):
    poem_id = forms.ModelChoiceField(queryset=Poem.objects.none())
    scope = forms.ChoiceField(choices=MemorizationItem.SCOPES)
    start_verse_id = forms.ModelChoiceField(queryset=Verse.objects.none(), required=False)
    end_verse_id = forms.ModelChoiceField(queryset=Verse.objects.none(), required=False)

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['poem_id'].queryset = Poem.objects.filter(owner=owner, archived_at__isnull=True)
        for name in ['start_verse_id', 'end_verse_id']:
            self.fields[name].queryset = Verse.objects.filter(poem__owner=owner)

    def clean(self):
        data = super().clean()
        if data.get('scope') == 'full' and (data.get('start_verse_id') or data.get('end_verse_id')):
            raise forms.ValidationError('کارت کامل نباید مرز بازه داشته باشد.')
        return data

class ReviewRatingForm(forms.Form):
    rating = forms.ChoiceField(choices=ReviewLog.RATINGS)
    request_id = forms.UUIDField()
