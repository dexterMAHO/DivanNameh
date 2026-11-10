from django import forms
from .models import Poem, Tag
from .services.poem_editor import parse_verses, validate_verses

class PoemForm(forms.ModelForm):
    new_tag = forms.CharField(label='ساخت تگ جدید (اختیاری)', max_length=60, required=False)
    input_mode = forms.ChoiceField(label='روش ورود', choices=[('structured', 'ورود بیت به بیت'), ('lines', 'هر خط یک بیت؛ جداکنندهٔ |'), ('pairs', 'هر دو خط یک بیت')])
    bulk_text = forms.CharField(label='متن شعر', widget=forms.Textarea(attrs={'rows': 8}), required=False)

    class Meta:
        model = Poem
        fields = ['title', 'poet_name', 'source_url', 'notes', 'tags']
        widgets = {'notes': forms.Textarea(attrs={'rows': 3}), 'tags': forms.CheckboxSelectMultiple()}

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tags'].queryset = Tag.objects.filter(owner=owner)
        for field in self.fields.values():
            field.error_messages.update(required='این فیلد الزامی است.', invalid='مقدار واردشده معتبر نیست.', invalid_choice='گزینهٔ انتخاب‌شده معتبر نیست.')

    def clean_source_url(self):
        url = self.cleaned_data['source_url']
        if url and not url.startswith(('https://', 'http://')):
            raise forms.ValidationError('نشانی منبع باید با http یا https آغاز شود.')
        return url

    def clean(self):
        data = super().clean()
        mode = data.get('input_mode')
        if mode == 'structured':
            first, second = self.data.getlist('hemistich_1'), self.data.getlist('hemistich_2')
            if len(first) != len(second):
                raise forms.ValidationError('ساختار ابیات معتبر نیست.')
            data['verses'] = validate_verses(list(zip(first, second)))
        elif mode:
            data['verses'] = parse_verses(data.get('bulk_text', ''), mode)
        if self.instance.pk and len(data.get('verses', [])) < self.instance.verses.count():
            raise forms.ValidationError('حذف بیت در ویرایش مجاز نیست.')
        return data

class TagForm(forms.Form):
    name = forms.CharField(label='نام تگ', max_length=60)
