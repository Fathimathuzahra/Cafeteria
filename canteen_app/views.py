# Standard library imports
from collections import defaultdict
from datetime import datetime, time
from decimal import Decimal, InvalidOperation
import uuid
from datetime import time as dt_time
from datetime import timedelta
import qrcode
import io
import base64
from io import BytesIO
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.hashers import make_password
from django import forms
from django.utils import timezone
import re

# Import your custom User model and other models
from .models import User, MealToken, TokenStatus, DailyReport, MenuItem


from django.contrib.auth.models import User
from canteen_app.models import MenuItem, Order, MealToken, Notification
# Django imports
from django.contrib.auth.hashers import make_password
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.db import transaction
from django.db.models import Count
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model

# Local app imports
from .models import (
    User,
    MenuItem,
    Order,
    OrderItem,
    MealToken,
    Review,
    TokenStatus,
    Notification,
    DailyReport,
    Serving,
    TokenSettings  # ADD THIS IMPORT
)
from .forms import DailyMenuForm, MainMenuForm, RegisterForm
from .utils import generate_unique_meal_token_code, create_meal_token

# =====================
# Role Check Helpers
# =====================
def is_student(user):
    return user.is_authenticated and user.role == "user"

def is_canteen_staff(user):
    return user.is_authenticated and user.role == "canteenstaff"

def is_admin(user):
    return user.is_authenticated and user.role == "admin"

# =====================
# Authentication & General Views
# =====================
def index(request):
    try:
        principal = User.objects.get(username='principal')
    except User.DoesNotExist:
        principal = None 
    context = {
        'principal': principal
    }
    return render(request, "index.html", context)

def about(request):
    return render(request, "about.html")

def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, "Account created successfully! Please log in.")
            return redirect("login")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = RegisterForm()
    return render(request, "register.html", {"form": form})




# =====================
# Authentication Views
# =====================
def login_view(request):
    """
    Handle user login with role-based redirection
    """
    # ✅ Properly clear all old messages before showing login page
    storage = messages.get_messages(request)
    storage.used = True


    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            # -----------------------------
            # Role-based and Pattern-based Logic
            # -----------------------------

            # 1️⃣ Principal (Admin)
            if username.lower() == "principal" or getattr(user, "role", "") == "admin":
                messages.success(request, f"Welcome Principal {username}!")
                return redirect("admin_dashboard")

            # 2️⃣ Students (AWHCSxxxx) or Faculty (AWHCFxxxx)
            elif username.upper().startswith("AWHCS") or username.upper().startswith("AWHCF"):
                if getattr(user, "role", "") != "user":
                    user.role = "user"
                    user.save()
                messages.success(request, f"Welcome {username}!")
                return redirect("user_dashboard")

            # 3️⃣ All others = Canteen Staff
            else:
                if getattr(user, "role", "") != "canteenstaff":
                    user.role = "canteenstaff"
                    user.save()
                messages.success(request, f"Welcome {username}!")
                return redirect("staff_dashboard")

        else:
            messages.error(request, "Invalid username or password.")
            return redirect("login")

    return render(request, "login.html")

def reset_password(request):
    """
    View for resetting user password
    """
    if request.method == 'POST':
        username = request.POST.get('username')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        # Validate form data
        errors = []
        
        # Check if all fields are filled
        if not username or not new_password or not confirm_password:
            errors.append("All fields are required.")
        
        # Check if passwords match
        if new_password != confirm_password:
            errors.append("Passwords do not match.")
        
        # Validate password strength
        if new_password:
            password_errors = validate_password_strength(new_password)
            if password_errors:
                errors.extend(password_errors)
        
        # Check if user exists
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            errors.append("User with this username does not exist.")
        
        # If there are errors, show them
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'forgot_password.html')
        
        # If no errors, update the password
        try:
            user.set_password(new_password)  # Use set_password for proper hashing
            user.save()
            messages.success(request, "Password reset successfully! You can now login with your new password.")
            return redirect('login')
            
        except Exception as e:
            messages.error(request, f"An error occurred while resetting password: {str(e)}")
            return render(request, 'forgot_password.html')
    
    # GET request - show the reset password form
    return render(request, 'forgot_password.html')

def validate_password_strength(password):
    """
    Validate password strength
    """
    errors = []
    
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long.")
    
    if not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter.")
    
    if not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter.")
    
    if not re.search(r'[0-9]', password):
        errors.append("Password must contain at least one number.")
    
    
    return errors

# Form-based reset password view (alternative)
class PasswordResetForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your username',
            'required': True
        })
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter new password',
            'required': True
        })
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password',
            'required': True
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        username = cleaned_data.get('username')
        
        # Check if passwords match
        if new_password and confirm_password and new_password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")
        
        # Validate password strength
        if new_password:
            password_errors = validate_password_strength(new_password)
            if password_errors:
                raise forms.ValidationError(" ".join(password_errors))
        
        # Check if user exists
        if username and not User.objects.filter(username=username).exists():
            raise forms.ValidationError("User with this username does not exist.")
        
        return cleaned_data

def reset_password_with_form(request):
    """
    Alternative view using Django forms
    """
    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            new_password = form.cleaned_data['new_password']
            
            try:
                user = User.objects.get(username=username)
                user.set_password(new_password)
                user.save()
                
                messages.success(request, "Password reset successfully! You can now login with your new password.")
                return redirect('login')
                
            except User.DoesNotExist:
                messages.error(request, "User not found.")
            except Exception as e:
                messages.error(request, f"An error occurred: {str(e)}")
    else:
        form = PasswordResetForm()
    
    return render(request, 'reset_password.html', {'form': form})

def logout_view(request):
    logout(request)
    # Instead of redirecting, render the logout template
    return render(request, 'logout.html') 
# =====================
# Real-time Display
# =====================
def now_serving_display(request):
    """Public display for current serving numbers"""
    current_serving = Serving.objects.first()
    recent_served = MealToken.objects.filter(
        status=TokenStatus.USED,
        served_at__date=timezone.localdate()
    ).order_by('-served_at')[:5]
    
    return render(request, "display/now_serving.html", {
        "current_number": current_serving.current_number if current_serving else 0,
        "recent_served": recent_served
    })
from collections import defaultdict
from django.shortcuts import render
from .models import MenuItem

CATEGORY_DISPLAY = dict(MenuItem.CATEGORY_CHOICES)

def view_menu(request, category=None):
    # Show all items to all users (no availability filter)
    menu_items = MenuItem.objects.all()

    # Filter by category if provided
    if category:
        category_key = category.lower()
        menu_items = menu_items.filter(category__iexact=category_key)

    # Categorize items for template
    categorized_items = defaultdict(list)
    for item in menu_items:
        display_category = CATEGORY_DISPLAY.get(item.category, item.category.title())
        categorized_items[display_category].append(item)

    return render(request, "menu/view_menu.html", {
        "categorized_items": dict(categorized_items),
        "selected_category": category.title() if category else "All",
    })

