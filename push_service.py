import os
import json
import logging

logger = logging.getLogger(__name__)

_app = None
_enabled = False


def init_firebase():
    global _app, _enabled
    creds_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        logger.info("FIREBASE_SERVICE_ACCOUNT_JSON not set — push notifications disabled")
        return
    try:
        import firebase_admin
        from firebase_admin import credentials
        creds_dict = json.loads(creds_json)
        cred = credentials.Certificate(creds_dict)
        _app = firebase_admin.initialize_app(cred)
        _enabled = True
        logger.info("Firebase Admin SDK initialized — push notifications enabled")
    except Exception as e:
        logger.error(f"Firebase init failed: {e}")


def send_push(token: str, title: str, body: str, data: dict = None):
    if not _enabled or not token:
        return
    try:
        from firebase_admin import messaging
        msg = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in (data or {}).items()},
            token=token,
            android=messaging.AndroidConfig(priority="high"),
        )
        messaging.send(msg, app=_app)
    except Exception as e:
        logger.warning(f"Push send failed (token={token[:20]}…): {e}")
