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
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        with open('schema.sql', 'r') as f:
            cursor.executescript(f.read())
        conn.commit()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    chat_id = update.effective_chat.id

    logger.info(f"Starting registration for user_id: {user_id}, username: {username}, chat_id: {chat_id}")

    # 사용자 등록
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO users (user_id, username, chat_id) VALUES (?, ?, ?)",
                (user_id, username, chat_id)
            )
            conn.commit()
        await update.message.reply_text("안녕하세요! 키워드를 등록하고 알림을 받아보세요. /add로 키워드를 추가해주세요.")
        logger.info(f"User {username} registered successfully.")

    except Exception as e:
        logger.error(f"Error registering user {username}: {e}")
        await update.message.reply_text("사용자 등록 중 오류가 발생했어요. 다시 시도해 주세요.")

async def add_keyword(update: Update, context):
    user_id = update.effective_user.id
    keyword = ' '.join(context.args)

    if not keyword:
        await update.message.reply_text("추가할 키워드를 입력해 주세요!")
        return

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO keywords (user_id, keyword) VALUES ((SELECT id FROM users WHERE user_id = ?), ?)",
            (user_id, keyword)
        )
        conn.commit()

    await update.message.reply_text(f"키워드 '{keyword}'가 등록되었습니다.")

    logger.info(f"Keyword '{keyword}' added for user {update.effective_user.username}")

async def remove_keyword(update: Update, context):
    user_id = update.effective_user.id
    keyword = ' '.join(context.args)

    if not keyword:
        await update.message.reply_text("삭제할 키워드를 입력해 주세요!")
        return
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            
            if not result:
                await update.message.reply_text("등록되지 않은 사용자예요. /start로 등록해주세요.")
                return
            
            user_id = result[0]
            cursor.execute("SELECT keyword FROM keywords WHERE user_id = ?", (user_id,))
            keyword_list = [row[0] for row in cursor.fetchall()]
            
            if not keyword_list:
                await update.message.reply_text("등록된 키워드가 없어요. /add로 키워드를 추가해주세요.")
                return
            
            if keyword not in keyword_list:
                await update.message.reply_text("등록되지 않은 키워드예요. /add로 키워드를 추가해주세요.")
                return
            
            cursor.execute("DELETE FROM keywords WHERE user_id = ? AND keyword = ?", (user_id, keyword))
            conn.commit()
            await update.message.reply_text(f"키워드 '{keyword}'가 삭제되었어요.")
            logger.info(f"Keyword '{keyword}' removed for user {update.effective_user.username}")
        
    except Exception as e:
        await update.message.reply_text("키워드 삭제 중 오류가 발생했어요. 상세 내용은 다음과 같아요.")
        await update.message.reply_text(f"Error: '{e}'")
        if keyword:
            logger.error(f"Error removing keyword '{keyword}' for user {update.effective_user.username}: {e}")
        else:
            logger.error(f"Error removing keyword for user {update.effective_user.username}: {e}")

async def handle_message(update: Update, context):
    message_text = update.message.text
    with sqlite3.connect(DB_PATH) as conn:
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
                logger.info(f"Keyword '{keyword}' detected in message: {message_text}")


@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()
    update = Update.de_json(data)
    app.update_queue.put(update)
    return "OK", 200

def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN not provided")
    if not WEBHOOK_URL:
        raise ValueError("WEBHOOK_URL not provided")
    
    # 데이터베이스 초기화
    if not os.path.exists(DB_PATH):
        init_db()
        logger.info("Database initialized successfully.")

    # Bot 구성
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # 핸들러 추가
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_keyword))
    app.add_handler(CommandHandler("remove", remove_keyword))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Webhook 시작
    app.run_webhook(
        listen="0.0.0.0",
        port=8000,
        webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
    )

if __name__ == '__main__':
    main()