# --------------------
# User Dashboard
# --------------------
@login_required
@user_passes_test(is_student)
def user_dashboard(request):
    today = timezone.localdate()
    menu_items = MenuItem.objects.filter(date_available=today, available=True)
    tokens = MealToken.objects.filter(order__user=request.user).order_by('-generated_at', 'status')
    
    # Check for expired tokens automatically
    expired_count = 0
    for token in tokens:
        if token.status == TokenStatus.PENDING and token.is_expired:
            if token.mark_expired_auto():
                expired_count += 1
    
    if expired_count > 0:
        messages.warning(request, f"{expired_count} tokens expired automatically.")
    
    # Refresh tokens after updates
    tokens = MealToken.objects.filter(order__user=request.user).order_by('-generated_at', 'status')
    reviews = Review.objects.filter(is_visible=True)

    unread_count = request.user.notifications.filter(is_read=False).count()

    username = request.user.username.upper()
    now = timezone.localtime().time()

    if username.startswith("AWHCS"):
        user_type = "student"
        start_time = time(12, 0)
        end_time = time(14, 0)
    elif username.startswith("AWHCF"):
        user_type = "faculty"
        start_time = time(12, 0)
        end_time = time(15, 0)
    else:
        user_type = "unknown"
        start_time = end_time = now

    token_active = start_time <= now <= end_time

    if user_type == "student" and not token_active:
        messages.warning(request, f"⚠ Sorry, you can activate lunch token only between {start_time.strftime('%I:%M %p')} and {end_time.strftime('%I:%M %p')}.")

    context = {
        "tokens": tokens,
        "menu_items": menu_items,
        "reviews": reviews,
        "selected_category": "All",
        "unread_count": unread_count,
        "user_type": user_type,
        "token_active": token_active,
    }
    return render(request, "customer/user_dashboard.html", context)

@login_required
@user_passes_test(is_student)
def user_menu_list(request):
    today = timezone.localdate()

    # Available items
    items = MenuItem.objects.filter(
        date_available=today,
        available=True,
        available_quantity__gt=0
    )

    categorized_available = defaultdict(list)
    for item in items:
        categorized_available[item.category].append(item)

    # Out-of-stock items
    out_of_stock_items = MenuItem.objects.filter(
        date_available=today,
        available_quantity__lte=0
    )
    categorized_out_of_stock = defaultdict(list)
    for item in out_of_stock_items:
        categorized_out_of_stock[item.category].append(item)

    return render(request, "customer/daily_menu.html", {
        "categorized_available": dict(categorized_available),
        "categorized_out_of_stock": dict(categorized_out_of_stock),
    })

# --- Add item to cart with drinks preferred time ---
@login_required
@user_passes_test(is_student)
def cart_add(request, item_id):
    item = get_object_or_404(MenuItem, id=item_id)
    username = request.user.username.upper()
    now = timezone.localtime().time()

    # Determine user type & lunch window
    if username.startswith("AWHCS"):
        user_type = "student"
        start_time = dt_time(12, 0)
        end_time = dt_time(14, 0)
    elif username.startswith("AWHCF"):
        user_type = "faculty"
        start_time = dt_time(12, 0)
        end_time = dt_time(14, 0)
    else:
        user_type = "unknown"
        start_time = end_time = now

    token_active = start_time <= now <= end_time

    # Restrict lunch ordering outside lunch hours
    if item.category.lower() == "lunch" and not token_active:
        messages.warning(
            request,
            f"⚠ {user_type.title()} lunch items can only be ordered between "
            f"{start_time.strftime('%I:%M %p')} and {end_time.strftime('%I:%M %p')}."
        )
        return redirect("user_dashboard")

    # Quantity
    try:
        qty_to_add = int(request.POST.get("quantity", 1))
        if qty_to_add < 1:
            qty_to_add = 1
    except (ValueError, TypeError):
        qty_to_add = 1

    # ✅ Drinks minimum quantity check
    if item.category.lower() == "drinks" and qty_to_add < 5:
        messages.warning(request, "⚠ Minimum order for drinks is 5.")
        return redirect("user_dashboard")

    # Portion
    portion = request.POST.get("portion", "full").lower()
    if portion not in ["full", "half"]:
        portion = "full"

    # ✅ Preferred time for drinks
    preferred_time = None
    if item.category.lower() == "drinks":
        preferred_time_str = request.POST.get("preferred_time")
        if preferred_time_str:
            try:
                preferred_time = datetime.strptime(preferred_time_str, "%H:%M").time()
            except ValueError:
                preferred_time = None

    # Add/update item in session cart
    cart = request.session.get("cart", {})
    key = f"{item_id}_{portion}"

    if key in cart:
        if isinstance(cart[key], dict):
            cart[key]["quantity"] += qty_to_add
        else:
            old_qty = int(cart.get(key, 0) or 0)
            cart[key] = {"item_id": item_id, "quantity": old_qty + qty_to_add, "portion": portion}
    else:
        cart[key] = {
            "item_id": item_id,
            "quantity": qty_to_add,
            "portion": portion,
            "preferred_time": preferred_time_str if preferred_time else None  # store preferred_time in session
        }

    request.session["cart"] = cart
    request.session.modified = True

    portion_text = "full" if portion == "full" else "half"
    if qty_to_add > 1:
        messages.success(request, f"{qty_to_add} {item.name} ({portion_text} portions) added to cart successfully!")
    else:
        messages.success(request, f"{item.name} ({portion_text} portion) added to cart successfully!")

    return redirect("cart_view")



@login_required
@user_passes_test(is_student)
def cart_view(request):
    cart = request.session.get("cart", {})
    cart_items = []
    total = Decimal("0.0")

    for key, value in cart.items():
        item_id = value.get("item_id")
        quantity = value.get("quantity", 0)
        portion = value.get("portion", "full")
        menu_item = get_object_or_404(MenuItem, id=item_id)
        price = menu_item.price * Decimal("0.5") if portion=="half" else menu_item.price
        subtotal = price * quantity
        total += subtotal
        cart_items.append({
            "menu_item": menu_item,
            "quantity": quantity,
            "portion": portion,
            "price": price,
            "subtotal": subtotal,
            "key": key,
        })

    return render(request, "customer/cart.html", {
        "cart_items": cart_items,
        "total": total,
        "has_items": bool(cart_items),
    })


# --- Update Cart Quantities ---
@login_required
@user_passes_test(is_student)
def cart_update(request):
    if request.method == "POST":
        cart = request.session.get("cart", {})
        for key in list(cart.keys()):
            quantity_str = request.POST.get(f"quantity_{key}")
            if quantity_str:
                try:
                    quantity = int(quantity_str)
                    if quantity > 0:
                        cart[key]["quantity"] = quantity
                    else:
                        del cart[key]
                except (ValueError, TypeError):
                    pass
        request.session["cart"] = cart
        request.session.modified = True
        messages.success(request, "Cart updated successfully!")
    return redirect("cart_view")


# --- Remove Single Item ---
@login_required
@user_passes_test(is_student)
def cart_remove(request, key):
    cart = request.session.get("cart", {})
    if key in cart:
        item_name = "Item"
        try:
            item_id = cart[key].get("item_id")
            menu_item = MenuItem.objects.get(id=item_id)
            item_name = menu_item.name
        except Exception:
            pass
        del cart[key]
        messages.success(request, f"{item_name} removed from cart.")
    else:
        messages.warning(request, "Item not found in cart.")

    request.session["cart"] = cart
    request.session.modified = True
    return redirect("cart_view")


# --- Clear Cart ---
@login_required
@user_passes_test(is_student)
def cart_clear(request):
    request.session["cart"] = {}
    messages.success(request, "Cart cleared successfully!")
    return redirect("cart_view")

