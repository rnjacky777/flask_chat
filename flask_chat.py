from typing import List

import socketio
from database import SessionLocal, Message, User
from sqlalchemy.exc import SQLAlchemyError
from flask import request
from pathlib import Path
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
from werkzeug.security import check_password_hash, generate_password_hash
import qrcode
import os
from datetime import datetime
from database import get_db
from flask_socketio import SocketIO, emit

from schemas import MessageSchema
qr_base_dir = Path(__file__).resolve().parent

app = Flask(__name__)
app.secret_key = "1234"  # 隨便設，但一定要有
socketio = SocketIO(app)


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


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            return jsonify({"success": False, "error": "給我輸入帳密ZZZ"})

        try:
            db = SessionLocal()
            user = db.query(User).filter_by(username=username).first()
        except SQLAlchemyError as e:
            print(f"[DB ERROR] {e}")
            return jsonify({"success": False, "error": "Server side error"})
        finally:
            db.close()

        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            session["username"] = user.username
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "不是本人不要盜帳號"})

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()

        if not username or not password:
            return jsonify({"success": False, "error": "帳號和密碼不可為空。"})
        else:
            db = SessionLocal()
            try:
                existing_user = db.query(User).filter_by(
                    username=username).first()
                if existing_user:
                    return jsonify({"success": False, "error": "帳號已存在，請選擇其他帳號。"})
                else:
                    password_hash = generate_password_hash(password)
                    new_user = User(username=username,
                                    password_hash=password_hash)
                    db.add(new_user)
                    db.commit()
                    return jsonify({"success": True, "message": "註冊成功，請登入。"})
            except Exception:
                db.rollback()
                return jsonify({"success": False, "error": "註冊失敗，請稍後再試。"})
            finally:
                db.close()

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear() 
    return redirect("/login")


@app.route("/")
def main_page():
    qr_img_url = url_for("static", filename='qrcode.png')
    if "username" not in session:
        return redirect("/login")
    user_id = session.get("user_id")
    return render_template('chat.html', local_url=local_url, qr_img_url=qr_img_url,current_user_id=user_id)

@socketio.on("send_message")
def handle_send_message(data):
    content = data.get("message", "").strip()
    user_id = session.get("user_id")
    username = session.get("username") 

    if not user_id or not content:
        return

    db = SessionLocal()
    try:
        time_ = datetime.now()
        msg = Message(user_id=user_id, message=content, timestamp=datetime.now())
        db.add(msg)
        db.commit()

        emit("messages", {
            "user_id": user_id,
            "name":username,
            "message": content,
            "timestamp": time_.strftime("%Y-%m-%d %H:%M:%S")
        }, broadcast=True)

    except Exception:
        db.rollback()
        emit("error", {"message": "訊息儲存失敗"})
    finally:
        db.close()

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
        return jsonify({
            "messages": [msg.model_dump() for msg in pydantic_messages]
        })
    except Exception as e:
        return "Error", 500
    finally:
        db.close()


# === 主程式 ===
if __name__ == "__main__":
    local_ip = get_local_ip()
    local_url = f"http://{local_ip}:5000"
    app.config["local_url"] = local_url
    generate_qrcode(local_url)
    print(f"✅ Local Chatroom running at: {local_url}")
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)