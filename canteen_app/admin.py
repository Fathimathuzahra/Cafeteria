# admin.py
from django.contrib import admin
from .models import (
    User, MenuItem, Order, OrderItem, MealToken,
    Notification, DailyReport, Feedback, Serving,
    Holiday, Review, HalfPortion, TokenStatusHistory,  # ADD THESE
    MealTokenCounter, TokenSettings  # ADD THESE
)

# -------------------
# User
# -------------------
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "role", "phone")
    list_filter = ("role",)
    search_fields = ("username", "phone")


# -------------------
# Menu Items & Half Portions
# -------------------
class HalfPortionInline(admin.StackedInline):
    model = HalfPortion
    can_delete = True
    verbose_name_plural = 'Half Portion Pricing'

@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "daily_quantity", "available_quantity", "available", "date_available", "has_half", "get_half_price")
    list_filter = ("category", "available", "has_half")
    search_fields = ("name",)
    inlines = [HalfPortionInline]
    
    def get_half_price(self, obj):
        return obj.half_price
    get_half_price.short_description = 'Half Price'


# -------------------
# Orders
# -------------------
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1
    readonly_fields = ['price']  # Price is now a property


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "meal_type", "order_date", "get_total_amount", "status")
    list_filter = ("status", "meal_type")
    search_fields = ("user__username",)
    inlines = [OrderItemInline]
    readonly_fields = ['total_amount']  # Total is now a property
    
    def get_total_amount(self, obj):
        return obj.total_amount
    get_total_amount.short_description = 'Total Amount'


# -------------------
# Tokens & Status History
# -------------------
class TokenStatusHistoryInline(admin.TabularInline):
    model = TokenStatusHistory
    extra = 0
    readonly_fields = ['timestamp']
    can_delete = False

@admin.register(MealToken)
class MealTokenAdmin(admin.ModelAdmin):
    list_display = ("code", "order", "token_number", "generated_at", "status", "get_served_by", "get_served_at")
    list_filter = ("status", "generated_at")
    search_fields = ("code", "order__user__username")
    readonly_fields = ['served_at', 'served_by', 'payment_time']  # These are now properties
    inlines = [TokenStatusHistoryInline]
    
    def get_served_by(self, obj):
        return obj.served_by
    get_served_by.short_description = 'Served By'
    
    def get_served_at(self, obj):
        return obj.served_at
    get_served_at.short_description = 'Served At'


@admin.register(TokenStatusHistory)
class TokenStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("token", "status", "timestamp", "served_by")
    list_filter = ("status", "timestamp")
    search_fields = ("token__code", "served_by__username")
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'


# -------------------
# Other Models
# -------------------
@admin.register(MealTokenCounter)
class MealTokenCounterAdmin(admin.ModelAdmin):
    list_display = ("date", "counter")
    readonly_fields = ['date', 'counter']

@admin.register(TokenSettings)
class TokenSettingsAdmin(admin.ModelAdmin):
    list_display = ("token_expiry_minutes", "auto_expire_tokens", "qr_payment_auto_use")
    def has_add_permission(self, request):
        return False  # Only one instance allowed


# -------------------
# Notifications
# -------------------
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "message", "created_at", "is_read")
    list_filter = ("is_read", "type")
    search_fields = ("user__username", "message")


@admin.register(DailyReport)
class DailyReportAdmin(admin.ModelAdmin):
    list_display = [
        "date",
        "menu_item",
        "total_tokens",
        "sold_count",
        "used_tokens_count",
        "cancelled_tokens_count",
        "expired_tokens_count",
        "reviews_count",
        "collected_count",
    ]
    list_filter = ["date"]
    search_fields = ["menu_item__name"]

    def reviews_count(self, obj):
        return obj.menu_item.review_set.count() if obj.menu_item else 0
    reviews_count.short_description = "Reviews"

    def collected_count(self, obj):
        return obj.used_tokens_count + obj.cancelled_tokens_count + obj.expired_tokens_count
    collected_count.short_description = "Collected Tokens"


# -------------------
# Feedback
# -------------------
@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("user", "item", "rating", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("user__username", "item__name")


# -------------------
# Serving - UPDATED
# -------------------
@admin.register(Serving)
class ServingAdmin(admin.ModelAdmin):
    list_display = ("get_item_name", "current_number", "updated_at")  # CHANGED: item_name → get_item_name
    list_filter = ("menu_item__category",)  # ADDED: Filter by category
    search_fields = ("menu_item__name",)  # CHANGED: Search by menu item name
    
    def get_item_name(self, obj):
        return obj.menu_item.name
    get_item_name.short_description = 'Item Name'  # Keep the same display name
    get_item_name.admin_order_field = 'menu_item__name'  # Enable ordering


# -------------------
# Holidays
# -------------------
@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ("holiday_date", "title", "ordering_disabled")
    list_filter = ("ordering_disabled", "holiday_date")
    search_fields = ("title",)


# -------------------
# Reviews
# -------------------
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("user", "item", "rating", "is_visible", "created_at")
    list_filter = ("rating", "is_visible", "created_at")
    search_fields = ("user__username", "comment")