@login_required
@user_passes_test(is_student)
def checkout(request):
    cart = request.session.get("cart", {})
    if not cart:
        messages.error(request, "Your cart is empty!")
        return redirect("cart_view")

    # 1️⃣ PRE-VALIDATE STOCK AVAILABILITY BEFORE CREATING ANYTHING
    insufficient_stock_items = []
    cart_items_data = []  # Store validated cart items
    
    for key, details in cart.items():
        item_id = details.get("item_id")
        quantity = details.get("quantity", 1)
        portion = details.get("portion", "FULL").upper()
        menu_item = get_object_or_404(MenuItem, id=item_id)

        # Check if item is available today
        if not menu_item.is_available_now():
            insufficient_stock_items.append(f"{menu_item.name} is not available today.")
            continue

        # Calculate required quantity (considering half portions)
        unit_qty = Decimal(quantity) * (Decimal("0.5") if portion == "HALF" else Decimal("1.0"))
        
        # Check stock availability
        if menu_item.available_quantity < unit_qty:
            insufficient_stock_items.append(
                f"Only {menu_item.available_quantity} {menu_item.name} left today. You requested {unit_qty}."
            )
        else:
            # Store valid items
            cart_items_data.append({
                'key': key,
                'menu_item': menu_item,
                'quantity': quantity,
                'portion': portion,
                'preferred_time_str': details.get("preferred_time"),
                'unit_qty': unit_qty
            })

    # If any items have insufficient stock, show error and abort
    if insufficient_stock_items:
        for error_msg in insufficient_stock_items:
            messages.error(request, error_msg)
        return redirect("cart_view")

    # 2️⃣ ONLY PROCEED IF ALL ITEMS HAVE SUFFICIENT STOCK
    with transaction.atomic():
        # Create Order
        order = Order.objects.create(user=request.user)
        
        total_amount = Decimal("0.0")
        order_items_list = []
        preferred_datetime = None

        # REDUCE STOCK FOR ALL ITEMS FIRST
        for item_data in cart_items_data:
            menu_item = item_data['menu_item']
            unit_qty = item_data['unit_qty']
            
            try:
                # Use the MenuItem's reduce_stock method
                menu_item.reduce_stock(unit_qty)
            except ValueError as e:
                messages.error(request, str(e))
                return redirect("cart_view")

        # CREATE ORDER ITEMS AFTER STOCK REDUCTION
        for item_data in cart_items_data:
            menu_item = item_data['menu_item']
            quantity = item_data['quantity']
            portion = item_data['portion']
            preferred_time_str = item_data['preferred_time_str']
            
            # Price calculation (for total amount only)
            if portion == "HALF" and menu_item.has_half and menu_item.half_price:
                item_price = menu_item.half_price
            else:
                item_price = menu_item.price
            
            # Create OrderItem - NO STOCK CHECKING HERE
            order_item = OrderItem.objects.create(
                order=order, 
                menu_item=menu_item, 
                quantity=quantity, 
                portion=portion
            )
            order_items_list.append(order_item)
            total_amount += item_price * Decimal(quantity)

            # ✅ Capture preferred datetime if any (for drinks)
            if menu_item.category.lower() == "drinks" and preferred_time_str:
                try:
                    from datetime import datetime, time
                    preferred_time = datetime.strptime(preferred_time_str, "%H:%M").time()
                    today = timezone.localdate()
                    preferred_datetime = timezone.make_aware(
                        datetime.combine(today, preferred_time)
                    )
                    # Validate it's not in the past
                    if preferred_datetime < timezone.now():
                        messages.warning(request, f"Preferred time for {menu_item.name} is in the past. Using current time.")
                        preferred_datetime = None
                except ValueError:
                    preferred_datetime = None

            # Update Daily Report
            daily_report, created = DailyReport.objects.get_or_create(
                date=timezone.localdate(),
                menu_item=menu_item,
                defaults={
                    'total_tokens': 0, 
                    'sold_count': 0,
                    'used_tokens_count': 0,
                    'cancelled_tokens_count': 0,
                    'expired_tokens_count': 0
                }
            )
            daily_report.total_tokens += 1
            daily_report.sold_count += quantity
            daily_report.save()

        # Update order with meal type
        categories = [item.menu_item.category for item in order_items_list]
        if categories:
            from collections import Counter
            meal_type = Counter(categories).most_common(1)[0][0]
            order.meal_type = meal_type
        order.save()

        # Create MealToken
        token = create_meal_token(order)

        # If we have preferred datetime for drinks, update the token
        if preferred_datetime:
            token.start_time = preferred_datetime
            token.save()

        # Generate UPI QR
        upi_id = "canteen@upi"
        upi_link = f"upi://pay?pa={upi_id}&pn=CollegeCanteen&am={float(order.total_amount)}&cu=INR&tn={token.code}"
        qr_img = qrcode.make(upi_link)
        buffer = io.BytesIO()
        qr_img.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()

        # Clear cart
        request.session["cart"] = {}
        request.session.modified = True

        # Send success message
        messages.success(request, f"Order placed successfully! Token: {token.code}")

    # Render token ticket page
    return render(request, "customer/token_ticket.html", {
        "token": token,
        "order": order,
        "order_items": order_items_list,
        "qr_img": qr_base64,
        "expires_at": token.expires_at,
    })

@login_required
@user_passes_test(is_student)
def my_tokens(request):
    tokens = MealToken.objects.filter(order__user=request.user).order_by("-generated_at")
    
    # FIXED: Force expire ALL tokens that should be expired
    expired_count = 0
    for token in tokens:
        # Check if token should be expired (more comprehensive check)
        if token.status.upper() in ['PENDING', 'PAID']:
            # Calculate expiry time manually to be sure
            expiry_time = token.generated_at + timedelta(minutes=token.validity_minutes)
            is_expired = timezone.now() > expiry_time
            
            if is_expired:
                # Force update status to EXPIRED
                token.status = 'EXPIRED'
                token.save(update_fields=['status'])
                expired_count += 1
                
                # Send notification
                Notification.objects.create(
                    user=request.user,
                    message=f"⚠️ Your token {token.code} expired after {token.validity_minutes} minutes."
                )
                print(f"DEBUG: Force expired token {token.code}")

    if expired_count > 0:
        messages.warning(request, f"{expired_count} tokens expired automatically.")

    # Refresh tokens after updates
    tokens = MealToken.objects.filter(order__user=request.user).order_by("-generated_at")
    
    # Debug information
    print(f"DEBUG: Found {tokens.count()} tokens for user {request.user.username}")
    for token in tokens:
        expiry_time = token.generated_at + timedelta(minutes=token.validity_minutes)
        is_expired = timezone.now() > expiry_time
        print(f"DEBUG: {token.code} - Status: '{token.status}' - Should be expired: {is_expired}")
    
    return render(request, "customer/my_tokens.html", {
        "tokens": tokens,
        "now": timezone.now()
    })

