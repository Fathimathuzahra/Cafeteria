import os
import django
from django.db import connection, connections

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'canteen.settings')
django.setup()

print("🧹 Clearing Django database cache...")

# Clear all connection caches
for conn_name in connections:
    connection = connections[conn_name]
    
    # Clear table cache
    if hasattr(connection, 'introspection'):
        if hasattr(connection.introspection, '_table_cache'):
            connection.introspection._table_cache = {}
            print(f"✅ Cleared table cache for {conn_name}")
    
    # Clear table description cache  
    if hasattr(connection, '_table_description_cache'):
        connection._table_description_cache = {}
        print(f"✅ Cleared table description cache for {conn_name}")

# Close all connections
connection.close()
connections.close_all()
print("✅ Database connections closed and cache cleared.")

# Test the connection
print("\n🧪 Testing database connection...")
from canteen_app.models import MealToken
try:
    token = MealToken.objects.first()
    if token:
        print(f"✅ SUCCESS! Can access token: {token.code}")
        print(f"   Payment time: {token.payment_time}")
        print(f"   UPI ID: {token.upi_transaction_id}")
    else:
        print("✅ SUCCESS! ORM working (no tokens in DB)")
except Exception as e:
    print(f"❌ Error: {e}")