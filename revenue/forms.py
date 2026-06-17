from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import DataUpload


class UploadExcelForm(forms.ModelForm):
    class Meta:
        model = DataUpload
        fields = ["file"]
        widgets = {
            "file": forms.ClearableFileInput(attrs={"accept": ".xlsx,.xls", "class": "file-input"})
        }

    def clean_file(self):
        file = self.cleaned_data["file"]
        name = file.name.lower()
        if not name.endswith((".xlsx", ".xls")):
            raise forms.ValidationError("Le fichier doit être au format Excel .xlsx ou .xls")
        if file.size > 30 * 1024 * 1024:
            raise forms.ValidationError("Le fichier dépasse 30 MB.")
        return file


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user
