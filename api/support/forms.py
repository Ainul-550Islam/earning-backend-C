# api/support/forms.py
"""
Django forms for support system.
Used in admin and any non-API HTML form views.
These complement serializers.py (which is for DRF/API).
"""
from django import forms
from django.core.exceptions import ValidationError


class TicketSubmitForm(forms.Form):
    """Public ticket submission form."""
    CATEGORY_CHOICES = [
        ('payment',   'Payment Issue'),
        ('coins',     'Coins Not Added'),
        ('account',   'Account Problem'),
        ('technical', 'Technical Issue'),
        ('withdrawal','Withdrawal Issue'),
        ('kyc',       'KYC Verification'),
        ('fraud',     'Fraud/Security'),
        ('referral',  'Referral Issue'),
        ('offer',     'Offer Issue'),
        ('other',     'Other'),
    ]
    subject     = forms.CharField(max_length=200, min_length=5,
                    widget=forms.TextInput(attrs={'placeholder': 'Brief subject of your issue'}))
    category    = forms.ChoiceField(choices=CATEGORY_CHOICES)
    description = forms.CharField(min_length=10, max_length=10000,
                    widget=forms.Textarea(attrs={'rows': 5, 'placeholder': 'Describe your issue in detail...'}))
    screenshot  = forms.ImageField(required=False)

    def clean_description(self):
        desc = self.cleaned_data.get('description', '').strip()
        if len(desc) < 10:
            raise ValidationError('Description must be at least 10 characters.')
        return desc


class TicketRatingForm(forms.Form):
    """CSAT rating form."""
    SCORE_CHOICES = [(i, str(i)) for i in range(1, 6)]
    score   = forms.ChoiceField(choices=SCORE_CHOICES, widget=forms.RadioSelect)
    comment = forms.CharField(required=False, max_length=500,
                widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional comment...'}))

    def clean_score(self):
        score = int(self.cleaned_data['score'])
        if not 1 <= score <= 5:
            raise ValidationError('Score must be between 1 and 5.')
        return score


class OfferDisputeForm(forms.Form):
    """Offer dispute submission form."""
    offer_id        = forms.CharField(max_length=200, label='Offer ID')
    offer_name      = forms.CharField(max_length=500, required=False, label='Offer Name')
    expected_amount = forms.DecimalField(min_value=1, max_value=100000, decimal_places=2)
    click_id        = forms.CharField(max_length=200, required=False, label='Click ID (optional)')
    description     = forms.CharField(min_length=10, max_length=5000,
                        widget=forms.Textarea(attrs={'rows': 4}))
    proof_screenshot = forms.ImageField(required=False)


class FAQSearchForm(forms.Form):
    """FAQ/KB search form."""
    q        = forms.CharField(max_length=200, required=False, label='Search')
    category = forms.CharField(max_length=50, required=False)


class SupportSettingsUpdateForm(forms.Form):
    """Admin form to update support settings quickly."""
    is_support_online = forms.BooleanField(required=False)
    maintenance_mode  = forms.BooleanField(required=False)
    maintenance_message = forms.CharField(required=False, max_length=500,
                            widget=forms.Textarea(attrs={'rows': 2}))
    chat_widget_enabled = forms.BooleanField(required=False)
    ai_auto_response_enabled = forms.BooleanField(required=False)


class CannedResponseForm(forms.Form):
    """Form to create/edit a canned response."""
    shortcut  = forms.SlugField(max_length=50, label='Shortcut (e.g. /greet)')
    title     = forms.CharField(max_length=200)
    content   = forms.CharField(widget=forms.Textarea(attrs={'rows': 5}))
    category  = forms.CharField(max_length=50, required=False, initial='general')
    is_active = forms.BooleanField(required=False, initial=True)