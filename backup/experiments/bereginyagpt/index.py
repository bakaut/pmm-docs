import logging
from pythonjsonlogger import jsonlogger
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
import os
import json
import time
import hmac
import hashlib
from urllib.parse import urlencode, parse_qs
from supabase import create_client

# ──────────────────────────
#  LOGGING
# ──────────────────────────

#level=os.getenv("LOG_LEVEL", "INFO"),
class YcLoggingFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(YcLoggingFormatter, self).add_fields(log_record, record, message_dict)
        log_record['logger'] = record.name
        log_record['level'] = str.replace(str.replace(record.levelname, "WARNING", "WARN"), "CRITICAL", "FATAL")

# Set up the logger
logger = logging.getLogger('MyLogger')
logger.setLevel(logging.DEBUG)
logger.propagate = False

# Console Handler (for Yandex)
console_handler = logging.StreamHandler()
console_formatter = YcLoggingFormatter('%(message)s %(level)s %(logger)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# ──────────────────────────
#  ENVIRONMENT VARIABLES
# ──────────────────────────
SUPABASE_URL   = os.getenv("SUPABASE_URL")
SUPABASE_KEY   = os.getenv("SUPABASE_KEY")
PAYEER_ACCOUNT = os.getenv("PAYEER_SHOP_ID")
PAYEER_SECRET  = os.getenv("PAYEER_SECRET_KEY")
CALLBACK_URL   = os.getenv("CALLBACK_URL")  # https://some_id.apigw.yandexcloud.net/payeer_status

# ──────────────────────────
#  HELPERS
# ──────────────────────────

def generate_sign(parts: list[str]) -> str:
    """Генерируем HMAC-SHA256 подпись для Payeer"""
    msg = ":".join(parts)
    return hmac.new(PAYEER_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest().upper()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def handler(event: Dict[str, Any], context):  # noqa: C901
    logger.debug("Incoming event: %s", event)

    path   = event.get("path", "")
    method = event.get("httpMethod", "")
    body   = event.get("body", "")

    # Парсим JSON-тело, если есть
    try:
        data = json.loads(body) if body else {}
        logger.debug("Parsed body: %s", data)
    except json.JSONDecodeError:
        data = {}
        logger.error("Failed to parse JSON body")

    # Берём session_id из заголовка Openai-Ephemeral-User-Id, которое OpenAI передаёт автоматически
    headers = event.get("headers")
    session_id = headers.get("Openai-Ephemeral-User-Id")

    logger.debug("Initial session_id success")

    # 1) START SESSION
    if path == "/start_session" and method == "POST":
        logger.debug("Starting session")
        try:
            supabase.table('sessions').insert({
                'session_id': session_id,
                'start_ts': int(time.time())
            }).execute()
            body = {"status": "ok", "session_id": session_id}
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(body)
            }
        except Exception as e:
            logger.error("Failed to create session: %s", e)
            return {"statusCode": 500, "body": "Failed to execute query to create session"}

    # 2) CHECK SESSION
    if path == "/check_session" and method == "POST":
        logger.debug("Checking session")
        try:
            res = supabase.table("sessions").select("start_ts").eq('session_id', session_id).single().execute()
            logger.debug("Checked session: %s", res)

            start = res.data.get('start_ts') if res.data else None
            allowed = False
            if start and (time.time() - int(start)) < 3600:
                allowed = True
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"allowed": allowed})
            }
        except Exception as e:
            logger.error("Failed to check session: %s", e)
            return {"statusCode": 500, "body": "Failed to execute checking session query"}

    # 3) CREATE PAYEER PAYMENT
    if path == "/create_payeer_payment" and method == "POST":
        amount   = data.get('amount')
        currency = data.get('currency')
        ts       = int(time.time())
        order_id = f"{session_id}_{ts}"
        desc_hex = "Продление чата Custom GPT".encode("utf-8").hex()

        params = {
            "m_shop":       PAYEER_ACCOUNT,
            "m_orderid":    order_id,
            "m_amount":     f"{float(amount):.2f}",
            "m_curr":       currency,
            "m_desc":       desc_hex,
            "m_system_url": CALLBACK_URL,
            "m_expire":     3600
        }
        sign = generate_sign([
            params["m_shop"],
            params["m_orderid"],
            params["m_amount"],
            params["m_curr"],
            params["m_desc"]
        ])
        params["m_sign"] = sign

        # Сохраняем новый платёж в Supabase
        supabase.table('payments').insert({
            'order_id':   order_id,
            'session_id': session_id,
            'status':     False
        }).execute()

        url = (
            "https://payeer.com/merchant/?" +
            urlencode({k: params[k] for k in [
                "m_shop","m_orderid","m_amount",
                "m_curr","m_desc","m_sign"
            ]})
        )
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"payment_id": order_id, "url": url})
        }

    # 4) PAYEER CALLBACK
    if path == "/payeer_status" and method == "POST":
        form   = parse_qs(body)
        m_sign = form.get("m_sign", [""])[0]
        payload = {k: v[0] for k, v in form.items() if k != "m_sign"}

        parts = [
            payload["m_shop"], payload["m_orderid"],
            payload["m_amount"], payload["m_curr"],
            payload["m_desc"], payload["m_status"]
        ]
        if generate_sign(parts) != m_sign:
            return {"statusCode": 400, "body": "ERROR"}

        if payload.get("m_status") == "1":
            supabase.table('payments').update({'status': True}).eq('order_id', payload.get('m_orderid')).execute()
        return {"statusCode": 200, "body": "OK"}

    # 5) CHECK PAYEER PAYMENT
    if path == "/check_payeer_payment" and method == "POST":
        payment_id = data.get('payment_id')
        res = supabase.table("payments").select("status").eq('order_id', payment_id).single().execute()
        paid = bool(res.data.get('status')) if res.data else False
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"paid": paid})
        }

    # Если путь не распознан
    return {"statusCode": 404, "body": "Not Found"}
