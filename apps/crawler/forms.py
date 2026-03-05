from django import forms

from .models import Topic


class TopicForm(forms.ModelForm):
    """Form for creating/editing topics."""

    keywords_input = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-textarea',
            'rows': 3,
            'placeholder': 'Enter keywords, one per line'
        }),
        help_text='Enter one keyword or phrase per line'
    )

    seed_urls_input = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-textarea',
            'rows': 3,
            'placeholder': 'Enter seed URLs, one per line\ne.g., https://www.reddit.com/r/fantasyfootball/'
        }),
        help_text='Enter one URL per line. The crawler will visit these pages and follow same-domain links.'
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
            self.fields['seed_urls_input'].initial = '\n'.join(self.instance.seed_urls or [])

    def clean_keywords_input(self):
        keywords_text = self.cleaned_data.get('keywords_input', '')
        keywords = [k.strip() for k in keywords_text.split('\n') if k.strip()]
        return keywords

    def clean_seed_urls_input(self):
        urls_text = self.cleaned_data.get('seed_urls_input', '')
        urls = [u.strip() for u in urls_text.split('\n') if u.strip()]
        for url in urls:
            if not url.startswith(('http://', 'https://')):
                raise forms.ValidationError(f'Invalid URL: {url}. URLs must start with http:// or https://')
        return urls

    def clean(self):
        cleaned_data = super().clean()
        keywords = cleaned_data.get('keywords_input', [])
        seed_urls = cleaned_data.get('seed_urls_input', [])
        if not keywords and not seed_urls:
            raise forms.ValidationError('You must provide at least one keyword or seed URL.')
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.keywords = self.cleaned_data['keywords_input']
        instance.seed_urls = self.cleaned_data.get('seed_urls_input', [])
        if commit:
            instance.save()
        return instance
