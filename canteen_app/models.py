from decimal import Decimal
from datetime import timedelta
from django.db import models, transaction
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import post_save
from django.dispatch import receiver
import uuid
import logging


# -------------------
# Token Status Enum
# -------------------
class TokenStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PAID = "PAID", "Paid"
    USED = "USED", "Used"
    EXPIRED = "EXPIRED", "Expired"
    CANCELLED = "CANCELLED", "Cancelled"


# -------------------
# Custom User
# -------------------
class User(AbstractUser):
    ROLE_CHOICES = (
        ("user", "User"),
        ("canteenstaff", "Canteen Staff"),
        ("admin", "Admin"),
    )
    role = models.CharField(max_length=15, choices=ROLE_CHOICES, default="user")
    phone = models.CharField(max_length=20, blank=True, default="9999999999")

    def __str__(self):
        return f"{self.username} ({self.role})"


# -------------------
# Meal Token Counter
# -------------------
class MealTokenCounter(models.Model):
    date = models.DateField(default=timezone.localdate, unique=True)
    counter = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Counter for {self.date}: {self.counter}"


# -------------------
# Menu Item
# -------------------
class MenuItem(models.Model):
    CATEGORY_CHOICES = [
        ("breakfast", "Breakfast"),
        ("lunch", "Lunch"),
        ("snacks", "Snacks"),
        ("drinks", "Drinks"),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    image = models.ImageField(upload_to="menu_images/", blank=True, null=True)

    available = models.BooleanField(default=True)
    date_available = models.DateField(default=timezone.localdate)

    daily_quantity = models.DecimalField(
        max_digits=6, decimal_places=1, default=0,
        help_text="How many available today (supports .5 for half-portions)"
    )
    available_quantity = models.DecimalField(
        max_digits=6, decimal_places=1, default=0,
        help_text="Remaining quantity for today (supports halves)"
    )

    max_per_user_per_day = models.PositiveIntegerField(default=2)
    has_half = models.BooleanField(default=False)
    half_price = models.DecimalField(
        max_digits=8, decimal_places=2,
        null=True, blank=True,
        help_text="Price for half portion if allowed"
    )

    def __str__(self):
        return f"{self.name} ({self.category})"

    def is_available_now(self):
        return self.available

    def reset_daily_stock(self):
        self.available_quantity = Decimal(str(self.daily_quantity))
        self.available = self.daily_quantity > 0  # Fixed: No float conversion needed
        self.date_available = timezone.localdate()
        super().save(update_fields=["available_quantity", "available", "date_available"])

    def reduce_stock(self, qty=Decimal("1")):
        qty = Decimal(qty)
        if qty <= 0:
            raise ValueError("Quantity must be positive.")
        if qty > self.available_quantity:
            raise ValueError(f"Not enough {self.name} left today.")
        self.available_quantity -= qty
        self.available = self.available_quantity > 0
        super().save(update_fields=["available_quantity", "available"])

    def increase_stock(self, qty=Decimal("1")):
        qty = Decimal(qty)
        if qty <= 0:
            return
        self.available_quantity += qty
        self.available = self.available_quantity > 0
        super().save(update_fields=["available_quantity", "available"])

    def save(self, *args, **kwargs):
        today = timezone.localdate()
        if self.date_available != today:
            self.available_quantity = Decimal("0")
            self.available = False
            self.date_available = today
        super().save(*args, **kwargs)


# -------------------
# Orders & Items
# -------------------
class Order(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("preparing", "Preparing"),
        ("ready", "Ready for Pickup"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    MEAL_TYPE_CHOICES = [
        ("breakfast", "Breakfast"),
        ("lunch", "Lunch"),
        ("snacks", "Snacks"),
        ("drinks", "Drinks"),
        ("all", "All Items"),
    ]

    user = models.ForeignKey("User", on_delete=models.CASCADE)
    meal_type = models.CharField(max_length=20, choices=MEAL_TYPE_CHOICES, default="all")
    order_date = models.DateTimeField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    def __str__(self):
        return f"Order {self.id} - {self.user.username} ({self.status})"

    def calculate_total(self):
        total = sum(item.subtotal() for item in self.items.all())
        if self.total_amount != total:
            Order.objects.filter(pk=self.pk).update(total_amount=total)
            self.total_amount = total
        return total

    def detect_meal_type_from_items(self):
        if not self.pk:
            return "all"
            
        if self.items.exists():
            categories = list(self.items.values_list('menu_item__category', flat=True))
            if categories:
                from collections import Counter
                category_count = Counter(categories)
                most_common_category = category_count.most_common(1)[0][0]
                return most_common_category
        return "all"

    def save(self, *args, **kwargs):
            creating = self._state.adding  # Check if this is a new order
            
            # Your existing save logic
            if self.pk and (self.meal_type == "all" or not self.meal_type):
                detected_type = self.detect_meal_type_from_items()
                if detected_type != "all":
                    self.meal_type = detected_type
            
            if self.pk:
                self.calculate_total()
            
            super().save(*args, **kwargs)
            
            # AUTO-CREATE TOKEN WHEN ORDER IS CREATED AND HAS ITEMS
            # This is a backup to the signals
            if creating and self.items.exists():
                try:
                    # Use get_or_create to avoid duplicates
                    MealToken.objects.get_or_create(order=self)
                    print(f"Token automatically created for order #{self.id}")
                except Exception as e:
                    print(f"Error creating token for order #{self.id}: {e}")

    @property
    def display_meal_type(self):
        if self.meal_type != "all":
            return self.meal_type
        return self.detect_meal_type_from_items()


# -------------------
# Order Item
# -------------------
class OrderItem(models.Model):
    PORTION_CHOICES = [
        ("FULL", "Full"),
        ("HALF", "Half"),
    ]

    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    portion = models.CharField(max_length=4, choices=PORTION_CHOICES, default="FULL")

    def __str__(self):
        return f"{self.quantity} × {self.menu_item.name} (Order {self.order.id})"

    def subtotal(self):
        return (self.price or Decimal("0")) * Decimal(self.quantity)

    def save(self, *args, **kwargs):
        creating = self._state.adding
        if not self.price:
            if self.portion == "FULL" or not self.menu_item.has_half:
                self.price = self.menu_item.price
            else:
                self.price = (
                    self.menu_item.half_price
                    if self.menu_item.half_price is not None
                    else self.menu_item.price / Decimal("2")
                )

        if creating:
            unit_qty = Decimal(self.quantity)
            if self.portion == "HALF":
                unit_qty *= Decimal("0.5")

            today = timezone.localdate()
            if self.menu_item.date_available != today:
                self.menu_item.reset_daily_stock()

            if self.menu_item.available_quantity < unit_qty:
                raise ValueError(f"Sorry, only {self.menu_item.available_quantity} {self.menu_item.name} left today.")

            self.menu_item.reduce_stock(unit_qty)

        super().save(*args, **kwargs)
        
        if self.order:
            self.order.save()


# -------------------
# Token Settings Model
# -------------------
class TokenSettings(models.Model):
    token_expiry_minutes = models.PositiveIntegerField(default=90)
    auto_expire_tokens = models.BooleanField(default=True)
    qr_payment_auto_use = models.BooleanField(default=True)
    
    class Meta:
        verbose_name_plural = "Token Settings"
    
    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
    
    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
    
    def __str__(self):
        return "Token Settings"


# -------------------
# Meal Tokens
# -------------------
class MealToken(models.Model):
    logger = logging.getLogger(__name__)
    
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="meal_token")
    code = models.CharField(max_length=50, unique=True, editable=False)
    token_number = models.PositiveIntegerField(editable=False)
    generated_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=TokenStatus.choices, default=TokenStatus.PENDING)
    served_at = models.DateTimeField(null=True, blank=True)
    served_by = models.ForeignKey(
        "User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="served_tokens"
    )
    validity_minutes = models.PositiveIntegerField(default=90)

    payment_time = models.DateTimeField(null=True, blank=True)
    upi_transaction_id = models.CharField(max_length=100, blank=True, null=True)
    payment_verified = models.BooleanField(default=False)

    class Meta:
        ordering = ['-generated_at']

    def __str__(self):
        return f"Token {self.token_number} ({self.code}) - Order {self.order.id} [{self.status}]"

    def save(self, *args, **kwargs):
        if self._state.adding:
            today = timezone.localdate()
            if not self.order.items.exists():
                raise ValueError("Order has no items to create a token for.")

            with transaction.atomic():
                counter_obj, _ = MealTokenCounter.objects.select_for_update().get_or_create(date=today)

                for _ in range(10):
                    counter_obj.counter += 1
                    token_number = counter_obj.counter
                    code = f"T-{token_number:03d}"
                    if not MealToken.objects.filter(code=code).exists():
                        self.token_number = token_number
                        self.code = code
                        counter_obj.save()
                        break
                else:
                    # Log collision for monitoring
                    self.logger.warning(f"Token number collision detected for date {today}, using UUID fallback")
                    self.token_number = counter_obj.counter + 1
                    self.code = f"T-{uuid.uuid4().hex[:6].upper()}"
                    counter_obj.counter = self.token_number
                    counter_obj.save()

        super().save(*args, **kwargs)

    @property
    def expires_at(self):
        return self.generated_at + timedelta(minutes=self.validity_minutes)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at and self.status in [TokenStatus.PENDING, TokenStatus.PAID]

    @property
    def time_remaining(self):
        if self.status in [TokenStatus.USED, TokenStatus.EXPIRED, TokenStatus.CANCELLED]:
            return 0
        remaining = (self.expires_at - timezone.now()).total_seconds() / 60
        return max(0, int(remaining))

    @property
    def can_pay(self):
        return self.status == TokenStatus.PENDING and not self.is_expired

    @property
    def display_status(self):
        status_icons = {
            TokenStatus.PENDING: "⏳",
            TokenStatus.PAID: "✅", 
            TokenStatus.USED: "🍽️",
            TokenStatus.EXPIRED: "⏰",
            TokenStatus.CANCELLED: "❌"
        }
        return f"{status_icons.get(self.status, '')} {self.status}"

    def mark_used_auto(self):
        if self.status in [TokenStatus.PENDING, TokenStatus.PAID] and not self.is_expired:
            self.status = TokenStatus.USED
            self.served_at = timezone.now()
            self.save(update_fields=["status", "served_at"])
            
            self._update_daily_report_on_use()
            return True
        return False

    def mark_expired_auto(self):
        if self.status in [TokenStatus.PENDING, TokenStatus.PAID] and self.is_expired:
            self.status = TokenStatus.EXPIRED
            self.save(update_fields=["status"])
            
            self._update_daily_report_on_expiry()
            self._restore_stock_on_expiry()
            return True
        return False

    def process_upi_payment(self, transaction_id, verified=False):
        with transaction.atomic():
            if self.status != TokenStatus.PENDING:
                return False, "Token already processed."

            if self.is_expired:
                self.status = TokenStatus.EXPIRED
                self.save(update_fields=["status"])
                return False, "Token expired."

            if not verified:
                return False, "Payment not verified by gateway."

            self.status = TokenStatus.USED
            self.payment_time = timezone.now()
            self.upi_transaction_id = transaction_id
            self.payment_verified = True
            self.served_at = timezone.now()
            self.save(update_fields=["status", "payment_time", "upi_transaction_id", "payment_verified", "served_at"])

            self._update_daily_report_on_use()
            self._create_payment_success_notification()

            return True, "Payment successful and token marked as used."

    def _update_daily_report_on_use(self):
        for order_item in self.order.items.all():
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

    def _update_daily_report_on_expiry(self):
        for order_item in self.order.items.all():
            daily_report, created = DailyReport.objects.get_or_create(
                date=timezone.now().date(),
                menu_item=order_item.menu_item,
                defaults={
                    'total_tokens': 0,
                    'sold_count': order_item.quantity,
                    'used_tokens_count': 0,
                    'cancelled_tokens_count': 0,
                    'expired_tokens_count': 1
                }
            )
            if not created:
                daily_report.expired_tokens_count += 1
                daily_report.save()

    def _restore_stock_on_expiry(self):
        for order_item in self.order.items.all():
            qty = Decimal(order_item.quantity)
            if order_item.portion == "HALF":
                qty *= Decimal("0.5")
            order_item.menu_item.increase_stock(qty)

    def _create_payment_success_notification(self):
        try:
            exists = Notification.objects.filter(
                user=self.order.user,
                type="payment_success",
                message__icontains=self.code
            ).exists()

            if not exists:
                Notification.objects.create(
                    user=self.order.user,
                    message=f"✅ Payment confirmed! Token {self.code} has been served. Transaction ID: {self.upi_transaction_id}",
                    type="payment_success"
                )
        except Exception as e:
            self.logger.error(f"Notification creation failed for token {self.code}: {e}")

    def get_qr_payment_data(self):
        upi_id = "canteen@upi"
        amount = float(self.order.total_amount)
        note = f"College Canteen - Token {self.code}"
        
        upi_link = f"upi://pay?pa={upi_id}&pn=College%20Canteen&am={amount}&cu=INR&tn={note}"
        
        return {
            'upi_link': upi_link,
            'amount': amount,
            'token_code': self.code,
            'note': note
        }

    def validate_upi_transaction_format(self, transaction_id):
        """
        Enhanced validation with proper format checking
        """
        if not transaction_id:
            return False, "Transaction ID is required."
        
        transaction_id = transaction_id.strip()
        
        if len(transaction_id) < 8:
            return False, "Transaction ID too short (min 8 characters)."
        if len(transaction_id) > 20:
            return False, "Transaction ID too long (max 20 characters)."
        
        # Enhanced format validation - alphanumeric and uppercase
        if not transaction_id.isalnum():
            return False, "Transaction ID must contain only letters and numbers."
        
        # Optional: Enforce uppercase for consistency
        if transaction_id != transaction_id.upper():
            return False, "Transaction ID must be in uppercase."
            
        return True, "Format valid."

    # Compatibility methods
    def mark_used(self, served_by_user=None):
        if served_by_user and served_by_user.role == "canteenstaff":
            raise PermissionError("Staff cannot manually mark tokens as used. Use QR payment system.")
        
        if self.status != TokenStatus.PAID:
            return False
        return self.mark_used_auto()

    def mark_expired(self):
        if self.status != TokenStatus.PENDING or not self.is_expired:
            return False
        return self.mark_expired_auto()

    def mark_paid(self):
        if self.status == TokenStatus.PENDING:
            self.status = TokenStatus.PAID
            self.save(update_fields=["status"])
            return True
        return False

    def mark_cancelled(self):
        if self.status != TokenStatus.PENDING:
            return False
        
        with transaction.atomic():
            self.status = TokenStatus.CANCELLED
            self.save(update_fields=["status"])
            
            for oi in self.order.items.all():
                qty = Decimal(oi.quantity) * (Decimal("0.5") if oi.portion == "HALF" else Decimal("1.0"))
                oi.menu_item.increase_stock(qty)
            
            for order_item in self.order.items.all():
                daily_report, created = DailyReport.objects.get_or_create(
                    date=timezone.now().date(),
                    menu_item=order_item.menu_item,
                    defaults={
                        'total_tokens': 1,
                        'sold_count': order_item.quantity,
                        'used_tokens_count': 0,
                        'cancelled_tokens_count': 1,
                        'expired_tokens_count': 0
                    }
                )
                if not created:
                    daily_report.cancelled_tokens_count += 1
                    daily_report.save()
        
        return True

    def get_status_color(self):
        color_map = {
            TokenStatus.PENDING: 'warning',
            TokenStatus.PAID: 'info',
            TokenStatus.USED: 'success',
            TokenStatus.EXPIRED: 'danger',
            TokenStatus.CANCELLED: 'secondary'
        }
        return color_map.get(self.status, 'secondary')

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'token_number': self.token_number,
            'status': self.status,
            'generated_at': self.generated_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'is_expired': self.is_expired,
            'time_remaining': self.time_remaining,
            'can_pay': self.can_pay,
            'order_total': float(self.order.total_amount),
            'upi_transaction_id': self.upi_transaction_id,
            'payment_time': self.payment_time.isoformat() if self.payment_time else None,
            'served_at': self.served_at.isoformat() if self.served_at else None,
        }