@login_required
@user_passes_test(is_student)
def cancel_token(request, token_code):
    # FIX: Use order__user instead of user
    token = get_object_or_404(MealToken, code=token_code, order__user=request.user)

    # Check if token is already used, expired, or cancelled
    if token.status.upper() in ["USED", "EXPIRED", "CANCELLED"]:
        messages.error(request, f"Cannot cancel this token. It is already {token.status.lower()}.")
        return redirect("my_tokens")

    # Check if token is already paid (optional restriction)
    if hasattr(token, 'paid') and token.paid:
        messages.warning(request, "This token has already been paid. Please contact staff for refund.")
        return redirect("my_tokens")

    with transaction.atomic():
        try:
            # 1️⃣ Update token status
            token.status = "CANCELLED"
            token.cancelled_at = timezone.now()
            
            # Save all fields to be safe
            token.save()

            # 2️⃣ Refund stock to MenuItems
            order_items = OrderItem.objects.filter(order=token.order)
            for item in order_items:
                menu_item = item.menu_item
                unit_qty = Decimal(item.quantity) * (Decimal("0.5") if item.portion == "HALF" else Decimal("1.0"))
                menu_item.increase_stock(unit_qty)

                print(f"DEBUG: Refunded {unit_qty} units of {menu_item.name} to stock")

                # 3️⃣ Update DailyReport if it exists
                try:
                    daily_report = DailyReport.objects.get(
                        date=timezone.localdate(),
                        menu_item=menu_item
                    )
                    daily_report.cancelled_tokens_count += item.quantity
                    daily_report.sold_count -= item.quantity
                    daily_report.save()
                    
                    print(f"DEBUG: Updated DailyReport for {menu_item.name}")
                except DailyReport.DoesNotExist:
                    print(f"DEBUG: No DailyReport found for {menu_item.name}")
                    # Continue without DailyReport update if it doesn't exist

            # 4️⃣ Optionally: refund payment if already paid
            if hasattr(token, 'paid') and token.paid:
                # Your payment gateway refund logic here
                token.refunded = True
                token.save(update_fields=["refunded"])
                print(f"DEBUG: Marked token {token.code} as refunded")

            messages.success(request, f"Token {token.code} has been cancelled successfully. Stock has been refunded.")
            
        except Exception as e:
            messages.error(request, f"Error cancelling token: {str(e)}")
            print(f"ERROR in cancel_token: {str(e)}")
            return redirect("my_tokens")

    return redirect("my_tokens")

# --- Token Ticket View ---
@login_required
@user_passes_test(is_student)
def fetch_token(request, code):
    token = get_object_or_404(MealToken, code=code, order__user=request.user)
    order_items = token.order.items.all()
    return render(request, "customer/token_ticket.html", {
        "token": token, 
        "order_items": order_items,
        "expires_at": token.expires_at
    })


# --- Add Review ---
@login_required
@user_passes_test(is_student)
def add_review(request, token_id):
    token = get_object_or_404(MealToken, id=token_id, order__user=request.user)
    if token.status not in [TokenStatus.USED]:
        messages.error(request, "You can only review completed meals.")
        return redirect("my_tokens")

    if request.method == "POST":
        rating = request.POST.get("rating")
        comment = request.POST.get("comment")

        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                raise ValueError
        except ValueError:
            messages.error(request, "Rating must be between 1 and 5.")
            return redirect("my_tokens")

        if not comment:
            messages.error(request, "Please provide a comment.")
            return redirect("my_tokens")

        created_count = 0
        for order_item in token.order.items.all():
            if not Review.objects.filter(item=order_item.menu_item, user=request.user).exists():
                Review.objects.create(
                    item=order_item.menu_item,
                    user=request.user,
                    rating=rating,
                    comment=comment,
                    is_visible=True
                )
                created_count += 1

        if created_count > 0:
            messages.success(request, "✅ Your review(s) have been submitted.")
        else:
            messages.info(request, "You have already reviewed this meal.")

        return redirect("reviews")

    return render(request, "customer/add_review.html", {"token": token})

@login_required
@user_passes_test(is_student)
def migrate_cart(request):
    """
    Converts old-format cart (int quantity) to new dict format.
    """
    cart = request.session.get("cart", {})
    new_cart = {}

    for key, value in cart.items():
        if isinstance(value, int):
            try:
                item_id, portion = key.split("_")
                new_cart[key] = {
                    "item_id": int(item_id),
                    "quantity": value,
                    "portion": portion.lower()
                }
            except (ValueError, IndexError):
                continue
        else:
            new_cart[key] = value

    request.session["cart"] = new_cart
    request.session.modified = True
    messages.success(request, "Cart migrated to new format!")
    return redirect("cart_view")

@login_required
@user_passes_test(is_student)
def user_tokens(request):
    orders = Order.objects.filter(user=request.user).order_by('-id')
    tokens = MealToken.objects.filter(order__in=orders).order_by('-id')
    context = {'tokens': tokens}
    return render(request, "customer/my_tokens.html", context)


@login_required
@user_passes_test(is_student)
def reviews(request):
    try:
        reviews_list = Review.objects.filter(is_visible=True).order_by('-created_at')
        
        # Debug
        print(f"Total reviews in DB: {Review.objects.count()}")
        print(f"Visible reviews: {reviews_list.count()}")
        
        context = {
            "reviews": reviews_list,
            "show_user": True,
            "title": "Customer Reviews"
        }
        
        return render(request, "customer/reviews.html", context)
        
    except Exception as e:
        print(f"Error in reviews view: {e}")
        # Fallback - show empty reviews
        return render(request, "customer/reviews.html", {
            "reviews": [],
            "show_user": True,
            "title": "Customer Reviews"
        })
 
@login_required
def mark_notifications_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    messages.info(request, "All notifications marked as read.")
    return redirect(request.META.get("HTTP_REFERER", "user_dashboard"))

