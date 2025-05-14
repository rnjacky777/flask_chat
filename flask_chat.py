from typing import List
from database import SessionLocal, Message, User
from sqlalchemy.exc import SQLAlchemyError
from flask import request,Response
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
import sqlite3
from werkzeug.security import check_password_hash, generate_password_hash
import qrcode
import os
from datetime import datetime
from database import Base, get_db
from flask_socketio import SocketIO, send

from schemas import MessageSchema
qr_base_dir = Path(__file__).resolve().parent

app = Flask(__name__)
app.secret_key = "1234"  # 隨便設，但一定要有

# === 資料庫設定（存在手機 Download/ChatMessages/ 資料夾） ===
DB_DIR = "./"
DB_PATH = os.path.join(DB_DIR, "chat.db")
os.makedirs(DB_DIR, exist_ok=True)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


init_db()

# === 取得本地內網 IP ===


def get_local_ip():
    import netifaces
    for iface in netifaces.interfaces():
        try:
            addrs = netifaces.ifaddresses(iface)
            if netifaces.AF_INET in addrs:
                ip = addrs[netifaces.AF_INET][0]['addr']
                print(f"📱 Detected Local IP: {ip}")
                if ip != "127.0.0.1":
                    return ip
        except Exception:
            continue
    return "127.0.0.1"

# === 產生 QRCode 儲存 Download/QRcode ===


def generate_qrcode(url):
    # 找到目前檔案位置，定位 static/qr_codes 資料夾
    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)

    img_path = static_dir / "qrcode.png"

    if img_path.exists():
        img_path.unlink()  # 刪除舊的 QR 圖片

    qrcode.make(url).save(img_path)
    print(f"✅ QR Code saved at: {img_path}, ip is {url}")
    return str(img_path)

# === 登入 ===


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            return render_template("login.html", error="給我輸入帳密ZZZ")
        try:
            db = SessionLocal()
            user = db.query(User).filter_by(username=username).first()
        except SQLAlchemyError as e:
            print(f"[DB ERROR] {e}")
            return render_template("login.html", error="Server side error")
        finally:
            db.close()

        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            session["username"] = user.username
            return redirect("/")
        else:
            return render_template("login.html", error="不是本人不要盜帳號")

    return render_template("login.html", error=error)

# === 註冊 ===


@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    success = None

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()

        if not username or not password:
            error = "帳號和密碼不可為空。"
        else:
            password_hash = generate_password_hash(password)
            db = SessionLocal()
            try:
                # 檢查是否已有該帳號
                existing_user = db.query(User).filter_by(
                    username=username).first()
                if existing_user:
                    error = "帳號已存在，請選擇其他帳號。"
                else:
                    # 新增使用者
                    new_user = User(username=username,
                                    password_hash=password_hash)
                    db.add(new_user)
                    db.commit()
                    success = "註冊成功，請登入。"
                    return redirect("/login")  # 或直接登入
            except Exception:
                db.rollback()
                error = "註冊失敗，請稍後再試。"
            finally:
                db.close()

    return render_template("register.html", error=error, success=success)

# === 登出 ===


@app.route("/logout")
def logout():
    session.clear() 
    return redirect("/login")


@app.route("/")
def main_page():
    qr_img_url = url_for("static", filename='qrcode.png')
    if "username" not in session:
        return redirect("/login")
    return render_template('chat.html', local_url=local_url, qr_img_url=qr_img_url)

@app.route("/send_msg", methods=["POST"])
def send_msg():
    message = request.form.get("message", "").strip()
    timestamp = datetime.now()

    db = next(get_db())
    try:
        new_message = Message(message=message,
                              user_id=session["user_id"],
                              timestamp=timestamp)
        db.add(new_message)
        db.commit()
        return Response(status=200)
    except SQLAlchemyError as e:
        db.rollback()
        return Response("Error saving message", status=500)
    finally:
        db.close()


# === 讀取訊息 ===
@app.route("/get_recent_msg", methods=["GET"])
def get_recent_messages():
    db = next(get_db())
    try:
        rows: List[Message] = db.query(
            Message).order_by(Message.id.asc()).all()
        pydantic_messages: List[MessageSchema] = [MessageSchema(timestamp=msg.timestamp,
                                                                name=msg.user.username,
                                                                message=msg.message,
                                                                user_id=msg.user_id) for msg in rows]
        current_user_id = session.get("user_id")
        return jsonify({
            "current_user_id": current_user_id,
            "messages": [msg.model_dump() for msg in pydantic_messages]
        })
    except Exception as e:
        return "Error", 500
    finally:
        db.close()


# === 主程式 ===
if __name__ == "__main__":
    local_ip = get_local_ip()
    local_url = f"http://{local_ip}:8080"
    app.config["local_url"] = local_url
    generate_qrcode(local_url)
    print(f"✅ Local Chatroom running at: {local_url}")
    app.run(host="0.0.0.0", port=8080, debug=True)
