import telebot
import requests
import json
import os
import re
from flask import Flask
from threading import Thread
from bs4 import BeautifulSoup
from urllib.parse import quote

# Initialize bot and Flask app
MM = telebot.TeleBot('6235763696:AAFsybffK2OrVqEWUeVIKrd2MKV54nFkN4Y')

app = Flask(__name__)

YOUR_ADMIN_ID = 5495732905  # Replace with your admin ID

# File path for storing users
USERS_FILE = "users.json"

headers = {
    'authority': 'pinterestvideodownloader.com',
    'content-type': 'application/x-www-form-urlencoded',
}

# Function to load users from the users.json file
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r") as f:
        return json.load(f)

# Function to save users to users.json
def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)

# Flask route for the index
@app.route('/')
def index():
    return "Telegram Bot is running!"

# Function to run the Flask app
def run_flask():
    app.run(host="0.0.0.0", port=5000)

# Function to run the Telegram bot
def run_bot():
    MM.polling(non_stop=True)

# Function to start both Flask and the bot in separate threads
def start_services():
    # Start Flask server in a separate thread
    flask_thread = Thread(target=run_flask)
    flask_thread.start()

    # Start the Telegram bot in the main thread
    run_bot()

# Handle the /start command
@MM.message_handler(commands=['start'])
def seeee(mm):
    users = load_users()
    user_id = str(mm.from_user.id)
    if user_id not in users:
        users[user_id] = {"first_name": mm.from_user.first_name, "username": mm.from_user.username}
        save_users(users)
    markup = MM_2025(mm.from_user.id)
    MM.send_message(mm.chat.id, f"مرحبًا {mm.from_user.first_name}! 🌟\nفي بوت Pinterest، يمكنك البحث عن الصور ومقاطع الفيديو بسهولة. اختر أحد الخيارات من القائمة أدناه للبدء.", reply_markup=markup, parse_mode="Markdown")

# Function to create the inline keyboard for the start command
def MM_2025(user_id):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        telebot.types.InlineKeyboardButton("البحث - Search", callback_data='search'),
        telebot.types.InlineKeyboardButton("BOT'S OWNER 🤖", url='https://t.me/Fbi_mf'),  
        telebot.types.InlineKeyboardButton("مشاركة البوت - Share Bot", switch_inline_query=""),
        telebot.types.InlineKeyboardButton("تحميل صور من Pinterest - Download Images", callback_data='download_images'),
        telebot.types.InlineKeyboardButton("تنزيل مقاطع قصيرة من Pinterest - Download Videos", callback_data='download_videos')
    )
    if user_id == YOUR_ADMIN_ID:
        markup.add(telebot.types.InlineKeyboardButton("عرض عدد المستخدمين - Show Users Count", callback_data='users_count'))
    return markup

# Function to handle the "search" callback
@MM.callback_query_handler(func=lambda call: call.data == 'search')
def MM_Swad(trt):
    MM.edit_message_text("ما الموضوع الذي تريد البحث عنه؟ اكتب الكلمة المفتاحية وسأبحث لك عن الصور ذات الصلة.", chat_id=trt.message.chat.id, message_id=trt.message.message_id, reply_markup=F_MM(), parse_mode="Markdown")

# Back button in search
def F_MM():
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("رجوع", callback_data='back'))
    return markup

# Function to go back to the main menu
@MM.callback_query_handler(func=lambda call: call.data == 'back')
def MM_Tom(call):
    markup = MM_2025(call.from_user.id)
    MM.edit_message_text(f"مرحبًا {call.from_user.first_name}! 🌟\nفي بوت Pinterest، يمكنك البحث عن الصور ومقاطع الفيديو بسهولة. اختر أحد الخيارات من القائمة أدناه للبدء.", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# Main bot function to handle messages
@MM.message_handler(func=lambda message: True)
def MM_Six(mm):
    query = mm.text
    r = requests.get("https://www.pinterest.com/resource/BaseSearchResource/get/", headers={"User-Agent": "Mozilla/5.0"}, params={"source_url": f"/search/pins/?q={query}&rs=typed", "data": json.dumps({"options": {"query": query, "scope": "pins"}})})
    try:
        data = r.json()
        images = [item["images"]["orig"]["url"] for item in data["resource_response"]["data"]["results"] if "images" in item and "orig" in item["images"]]
    except (json.JSONDecodeError, KeyError):
        MM.send_message(mm.chat.id, f"عذرًا، لم أتمكن من العثور على صور تتطابق مع الكلمة المفتاحية: `{query}`.", parse_mode="Markdown")
        return
    if images:
        MM.send_photo(mm.chat.id, images[0], caption="Here is the first image!")
    else:
        MM.send_message(mm.chat.id, f"عذرًا، لم أتمكن من العثور على صور تتطابق مع الكلمة المفتاحية: `{query}`.", parse_mode="Markdown")

# Broadcast a message to all users (Admin only)
@MM.message_handler(commands=['broadcast'])
def broadcast_message(mm):
    if mm.from_user.id == YOUR_ADMIN_ID:
        users = load_users()
        if len(users) == 0:
            MM.send_message(mm.chat.id, "عذرًا، لا يوجد مستخدمين مسجلين في البوت حتى الآن.")
            return
        message = mm.text.replace("/broadcast", "").strip()
        if message == "":
            MM.send_message(mm.chat.id, "من فضلك، أدخل الرسالة التي تريد إرسالها إلى جميع المستخدمين.")
            return
        for user_id in users:
            try:
                MM.send_message(user_id, f"📢 إشعار عام من الإدارة:\n{message}", parse_mode="Markdown")
            except Exception as e:
                print(f"فشل في إرسال الرسالة إلى {user_id}: {e}")
        MM.send_message(mm.chat.id, f"تم إرسال الرسالة بنجاح إلى {len(users)} مستخدم.")
    else:
        MM.send_message(mm.chat.id, "عذرًا، هذا الأمر متاح فقط لمدير البوت.")

# Run both Flask app and bot
if __name__ == "__main__":
    start_services()
