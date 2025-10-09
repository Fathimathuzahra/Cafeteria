from rest_framework import serializers
from .models import MealToken

class MealTokenSerializer(serializers.ModelSerializer):
    expires_at = serializers.DateTimeField(read_only=True)
    time_remaining = serializers.IntegerField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = MealToken
        fields = [
            'id', 'code', 'token_number', 'generated_at', 
            'status', 'expires_at', 'time_remaining', 'is_expired',
            'payment_time', 'upi_transaction_id'
        ]