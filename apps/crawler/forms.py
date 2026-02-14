from django import forms

from .models import Topic


class TopicForm(forms.ModelForm):
    """Form for creating/editing topics."""

    keywords_input = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-textarea',
            'rows': 3,
            'placeholder': 'Enter keywords, one per line'
        }),
        help_text='Enter one keyword or phrase per line'
    )

    class Meta:
        model = Topic
        fields = ['name', 'is_active', 'crawl_frequency_hours', 'max_pages_per_crawl']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., Startup Funding News'
            }),
            'crawl_frequency_hours': forms.NumberInput(attrs={
                'class': 'form-input',
                'min': 1,
                'max': 168
            }),
            'max_pages_per_crawl': forms.NumberInput(attrs={
                'class': 'form-input',
                'min': 1,
                'max': 50
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['keywords_input'].initial = '\n'.join(self.instance.keywords or [])

    def clean_keywords_input(self):
        keywords_text = self.cleaned_data['keywords_input']
        keywords = [k.strip() for k in keywords_text.split('\n') if k.strip()]
        if not keywords:
            raise forms.ValidationError('At least one keyword is required')
        return keywords

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.keywords = self.cleaned_data['keywords_input']
        if commit:
            instance.save()
        return instance
