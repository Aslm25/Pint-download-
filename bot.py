import os
import logging
from telegram import Update, Poll, ParseMode, InputMediaPhoto, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler, CallbackQueryHandler
from flask import Flask
import threading

# States
QUESTION = 0
IMAGE_MENU = 1
WAITING_FOR_IMAGE = 2
CHANNEL_USERNAME = 3

QUIZ_TYPE = "quiz"

# Specific authorized users list
AUTHORIZED_USERS = [
    1145716840,
    5495732905,
    5969258058,
    5644736114,
    1428949114
]

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

class QuizPollBot:
    def __init__(self, token: str):
        self.updater = Updater(token, use_context=True)
        self.dispatcher = self.updater.dispatcher
        self.user_data = {}

        quiz_handler = ConversationHandler(
            entry_points=[CommandHandler('create_quiz', self.start_quiz)],
            states={
                QUESTION: [
                    MessageHandler(Filters.text & ~Filters.command, self.receive_quiz_data)
                ],
                IMAGE_MENU: [
                    MessageHandler(Filters.text & ~Filters.command, self.handle_image_menu)
                ],
                WAITING_FOR_IMAGE: [
                    MessageHandler(Filters.photo, self.add_image_to_question),
                    CommandHandler('done', self.finish_images)
                ],
                CHANNEL_USERNAME: [
                    MessageHandler(Filters.text & ~Filters.command, self.send_to_channel),
                    CallbackQueryHandler(self.button_channel_select)
                ]
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )

        self.dispatcher.add_handler(quiz_handler)
        self.dispatcher.add_handler(CommandHandler('start', self.start))
        self.dispatcher.add_handler(CommandHandler('help', self.help))

    def start(self, update: Update, context: CallbackContext):
        welcome_message = (
            "👋 Welcome to the Quiz Bot!\n\n"
            "Commands:\n"
            "/create_quiz - Create a quiz with images\n"
            "/cancel - Cancel creation process\n"
            "/help - Show the Help message\n\n"
            "For contact, @FBI_MF ⚡️"
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
            "    Option 4\n"
            "    Correct Answer (1, 2, 3, etc.)\n"
            "    Explanation (or type 'n' for no explanation)\n"
            "    ---\n"
            "3. You can then add images to any question\n"
            "4. Select or enter the channel to send quizzes\n\n"
            "For each question, separate with '---'\n\n"
            "For help, contact @FBI_MF"
        )
        update.message.reply_text(help_message)

    def is_user_authorized(self, user_id: int) -> bool:
        """Check if user is authorized to see BASMGA channel"""
        return user_id in AUTHORIZED_USERS

    def get_admin_channels(self, user_id: int):
        """Get list of channels based on user authorization"""
        try:
            channels = []
            if self.is_user_authorized(user_id):
                channels.append({"username": "@BASMGA", "title": "BASMGA Channel"})
            return channels
        except Exception as e:
            logger.error(f"Error getting admin channels: {e}")
            return []

    def create_channel_keyboard(self, user_id: int):
        """Create inline keyboard with channel buttons based on user authorization"""
        channels = self.get_admin_channels(user_id)
        keyboard = []
        
        for channel in channels:
            keyboard.append([InlineKeyboardButton(
                channel['title'], 
                callback_data=f"channel:{channel['username']}"
            )])
            
        keyboard.append([InlineKeyboardButton(
            "Enter Channel Username", 
            callback_data="channel:manual"
        )])
        return InlineKeyboardMarkup(keyboard)

    def start_quiz(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        self.user_data[user_id] = {'questions': []}
        update.message.reply_text("Please send me your quiz questions in the format mentioned in /help.")
        return QUESTION

    def receive_quiz_data(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        message = update.message.text.strip()
        questions_data = message.split('---')
        
        for idx, question_set in enumerate(questions_data, 1):
            if not question_set.strip():
                continue

            lines = [line.strip() for line in question_set.strip().split('\n')]
            
            if len(lines) < 6:
                update.message.reply_text("Each question must have at least a question, 4 options, and a correct answer.")
                return QUESTION

            question = lines[0]
            options = lines[1:5]
            correct_answer = int(lines[5])
            explanation = lines[6] if len(lines) > 6 and lines[6].lower() != 'n' else None

            self.user_data[user_id]['questions'].append({
                'id': idx,
                'question': question,
                'options': options,
                'correct_answer': correct_answer,
                'explanation': explanation,
                'image_id': None
            })

        questions_list = "\n".join([f"{q['id']}. {q['question']}" for q in self.user_data[user_id]['questions']])
        reply_markup = ReplyKeyboardMarkup([['Add Images', 'Skip Images']], one_time_keyboard=True)
        
        update.message.reply_text(
            f"Your questions:\n\n{questions_list}\n\n"
            "Would you like to add images to any questions?",
            reply_markup=reply_markup
        )
        return IMAGE_MENU

    def handle_image_menu(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        choice = update.message.text

        if choice == 'Skip Images':
            reply_markup = self.create_channel_keyboard(user_id)
            if self.get_admin_channels(user_id):
                update.message.reply_text(
                    "Please select a channel to send the quizzes:",
                    reply_markup=reply_markup
                )
            else:
                update.message.reply_text(
                    "Please enter the channel username (including @) where you want to send the quizzes:",
                    reply_markup=ReplyKeyboardRemove()
                )
            return CHANNEL_USERNAME
        elif choice == 'Add Images':
            questions_list = "\n".join([
                f"{q['id']}. {q['question']}" for q in self.user_data[user_id]['questions']
            ])
            update.message.reply_text(
                f"Here are your questions:\n\n{questions_list}\n\n"
                "To add images:\n"
                "1. Send an image with the question number as the caption\n"
                "For example: Send image with caption '1' for Question 1\n\n"
                "Type /done when finished adding images.",
                reply_markup=ReplyKeyboardRemove()
            )
            return WAITING_FOR_IMAGE

    def add_image_to_question(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        caption = update.message.caption
        
        if not caption or not caption.isdigit():
            update.message.reply_text(
                "Please add a question number as the caption when sending the image.\n"
                "For example: Send image with caption '1' for Question 1"
            )
            return WAITING_FOR_IMAGE

        question_num = int(caption)
        
        if question_num < 1 or question_num > len(self.user_data[user_id]['questions']):
            update.message.reply_text(
                f"Invalid question number. Please use a number between 1 and {len(self.user_data[user_id]['questions'])}"
            )
            return WAITING_FOR_IMAGE

        photo = update.message.photo[-1]
        self.user_data[user_id]['questions'][question_num - 1]['image_id'] = photo.file_id
        
        update.message.reply_text(
            f"✅ Image added to Question {question_num}!\n\n"
            "Send another image with a question number as caption, or type /done to finish."
        )
        return WAITING_FOR_IMAGE

    def finish_images(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        reply_markup = self.create_channel_keyboard(user_id)
        
        if self.get_admin_channels(user_id):
            update.message.reply_text(
                "Please select a channel to send the quizzes:",
                reply_markup=reply_markup
            )
        else:
            update.message.reply_text(
                "Please enter the channel username (including @) where you want to send the quizzes:"
            )
        return CHANNEL_USERNAME

    def button_channel_select(self, update: Update, context: CallbackContext):
        query = update.callback_query
        query.answer()

        if query.data == "channel:manual":
            query.edit_message_text(
                "Please enter the channel username (including @) where you want to send the quizzes:"
            )
            return CHANNEL_USERNAME

        if query.data.startswith("channel:"):
            channel_username = query.data.split(":")[1]
            user_id = query.from_user.id
            self.user_data[user_id]['selected_channel'] = channel_username
            return self.send_to_channel_internal(update, context, channel_username)

    def send_to_channel_internal(self, update, context, channel_username):
        user_id = update.callback_query.from_user.id if update.callback_query else update.message.from_user.id

        try:
            for question_data in self.user_data[user_id]['questions']:
                if question_data['image_id']:
                    context.bot.send_photo(
                        chat_id=channel_username,
                        photo=question_data['image_id'],
                        caption=question_data['question']
                    )

                context.bot.send_poll(
                    chat_id=channel_username,
                    question=question_data['question'],
                    options=question_data['options'],
                    type="quiz",
                    correct_option_id=question_data['correct_answer'] - 1,
                    is_anonymous=True,
                    explanation=question_data['explanation'] if question_data['explanation'] else None
                )

            success_message = "All quizzes have been sent to the channel! Press /create_quiz to create more quizzes."
            if update.callback_query:
                update.callback_query.edit_message_text(success_message)
            else:
                update.message.reply_text(success_message)
            return ConversationHandler.END

        except Exception as e:
            error_message = (
                "Failed to send quizzes. Please check:\n"
                "1. Channel username is correct\n"
                "2. Bot is an admin in the channel\n"
                "3. Bot has permission to post\n\n"
                "Please try again with the correct channel username:"
            )
            if update.callback_query:
                update.callback_query.edit_message_text(error_message)
            else:
                update.message.reply_text(error_message)
            return CHANNEL_USERNAME

    def send_to_channel(self, update: Update, context: CallbackContext):
        channel_username = update.message.text.strip()
        
        if not channel_username.startswith('@'):
            update.message.reply_text("Channel username must start with @. Please try again:")
            return CHANNEL_USERNAME

        return self.send_to_channel_internal(update, context, channel_username)

    def cancel(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        if user_id in self.user_data:
            del self.user_data[user_id]
        update.message.reply_text("Quiz creation canceled.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    def run(self):
        self.updater.start_polling()

# Initialize Flask
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=8000)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    bot = QuizPollBot("7824881467:AAGk0Bv8Ubos6RAy6tDM1jK8KfEkDFrFfLE")
    bot.run()
