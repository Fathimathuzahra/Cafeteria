# admin.py
from django.contrib import admin
from .models import (
    User, MenuItem, Order, OrderItem, MealToken,
    Notification, DailyReport, Feedback, Serving,
    Holiday, Review
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
# Menu Items
# -------------------
@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "daily_quantity", "available_quantity", "available", "date_available")
    list_filter = ("category", "available")
    search_fields = ("name",)


# -------------------
# Orders
# -------------------
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "meal_type", "order_date", "total_amount", "status")
    list_filter = ("status", "meal_type")
    search_fields = ("user__username",)
    inlines = [OrderItemInline]


# -------------------
# Tokens
# -------------------
@admin.register(MealToken)
class MealTokenAdmin(admin.ModelAdmin):
    list_display = ("code", "order", "token_number", "generated_at", "status", "served_by")
    list_filter = ("status", "generated_at")
    search_fields = ("code", "order__user__username")


# -------------------
# Notifications
# -------------------
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "message", "created_at", "is_read")
    list_filter = ("is_read",)
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
# Serving
# -------------------
@admin.register(Serving)
class ServingAdmin(admin.ModelAdmin):
    list_display = ("item_name", "current_number", "updated_at")
    search_fields = ("item_name",)


# -------------------
# Holidays
# -------------------
@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ("holiday_date", "title", "ordering_disabled")
    list_filter = ("ordering_disabled",)
    search_fields = ("title",)


# -------------------
# Reviews
# -------------------
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("user", "item", "rating", "is_visible", "created_at")
    list_filter = ("rating", "is_visible")
    search_fields = ("user__username", "comment")