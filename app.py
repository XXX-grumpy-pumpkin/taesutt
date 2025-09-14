from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, emit
from datetime import datetime, timezone
from collections import deque
import markdown
import bleach
import uuid
import os
from time import monotonic

app = Flask(__name__)
app.config['SECRET_KEY'] = 'change-me'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Single room
ROOM = "main"
HISTORY_LIMIT = 200
history = deque(maxlen=HISTORY_LIMIT)

# Auto-numbered usernames
user_counter = 0
sid_to_name = {}

# 최근 메시지 추적 (한글 IME 중복 방지)
recent_by_sid = {}  # {sid: {"text": str, "t": float}}

# Markdown/HTML sanitize allowlist
ALLOWED_TAGS = [
    'a','b','strong','i','em','u','s','code','pre','kbd','br',
    'p','ul','ol','li','blockquote'
]
ALLOWED_ATTRS = {
    'a': ['href','title','target','rel']
}
ALLOWED_PROTOCOLS = ['http','https','mailto']

def render_markdown_safe(text: str) -> str:
    html = markdown.markdown(text, extensions=['fenced_code', 'codehilite', 'nl2br'])
    clean = bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        protocols=ALLOWED_PROTOCOLS,
        strip=True
    )
    clean = bleach.linkify(clean, parse_email=True)
    return clean

@app.route("/")
def index():
    return render_template("index.html")

@socketio.on("join")
def on_join(_data=None):
    global user_counter
    sid = request.sid
    if sid not in sid_to_name:
        user_counter += 1
        sid_to_name[sid] = f"anonymous {user_counter}"
    username = sid_to_name[sid]

    join_room(ROOM)

    emit("set_username", {"username": username}, to=sid)
    emit("history", list(history), to=sid)

    emit("system", {
        "msg": f"{username} entered the chat",
        "ts": datetime.now(timezone.utc).isoformat()
    }, to=ROOM)

@socketio.on("chat_message")
def on_chat_message(data):
    sid = request.sid
    username = sid_to_name.get(sid, "anonymous")
    text = (data.get("text") if isinstance(data, dict) else "").strip()
    if not text:
        return

    # --- 한글 조합 중복 방지 ---
    now = monotonic()
    prev = recent_by_sid.get(sid)
    if prev:
        prev_text, prev_t = prev["text"], prev["t"]
        if (now - prev_t) < 0.6 and (
            text == prev_text or (len(text) <= 2 and prev_text.endswith(text))
        ):
            return  # 무시
    recent_by_sid[sid] = {"text": text, "t": now}

    html = render_markdown_safe(text)
    msg = {
        "id": str(uuid.uuid4()),
        "username": username,
        "text": text,
        "html": html,
        "ts": datetime.now(timezone.utc).isoformat()
    }
    history.append(msg)
    emit("chat_message", msg, to=ROOM)
    print("[server] RECV:", username, text, flush=True)

@socketio.on("typing")
def on_typing(_data=None):
    sid = request.sid
    username = sid_to_name.get(sid, "someone")
    emit("typing", {"username": username}, to=ROOM, include_self=False)

@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid
    username = sid_to_name.pop(sid, None)
    if username:
        emit("system", {
            "msg": f"{username} left the chat",
            "ts": datetime.now(timezone.utc).isoformat()
        }, to=ROOM)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    socketio.run(app, host="0.0.0.0", port=port)
