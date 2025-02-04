import telebot
import requests
import json
import os
import re
from bs4 import BeautifulSoup
from urllib.parse import quote

# Telegram Bot Token
BOT_TOKEN = "6235763696:AAFsybffK2OrVqEWUeVIKrd2MKV54nFkN4Y"  # Replace with your actual bot token
ADMIN_ID = 5495732905  # Replace with your Telegram User ID

bot = telebot.TeleBot(BOT_TOKEN)

USERS_FILE = "users.json"

headers = {
    'authority': 'pinterestvideodownloader.com',
    'content-type': 'application/x-www-form-urlencoded',
}

# Load users from JSON file
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r") as f:
        return json.load(f)

# Save users to JSON file
def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)

# Handle /start command
@bot.message_handler(commands=['start'])
def start_message(message):
    users = load_users()
    user_id = str(message.from_user.id)

    if user_id not in users:
        users[user_id] = {"first_name": message.from_user.first_name, "username": message.from_user.username}
        save_users(users)

    markup = get_main_menu(user_id)
    bot.send_message(message.chat.id, f"مرحبا {message.from_user.first_name}! 🌟\n"
                                      "في بوت Pinterest، يمكنك البحث عن الصور ومقاطع الفيديو بسهولة.\n"
                                      "اختر أحد الخيارات من القائمة أدناه للبدء.",
                     reply_markup=markup, parse_mode="Markdown")

# Main Menu Markup
def get_main_menu(user_id):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        telebot.types.InlineKeyboardButton("🔍 البحث", callback_data='search'),
        telebot.types.InlineKeyboardButton("📌 تحميل صور", callback_data='download_images'),
        telebot.types.InlineKeyboardButton("🎥 تحميل فيديو", callback_data='download_videos'),
        telebot.types.InlineKeyboardButton("🤖 صاحب البوت", url='https://t.me/Fbi_mf'),
        telebot.types.InlineKeyboardButton("📢 مشاركة البوت", switch_inline_query="")
    )

    if int(user_id) == ADMIN_ID:
        markup.add(telebot.types.InlineKeyboardButton("📊 عدد المستخدمين", callback_data='users_count'))

    return markup

# Handle callback queries (buttons)
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.data == 'search':
        bot.edit_message_text("🔍 أدخل الكلمة المفتاحية للبحث عن الصور:", chat_id=call.message.chat.id,
                              message_id=call.message.message_id, parse_mode="Markdown")
    elif call.data == 'download_images':
        bot.send_message(call.message.chat.id, "✏️ أدخل الكلمة المفتاحية لتحميل الصور من Pinterest.")
        bot.register_next_step_handler(call.message, download_pinterest_images)
    elif call.data == 'download_videos':
        bot.send_message(call.message.chat.id, "📌 أرسل رابط فيديو Pinterest لتنزيله.")
        bot.register_next_step_handler(call.message, download_pinterest_video)
    elif call.data == 'users_count' and call.from_user.id == ADMIN_ID:
        users = load_users()
        bot.answer_callback_query(call.id, f"👥 عدد المستخدمين: {len(users)}")

# Function to download Pinterest images
def download_pinterest_images(message):
    query = message.text
    chat_id = message.chat.id
    bot.send_message(chat_id, f"🔄 جاري البحث عن صور لـ: `{query}`...", parse_mode="Markdown")

    try:
        response = requests.get(
            f"https://www.pinterest.com/resource/BaseSearchResource/get/?source_url=/search/pins/?q={quote(query)}",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        data = response.json()
        images = [item["images"]["orig"]["url"] for item in data.get("resource_response", {}).get("data", {}).get("results", []) if "images" in item]

        if images:
            for img_url in images[:5]:  # Send only first 5 images
                bot.send_photo(chat_id, img_url)
            bot.send_message(chat_id, f"✅ تم إرسال {len(images[:5])} صور بنجاح!")
        else:
            bot.send_message(chat_id, "❌ لم يتم العثور على صور!")

    except Exception as e:
        bot.send_message(chat_id, f"⚠️ خطأ أثناء جلب الصور: {e}")

# Function to download Pinterest videos
def download_pinterest_video(message):
    url = message.text
    chat_id = message.chat.id
    processing_msg = bot.send_message(chat_id, '🔄 جاري معالجة الفيديو...')

    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    data = {'url': url}
    response = requests.post('https://pinterestvideodownloader.com/download.php', headers=headers, data=data).text
    video_links = re.findall(r'<video src="(.*?)"', response)

    if video_links:
        bot.delete_message(chat_id, processing_msg.message_id)
        bot.send_video(chat_id, video_links[0], caption="✅ تم تحميل الفيديو بنجاح!")
    else:
        bot.delete_message(chat_id, processing_msg.message_id)
        bot.send_message(chat_id, "❌ لم يتم العثور على فيديو!")

# Function for admin broadcast
@bot.message_handler(commands=['broadcast'])
def broadcast_message(message):
    if message.from_user.id == ADMIN_ID:
        users = load_users()
        broadcast_text = message.text.replace("/broadcast", "").strip()

        if not broadcast_text:
            bot.send_message(message.chat.id, "❌ يجب إدخال نص الرسالة.")
            return

        for user_id in users:
            try:
                bot.send_message(user_id, f"📢 إشعار هام:\n{broadcast_text}")
            except Exception as e:
                print(f"⚠️ فشل الإرسال إلى {user_id}: {e}")

        bot.send_message(message.chat.id, f"✅ تم إرسال الرسالة إلى {len(users)} مستخدم.")

# Start bot polling
bot.polling()
