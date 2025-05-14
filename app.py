import os
import sqlite3
from flask import Flask, request, abort
from dotenv import load_dotenv
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import openai

# .env読み込み
load_dotenv()

# 環境変数からAPIキーを取得
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
openai.api_key = os.getenv("OPENAI_API_KEY")



def init_db():
    conn = sqlite3.connect("chat_history.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()  # Flaskアプリ起動時にDB初期化


# SQLite接続
def get_chat_history(user_id):
    conn = sqlite3.connect("chat_history.db")
    cursor = conn.cursor()
    cursor.execute("SELECT role, content FROM messages WHERE user_id=? ORDER BY timestamp", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{"role": row[0], "content": row[1]} for row in rows]

def save_message(user_id, role, content):
    conn = sqlite3.connect("chat_history.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)", (user_id, role, content))
    conn.commit()
    conn.close()

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text

    keyword_replies = {
        "田中": "お前か、コロコロ言ってることが変わるバカは",
        "知輝": "お前か、コロコロ言ってることが変わるバカは",
        "山西": "お前あれじゃん、口だけのIQ低いやつじゃん",
        "西川": "よードブネズミ。早くポートフォリオ作れよ",
        "よしき": "よードブネズミ。早くポートフォリオ作れよ",
    }
    for keyword, reply in keyword_replies.items():
        if keyword in user_message:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=reply)
            )    
            return 
    
# systemにメッセージ（毒舌キャラ）
    system_message = {
        "role":"system",
        "content":"あなたは絶対に丁寧に話さない。上から話すかなり毒舌なAIです。必要な情報はしっかり教えます。"
    }
    history = get_chat_history(user_id)
    messages = [system_message]+history

    save_message(user_id, "user", user_message)
    history = get_chat_history(user_id)

    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages
    )

    ai_reply = response.choices[0].message.content.strip()
    save_message(user_id, "assistant", ai_reply)

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=ai_reply)
    )

if __name__ == "__main__":
    port=int(os.environ.get("PORT",5001))
    app.run(host="0.0.0.0",port=port)
