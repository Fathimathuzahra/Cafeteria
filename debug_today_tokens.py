import os
import django
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'canteen.settings')
django.setup()

from canteen_app.models import MealToken, Order
from datetime import datetime

print("🔍 DEEP DEBUG - ALL TOKENS ANALYSIS")
print("=" * 70)

# Get current time info
now = timezone.now()
today = now.date()
print(f"Current server time: {now}")
print(f"Today's date: {today}")

# Check all tokens in the system
all_tokens = MealToken.objects.all().order_by('-generated_at')
print(f"\n📊 Total tokens in system: {all_tokens.count()}")

if all_tokens.exists():
    print(f"\n📋 ALL TOKENS (newest first):")
    for token in all_tokens:
        token_date = token.generated_at.date()
        is_today = token_date == today
        time_diff = now - token.generated_at
        
        print(f"  - {token.code}: {token.status}")
        print(f"    Generated: {token.generated_at}")
        print(f"    Date: {token_date} (Today: {is_today})")
        print(f"    Age: {time_diff}")
        print(f"    Order ID: {token.order.id}")
        print()
else:
    print("❌ No tokens exist in the system at all!")

# Check recent orders
print(f"\n🛒 RECENT ORDERS:")
recent_orders = Order.objects.all().order_by('-order_date')[:5]
for order in recent_orders:
    has_token = hasattr(order, 'meal_token')
    print(f"  - Order #{order.id}: {order.order_date} | Has token: {has_token}")

print("=" * 70)