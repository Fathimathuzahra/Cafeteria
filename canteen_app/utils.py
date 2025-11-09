# utils.py
# utils.py
from datetime import datetime
from .models import MealToken
import uuid

def generate_unique_meal_token_code():
    """
    Generates a unique token code using UUID or retry method.
    """
    for _ in range(10):  # try 10 times
        code = f"T-{uuid.uuid4().hex[:6].upper()}"
        if not MealToken.objects.filter(code=code).exists():
            return code
    # fallback if repeated collision
    return f"T-{uuid.uuid4().hex[:8].upper()}"


# utils.py
def get_role_from_username(username):
    if username.startswith("AWHCF"):
        return "college_staff"
    elif username.startswith("AWHCS"):
        return "student"
    else:
        return "unknown"

# utils.py
from datetime import time
from django.utils import timezone
def is_lunch_token_active(username):
    role = get_role_from_username(username)
    if role not in ['student', 'college_staff']:  # Fixed role names
        return False  # unknown users cannot access

    now = timezone.localtime(timezone.now()).time()

    if role == 'college_staff':  # Fixed role name
        start_time = time(12, 0)
        end_time = time(15, 0)
    elif role == 'student':
        start_time = time(12, 0)
        end_time = time(14, 0)

    return start_time <= now <= end_time

# views.py (or canteen_app/utils.py)
from .models import MealToken
from .utils import generate_unique_meal_token_code
# utils.py
def create_meal_token(order):
    """
    Create a meal token for an order, or return existing one if it already exists.
    """
    # Check if a meal token already exists for this order
    try:
        existing_token = MealToken.objects.get(order=order)
        return existing_token  # Return existing token instead of creating new one
    except MealToken.DoesNotExist:
        # Only create new token if one doesn't exist
        code = generate_unique_meal_token_code()
        token = MealToken.objects.create(order=order, code=code, status='pending')
        return token
