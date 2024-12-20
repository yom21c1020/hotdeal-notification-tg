import logging
import sqlite3
from flask import Flask, request
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import os

WEBHOOK_URL = os.getenv('WEBHOOK_URL')
DB_PATH = '/app/db/database.db'
BOT_TOKEN = os.getenv('BOT_TOKEN')

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    with open('schema.sql', 'r') as f:
        cursor.executescript(f.read())
    conn.commit()
    conn.close()


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    chat_id = update.effective_chat.id

    # 사용자 등록
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username, chat_id) VALUES (?, ?, ?)",
        (user_id, username, chat_id)
    )
    conn.commit()
    conn.close()

    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")

async def add_keyword(update: Update, context):
    user_id = update.effective_user.id
    keyword = ' '.join(context.args)

    if not keyword:
        await update.message.reply_text("추가할 키워드를 입력해 주세요!")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO keywords (user_id, keyword) VALUES ((SELECT id FROM users WHERE user_id = ?), ?)",
        (user_id, keyword)
    )
    conn.commit()
    conn.close()

    await update.message.reply_text(f"키워드 '{keyword}'가 등록되었습니다.")


async def handle_message(update: Update, context):
    message_text = update.message.text
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 모든 사용자의 키워드 조회
    cursor.execute("SELECT user_id, keyword FROM keywords")
    keywords = cursor.fetchall()

    for user_id, keyword in keywords:
        if keyword in message_text:
            cursor.execute(
                "SELECT chat_id FROM users WHERE id = ?", (user_id,)
            )
            chat_id = cursor.fetchone()[0]

            await context.bot.send_message(chat_id=chat_id, text=f"키워드 '{keyword}' 감지: {message_text}")

    conn.close()

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()
    update = Update.de_json(data)
    app.update_queue.put(update)
    return "OK", 200

def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN not provided")
    
    # 데이터베이스 초기화
    if not os.path.exists(DB_PATH):
        init_db()

    # Bot 구성
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # 핸들러 추가
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_keyword))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Webhook 시작
    app.run_webhook(
        listen="0.0.0.0",
        port=8443,
        webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
    )

if __name__ == '__main__':
    main()