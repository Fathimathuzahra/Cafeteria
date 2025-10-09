from background_task import background
from django.core.management import call_command

@background(schedule=300)  # 5 minutes in seconds
def run_token_expiry():
    call_command('token_expiry')

# Start the task (call this once)
run_token_expiry(repeat=300)  # Repeat every 5 minutes