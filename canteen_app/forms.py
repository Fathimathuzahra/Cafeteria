# canteen_app/forms.py
from django import forms
from django.contrib.auth import get_user_model
from .models import MenuItem

from django.contrib.auth.forms import AuthenticationForm
User = get_user_model()

from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
import re

User = get_user_model()

from django import forms
from django.core.exceptions import ValidationError
import re
from .models import User

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
        # In RegisterForm.save():
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
# Menu Form (Staff/Admin)
# -------------------
# canteen_app/forms.py
from django import forms
from .models import MenuItem

class MainMenuForm(forms.ModelForm):
    class Meta:
        model = MenuItem
        fields = ["name", "description", "price", "category", "image"]

class DailyMenuForm(forms.ModelForm):
    class Meta:
        model = MenuItem
        fields = ["name", "description", "price", "category", "image",
                  "available_quantity", "available"]

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
