import os

import requests
from dotenv import load_dotenv


load_dotenv()

BASE_URL = "https://services.leadconnectorhq.com"
API_KEY = os.getenv("LEADCONNECTOR_API_KEY", "pit-fa2dcdfe-ec01-4ac0-a136-c6b81de499ca")
API_VERSION = "2021-07-28"


class GHLAPIError(Exception):
    pass

def send_email_message(contact_id, location_id, subject, body, email_to=None):
    if not body or not str(body).strip():
        raise ValueError("Email body is empty.")
    if not contact_id or not location_id or not subject:
        raise ValueError("contact_id, location_id, and subject are required.")

    url = f"{BASE_URL}/conversations/messages"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Version": API_VERSION,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    payload = {
        "type": "Email",
        "contactId": contact_id,
        "locationId": location_id,
        "subject": subject,
        # LeadConnector expects email content in `html` for Email messages.
        "html": str(body),
    }

    if email_to:
        payload["emailTo"] = email_to

    print("PAYLOAD:", payload)

    response = requests.post(url, headers=headers, json=payload, timeout=30)
    print("STATUS:", response.status_code)
    print("RESPONSE:", response.text)

    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    try:
        result = send_email_message(
            contact_id="c8FcC6lVydRwTlMNKFup",
            location_id="QRof2UTEMQswZAIO7A6Q",
            subject="Test email from Python",
            body="<p>Hello from Python via GoHighLevel API.</p>",
            email_to="03497748470b@gmail.com",  # optional

        )
        print("Email sent successfully:")
        print(result)
    except Exception as e:
        print(f"Failed to send email: {e}")
