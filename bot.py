import os
import logging
from telegram import Update, Poll, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
from flask import Flask
import threading

# States for conversation
QUESTION = 0
QUIZ_TYPE = "quiz"
POLL_TYPE = "poll"

# Set up logging for the bot
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

class QuizPollBot:
    def __init__(self, token: str):
        self.updater = Updater(token, use_context=True)
        self.dispatcher = self.updater.dispatcher

        # Add conversation handlers
        quiz_handler = ConversationHandler(
            entry_points=[CommandHandler('create_quiz', self.start_quiz)],
            states={
                QUESTION: [MessageHandler(Filters.text & ~Filters.command, self.receive_quiz_data)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )

        self.dispatcher.add_handler(quiz_handler)
        self.dispatcher.add_handler(CommandHandler('start', self.start))
        self.dispatcher.add_handler(CommandHandler('help', self.help))

        self.user_data = {}

    def start(self, update: Update, context: CallbackContext):
        welcome_message = (
            "👋 Welcome to the Quiz Bot!\n\n"
            "Commands:\n"
            "/create_quiz - Create a quiz with correct answers\n"
            "/cancel - Cancel creation process\n"
            "/help - Show this help message\n\n"
            "For contact , @FBI_MF ⚡️"
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
            "    Option 3\n"
            "    Correct Answer (1, 2, 3, etc.)\n"
            "    Explanation (Optional)\n"
            "    ---\n"
            "    Question 2\n"
            "    Option 1\n"
            "    Option 2\n"
            "    Option 3\n"
            "    Option 4\n"
            "    Correct Answer (1, 2, 3, etc.)\n"
            "    Explanation (Optional)\n"
            "    ---\n\n"
            "For each question, make sure to separate it with '---'.\n\n"
            "For any further Help Contact me @FBI_MF"
        )
        update.message.reply_text(help_message)

    def start_quiz(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        self.user_data[user_id] = {'type': QUIZ_TYPE, 'questions': []}
        update.message.reply_text("Please send me your quiz questions in the format mentioned in /help.")
        return QUESTION

    def receive_quiz_data(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        message = update.message.text.strip()

        # Split the message into different questions based on '---' separator
        questions_data = message.split('---')

        # Iterate through each question set
        for question_set in questions_data:
            lines = question_set.strip().split('\n')

            if len(lines) < 5:
                update.message.reply_text("Each question must have at least 4 options and a correct answer.")
                return QUESTION

            question = lines[0].strip()
            options = [line.strip() for line in lines[1:-2]]
            correct_answer = int(lines[-2].strip())
            explanation = lines[-1].strip() if len(lines) > 5 else None  # Optional explanation

            if user_id not in self.user_data:
                self.user_data[user_id] = {'questions': []}

            self.user_data[user_id]['questions'].append({
                'question': question,
                'options': options,
                'correct_answer': correct_answer,
                'explanation': explanation
            })

        update.message.reply_text("Got it! Your quiz is ready. Sending questions now. Press /create_quiz to create again 👋 ")
        self.send_quiz(update, user_id)
        return ConversationHandler.END

    def send_quiz(self, update: Update, user_id: int):
        """Send each question with options to the user as a quiz poll."""
        if user_id not in self.user_data or "questions" not in self.user_data[user_id]:
            update.message.reply_text("No questions found. Please create a quiz first.")
            return

        for question_data in self.user_data[user_id]['questions']:
            question_text = question_data['question']
            options = question_data['options']
            correct_answer = question_data['correct_answer'] - 1  # Adjust index to 0-based
            explanation = question_data.get('explanation', '')  # Get explanation, default to empty string

            # Send the quiz poll with or without explanation
            update.message.reply_poll(
                question=question_text,
                options=options,
                type="quiz",
                correct_option_id=correct_answer,
                is_anonymous=True,  # Quiz remains anonymous
                explanation=explanation if explanation else None  # Only include explanation if provided
            )

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
    app.run(host='0.0.0.0', port=8000)

if __name__ == "__main__":
    # Run Flask in a separate thread to handle the server
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Run Telegram bot
    bot = QuizPollBot("7824881467:AAGk0Bv8Ubos6RAy6tDM1jK8KfEkDFrFfLE")
    bot.run()
