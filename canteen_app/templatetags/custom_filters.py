from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    return value * arg

# custom_filters.py
@register.filter
def sum_total(order_items):
    return sum([item.price * item.quantity for item in order_items])
from django import template

register = template.Library()

@register.filter
def format_token_code(value):
    """Format token code like TK-0001 or similar."""
    if not value:
        return ""
    return f"TK-{str(value).zfill(4)}"

@register.filter
def format_status(value):
    """Format status with proper capitalization."""
    if not value:
        return ""
    return str(value).capitalize()
