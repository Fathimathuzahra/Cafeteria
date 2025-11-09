from django.core.management.base import BaseCommand
from django.utils import timezone
from canteen_app.models import MealToken, TokenSettings, TokenStatus
from django.db import transaction

class Command(BaseCommand):
    help = "Automatically expire overdue tokens"

    def handle(self, *args, **options):
        self.stdout.write("=== TOKEN EXPIRY CHECK STARTED ===")
        
        # Check if auto expiry is enabled
        settings = TokenSettings.load()
        if not settings.auto_expire_tokens:
            self.stdout.write('❌ Auto token expiry is disabled in settings')
            return
        
        self.stdout.write('✅ Auto expiry is enabled')
        
        # REMOVE the 60-minute cutoff - check ALL tokens regardless of age
        # Count before
        pending_before = MealToken.objects.filter(status=TokenStatus.PENDING).count()
        paid_before = MealToken.objects.filter(status=TokenStatus.PAID).count()
        expired_before = MealToken.objects.filter(status=TokenStatus.EXPIRED).count()
        
        self.stdout.write(f"Before: PENDING={pending_before}, PAID={paid_before}, EXPIRED={expired_before}")
        
        expired_count = 0
        with transaction.atomic():
            # ✅ REMOVED THE CUTOFF - check all active tokens
            tokens_to_check = MealToken.objects.filter(
                status__in=[TokenStatus.PENDING, TokenStatus.PAID]
            )
            
            self.stdout.write(f"Checking {tokens_to_check.count()} active tokens for expiry...")
            
            for token in tokens_to_check:
                try:
                    if token.is_expired:
                        self.stdout.write(f"⏰ Token {token.code} is expired (created: {token.generated_at})")
                        if token.mark_expired_auto():
                            # Create expired notification
                            token.create_expired_notification()
                            expired_count += 1
                            self.stdout.write(f"✅ Successfully expired: {token.code} with notification")
                        else:
                            self.stdout.write(f"❌ Failed to expire: {token.code}")
                    else:
                        # Log tokens that are not expired yet
                        time_remaining = token.time_remaining
                        self.stdout.write(f"✅ Token {token.code} not expired yet ({time_remaining} mins remaining)")
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"💥 Error processing token {token.code}: {str(e)}")
                    )
                    continue
        
        # Count after
        pending_after = MealToken.objects.filter(status=TokenStatus.PENDING).count()
        paid_after = MealToken.objects.filter(status=TokenStatus.PAID).count()
        expired_after = MealToken.objects.filter(status=TokenStatus.EXPIRED).count()
        
        self.stdout.write(f"After: PENDING={pending_after}, PAID={paid_after}, EXPIRED={expired_after}")
        
        if expired_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'🎉 Successfully expired {expired_count} tokens')
            )
        else:
            self.stdout.write('ℹ️ No tokens to expire')
        
        # Summary Statistics
        total_tokens = MealToken.objects.count()
        self.stdout.write(f"\n📊 Summary Statistics:")
        self.stdout.write(f"Total tokens in system: {total_tokens}")
        self.stdout.write(f"Active tokens (PENDING+PAID): {pending_after + paid_after}")
        
        if total_tokens > 0:
            expired_percentage = (expired_after / total_tokens) * 100
            self.stdout.write(f"Expired tokens: {expired_after} ({expired_percentage:.1f}%)")
        else:
            self.stdout.write(f"Expired tokens: {expired_after} (0.0%)")
        
        self.stdout.write("=== TOKEN EXPIRY CHECK COMPLETED ===")