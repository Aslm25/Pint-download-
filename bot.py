import os
import time
import sys
import telebot
import pyfiglet
import threading
from flask import Flask
from yt_dlp import YoutubeDL

# Telegram Bot Token
BOT_TOKEN = "6235763696:AAFsybffK2OrVqEWUeVIKrd2MKV54nFkN4Y"
bot = telebot.TeleBot(BOT_TOKEN)

# Flask app to keep the web service running
app = Flask(__name__)

# Output folder for downloads
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# ASCII Art for terminal display
ascii_art = pyfiglet.figlet_format("YT-Bot")
def animated_text(text):
    for line in text.splitlines():
        for char in line:
            sys.stdout.write("\033[32m" + char + "\033[0m")  # Green color
            sys.stdout.flush()
            time.sleep(0.01)
        sys.stdout.write('\n')
        time.sleep(0.1)
animated_text(ascii_art)

def get_video_info(url):
    """Extracts video details using yt-dlp."""
    try:
        options = {'quiet': True, 'skip_download': True}
        with YoutubeDL(options) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception:
        return None

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Welcome! Send a YouTube link to download video or audio.")

@bot.message_handler(func=lambda msg: msg.text and "youtube.com" in msg.text or "youtu.be" in msg.text)
def handle_youtube_link(message):
    url = message.text.strip()
    bot.reply_to(message, "Fetching video details...")

    info = get_video_info(url)
    if not info:
        bot.reply_to(message, "Failed to fetch video details. Try again.")
        return

    title = info.get("title", "Unknown Title")
    bot.send_message(message.chat.id, f"🎬 *{title}*\nChoose an option:", parse_mode="Markdown")

    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
    markup.add("🎵 Download Audio", "🎥 Download Video")
    bot.send_message(message.chat.id, "Select format:", reply_markup=markup)

    bot.register_next_step_handler(message, lambda msg: process_download(msg, url, info))

def process_download(message, url, info):
    if message.text == "🎵 Download Audio":
        format_id = get_best_audio(info)
        extension = "m4a"
    elif message.text == "🎥 Download Video":
        format_id = get_best_video(info)
        extension = "mp4"
    else:
        bot.send_message(message.chat.id, "Invalid choice.")
        return

    if not format_id:
        bot.send_message(message.chat.id, "No suitable format found.")
        return

    bot.send_message(message.chat.id, "Downloading... ⏳")
    file_path = download_file(url, format_id, info["title"], extension)

    if file_path:
        bot.send_message(message.chat.id, "Uploading file... ⬆️")
        with open(file_path, "rb") as f:
            if extension == "mp4":
                bot.send_video(message.chat.id, f)
            else:
                bot.send_audio(message.chat.id, f)
        os.remove(file_path)
        bot.send_message(message.chat.id, "Done! ✅")
    else:
        bot.send_message(message.chat.id, "Download failed.")

def get_best_audio(info):
    """Finds the best M4A audio format."""
    audio_formats = [f for f in info["formats"] if f.get("vcodec") == "none" and f["ext"] == "m4a"]
    return max(audio_formats, key=lambda f: f.get("abr", 0), default={}).get("format_id")

def get_best_video(info):
    """Finds the best MP4 video format."""
    video_formats = [f for f in info["formats"] if f["ext"] == "mp4" and f.get("height")]
    return max(video_formats, key=lambda f: f.get("height", 0), default={}).get("format_id")

def download_file(url, format_id, title, extension):
    """Downloads video or audio from YouTube."""
    file_path = os.path.join(DOWNLOAD_FOLDER, f"{title}.{extension}")
    options = {'format': format_id, 'outtmpl': file_path, 'quiet': True}
    
    try:
        with YoutubeDL(options) as ydl:
            ydl.download([url])
        return file_path
    except Exception:
        return None

# Flask route for Koyeb web service
@app.route("/")
def home():
    return "Telegram Bot is Running!"

# Start Telegram bot in a separate thread
def start_bot():
    bot.polling(none_stop=True)

threading.Thread(target=start_bot).start()

# Run Flask app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
