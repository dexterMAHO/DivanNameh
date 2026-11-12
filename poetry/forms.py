from django import forms
from .models import Poem, Tag
from .services.poem_editor import parse_verses, validate_verses

class PoemForm(forms.ModelForm):
    new_tag = forms.CharField(label='ساخت موضوع جدید (اختیاری)', max_length=60, required=False)
    input_mode = forms.ChoiceField(label='روش ورود', choices=[('structured', 'ورود بیت به بیت'), ('lines', 'هر خط یک بیت؛ جداکنندهٔ |'), ('pairs', 'هر دو خط یک بیت')])
    line_layout = forms.BooleanField(label='چیدمان سطری برای شعر نو', required=False)
    bulk_text = forms.CharField(label='متن شعر', widget=forms.Textarea(attrs={'rows': 8}), required=False)

    class Meta:
        model = Poem
        fields = ['title', 'poet_name', 'source_url', 'notes', 'tags', 'line_layout']
        widgets = {'notes': forms.Textarea(attrs={'rows': 3}), 'tags': forms.CheckboxSelectMultiple()}

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tags'].queryset = Tag.objects.filter(owner=owner)
        for field in self.fields.values():
            field.error_messages.update(required='این فیلد الزامی است.', invalid='مقدار واردشده معتبر نیست.', invalid_choice='گزینهٔ انتخاب‌شده معتبر نیست.')

    def clean_line_layout(self):
        if self.instance.pk and 'layout_control' not in self.data and 'line_layout' not in self.data:
            return self.instance.line_layout
        return self.cleaned_data['line_layout']

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
            data['verses'] = validate_verses(list(zip(first, second)), minimum=self.instance.verses.count() if self.instance.pk else 0)
        elif mode:
            data['verses'] = parse_verses(data.get('bulk_text', ''), mode, line_layout=data.get('line_layout', False))
        if data.get('line_layout') and any(second for _, second in data.get('verses', [])):
            raise forms.ValidationError('در چیدمان سطری، هر ردیف فقط یک سطر دارد.')
        if self.instance.pk and len(data.get('verses', [])) < self.instance.verses.count():
            raise forms.ValidationError('حذف بیت در ویرایش مجاز نیست.')
        return data

class TagForm(forms.Form):
    name = forms.CharField(label='نام موضوع', max_length=60)