@login_required
@user_passes_test(is_student)
def my_notifications(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    notifications.filter(is_read=False).update(is_read=True)
    return render(request, "customer/my_notifications.html", {"notifications": notifications})

# --- Token Ticket View ---
@login_required
@user_passes_test(is_student)
def token_ticket(request, code):
    token = get_object_or_404(MealToken, code=code, order__user=request.user)
    order_items = token.order.items.all()

    # FIX: Handle case sensitivity - database has "pending" but TokenStatus expects "PENDING"
    is_pending = (token.status.upper() == TokenStatus.PENDING)
    
    print(f"DEBUG Token Status: '{token.status}'")
    print(f"DEBUG Is PENDING (case-insensitive): {is_pending}")
    print(f"DEBUG Is Expired: {token.is_expired}")
    print(f"DEBUG Can Pay: {token.can_pay}")

    # QR only if PENDING and not expired - FIXED with case-insensitive check
    qr_img = None
    if is_pending and not token.is_expired:
        upi_id = "canteen@upi"  # Replace with actual UPI ID
        amount = token.order.total_amount
        upi_link = f"upi://pay?pa={upi_id}&pn=CollegeCanteen&am={amount}&cu=INR&tn=Token_{token.code}"
        qr = qrcode.make(upi_link)
        buffer = io.BytesIO()
        qr.save(buffer, format="PNG")
        qr_img = base64.b64encode(buffer.getvalue()).decode()
        
        print(f"DEBUG: QR code generated for token {token.code}, Amount: ₹{amount}")

    return render(request, "customer/token_ticket.html", {
        "token": token,
        "order": token.order,
        "order_items": order_items,
        "qr_img": qr_img,
        "expires_at": token.expires_at,
        "is_expired": token.is_expired,
        "is_pending": is_pending,
    })

# =====================
# ENHANCED PAYMENT SYSTEM
# =====================
@login_required
@user_passes_test(is_student)
def process_upi_payment(request, code):
    """
    Process UPI payment and automatically mark token as PAID and USED
    """
    token = get_object_or_404(MealToken, code=code, order__user=request.user)
    
    # Check if token can be processed
    if token.status.upper() != 'PENDING':
        messages.error(request, f"Cannot process payment. Token status is {token.status}.")
        return redirect(f"{reverse('token_ticket', kwargs={'code': token.code})}#payment")
    
    if token.is_expired:
        messages.error(request, "Token has expired. Please place a new order.")
        return redirect(f"{reverse('token_ticket', kwargs={'code': token.code})}#payment")
    
    if request.method == "POST":
        upi_transaction_id = request.POST.get('upi_transaction_id', '').strip().upper()
        
        # Validate transaction ID
        if not upi_transaction_id:
            messages.error(request, "Please enter your UPI Transaction ID.")
            return redirect(f"{reverse('token_ticket', kwargs={'code': token.code})}#payment")
        
        if len(upi_transaction_id) < 6:
            messages.error(request, "Transaction ID must be at least 6 characters.")
            return redirect(f"{reverse('token_ticket', kwargs={'code': token.code})}#payment")
        
        # Check if transaction ID was already used
        if MealToken.objects.filter(upi_transaction_id=upi_transaction_id).exclude(id=token.id).exists():
            messages.error(request, "This transaction ID has already been used.")
            return redirect(f"{reverse('token_ticket', kwargs={'code': token.code})}#payment")
        
        try:
            with transaction.atomic():
                # Process payment and mark as USED directly
                token.status = TokenStatus.USED
                token.upi_transaction_id = upi_transaction_id
                token.payment_datetime = timezone.now()
                token.served_at = timezone.now()
                token.payment_verified = True
                token.save()
                
                # Update daily report - SIMPLIFIED VERSION (remove models.F)
                for order_item in token.order.items.all():
                    daily_report, created = DailyReport.objects.get_or_create(
                        date=timezone.now().date(),
                        menu_item=order_item.menu_item,
                        defaults={
                            'total_tokens': 1,
                            'sold_count': order_item.quantity,
                            'used_tokens_count': 1,
                            'cancelled_tokens_count': 0,
                            'expired_tokens_count': 0
                        }
                    )
                    if not created:
                        # Simple increment without models.F
                        daily_report.used_tokens_count += 1
                        daily_report.sold_count += order_item.quantity
                        daily_report.total_tokens += 1
                        daily_report.save()
                
                # Create success notification
                Notification.objects.create(
                    user=request.user,
                    message=f"✅ Payment confirmed! Token {token.code} has been served. Transaction ID: {upi_transaction_id}",
                    type="payment_success"
                )
                
                messages.success(request, 
                    f"✅ Payment verified successfully! Token {token.code} has been served and marked as completed."
                )
                print(f"PAYMENT SUCCESS: Token {token.code} marked as USED with transaction {upi_transaction_id}")
                
        except Exception as e:
            messages.error(request, f"Payment processing failed: {str(e)}")
            print(f"PAYMENT ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
    
    return redirect("token_ticket", code=token.code)

@login_required
@user_passes_test(is_student)
def mock_payment_success(request, code):
    """
    Enhanced mock payment for testing - automatically marks as PAID and USED
    """
    token = get_object_or_404(MealToken, code=code, order__user=request.user)
    
    if token.is_expired:
        messages.error(request, "Token has expired. Please place a new order.")
        return redirect("token_ticket", code=token.code)
    
    if token.status.upper() != 'PENDING':
        messages.info(request, f"Token is already {token.status}.")
        return redirect("token_ticket", code=token.code)
    
    try:
        with transaction.atomic():
            # Generate mock transaction ID
            import random
            mock_transaction_id = f"MOCK{token.code.replace('T-', '')}{random.randint(1000, 9999)}"
            
            # Mark as PAID first
            token.status = TokenStatus.PAID
            token.upi_transaction_id = mock_transaction_id
            token.payment_time = timezone.now()
            
            # AUTOMATICALLY mark as USED
            token.status = TokenStatus.USED
            token.served_at = timezone.now()
            token.save()
            
            # Update daily report
            for order_item in token.order.items.all():
                daily_report, created = DailyReport.objects.get_or_create(
                    date=timezone.now().date(),
                    menu_item=order_item.menu_item,
                    defaults={
                        'total_tokens': 0,
                        'sold_count': order_item.quantity,
                        'used_tokens_count': 1,
                        'cancelled_tokens_count': 0,
                        'expired_tokens_count': 0
                    }
                )
                if not created:
                    daily_report.used_tokens_count += 1
                    daily_report.save()
            
            messages.success(request, 
                f"🧪 Mock payment successful! Token {token.code} has been served and marked as completed. "
                f"Mock Transaction ID: {mock_transaction_id}"
            )
            
            Notification.objects.create(
                user=request.user,
                message=f"Mock payment completed for token {token.code}. Your meal has been served."
            )
            
            print(f"MOCK PAYMENT: Token {token.code} marked as PAID and USED")
            
    except Exception as e:
        messages.error(request, f"Mock payment failed: {str(e)}")
        print(f"MOCK PAYMENT ERROR: {str(e)}")
    
    return redirect("token_ticket", code=token.code)

@login_required
@user_passes_test(is_student)
def manual_mark_served(request, code):
    """
    Manual mark as served for testing (bypasses payment)
    """
    token = get_object_or_404(MealToken, code=code, order__user=request.user)
    
    if token.status.upper() == 'PENDING' and not token.is_expired:
        try:
            with transaction.atomic():
                # Mark as USED directly (bypass payment)
                token.status = TokenStatus.USED
                token.served_at = timezone.now()
                token.upi_transaction_id = f"MANUAL{timezone.now().strftime('%Y%m%d%H%M%S')}"
                token.save()
                
                # Update daily report
                for order_item in token.order.items.all():
                    daily_report, created = DailyReport.objects.get_or_create(
                        date=timezone.now().date(),
                        menu_item=order_item.menu_item,
                        defaults={
                            'total_tokens': 0,
                            'sold_count': order_item.quantity,
                            'used_tokens_count': 1,
                            'cancelled_tokens_count': 0,
                            'expired_tokens_count': 0
                        }
                    )
                    if not created:
                        daily_report.used_tokens_count += 1
                        daily_report.save()
                
                messages.success(request, f"Token {token.code} manually marked as served.")
                print(f"MANUAL SERVE: Token {token.code} marked as USED")
                
        except Exception as e:
            messages.error(request, f"Failed to mark token as served: {str(e)}")
    else:
        messages.error(request, "Cannot mark this token as served.")
    
    return redirect("token_ticket", code=token.code)

# =====================
# Staff Views - UPDATED TO PREVENT MANUAL MARKING
# =====================
@login_required
@user_passes_test(is_canteen_staff)
def staff_dashboard(request):
    today = timezone.localdate()
    
    # Menu items
    items = MenuItem.objects.filter(date_available=today).order_by("category", "name")
    categorized_items = defaultdict(list)
    for item in items:
        categorized_items[item.category].append(item)
    
    # Today's tokens with status counts
    tokens_today = get_todays_tokens()
    
    # Auto-expire tokens on staff dashboard view
    expired_count = 0
    for token in tokens_today:
        if token.status in [TokenStatus.PENDING, TokenStatus.PAID] and token.is_expired:
            if token.mark_expired_auto():
                expired_count += 1
    
    if expired_count > 0:
        messages.info(request, f"{expired_count} tokens auto-expired.")
    
    # Refresh token stats
    tokens_today = get_todays_tokens()
    token_stats = {
        'total': tokens_today.count(),
        'pending': tokens_today.filter(status=TokenStatus.PENDING).count(),
        'paid': tokens_today.filter(status=TokenStatus.PAID).count(),
        'used': tokens_today.filter(status=TokenStatus.USED).count(),
        'expired': tokens_today.filter(status=TokenStatus.EXPIRED).count(),
        'cancelled': tokens_today.filter(status=TokenStatus.CANCELLED).count(),
    }
    
    # Recent paid tokens (ready for serving)
    recent_paid_tokens = tokens_today.filter(status=TokenStatus.PAID).order_by('-generated_at')[:10]
    
    return render(request, "staff/staff_dashboard.html", {
        "categorized_items": dict(categorized_items),
        "token_stats": token_stats,
        "recent_paid_tokens": recent_paid_tokens
    })

@login_required
@user_passes_test(is_canteen_staff)
def menu_list(request):
    today = timezone.localdate()
    all_items = MenuItem.objects.filter(date_available=today).order_by('category', 'name')

    categorized_available = defaultdict(list)
    categorized_out_of_stock = defaultdict(list)

    for item in all_items:
        if item.available_quantity > 0:
            categorized_available[item.category].append(item)
        else:
            categorized_out_of_stock[item.category].append(item)

    context = {
        "categorized_available": dict(categorized_available),
        "categorized_out_of_stock": dict(categorized_out_of_stock)
    }
    return render(request, "staff/menu_list.html", context)

@login_required
@user_passes_test(is_canteen_staff)
def reset_all_stock(request):
    today = timezone.localdate()
    items = MenuItem.objects.all().order_by("category", "name")
    if request.method == "POST":
        for item in items:
            qty_str = request.POST.get(f"qty_{item.id}")
            if qty_str:
                try:
                    qty = Decimal(qty_str)
                    item.daily_quantity = qty
                    item.available_quantity = qty
                    item.available = float(qty) > 0
                    item.date_available = today
                    item.save(update_fields=["daily_quantity", "available_quantity", "available", "date_available"])
                except (ValueError, InvalidOperation):
                    continue
        messages.success(request, "🔄 All menu items stock updated successfully!")
        return redirect("menu_list")
    return render(request, "staff/reset_all_stock.html", {"items": items})

# =====================
# Add Menu Item
# =====================
@login_required
@user_passes_test(is_canteen_staff)
def add_menu_item(request):
    if request.method == "POST":
        form = DailyMenuForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save(commit=False)
            item.date_available = timezone.localdate()
            item.save()
            item.reset_daily_stock()
            messages.success(request, "✅ Menu item added successfully.")
            return redirect("staff_view_menu")
        else:
            messages.error(request, "⚠️ Please fix the errors below.")
    else:
        form = MainMenuForm()
    return render(request, "staff/add_menu_item.html", {"form": form})


@login_required
def staff_view_menu(request, category=None):
    # Staff should see all items
    menu_items = MenuItem.objects.all()

    categorized_items = defaultdict(list)
    for item in menu_items:
        display_category = CATEGORY_DISPLAY.get(item.category, item.category.title())
        categorized_items[display_category].append(item)

    return render(request, "staff/view_menu.html", {
        "categorized_items": dict(categorized_items),
        "selected_category": category.title() if category else "All",
    })

@login_required
@user_passes_test(is_canteen_staff)
def edit_daily_menu_item(request, pk):
    item = get_object_or_404(MenuItem, pk=pk)
    
    if request.method == "POST":
        form = DailyMenuForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            item = form.save(commit=False)
            item.date_available = timezone.localdate()
            item.save()
            messages.success(request, "✅ Menu item updated successfully.")
            return redirect("menu_list")
        else:
            messages.error(request, "⚠️ Please fix the errors below.")
    else:
        form = DailyMenuForm(instance=item)
    return render(request, "staff/edit_menu_item.html", {"form": form, "item": item})


@login_required
@user_passes_test(is_canteen_staff)
def edit_main_menu_item(request, pk):
    item = get_object_or_404(MenuItem, pk=pk)
    form_class = MainMenuForm

    if request.method == "POST":
        form = form_class(request.POST, request.FILES, instance=item)
        if form.is_valid():
            updated_item = form.save(commit=False)
            updated_item.date_available = timezone.localdate()
            updated_item.save()
            messages.success(request, "✅ Menu item updated successfully.")
            return redirect("staff_view_menu")
        else:
            messages.error(request, "⚠️ Please fix the errors below.")
    else:
        form = form_class(instance=item)

    # ✅ Pass model choices to template (capitalized consistently)
    categories = [choice[0] for choice in MenuItem.CATEGORY_CHOICES]

    return render(request, "staff/edit_main_menu_item.html", {
        "form": form,
        "item": item,
        "categories": categories,
    })


@login_required
@user_passes_test(is_canteen_staff)
def delete_main_menu_item(request, pk):
    item = get_object_or_404(MenuItem, pk=pk)
    if request.method == "POST":
        item.delete()
        messages.success(request, f"🗑️ Menu item '{item.name}' deleted successfully.", extra_tags="success")

        return redirect("staff_view_menu")
    return render(request, "staff/delete_main_menu_item.html", {"item": item, "menu_type": "Main Menu"})


@login_required
@user_passes_test(is_canteen_staff)
def delete_daily_menu_item(request, pk):
    item = get_object_or_404(MenuItem, pk=pk)  # or DailyMenuItem if separate
    if request.method == "POST":
        item.delete()
        messages.success(request, f"🗑️ Menu item '{item.name}' deleted successfully.", extra_tags="success")

        return redirect("menu_list")
    return render(request, "staff/delete_menu_item.html", {"item": item, "menu_type": "Daily Menu"})


# =====================
# Update Item Quantity
# =====================
@login_required
@user_passes_test(is_canteen_staff)
def update_item_quantity(request, item_id):
    item = get_object_or_404(MenuItem, id=item_id)
    if request.method == "POST":
        try:
            qty = int(request.POST.get("quantity", 0))
            item.available_quantity = qty
            item.available = qty > 0
            item.save()
            messages.success(request, f"Quantity updated for {item.name}.")
        except ValueError:
            messages.error(request, "Invalid quantity entered.")
    return redirect("menu_list")

# =====================
# Reset Stock
# =====================
@login_required
@user_passes_test(is_canteen_staff)
def reset_stock(request, pk):
    item = get_object_or_404(MenuItem, pk=pk)
    item.reset_daily_stock()
    messages.success(request, f"🔄 Stock for {item.name} reset to {item.daily_quantity}.")
    return redirect("menu_list")


def get_todays_tokens():
    """Helper function to get today's tokens consistently"""
    today = timezone.localdate()
    # Try different possible field names
    if hasattr(MealToken, 'generated_at'):
        return MealToken.objects.filter(generated_at__date=today)
    elif hasattr(MealToken, 'created_at'):
        return MealToken.objects.filter(created_at__date=today)
    else:
        # Fallback to any datetime field
        return MealToken.objects.filter(
            models.Q(generated_at__date=today) | 
            models.Q(created_at__date=today)
        )

def get_recent_tokens(days=2):
    """Get tokens from recent days for testing"""
    today = timezone.localdate()
    start_date = today - timedelta(days=days)
    return MealToken.objects.filter(generated_at__date__gte=start_date)

from django.utils import timezone
from datetime import timedelta, datetime
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from collections import defaultdict
from .models import MealToken, TokenStatus, MenuItem

@login_required
@user_passes_test(is_canteen_staff)
def tokens_today(request):
    today = timezone.localdate()
    now = timezone.now()

    # FIXED: Use timezone-aware range filtering
    start_date = timezone.make_aware(datetime.combine(today - timedelta(days=2), datetime.min.time()))
    end_date = timezone.make_aware(datetime.combine(today + timedelta(days=1), datetime.min.time()))
    
    tokens = MealToken.objects.filter(
        generated_at__gte=start_date,
        generated_at__lt=end_date
    ).select_related('order__user').prefetch_related('order__items__menu_item').order_by('-generated_at')

    # Process each token
    for token in tokens:
        # Handle both uppercase and lowercase status
        if token.status.upper() in [TokenStatus.PENDING, TokenStatus.PAID]:
            expiry_time = token.generated_at + timedelta(hours=1, minutes=30)
            if now >= expiry_time:
                token.status = TokenStatus.EXPIRED
                token.save()
        

    # Group tokens by category for display
    categories = MenuItem.CATEGORY_CHOICES
    tokens_by_category = defaultdict(list)
    uncategorized_tokens = []
    
    for token in tokens:
        token_categories = set()
        # Check if token has order and items
        if hasattr(token, 'order') and token.order:
            for order_item in token.order.items.all():
                token_categories.add(order_item.menu_item.category)
        
        if token_categories:
            for cat in token_categories:
                cat_display = dict(categories).get(cat, cat)
                tokens_by_category[cat_display].append(token)
        else:
            uncategorized_tokens.append(token)

    # Add uncategorized tokens to a separate group
    if uncategorized_tokens:
        tokens_by_category['Uncategorized'] = uncategorized_tokens

    # Check if we're showing tokens from previous days
    show_recent = tokens.filter(generated_at__date__lt=today).exists()

    context = {
        'tokens': tokens,
        'tokens_by_category': dict(tokens_by_category),
        'today_date': today,
        'show_recent': show_recent,
    }
    return render(request, 'staff/tokens_today.html', context)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.db.models import Avg  # Import Avg directly
from .models import Review

@login_required
@user_passes_test(is_canteen_staff)
def user_reviews(request):
    # Handle POST request first (toggle visibility)
    if request.method == 'POST':
        review_id = request.POST.get('review_id')
        if review_id:
            try:
                review = get_object_or_404(Review, id=review_id)
                review.is_visible = not review.is_visible
                review.save()
            except Review.DoesNotExist:
                # Handle the case where review doesn't exist
                pass
        return redirect('user_reviews')

    # GET request - display reviews
    reviews = Review.objects.all().order_by('-created_at')
    
    # Statistics
    total_reviews = reviews.count()
    visible_reviews = reviews.filter(is_visible=True).count()
    today_reviews = reviews.filter(created_at__date=timezone.localdate()).count()
    average_rating = reviews.aggregate(avg_rating=Avg('rating'))['avg_rating'] or 0

    context = {
        'reviews': reviews,
        'total_reviews': total_reviews,
        'visible_reviews': visible_reviews,
        'today_reviews': today_reviews,
        'average_rating': round(average_rating, 1),
    }
    return render(request, 'staff/user_reviews.html', context)

# =====================
# Admin Views
# =====================
# =====================
# Dashboard Views
# =====================
@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    today = timezone.localdate()
    
    try:
        # Token analytics
        tokens_today = MealToken.objects.filter(generated_at__date=today)
        token_stats = {
            'total': tokens_today.count(),
            'pending': tokens_today.filter(status=TokenStatus.PENDING).count(),
            'paid': tokens_today.filter(status=TokenStatus.PAID).count(),
            'used': tokens_today.filter(status=TokenStatus.USED).count(),
            'expired': tokens_today.filter(status=TokenStatus.EXPIRED).count(),
            'cancelled': tokens_today.filter(status=TokenStatus.CANCELLED).count(),
        }
        
        # Sales analytics
        daily_reports = DailyReport.objects.filter(date=today)
        total_sold = sum(report.sold_count for report in daily_reports)
        total_revenue = sum(report.sold_count * report.menu_item.price for report in daily_reports if report.menu_item)
        
        # User statistics
        user_stats = {
            'total': User.objects.count(),
            'students': User.objects.filter(role='user').count(),
            'staff': User.objects.filter(role='canteenstaff').count(),
            'admins': User.objects.filter(role='admin').count(),
        }
        
        menus = MenuItem.objects.filter(available=True, date_available=today)
        
        return render(request, "admin/admin_dashboard.html", {
            "menus": menus,
            "token_stats": token_stats,
            "daily_reports": daily_reports,
            "total_sold": total_sold,
            "total_revenue": total_revenue,
            "user_stats": user_stats,
        })
    
    except Exception as e:
        messages.error(request, f"Error loading dashboard: {str(e)}")
        return render(request, "admin/admin_dashboard.html", {
            "menus": [],
            "token_stats": {},
            "daily_reports": [],
            "total_sold": 0,
            "total_revenue": 0,
            "user_stats": {},
        })
    
from django.utils import timezone
from datetime import timedelta, datetime
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from collections import defaultdict
from .models import MealToken, TokenStatus, MenuItem

@login_required
@user_passes_test(is_admin)  # Adjust permission check as needed
def admin_reports(request):
    today = timezone.localdate()
    now = timezone.now()

    # FIXED: Use timezone-aware range filtering (same as tokens_today)
    start_date = timezone.make_aware(datetime.combine(today - timedelta(days=2), datetime.min.time()))
    end_date = timezone.make_aware(datetime.combine(today + timedelta(days=1), datetime.min.time()))
    
    tokens = MealToken.objects.filter(
        generated_at__gte=start_date,
        generated_at__lt=end_date
    ).select_related('order__user').prefetch_related('order__items__menu_item').order_by('-generated_at')

    # Process each token for expiry (same as tokens_today)
    for token in tokens:
        # Handle both uppercase and lowercase status
        if token.status.upper() in [TokenStatus.PENDING, TokenStatus.PAID]:
            expiry_time = token.generated_at + timedelta(hours=1, minutes=30)
            if now >= expiry_time:
                token.status = TokenStatus.EXPIRED
                token.save()

    # Group tokens by category for display (same as tokens_today)
    categories = MenuItem.CATEGORY_CHOICES
    tokens_by_category = defaultdict(list)
    uncategorized_tokens = []
    
    for token in tokens:
        token_categories = set()
        # Check if token has order and items
        if hasattr(token, 'order') and token.order:
            for order_item in token.order.items.all():
                token_categories.add(order_item.menu_item.category)
        
        if token_categories:
            for cat in token_categories:
                cat_display = dict(categories).get(cat, cat)
                tokens_by_category[cat_display].append(token)
        else:
            uncategorized_tokens.append(token)

    # Add uncategorized tokens to a separate group
    if uncategorized_tokens:
        tokens_by_category['Uncategorized'] = uncategorized_tokens

    # Check if we're showing tokens from previous days
    show_recent = tokens.filter(generated_at__date__lt=today).exists()

    # Calculate summary statistics
    total_tokens = tokens.count()
    paid_tokens = tokens.filter(status__iexact=TokenStatus.PAID).count()
    pending_tokens = tokens.filter(status__iexact=TokenStatus.PENDING).count()
    used_tokens = tokens.filter(status__iexact=TokenStatus.USED).count()
    expired_tokens = tokens.filter(status__iexact=TokenStatus.EXPIRED).count()

    context = {
        'tokens': tokens,
        'tokens_by_category': dict(tokens_by_category),
        'today_date': today.strftime("%d %b %Y"),
        'show_recent': show_recent,
        'total_tokens': total_tokens,
        'paid_tokens': paid_tokens,
        'pending_tokens': pending_tokens,
        'used_tokens': used_tokens,
        'expired_tokens': expired_tokens,
    }
    return render(request, 'admin/reports.html', context)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.db.models import Avg  # Import Avg directly
from .models import Review

@login_required
@user_passes_test(is_admin)
def admin_reviews(request):
    # Handle POST request first (toggle visibility)
    if request.method == 'POST':
        review_id = request.POST.get('review_id')
        if review_id:
            try:
                review = get_object_or_404(Review, id=review_id)
                review.is_visible = not review.is_visible
                review.save()
            except Review.DoesNotExist:
                # Handle the case where review doesn't exist
                pass
        return redirect('admin_reviews')

    # GET request - display reviews
    reviews = Review.objects.all().order_by('-created_at')
    
    # Statistics
    total_reviews = reviews.count()
    visible_reviews = reviews.filter(is_visible=True).count()
    today_reviews = reviews.filter(created_at__date=timezone.localdate()).count()
    average_rating = reviews.aggregate(avg_rating=Avg('rating'))['avg_rating'] or 0

    context = {
        'reviews': reviews,
        'total_reviews': total_reviews,
        'visible_reviews': visible_reviews,
        'today_reviews': today_reviews,
        'average_rating': round(average_rating, 1),
    }
    return render(request, 'admin/reviews.html', context)

@login_required
@user_passes_test(is_admin)
def admin_menu_list(request):
    today = timezone.localdate()
    all_items = MenuItem.objects.filter(date_available=today).order_by('category', 'name')

    categorized_available = defaultdict(list)
    categorized_out_of_stock = defaultdict(list)

    for item in all_items:
        if item.available_quantity > 0:
            categorized_available[item.category].append(item)
        else:
            categorized_out_of_stock[item.category].append(item)

    context = {
        "categorized_available": dict(categorized_available),
        "categorized_out_of_stock": dict(categorized_out_of_stock)
    }
    return render(request, "admin/menu_list.html", context)

@login_required
@user_passes_test(is_admin)
def admin_users(request):
    users = User.objects.all().order_by("username")
    return render(request, "admin/users.html", {"users": users})

@login_required
@user_passes_test(is_admin)
def admin_view_menu(request, category=None):
    today = timezone.localdate()
    
    # Admin can see all items, including unavailable ones
    menu_items = MenuItem.objects.all().order_by("category", "name")
    
    categorized_items = defaultdict(list)
    for item in menu_items:
        display_category = CATEGORY_DISPLAY.get(item.category, item.category.title())
        categorized_items[display_category].append(item)
    
    return render(request, "admin/view_menu.html", {
        "categorized_items": dict(categorized_items),
        "selected_category": category.title() if category else "All",
    })

@login_required
@user_passes_test(is_admin)
def admin_add_user(request):
    message = None
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        role = request.POST.get("role")
        
        if username and password and role:
            if User.objects.filter(username=username).exists():
                message = "Username already exists! Choose a different one."
            else:
                User.objects.create(
                    username=username,
                    password=make_password(password),
                    role=role
                )
                return redirect("admin_users")
                
    return render(request, "admin/add_user.html", {"message": message})


@login_required
@user_passes_test(is_admin)
def admin_delete_user(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    if user.username != request.user.username:  # prevent deleting self
        user.delete()
        messages.success(request, f"User {user.username} deleted successfully.")
    else:
        messages.error(request, "You cannot delete your own account.")
    return redirect("admin_users")


# =====================
# Token Settings Management (ADD THESE NEW VIEWS)
# =====================
@login_required
@user_passes_test(is_admin)
def token_settings(request):
    settings = TokenSettings.load()
    
    if request.method == "POST":
        token_expiry_minutes = request.POST.get("token_expiry_minutes")
        auto_expire_tokens = request.POST.get("auto_expire_tokens") == "on"
        qr_payment_auto_use = request.POST.get("qr_payment_auto_use") == "on"
        
        try:
            settings.token_expiry_minutes = int(token_expiry_minutes)
            settings.auto_expire_tokens = auto_expire_tokens
            settings.qr_payment_auto_use = qr_payment_auto_use
            settings.save()
            messages.success(request, "Token settings updated successfully!")
            return redirect("token_settings")
        except ValueError:
            messages.error(request, "Invalid expiry minutes value.")
    
    return render(request, "admin/token_settings.html", {"settings": settings})


# =====================
# Manual Token Expiry Check (for testing)
# =====================
@login_required
@user_passes_test(is_admin)
def manual_expire_tokens(request):
    """Manual endpoint to expire tokens (for testing)"""
    from django.core.management import call_command
    call_command('expire_tokens')
    messages.success(request, "Manual token expiry check completed.")
    return redirect("admin_dashboard")

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from .models import MealToken
import json

def generate_qr_data(request, token_code):
    """
    Generate QR code data for a token
    URL: /api/tokens/<token_code>/qr-data/
    """
    try:
        # Get the token (using token_id field since that's what you have in your model)
        token = get_object_or_404(Token, token_id=token_code)
        
        # Create QR data structure
        qr_data = {
            'token_id': token.token_id,
            'status': token.status,
            'student_name': token.student.get_full_name() if token.student else 'Unknown',
            'student_id': token.student.username if token.student else 'Unknown',
            'created_at': token.created_at.isoformat(),
            'total_amount': float(token.total_amount),
            'items': []
        }
        
        # Add items if you have a related model for token items
        # If you have a TokenItem model, use this:
        if hasattr(token, 'items'):
            for item in token.items.all():
                qr_data['items'].append({
                    'name': item.food_item.name,
                    'quantity': item.quantity,
                    'price': float(item.food_item.price)
                })
        
        return JsonResponse({
            'success': True,
            'data': qr_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
    
from django.views import View
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .models import MealToken
import json

@method_decorator(csrf_exempt, name='dispatch')
class PaymentWebhookView(View):
    """
    Handle payment webhook notifications from UPI/payment gateway
    """
    
    def post(self, request, *args, **kwargs):
        try:
            # Parse the payment webhook data
            data = json.loads(request.body)
            
            # Extract payment details (adjust based on your payment provider)
            token_code = data.get('token_code')
            upi_transaction_id = data.get('transaction_id')
            payment_status = data.get('status')
            amount = data.get('amount')
            
            # Validate required fields
            if not token_code or not upi_transaction_id:
                return JsonResponse({
                    'success': False,
                    'error': 'Missing required fields'
                }, status=400)
            
            # Find the token
            try:
                token = MealToken.objects.get(code=token_code)
            except MealToken.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Token not found'
                }, status=404)
            
            # Process payment based on status
            if payment_status == 'success':
                # Mark token as paid and used
                if token.process_payment_success(upi_transaction_id):
                    return JsonResponse({
                        'success': True,
                        'message': 'Payment processed successfully',
                        'token_status': token.status
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'error': 'Failed to process payment for token'
                    }, status=400)
            
            elif payment_status == 'failed':
                # Handle failed payment
                return JsonResponse({
                    'success': False,
                    'error': 'Payment failed',
                    'token_status': token.status
                }, status=400)
            
            else:
                return JsonResponse({
                    'success': False,
                    'error': f'Unknown payment status: {payment_status}'
                }, status=400)
                
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)