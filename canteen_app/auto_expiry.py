import threading
import time
from django.core.management import call_command
from django.apps import AppConfig

class AutoExpiryConfig(AppConfig):
    name = 'canteen_app'
    
    def ready(self):
        """Start auto expiry when Django starts"""
        if not threading.current_thread().daemon:
            self.start_expiry_scheduler()
    
    def start_expiry_scheduler(self):
        """Start the token expiry scheduler in background"""
        def run_scheduler():
            while True:
                try:
                    print("Running token expiry check...")
                    call_command('token_expiry')
                except Exception as e:
                    print(f"Error in token expiry: {e}")
                # Wait 5 minutes (300 seconds)
                time.sleep(300)
        
        # Start in background thread
        thread = threading.Thread(target=run_scheduler, daemon=True)
        thread.start()
        print("✅ Auto token expiry scheduler started (runs every 5 minutes)")