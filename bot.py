import telebot
import requests
import json
import os
import re
from bs4 import BeautifulSoup
from urllib.parse import quote 

MM = telebot.TeleBot('6235763696:AAFsybffK2OrVqEWUeVIKrd2MKV54nFkN4Y')

YOUR_ADMIN_ID = 5495732905 #ايديك

USERS_FILE = "users.json"

headers = {
    'authority': 'pinterestvideodownloader.com',
    'content-type': 'application/x-www-form-urlencoded',
}

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)

def aslyou(you):
    if not os.path.exists(f"{you}.json"):
        return {"query": "", "images": [], "current_image_index": 0}
    with open(f"{you}.json", "r") as f:
        return json.load(f)

def MM_fuck(you, data):
    with open(f"{you}.json", "w") as f:
        json.dump(data, f)

@MM.message_handler(commands=['start'])
def seeee(mm):
    users = load_users()
    user_id = str(mm.from_user.id)
    if user_id not in users:
        users[user_id] = {"first_name": mm.from_user.first_name, "username": mm.from_user.username}
        save_users(users)
    markup = MM_2025(mm.from_user.id)
    MM.send_message(mm.chat.id, f"مرحبًا {mm.from_user.first_name}! 🌟\nفي بوت Pinterest، يمكنك البحث عن الصور ومقاطع الفيديو بسهولة. اختر أحد الخيارات من القائمة أدناه للبدء.", reply_markup=markup, parse_mode="Markdown")

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

@MM.callback_query_handler(func=lambda call: call.data == 'search')
def MM_Swad(trt):
    MM.edit_message_text("ما الموضوع الذي تريد البحث عنه؟ اكتب الكلمة المفتاحية وسأبحث لك عن الصور ذات الصلة.", chat_id=trt.message.chat.id, message_id=trt.message.message_id, reply_markup=F_MM(), parse_mode="Markdown")

def F_MM():
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("رجوع", callback_data='back'))
    return markup

@MM.callback_query_handler(func=lambda call: call.data == 'back')
def MM_Tom(call):
    markup = MM_2025(call.from_user.id)
    MM.edit_message_text(f"مرحبًا {call.from_user.first_name}! 🌟\nفي بوت Pinterest، يمكنك البحث عن الصور ومقاطع الفيديو بسهولة. اختر أحد الخيارات من القائمة أدناه للبدء.", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@MM.message_handler(func=lambda message: True)
def MM_Six(mm):
    Dr = aslyou(mm.from_user.id)
    query = mm.text
    r = requests.get("https://www.pinterest.com/resource/BaseSearchResource/get/", headers={"User-Agent": "Mozilla/5.0"}, params={"source_url": f"/search/pins/?q={query}&rs=typed", "data": json.dumps({"options": {"query": query, "scope": "pins"}})})
    try:
        data = r.json()
        Dr['images'] = [item["images"]["orig"]["url"] for item in data["resource_response"]["data"]["results"] if "images" in item and "orig" in item["images"]]
    except (json.JSONDecodeError, KeyError):
        MM.send_message(mm.chat.id, f"عذرًا، لم أتمكن من العثور على صور تتطابق مع الكلمة المفتاحية: `{query}`.", parse_mode="Markdown")
        return
    Dr['query'] = query
    Dr['current_image_index'] = 0
    MM_fuck(mm.from_user.id, Dr)
    if Dr['images']:
        MM_Gr(mm.chat.id, Dr)
    else:
        MM.send_message(mm.chat.id, f"عذرًا، لم أتمكن من العثور على صور تتطابق مع الكلمة المفتاحية: `{query}`.", parse_mode="Markdown")

def MM_Gr(chat_id, Dr):
    if Dr['current_image_index'] < len(Dr['images']):
        markup = MM_Komblit()
        MM.send_photo(chat_id, Dr['images'][Dr['current_image_index']], caption=f"الصورة {Dr['current_image_index'] + 1} من {len(Dr['images'])}", reply_markup=markup)
    else:
        pass

def MM_Komblit():
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        telebot.types.InlineKeyboardButton("⬅️", callback_data='prev'),
        telebot.types.InlineKeyboardButton("➡️", callback_data='next')
    )
    markup.add(
        telebot.types.InlineKeyboardButton("بحث من جديد", callback_data='search_again'),
        telebot.types.InlineKeyboardButton("مشاركة الصورة", callback_data='share_image')
    )
    return markup

