import os
import logging
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
from flask import Flask
import threading

# States for conversation
QUESTION, OPTIONS, CORRECT_ANSWER, EXPLANATION, MEDIA = range(5)
QUIZ_TYPE = "quiz"
POLL_TYPE = "poll"

# Set up logging for the bot
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

class QuizPollBot:
    def __init__(self, token: str):
        # Initialize the application with the token using Updater and Dispatcher
        self.updater = Updater(token, use_context=True)
        self.dispatcher = self.updater.dispatcher

        # Add conversation handlers
        quiz_handler = ConversationHandler(
            entry_points=[CommandHandler('create_quiz', self.start_quiz)],
            states={
                QUESTION: [MessageHandler(Filters.text & ~Filters.command, self.receive_question)],
                OPTIONS: [MessageHandler(Filters.text & ~Filters.command, self.receive_options)],
                CORRECT_ANSWER: [MessageHandler(Filters.text & ~Filters.command, self.receive_correct_answer)],
                EXPLANATION: [MessageHandler(Filters.text & ~Filters.command, self.receive_explanation)],
                MEDIA: [MessageHandler(Filters.photo, self.receive_media)]  # Media state
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )

        self.dispatcher.add_handler(quiz_handler)
        self.dispatcher.add_handler(CommandHandler('start', self.start))
        self.dispatcher.add_handler(CommandHandler('help', self.help))

        # Store temporary data
        self.user_data = {}

    def start(self, update: Update, context: CallbackContext):
        welcome_message = (
            "👋 Welcome to the Quiz & Poll Bot!\n\n"
            "Commands:\n"
            "/create_quiz - Create a quiz with correct answers\n"
            "/create_poll - Create a regular poll\n"
            "/cancel - Cancel creation process\n"
            "/help - Show this help message\n\n"
            "For contact @FBI_MF ⚡️"
        )
        update.message.reply_text(welcome_message)

    def help(self, update: Update, context: CallbackContext):
        help_message = (
            "How to create a quiz:\n"
            "1. Type /create_quiz\n"
            "2. Send your questions and options all at once in the following format:\n"
            "    Question 1\n"
            "    Option 1\n"
            "    Option 2\n"
            "    Correct Answer (1 or 2)\n"
            "    Explanation\n"
            "    ---\n"
            "    Question 2\n"
            "    Option 1\n"
            "    Option 2\n"
            "    Correct Answer (1 or 2)\n"
            "    Explanation\n"
            "    ---\n\n"
            "For each question, make sure to separate it with '---'.\n\n"
            "You can also send a picture for each question, by sending a photo after the question."
        )
        update.message.reply_text(help_message)

    def start_quiz(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        self.user_data[user_id] = {'type': QUIZ_TYPE, 'questions': []}
        update.message.reply_text("Please send me your quiz questions in the format mentioned in /help.")
        return QUESTION

    def receive_question(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        question = update.message.text.strip()
        self.user_data[user_id]['question'] = question
        update.message.reply_text("Got it! Now, please provide the options for this question.")
        return OPTIONS

    def receive_options(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        options = update.message.text.strip().split("\n")
        self.user_data[user_id]['options'] = options
        update.message.reply_text("Options saved! Now, please provide the correct answer (1 or 2).")
        return CORRECT_ANSWER

    def receive_correct_answer(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        correct_answer = update.message.text.strip()
        self.user_data[user_id]['correct_answer'] = correct_answer
        update.message.reply_text("Correct answer saved! Please provide an explanation.")
        return EXPLANATION

    def receive_explanation(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        explanation = update.message.text.strip()
        self.user_data[user_id]['explanation'] = explanation
        update.message.reply_text("Explanation saved! You can now send an image for this question if you'd like.")
        return MEDIA

    def receive_media(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        file = update.message.photo[-1].get_file()
        file.download(f"question_{user_id}.jpg")
        update.message.reply_text("Image saved! Your quiz question is now complete.")
        return ConversationHandler.END

    def cancel(self, update: Update, context: CallbackContext):
        update.message.reply_text("Quiz creation canceled.")
        return ConversationHandler.END

    def run(self):
        self.updater.start_polling()

# Initialize Flask
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running!"

# Run Flask and Telegram bot in separate threads
def run_flask():
    app.run(host='0.0.0.0', port=5000)

def run_telegram():
    bot.run()

if __name__ == "__main__":
    # Run Flask in a separate thread to handle the server
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    # Run Telegram bot
    bot = QuizPollBot("7824881467:AAGk0Bv8Ubos6RAy6tDM1jK8KfEkDFrFfLE")
    bot.run()
