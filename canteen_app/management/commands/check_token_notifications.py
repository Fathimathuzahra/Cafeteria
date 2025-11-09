from django.core.management.base import BaseCommand
from django.utils import timezone
from canteen_app.models import MealToken, TokenStatus, Notification
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Check for expiring tokens and send notifications every 30 minutes'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force check all tokens regardless of last notification time',
        )
    
    def handle(self, *args, **options):
        self.stdout.write("🔔 Starting token expiry notification check...")
        
        now = timezone.now()
        
        # Get active tokens that might need notifications
        active_tokens = MealToken.objects.filter(
            status__in=[TokenStatus.PENDING, TokenStatus.PAID]
        ).select_related('order__user')
        
        self.stdout.write(f"📊 Found {active_tokens.count()} active tokens to check")
        
        notifications_sent = 0
        tokens_expired = 0
        
        for token in active_tokens:
            try:
                # First, check if token should be expired
                if token.is_expired:
                    self.stdout.write(f"⏰ Token {token.code} has expired, marking as EXPIRED")
                    if token.mark_expired_auto():
                        # Create expired notification
                        token.create_expired_notification()
                        tokens_expired += 1
                        self.stdout.write(f"✅ Token {token.code} marked as expired with notification")
                    continue
                
                # Check if we should send expiry notification
                if options['force'] or token.should_send_expiry_notification():
                    notification = token.create_expiry_notification()
                    if notification:
                        notifications_sent += 1
                        time_left = token.get_time_until_expiry()
                        self.stdout.write(f"📨 Sent notification for {token.code} - {time_left}min remaining")
                
            except Exception as e:
                logger.error(f"Error processing token {token.code}: {e}")
                self.stdout.write(self.style.ERROR(f"❌ Error with token {token.code}: {str(e)}"))
        
        # Summary
        self.stdout.write("\n" + "="*50)
        if notifications_sent > 0 or tokens_expired > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"🎯 Notification check completed:\n"
                    f"   • Notifications sent: {notifications_sent}\n"
                    f"   • Tokens expired: {tokens_expired}"
                )
            )
        else:
            self.stdout.write("ℹ️  No notifications sent or tokens expired")
        
        self.stdout.write("="*50)