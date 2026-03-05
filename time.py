from datetime import datetime, time

# Get current time
def check_time():
    now = datetime.now().time()

    # Define time range
    start = time(19, 30)  # 7:30 PM
    end = time(20, 0)     # 8:00 PM

    # Check if current time is within the range
    if start <= now <= end:
        return True
    else:
        return False