@MM.callback_query_handler(func=lambda call: True)
def MM_Team(call):
    Dr = aslyou(call.from_user.id)
    if call.data == 'next':
        Dr['current_image_index'] += 1
        if Dr['current_image_index'] < len(Dr['images']):
            MM.edit_message_media(media=telebot.types.InputMediaPhoto(Dr['images'][Dr['current_image_index']]), chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=MM_Komblit())
        else:
            MM.answer_callback_query(call.id, "لقد وصلت إلى نهاية الصور. يمكنك البحث عن شيء جديد.")
            Dr['current_image_index'] -= 1
    elif call.data == 'prev':
        Dr['current_image_index'] -= 1
        if Dr['current_image_index'] >= 0:
            MM.edit_message_media(media=telebot.types.InputMediaPhoto(Dr['images'][Dr['current_image_index']]), chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=MM_Komblit())
        else:
            Dr['current_image_index'] = 0
            MM.answer_callback_query(call.id, "هذه هي الصورة الأولى في القائمة.")
    elif call.data == 'search_again':
        MM.delete_message(call.message.chat.id, call.message.message_id)
        MM.send_message(call.message.chat.id, "ما الموضوع الذي تريد البحث عنه؟ اكتب الكلمة المفتاحية وسأبحث لك عن الصور ذات الصلة.", reply_markup=F_MM(), parse_mode="Markdown")
    elif call.data == 'share_image':
        MM.answer_callback_query(call.id, "تم نسخ رابط الصورة بنجاح. يمكنك مشاركته مع الآخرين.")
        MM.send_message(call.message.chat.id, f"رابط الصورة: {Dr['images'][Dr['current_image_index']]}")
    elif call.data == 'users_count':
        if call.from_user.id == YOUR_ADMIN_ID:
            users = load_users()
            MM.answer_callback_query(call.id, f"إجمالي عدد المستخدمين المسجلين في البوت: {len(users)}")
        else:
            MM.answer_callback_query(call.id, "عذرًا، هذا الأمر متاح فقط لمدير البوت.")
    elif call.data == 'download_images':
        MM.send_message(call.message.chat.id, "من فضلك، أدخل الكلمة المفتاحية التي تريد البحث عنها لتنزيل الصور.")
        MM.register_next_step_handler(call.message, handle_download_images)
    elif call.data == 'download_videos':
        MM.send_message(call.message.chat.id, "من فضلك، قم بإدخال رابط Pinterest الخاص بالفيديو الذي تريد تحميله.")
        MM.register_next_step_handler(call.message, handle_download_videos)
    MM_fuck(call.from_user.id, Dr)

def download_and_send_pinterest_images(query, user_id, chat_id):
    try:
        r = requests.get(
            "https://www.pinterest.com/resource/BaseSearchResource/get/",
            headers={"User-Agent": "Mozilla/5.0"},
            params={
                "source_url": f"/search/pins/?q={query}&rs=typed",
                "data": json.dumps({"options": {"query": query, "scope": "pins"}})
            }
        )
        data = r.json()
        images = [item["images"]["orig"]["url"] for item in data["resource_response"]["data"]["results"] if "images" in item and "orig" in item["images"]]

        if not os.path.exists(f"downloads/{user_id}"):
            os.makedirs(f"downloads/{user_id}")
        for i, image_url in enumerate(images):
            response = requests.get(image_url)
            image_path = f"downloads/{user_id}/image_{i + 1}.jpg"
            with open(image_path, "wb") as f:
                f.write(response.content)
            with open(image_path, "rb") as photo:
                MM.send_photo(chat_id, photo)
            os.remove(image_path)
        return len(images)
    except Exception as e:
        print(f"حدث خطأ أثناء تنزيل الصور: {e}")
        return 0

def handle_download_images(mm):
    query = mm.text
    user_id = mm.from_user.id
    chat_id = mm.chat.id
    MM.send_message(chat_id, f"جاري تنزيل الصور للكلمة المفتاحية: `{query}`...", parse_mode="Markdown")
    num_images = download_and_send_pinterest_images(query, user_id, chat_id)
    if num_images > 0:
        MM.send_message(chat_id, f"تم تنزيل وإرسال {num_images} صورة بنجاح. استمتع بها!")
    else:
        MM.send_message(chat_id, "عذرًا، لم أتمكن من العثور على صور أو حدث خطأ أثناء عملية التنزيل.")

def handle_download_videos(mm):
    url = mm.text
    chat_id = mm.chat.id
    mg = MM.send_message(chat_id, 'جاري معالجة طلبك، يرجى الانتظار...', parse_mode='markdown')

    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    data = {
        'url': url,
    }
    response = requests.post('https://pinterestvideodownloader.com/download.php', headers=headers, data=data).text
    result = re.findall(r'<video src="(.*?)"', response)
    match = re.search(r"(.*?)pin(.*?)", url)

    if match and result:
        MM.delete_message(chat_id=chat_id, message_id=mg.message_id)
        MM.send_video(chat_id, result[0], caption='تم تحميل الفيديو بنجاح. \n بواسطة @FBI_MF')
    else:
        scrape_and_send_images(url, mm, mg.message_id)  # تم تغيير chat_id إلى mm

def scrape_and_send_images(url, message, message_id):
    try:
        encoded_url = quote(url, safe=':/?&=')
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
        }

        response = requests.get(encoded_url, headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')

        images = []
        for img in soup.find_all('img'):
            img_url = img.get('src')
            if img_url and img_url.startswith('http'):
                images.append(img_url)

        if images:
            MM.delete_message(chat_id=message.chat.id, message_id=message_id)
            for img_url in images[:5]:
                MM.send_photo(message.chat.id, img_url, caption='تم التحميل الصوره بنجاح')
        else:
            MM.reply_to(message, 'عذرًا، لم أتمكن من العثور على صور في الرابط الذي أدخلته.')
    except Exception as e:
        MM.reply_to(message, f"عذرًا، حدث خطأ أثناء معالجة الرابط: {e}")

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

MM.polling()