# -------------------
# Daily Report
# -------------------
class DailyReport(models.Model):
    date = models.DateField(default=timezone.now)
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, null=True, blank=True)
    total_tokens = models.PositiveIntegerField(default=0)
    sold_count = models.PositiveIntegerField(default=0)
    used_tokens_count = models.PositiveIntegerField(default=0)
    cancelled_tokens_count = models.PositiveIntegerField(default=0)
    expired_tokens_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        menu_item_name = self.menu_item.name if self.menu_item else "Unknown"
        return f"{self.date} - {menu_item_name}"

    class Meta:
        unique_together = ['date', 'menu_item']
        
    @receiver(post_save, sender=MealToken)
    def update_daily_report_on_token_create(sender, instance, created, **kwargs):
        """
        Simple signal to update daily report when token is created
        """
        if created:
            date = instance.generated_at.date()
            for order_item in instance.order.items.all():
                daily_report, created = DailyReport.objects.get_or_create(
                    date=date,
                    menu_item=order_item.menu_item,
                    defaults={
                        'total_tokens': 1,
                        'sold_count': order_item.quantity,
                        'used_tokens_count': 0,
                        'cancelled_tokens_count': 0,
                        'expired_tokens_count': 0
                    }
                )
                if not created:
                    daily_report.total_tokens += 1
                    daily_report.sold_count += order_item.quantity
                    daily_report.save()
                    
    # @receiver(post_save, sender=MealToken)
    # def update_reports_on_token(sender, instance, created, **kwargs):
    #     date = instance.generated_at.date()
    #     for oi in instance.order.items.all():
    #         report, _ = DailyReport.objects.get_or_create(
    #             date=date,
    #             menu_item=oi.menu_item,
    #             defaults={
    #                 'total_tokens': 0,
    #                 'sold_count': 0,
    #                 'used_tokens_count': 0,
    #                 'cancelled_tokens_count': 0,
    #                 'expired_tokens_count': 0,
    #             }
    #         )
    #         if created:
    #             report.total_tokens += 1
    #             report.sold_count += oi.quantity

    #         report.used_tokens_count = DailyReport.objects.filter(
    #             date=date,
    #             menu_item=oi.menu_item,
    #             total_tokens__gte=1
    #         ).aggregate(total=models.Sum(
    #             models.Case(
    #                 models.When(order__meal_token__status=TokenStatus.USED, then=1),
    #                 default=0,
    #                 output_field=models.IntegerField()
    #             )
    #         ))['total'] or report.used_tokens_count

    #         report.cancelled_tokens_count = DailyReport.objects.filter(
    #             date=date,
    #             menu_item=oi.menu_item,
    #             total_tokens__gte=1
    #         ).aggregate(total=models.Sum(
    #             models.Case(
    #                 models.When(order__meal_token__status=TokenStatus.CANCELLED, then=1),
    #                 default=0,
    #                 output_field=models.IntegerField()
    #             )
    #         ))['total'] or report.cancelled_tokens_count

    #         report.expired_tokens_count = DailyReport.objects.filter(
    #             date=date,
    #             menu_item=oi.menu_item,
    #             total_tokens__gte=1
    #         ).aggregate(total=models.Sum(
    #             models.Case(
    #                 models.When(order__meal_token__status=TokenStatus.EXPIRED, then=1),
    #                 default=0,
    #                 output_field=models.IntegerField()
    #             )
    #         ))['total'] or report.expired_tokens_count

    #         report.save()


