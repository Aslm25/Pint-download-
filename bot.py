# bot.py
from telegram import Update, Poll
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from flask import Flask
import asyncio
from threading import Thread
import os
import logging

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Initialize bot at module level
TOKEN = os.environ.get('TELEGRAM_TOKEN', '8078543359:AAHwbySKBQuXInox8-4viod9W-wdUZZQo-E')

# States for conversation
QUESTION, OPTIONS, CORRECT_ANSWER = range(3)
QUIZ_TYPE = "quiz"
POLL_TYPE = "poll"

class QuizPollBot:
    def __init__(self):
        self.application = Application.builder().token(TOKEN).build()
        self.user_data = {}

        # Define Conversation Handlers
        quiz_handler = ConversationHandler(
            entry_points=[CommandHandler('create_quiz', self.start_quiz)],
            states={
                QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_question)],
                OPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_options)],
                CORRECT_ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_correct_answer)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
        )
        
        poll_handler = ConversationHandler(
            entry_points=[CommandHandler('create_poll', self.start_poll)],
            states={
                QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_question)],
                OPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_options)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
        )
        
        self.application.add_handler(quiz_handler)
        self.application.add_handler(poll_handler)
        self.application.add_handler(CommandHandler('start', self.start))
        self.application.add_handler(CommandHandler('help', self.help))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        welcome_message = (
            "👋 Welcome to the Quiz & Poll Bot!\n\n"
            "Commands:\n"
            "/create_quiz - Create a quiz with correct answers\n"
            "/create_poll - Create a regular poll\n"
            "/cancel - Cancel creation process\n"
            "/help - Show this help message"
        )
        await update.message.reply_text(welcome_message)

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_message = (
            "How to create a quiz:\n"
            "1. Type /create_quiz\n"
            "2. Send your question\n"
            "3. Send options (one per line)\n"
            "4. Send the number of the correct answer (1, 2, 3, etc.)\n\n"
            "How to create a poll:\n"
            "1. Type /create_poll\n"
            "2. Send your question\n"
            "3. Send options (one per line)"
        )
        await update.message.reply_text(help_message)

    async def start_quiz(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        self.user_data[user_id] = {'type': QUIZ_TYPE}
        await update.message.reply_text("Please send me your quiz question.")
        return QUESTION

    async def start_poll(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        self.user_data[user_id] = {'type': POLL_TYPE}
        await update.message.reply_text("Please send me your poll question.")
        return QUESTION

    async def receive_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        self.user_data[user_id]['question'] = update.message.text
        
        await update.message.reply_text(
            "Great! Now send me the options, each on a new line.\n"
            "Example:\n"
            "Option 1\n"
            "Option 2\n"
            "Option 3"
        )
        return OPTIONS

    async def receive_options(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        options = [option.strip() for option in update.message.text.split('\n')]
        
        if len(options) < 2:
            await update.message.reply_text(
                "Please provide at least 2 options, each on a new line. Try again:"
            )
            return OPTIONS
        
        if len(options) > 10:
            await update.message.reply_text(
                "Maximum 10 options allowed. Please try again with fewer options:"
            )
            return OPTIONS

        self.user_data[user_id]['options'] = options
        
        if self.user_data[user_id]['type'] == QUIZ_TYPE:
            option_list = "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(options))
            await update.message.reply_text(
                f"Please send the number of the correct answer (1-{len(options)}):\n\n{option_list}"
            )
            return CORRECT_ANSWER
        else:
            await self.send_poll(update, context, user_id)
            return ConversationHandler.END

    async def receive_correct_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        try:
            correct_answer = int(update.message.text) - 1
            if 0 <= correct_answer < len(self.user_data[user_id]['options']):
                self.user_data[user_id]['correct_option_id'] = correct_answer
                await self.send_quiz(update, context, user_id)
                return ConversationHandler.END
            else:
                raise ValueError()
        except ValueError:
            await update.message.reply_text(
                f"Please send a valid number between 1 and {len(self.user_data[user_id]['options'])}:"
            )
            return CORRECT_ANSWER

    async def send_quiz(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        await context.bot.send_poll(
            chat_id=update.effective_chat.id,
            question=self.user_data[user_id]['question'],
            options=self.user_data[user_id]['options'],
            type=Poll.QUIZ,
            correct_option_id=self.user_data[user_id]['correct_option_id'],
            is_anonymous=True,
            explanation="Good luck!"
        )
        del self.user_data[user_id]
        await update.message.reply_text("Quiz created! You can create another with /create_quiz")

    async def send_poll(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        await context.bot.send_poll(
            chat_id=update.effective_chat.id,
            question=self.user_data[user_id]['question'],
            options=self.user_data[user_id]['options'],
            is_anonymous=True,
            allows_multiple_answers=False
        )
        del self.user_data[user_id]
        await update.message.reply_text("Poll created! You can create another with /create_poll")

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        if user_id in self.user_data:
            del self.user_data[user_id]
        await update.message.reply_text("Creation cancelled. You can start over with /create_quiz or /create_poll")
        return ConversationHandler.END

    def run_polling(self):
        """Run the bot polling in the current thread"""
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

# Initialize bot instance
bot = QuizPollBot()

# Flask routes
@app.route('/')
def home():
    return "Bot is running!"

def run_bot():
    """Run the bot polling in a separate thread"""
    asyncio.run(bot.application.run_polling(allowed_updates=Update.ALL_TYPES))

@app.before_first_request
def start_bot_polling():
    """Start the bot polling before the first request"""
    thread = Thread(target=run_bot)
    thread.daemon = True  # Thread will stop when main thread stops
    thread.start()

if __name__ == '__main__':
    # For local development
    port = int(os.environ.get("PORT", 5000))
    start_bot_polling()  # Start bot polling
    app.run(host='0.0.0.0', port=port)  # Start Flask app
