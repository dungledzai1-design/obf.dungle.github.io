import httpx
import asyncio
import logging
import base64
import os
import json
import hashlib
import random
import re
from enum import Enum
from urllib.parse import urlencode
# dzi meo meo
logger = logging.getLogger("zalo")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class LoginQRCallbackEventType(Enum):
    QRCodeGenerated = 0
    QRCodeExpired = 1
    QRCodeScanned = 2
    QRCodeDeclined = 3
    GotLoginInfo = 4

HEADERS_BASE = {
    "accept-language": "vi-VN,vi;q=0.9,fr-FR;q=0.8,fr;q=0.7,en-US;q=0.6,en;q=0.5",
    "sec-ch-ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Referrer-Policy": "strict-origin-when-cross-origin"
}

DEFAULT_TIMEOUT = 10.0  

class ZaloApiError(Exception):
    pass

def generate_zalo_uuid(user_agent: str) -> str:
    md5_hash = hashlib.md5(user_agent.encode("utf-8")).hexdigest()
    return md5_hash[:16]

def generate_random_user_agent_windows_android():
    windows_platforms = [
        "Windows NT  10.0; Win64; x64",
        "Windows NT 6.1; Win64; x64",
    ]
    android_platforms = [
        "Linux; Android 10; SM-G970F",
        "Linux; Android 11; Pixel 4",
        "Linux; Android 12; SM-G991B",
    ]

    browsers = ["chrome", "firefox"]
    platform_type = random.choice(["windows", "android"])

    if platform_type == "windows":
        platform = random.choice(windows_platforms)
    else:
        platform = random.choice(android_platforms)

    browser = random.choice(browsers)

    if browser == "chrome":
        version_major = random.randint(90, 130)
        version_build = random.randint(1000, 4000)
        version_patch = random.randint(0, 150)
        user_agent = (f"Mozilla/5.0 ({platform}) AppleWebKit/537.36 (KHTML, like Gecko) "
                      f"Chrome/{version_major}.0.{version_build}.{version_patch} Safari/537.36")
    else:
        version_major = random.randint(80, 115)
        user_agent = (f"Mozilla/5.0 ({platform}; rv:{version_major}.0) Gecko/20100101 "
                      f"Firefox/{version_major}.0")

    return user_agent

USED_AGENTS_FILE = "used_agents.txt"