# -------------------
# Notifications
# -------------------
class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ("payment_success", "Payment Success"),
        ("payment_failure", "Payment Failure"),
        ("system", "System"),
        ("info", "Info"),
    ]

    user = models.ForeignKey("User", on_delete=models.CASCADE, related_name="notifications")
    message = models.CharField(max_length=255)
    created_at = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)
    type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default="info")

    def __str__(self):
        return f"Notification for {self.user.username}: {self.message}"


# -------------------
# Feedback
# -------------------
class Feedback(models.Model):
    user = models.ForeignKey("User", on_delete=models.CASCADE)
    item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comments = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Feedback by {self.user.username} for {self.item.name}"


# -------------------
# Review
# -------------------
class Review(models.Model):
    user = models.ForeignKey("User", on_delete=models.CASCADE)
    item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, null=True, blank=True)
    rating = models.PositiveIntegerField()
    comment = models.TextField()
    is_visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        item_name = self.item.name if self.item else "Unknown Item"
        return f"Review by {self.user.username} for {item_name}"


# -------------------
# Serving
# -------------------
class Serving(models.Model):
    item_name = models.CharField(max_length=100, default='Default Item')
    current_number = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    @staticmethod
    def next_number():
        serving, _ = Serving.objects.get_or_create(id=1)
        serving.current_number += 1
        serving.save(update_fields=["current_number"])
        return serving.current_number

    @staticmethod
    def reset_daily_serving():
        Serving.objects.update(current_number=0)

    def __str__(self):
        return self.item_name


