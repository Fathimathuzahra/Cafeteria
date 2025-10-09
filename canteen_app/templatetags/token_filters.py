from django import template

register = template.Library()

# -------------------------------
# 1️⃣ Format Token Code
# -------------------------------
@register.filter
def format_token_code(code):
    """
    Format token code consistently as T-001, T-002, etc.
    Handles both numeric and alphanumeric codes.
    """
    if not code:
        return ""
    
    clean_code = str(code).replace('T:', '').replace('T-', '').strip()

    try:
        token_num = int(clean_code)
        return f"T-{token_num:03d}"  # e.g., T-001, T-045
    except (ValueError, TypeError):
        return f"T-{clean_code}"  # e.g., T-538EA9


# -------------------------------
# 2️⃣ Format Status
# -------------------------------
@register.filter
def format_status(status):
    """
    Format status for consistent display
    """
    if not status:
        return "Unknown"

    status_map = {
        'PENDING': 'Pending',
        'PAID': 'Paid',
        'USED': 'Used',
        'EXPIRED': 'Expired',
        'CANCELLED': 'Cancelled',
        'COMPLETED': 'Completed',
    }
    return status_map.get(status.upper(), status.title())


# -------------------------------
# 3️⃣ Format Meal Type
# -------------------------------
@register.filter
def format_meal_type(meal_type):
    """
    Format meal type for display
    """
    if not meal_type:
        return "Unknown"

    meal_type_map = {
        'all': 'All Items',
        'breakfast': 'Breakfast',
        'lunch': 'Lunch',
        'snacks': 'Snacks',
        'drinks': 'Drinks',
        'ai': 'All Items',
    }
    return meal_type_map.get(meal_type.lower(), meal_type.title())


# -------------------------------
# 4️⃣ Filter Tokens by Status
# -------------------------------
@register.filter
def filter_status(tokens, status):
    """
    Filters tokens queryset or list by the given status (case-insensitive).
    Usage: {{ tokens|filter_status:'PAID' }}
    """
    try:
        return tokens.filter(status__iexact=status)
    except Exception:
        return [t for t in tokens if getattr(t, 'status', '').lower() == status.lower()]
