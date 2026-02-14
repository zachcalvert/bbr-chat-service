from django import forms

from .models import KnowledgeEntry


class KnowledgeEntryForm(forms.ModelForm):
    """Form for creating/editing knowledge entries."""

    class Meta:
        model = KnowledgeEntry
        fields = ['title', 'content', 'category', 'source_url']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter a descriptive title'
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 10,
                'placeholder': 'Enter your knowledge content here...'
            }),
            'category': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., Funding, Legal, Marketing'
            }),
            'source_url': forms.URLInput(attrs={
                'class': 'form-input',
                'placeholder': 'https://...'
            }),
        }