def load_used_agents():
    if not os.path.exists(USED_AGENTS_FILE):
        return set()
    with open(USED_AGENTS_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_used_agent(user_agent, imei):
    with open(USED_AGENTS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{user_agent}|||{imei}\n")

def generate_unique_user_agent_and_imei():
    used_agents = load_used_agents()
    attempt = 0
    while True:
        user_agent = generate_random_user_agent_windows_android()
        imei = generate_zalo_uuid(user_agent)
        key = f"{user_agent}|||{imei}"
        if key not in used_agents:
            save_used_agent(user_agent, imei)
            return user_agent, imei
        attempt += 1
        if attempt > 100:
            raise Exception("Không thể tạo userAgent và IMEI mới, vui lòng kiểm tra lại.")

async def load_login_page(client):
    url = "https://id.zalo.me/account?continue=https%3A%2F%2Fchat.zalo.me%2F"
    headers = {
        **HEADERS_BASE,
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "cache-control": "max-age=0",
        "priority": "u=0, i",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-site",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "Referer": "https://chat.zalo.me/",
    }
    resp = await client.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
    html = resp.text
    match = re.search(r"https://stc-zlogin\.zdn\.vn/main-([\d.]+)\.js", html)
    return match.group(1) if match else None

async def post_form(client, url, data, referer, extra_headers=None):
    headers = {
        **HEADERS_BASE,
        "accept": "*/*",
        "content-type": "application/x-www-form-urlencoded",
        "Referer": referer
    }
    if extra_headers:
        headers.update(extra_headers)
    resp = await client.post(url, headers=headers, data=urlencode(data), timeout=DEFAULT_TIMEOUT)
    return resp.json()

async def get_login_info(client, version):
    data = {"continue": "https://zalo.me/pc", "v": version}
    return await post_form(client, "https://id.zalo.me/account/logininfo", data, "https://id.zalo.me/account?continue=https%3A%2F%2Fzalo.me%2Fpc")

async def verify_client(client, version):
    data = {"type": "device", "continue": "https://zalo.me/pc", "v": version}
    return await post_form(client, "https://id.zalo.me/account/verify-client", data, "https://id.zalo.me/account?continue=https%3A%2F%2Fzalo.me%2Fpc")

async def generate_qr(client, version):
    data = {"continue": "https://zalo.me/pc", "v": version}
    return await post_form(client, "https://id.zalo.me/account/authen/qr/generate", data, "https://id.zalo.me/account?continue=https%3A%2F%2Fzalo.me%2Fpc")

async def waiting_scan(client, version, code, callback=None, timeout=100):
    start = asyncio.get_event_loop().time()
    while True:
        if asyncio.get_event_loop().time() - start > timeout:
            return {"error_code": "expired"}
        data = {"code": code, "continue": "https://chat.zalo.me/", "v": version}
        try:
            res = await post_form(client, "https://id.zalo.me/account/authen/qr/waiting-scan", data, "https://id.zalo.me/account?continue=https%3A%2F%2Fchat.zalo.me%2F")
            if res.get("error_code") != 8:
                return res
        except httpx.ReadTimeout:
            logger.warning("Timeout while waiting for QR scan. Retrying...")
        await asyncio.sleep(1)

async def waiting_confirm(client, version, code, callback=None, timeout=100):
    start = asyncio.get_event_loop().time()
    while True:
        if asyncio.get_event_loop().time() - start > timeout:
            return {"error_code": "expired"}
        data = {"code": code, "gToken": "", "gAction": "CONFIRM_QR", "continue": "https://chat.zalo.me/", "v": version}
        logger.info("Please confirm on your phone")
        try:
            res = await post_form(client, "https://id.zalo.me/account/authen/qr/waiting-confirm", data, "https://id.zalo.me/account?continue=https%3A%2F%2Fchat.zalo.me%2F")
            if res.get("error_code") != 8:
                return res
        except httpx.ReadTimeout:
            logger.warning("Timeout while waiting for QR confirmation. Retrying...")
        await asyncio.sleep(1)

async def check_session(client):
    url = "https://id.zalo.me/account/checksession?continue=https%3A%2F%2Fchat.zalo.me%2Findex.html"
    headers = {
        **HEADERS_BASE,
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "priority": "u=0, i",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "upgrade-insecure-requests": "1",
        "Referer": "https://id.zalo.me/account?continue=https%3A%2F%2Fchat.zalo.me%2F"
    }
    return await client.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)

async def get_user_info(client):
    url = "https://jr.chat.zalo.me/jr/userinfo"
    headers = {**HEADERS_BASE, "accept": "*/*", "Referer": "https://chat.zalo.me/"}
    resp = await client.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
    return resp.json()

async def login_qr(options=None, callback=None):
    options = options or {}
    user_agent = options.get("userAgent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")

    cookies = httpx.Cookies()
    headers = {**HEADERS_BASE, "User-Agent": user_agent}

    async with httpx.AsyncClient(cookies=cookies, headers=headers, follow_redirects=True) as client:
        version = await load_login_page(client)
        if not version:
            raise ZaloApiError("Cannot get API login version")
        logger.info(f"Got login version: {version}")

        await get_login_info(client, version)
        await verify_client(client, version)

        qr_json = await generate_qr(client, version)
        if not qr_json or not qr_json.get("data"):
            raise ZaloApiError(f"Unable to generate QRCode\nResponse: {qr_json}")
        qr_data = qr_json["data"]
        qr_image = qr_data["image"]
        if qr_image.startswith("data:image/png;base64,"):
            qr_image = qr_image.replace("data:image/png;base64,", "")

        def retry():
            return asyncio.create_task(login_qr(options, callback))
        def abort():
            return None
        actions = {"saveToFile": lambda path=None: None, "retry": retry, "abort": abort}

        if callback:
            await callback({"type": LoginQRCallbackEventType.QRCodeGenerated, "data": {**qr_data, "image": qr_image}, "actions": actions})

        scan_result = await waiting_scan(client, version, qr_data["code"], callback, timeout=100)
        if scan_result.get("error_code") == "expired":
            if callback:
                await callback({"type": LoginQRCallbackEventType.QRCodeExpired, "data": None, "actions": actions})
            return None
        if not scan_result or not scan_result.get("data"):
            return None

        logger.info(f"QR code scanned by {scan_result['data'].get('display_name', 'unknown user')}")
        if callback:
            await callback({"type": LoginQRCallbackEventType.QRCodeScanned, "data": scan_result["data"], "actions": actions})

        confirm_result = await waiting_confirm(client, version, qr_data["code"], callback, timeout=100)
        if confirm_result.get("error_code") == "expired":
            if callback:
                await callback({"type": LoginQRCallbackEventType.QRCodeExpired, "data": None, "actions": actions})
            return None
        if not confirm_result:
            return None

        try:
            await check_session(client)
        except httpx.UnsupportedProtocol as e:
            logger.warning(f"Bỏ qua lỗi UnsupportedProtocol khi check session: {e}")

        if confirm_result.get("error_code") == -13:
            if callback:
                await callback({"type": LoginQRCallbackEventType.QRCodeDeclined, "data": {"code": qr_data["code"]}, "actions": actions})
            return None
        elif confirm_result.get("error_code") != 0:
            raise ZaloApiError(f"An error occurred.\nResponse: {confirm_result}")

        user_info_json = await get_user_info(client)
        if not user_info_json:
            raise ZaloApiError("Can't get account info")
        if not user_info_json["data"].get("logged"):
            raise ZaloApiError("Can't login")

        cookie_dict = {cookie.name: cookie.value for cookie in client.cookies.jar}

        imei = cookie_dict.get("imei")
        if not imei:
            imei = user_info_json["data"]["info"].get("imei")
        if not imei:
            imei = generate_zalo_uuid(user_agent)

        user_info_data = user_info_json["data"]["info"]
        display_name = user_info_data.get("displayName") or user_info_data.get("name", "N/A")

        return {
            "cookies": cookie_dict,
            "user_info": {
                "displayName": display_name,
            },
            "imei": imei
        }

async def login_qr_with_unique_imei(callback=None):
    user_agent, imei = generate_unique_user_agent_and_imei()
    options = {"userAgent": user_agent}
    result = await login_qr(options=options, callback=callback)
    return result