# -------------------
# Holidays
# -------------------
class Holiday(models.Model):
    holiday_date = models.DateField(default=timezone.now)
    title = models.CharField(max_length=255, default='General Holiday')
    ordering_disabled = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=['holiday_date']),  # Added index for faster queries
        ]

    def __str__(self):
        return f"{self.title} ({self.holiday_date})"
    

    # ==================== ADD THESE SIGNALS ====================

@receiver(post_save, sender=Order)
def create_meal_token_for_order(sender, instance, created, **kwargs):
    """
    Automatically create a meal token when a new order is created and has items
    """
    if created and instance.items.exists():
        try:
            # Check if token already exists (shouldn't, but just in case)
            if not hasattr(instance, 'meal_token'):
                MealToken.objects.create(order=instance)
                print(f"✅ Token automatically created for order #{instance.id}")
        except Exception as e:
            print(f"❌ Error creating token for order #{instance.id}: {e}")

@receiver(post_save, sender=OrderItem)
def create_token_if_order_has_no_token(sender, instance, created, **kwargs):
    """
    Create token if order gets its first item and doesn't have a token yet
    """
    if created:
        order = instance.order
        if not hasattr(order, 'meal_token') and order.items.count() == 1:
            try:
                MealToken.objects.create(order=order)
                print(f"✅ Token created for order #{order.id} after adding first item")
            except Exception as e:
                print(f"❌ Error creating token: {e}")

# ==================== END OF SIGNALS ====================