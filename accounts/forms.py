from django import forms


class EmailLoginForm(forms.Form):
    email = forms.EmailField(label='ایمیل', max_length=254, widget=forms.EmailInput(attrs={'autocomplete': 'email', 'dir': 'ltr'}))

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if len(email) > 254:
            raise forms.ValidationError('نشانی ایمیل طولانی است.')
        return email
