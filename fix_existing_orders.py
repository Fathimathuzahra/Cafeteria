import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'canteen.settings')
django.setup()

from canteen_app.models import Order
from collections import Counter

print("🔄 Fixing meal types for existing orders...")

orders_updated = 0
for order in Order.objects.all():
    detected_type = order.detect_meal_type_from_items()
    
    if detected_type != "all" and order.meal_type == "all":
        order.meal_type = detected_type
        order.save()
        orders_updated += 1
        print(f"✅ Updated Order #{order.id}: {detected_type}")

print(f"\n🎉 Updated {orders_updated} orders with proper meal types")