# canteen_app/forms.py
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from .models import MenuItem, Review

User = get_user_model()

# -------------------
# Registration Form
# -------------------
class RegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput, label="Confirm Password")
    
    class Meta:
        model = User
        fields = ['username', 'phone']  # 'role' is not exposed in the form

    def clean_username(self):
        username = self.cleaned_data['username'].lower().replace("-", "").strip()
    
        # If username starts with student or faculty prefix, enforce format
        if username.startswith("AWHCS"):
            student_number = username.replace("AWHCS", "")
            if not student_number.isdigit() or len(student_number) != 4:
                raise ValidationError("Invalid student number format. Must be AWHCS followed by 4 digits.")
        
        elif username.startswith("AWHCF"):
            faculty_number = username.replace("AWHCF", "")
            if not faculty_number.isdigit() or len(faculty_number) != 3:
                raise ValidationError("Invalid faculty number format. Must be AWHCF followed by 3 digits.")
        
        # For other usernames (canteen staff), no restrictions
        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")
        
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        username = self.cleaned_data['username'].lower().replace("-", "").strip()
        user.username = username

        # Assign role based on username pattern
        if username.startswith("AWHCS") or username.startswith("AWHCF"):
            user.role = "user"
        else:
            user.role = "canteenstaff"

        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user

# -------------------
# Login Form
# -------------------
class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'})
    )

# -------------------
# Review Form (NEW - ADD THIS)
# -------------------
class ReviewForm(forms.ModelForm):
    RATING_CHOICES = [
        (1, '1 Star - Poor'),
        (2, '2 Stars - Fair'),
        (3, '3 Stars - Good'),
        (4, '4 Stars - Very Good'),
        (5, '5 Stars - Excellent')
    ]
    
    rating = forms.ChoiceField(
        choices=RATING_CHOICES,
        widget=forms.RadioSelect,
        initial=5
    )
    
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Share your experience with the canteen service...',
                'class': 'form-control'
            }),
        }
        labels = {
            'comment': 'Your Review',
            'rating': 'Rating'
        }

    def clean_rating(self):
        rating = self.cleaned_data['rating']
        # Convert to integer since ChoiceField returns string
        rating = int(rating)
        if rating < 1 or rating > 5:
            raise forms.ValidationError("Rating must be between 1 and 5")
        return rating

    def clean_comment(self):
        comment = self.cleaned_data['comment']
        if not comment.strip():
            raise forms.ValidationError("Comment cannot be empty")
        if len(comment) > 500:
            raise forms.ValidationError("Comment too long (max 500 characters)")
        return comment

# -------------------
# Menu Forms (Staff/Admin)
# -------------------
class MainMenuForm(forms.ModelForm):
    class Meta:
        model = MenuItem
        fields = ["name", "description", "price", "category", "image"]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'price': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }

class DailyMenuForm(forms.ModelForm):
    class Meta:
        model = MenuItem
        fields = ["name", "description", "price", "category", "image",
                  "available_quantity", "available"]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'price': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'available_quantity': forms.NumberInput(attrs={'min': '0'}),
        }

# -------------------
# Order Form (Student Checkout)
# -------------------
class OrderForm(forms.Form):
    items = forms.ModelMultipleChoiceField(
        queryset=MenuItem.objects.filter(available=True),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Select Menu Items"
    )