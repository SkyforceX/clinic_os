import random, requests
from django.conf import settings
import hmac
import hashlib

def generate_otp():
    return str(random.randint(100000, 999999))


def make_appsecret_proof(access_token, app_secret):
    return hmac.new(
        app_secret.encode('utf-8'),
        access_token.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


def send_zalo_otp(phone, otp):
    ZALO_API_URL = 'https://business.openapi.zalo.me/message/template'
    ZALO_ACCESS_TOKEN = settings.ZALO_ACCESS_TOKEN  
    ZALO_TEMPLATE_ID = settings.ZALO_TEMPLATE_ID  
    ZALO_APP_SECRET = settings.ZALO_APP_SECRET  
    # appsecret_proof = make_appsecret_proof(ZALO_ACCESS_TOKEN, ZALO_APP_SECRET)

    headers = {
        'Content-Type': 'application/json',
        'access_token': ZALO_ACCESS_TOKEN,
    }
    data = {
        "phone": phone,
        "template_id": ZALO_TEMPLATE_ID,
        "template_data": {
            "otp": otp,
        },
        "tracking_id": "resetpw-" + phone + "-" + otp,
        "mode": "development",  # or "production" for live use
    }
    response = requests.post(ZALO_API_URL, json=data, headers=headers)
    print(response.status_code)
    print(response.text)
    return response.json()
    
