import os
import logging
import time
import asyncio
import re
import json
from typing import List, Dict
import google.generativeai as genai
from telegram import Update, Poll, ParseMode, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler, CallbackQueryHandler
from telegram.error import TelegramError, RetryAfter
from flask import Flask
import threading
import PyPDF2
import io

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# States
SELECTING_MODE = 0
WAITING_FOR_INPUT = 1
QUESTION = 2
IMAGE_MENU = 3
WAITING_FOR_IMAGE = 4
CHANNEL_USERNAME = 5

# Constants
AUTHORIZED_USERS = [
    1145716840,
    5495732905,
    5969258058,
    5644736114,
    1428949114
]

class GeminiQuizGenerator:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')
    
    def extract_text_from_pdf(self, pdf_file) -> str:
        """Extract text from PDF file."""
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            raise

    def generate_quiz(self, text: str, num_questions: int = 25) -> List[Dict]:
        """Generate quiz questions using Gemini."""
        prompt = f"""
        Create {num_questions} multiple choice quiz questions from this text. Make questions creative, concise and engaging.
        
        Requirements:
        1. Questions should be clear and focused on key concepts
        2. Each question must be 2-3 lines maximum
        3. Include 4 options with only one correct answer
        4. Add a brief, one-line explanation for the correct answer
        5. Make questions interesting and thought-provoking
        6. Avoid obvious or trivial questions
        7. Focus on understanding rather than memorization, be creative like a lecturer
        8.You should know that is a medical content so it might contain sensitive content you could misunderstand as a sexual content.
        Format each question exactly as this JSON:
        {{
            "question": "Question text here?",
            "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
            "correct_answer": 0,
            "explanation": "Brief explanation here"
        }}
        
        Text to generate questions from:
        {text}
        """
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text
            
            # Extract JSON from response
            json_matches = re.findall(r'\{[^{}]*\}', response_text)
            questions = []
            
            for i, json_str in enumerate(json_matches[:num_questions], 1):
                try:
                    question_data = json.loads(json_str)
                    # Adjust correct_answer to be 0-based index
                    questions.append({
                        'id': i,
                        'question': question_data['question'],
                        'options': question_data['options'],
                        'correct_answer': question_data['correct_answer'],
                        'explanation': question_data['explanation'],
                        'image_id': None
                    })
                except json.JSONDecodeError:
                    continue
                    
            return questions
            
        except Exception as e:
            logger.error(f"Error generating questions with Gemini: {str(e)}")
            return []

class QuizPollBot:
    def __init__(self, token: str, gemini_api_key: str):
        self.updater = Updater(token, use_context=True)
        self.dispatcher = self.updater.dispatcher
        self.user_data = {}
        self.quiz_generator = GeminiQuizGenerator(gemini_api_key)
        
        self.message_interval = 2  # Increased interval
        self.chunk_size = 3  # Reduced chunk size
        self.chunk_interval = 7  # Increased chunk interval
        
        self.setup_handlers()

    def setup_handlers(self):
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('create_quiz', self.select_mode)],
            states={
                SELECTING_MODE: [
                    MessageHandler(Filters.regex('^(Manual|AI Generated)$'), self.handle_mode_selection)
                ],
                WAITING_FOR_INPUT: [
                    MessageHandler(Filters.text | Filters.document, self.handle_input)
                ],
                QUESTION: [
                    MessageHandler(Filters.text & ~Filters.command, self.receive_quiz_data)
                ],
                IMAGE_MENU: [
                    MessageHandler(Filters.regex('^(Add Images|Skip Images)$'), self.handle_image_menu)
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

        self.dispatcher.add_handler(conv_handler)
        self.dispatcher.add_handler(CommandHandler('start', self.start))
        self.dispatcher.add_handler(CommandHandler('help', self.help))

    def start(self, update: Update, context: CallbackContext):
        welcome_message = (
            "👋 Welcome to the Quiz Bot!\n\n"
            "Commands:\n"
            "/create_quiz - Create a quiz (manual or AI-generated)\n"
            "/cancel - Cancel creation process\n"
            "/help - Show the Help message\n\n"
            "For contact, @FBI_MF ⚡️"
        )
        update.message.reply_text(welcome_message)

    def help(self, update: Update, context: CallbackContext):
        help_message = (
            "How to create a quiz:\n\n"
            "1. Type /create_quiz\n"
            "2. Choose mode:\n"
            "   - Manual: Enter questions yourself\n"
            "   - AI Generated: Bot creates questions from your text or PDF\n\n"
            "For Manual mode:\n"
            "Send questions in this format:\n"
            "Question\n"
            "Option 1\n"
            "Option 2\n"
            "Option 3\n"
            "Option 4\n"
            "Correct Answer (1-4)\n"
            "Explanation (or 'n')\n"
            "---\n\n"
            "For AI Generated mode:\n"
            "Simply paste your lecture text or upload a PDF file\n\n"
            "For help, contact @FBI_MF"
        )
        update.message.reply_text(help_message)

    def select_mode(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        if not self.is_user_authorized(user_id):
            update.message.reply_text("Sorry, you are not authorized to use this bot.")
            return ConversationHandler.END
        
        keyboard = ReplyKeyboardMarkup([['Manual', 'AI Generated']], 
                                     one_time_keyboard=True,
                                     resize_keyboard=True)
        update.message.reply_text(
            "Please select quiz creation mode:",
            reply_markup=keyboard
        )
        return SELECTING_MODE

    def handle_mode_selection(self, update: Update, context: CallbackContext):
        mode = update.message.text
        user_id = update.message.from_user.id
        self.user_data[user_id] = {'mode': mode}
        
        update.message.reply_text(
            "Manual" if mode == "Manual" else "AI Generated" + " mode selected.",
            reply_markup=ReplyKeyboardRemove()
        )
        
        if mode == 'Manual':
            update.message.reply_text(
                "Please send me your quiz questions in the format:\n\n"
                "Question\n"
                "Option 1\n"
                "Option 2\n"
                "Option 3\n"
                "Option 4\n"
                "Correct Answer (1-4)\n"
                "Explanation (or 'n')\n"
                "---"
            )
            return QUESTION
        else:
            update.message.reply_text(
                "Please send me either:\n"
                "1. A PDF file containing the lecture material, or\n"
                "2. Paste the lecture text directly\n\n"
                "I'll generate quiz questions from it."
            )
            return WAITING_FOR_INPUT

    def handle_input(self, update: Update, context: CallbackContext):
        try:
            user_id = update.message.from_user.id
            
            if update.message.document:
                file = context.bot.get_file(update.message.document.file_id)
                pdf_bytes = io.BytesIO()
                file.download(out=pdf_bytes)
                pdf_bytes.seek(0)
                text = self.quiz_generator.extract_text_from_pdf(pdf_bytes)
            else:
                text = update.message.text.strip()

            if len(text) < 100:
                update.message.reply_text(
                    "Please provide more text for generating meaningful questions "
                    "(at least 100 characters).",
                    reply_markup=ReplyKeyboardRemove()
                )
                return WAITING_FOR_INPUT

            update.message.reply_text("Generating questions... Please wait.")
            questions = self.quiz_generator.generate_quiz(text)
            
            if not questions:
                update.message.reply_text(
                    "Unable to generate questions from the provided content. "
                    "Please try with different content."
                )
                return WAITING_FOR_INPUT

            self.user_data[user_id]['questions'] = questions
            
            questions_list = "\n".join([
                f"{q['id']}. {q['question']}" for q in questions
            ])
            
            keyboard = ReplyKeyboardMarkup(
                [['Add Images', 'Skip Images']], 
                one_time_keyboard=True,
                resize_keyboard=True
            )
            
            update.message.reply_text(
                f"✅ Successfully generated {len(questions)} questions!\n\n"
                f"Questions:\n\n{questions_list}\n\n"
                "Would you like to add images to any questions?",
                reply_markup=keyboard
            )
            return IMAGE_MENU

        except Exception as e:
            logger.error(f"Error handling input: {str(e)}")
            update.message.reply_text(
                "Sorry, there was an error processing your input. "
                "Please try again with different content."
            )
            return WAITING_FOR_INPUT

    def receive_quiz_data(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        message = update.message.text.strip()
        questions_data = message.split('---')
        
        questions_data = [q.strip() for q in questions_data if q.strip()]
        
        if not questions_data:
            update.message.reply_text(
                "❌ Invalid format! Please send your questions in this format:\n\n"
                "Question\n"
                "Option 1\n"
                "Option 2\n"
                "Option 3\n"
                "Option 4\n"
                "Correct Answer (1-4)\n"
                "Explanation (or 'n')\n"
                "---"
            )
            return QUESTION

        valid_questions = []
        has_errors = False

        for idx, question_set in enumerate(questions_data, 1):
            lines = [line.strip() for line in question_set.split('\n') if line.strip()]
            
            if len(lines) < 6:
                update.message.reply_text(
                    f"❌ Question {idx} is incomplete. Each question needs:\n"
                    "- Question text\n"
                    "- 4 options\n"
                    "- Correct answer number\n"
                    "- Optional explanation"
                )
                return QUESTION

            try:
                correct_answer = int(lines[5])
                if not 1 <= correct_answer <= 4:
                    raise ValueError
            except ValueError:
                update.message.reply_text(
                    f"❌ Question {idx}: Correct answer must be a number between 1 and 4"
                )
                return QUESTION

            question = lines[0]
            options = lines[1:5]
            explanation = lines[6] if len(lines) > 6 and lines[6].lower() != 'n' else None

            valid_questions.append({
                'id': idx,
                'question': question,
                'options': options,
                'correct_answer': correct_answer,
                'explanation': explanation,
                'image_id': None
            })

        if has_errors:
            return QUESTION

        self.user_data[user_id] = {'questions': valid_questions}
        
        questions_list = "\n".join([f"{q['id']}. {q['question']}" for q in valid_questions])
        keyboard = ReplyKeyboardMarkup(
            [['Add Images', 'Skip Images']], 
            one_time_keyboard=True,
            resize_keyboard=True
        )
        
        update.message.reply_text(
            f"✅ Successfully parsed {len(valid_questions)} questions!\n\n"
            f"Your questions:\n\n{questions_list}\n\n"
            "Would you like to add images to any questions?",
            reply_markup=keyboard
        )
        return IMAGE_MENU

    def handle_image_menu(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        choice = update.message.text.strip()

        if choice not in ['Add Images', 'Skip Images']:
            keyboard = ReplyKeyboardMarkup(
                [['Add Images', 'Skip Images']], 
                one_time_keyboard=True,
                resize_keyboard=True
            )
            update.message.reply_text(
                "Please use the provided buttons to choose an option.",
                reply_markup=keyboard
            )
            return IMAGE_MENU

        update.message.reply_text(
            "Processing...",
            reply_markup=ReplyKeyboardRemove()
        )

        if choice == 'Skip Images':
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
        else:
            questions_list = "\n".join([
                f"{q['id']}. {q['question']}" 
                for q in self.user_data[user_id]['questions']
            ])
            update.message.reply_text(
                f"Here are your questions:\n\n{questions_list}\n\n"
                "To add images:\n"
                "1. Send an image with the question number as the caption\n"
                "For example: Send image with caption '1' for Question 1\n\n"
                "Type /done when finished adding images."
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
        questions = self.user_data[user_id]['questions']
        
        if question_num < 1 or question_num > len(questions):
            update.message.reply_text(
                f"Invalid question number. Please use a number between 1 and {len(questions)}"
            )
            return WAITING_FOR_IMAGE

        photo = update.message.photo[-1]
        self.user_data[user_id]['questions'][question_num - 1]['image_id'] = photo.file_id
        
        update.message.reply_text(
            f"✅ Image added to Question {question_num}!\n\n"
            "Send another image with a question number as caption, or type /done to finish.",
            reply_markup=ReplyKeyboardRemove()
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
                "Please enter the channel username (including @) where you want to send the quizzes:",
                reply_markup=ReplyKeyboardRemove()
            )
        return CHANNEL_USERNAME

    def get_admin_channels(self, user_id: int):
        try:
            channels = []
            if self.is_user_authorized(user_id):
                channels.append({"username": "@BASMGA", "title": "BASMGA Channel"})
            return channels
        except Exception as e:
            logger.error(f"Error getting admin channels: {e}")
            return []

    def create_channel_keyboard(self, user_id: int):
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

    def safe_send_message(self, update, text):
        try:
            if update.callback_query:
                update.callback_query.edit_message_text(text)
            else:
                update.message.reply_text(text, reply_markup=ReplyKeyboardRemove())
        except Exception as e:
            logger.error(f"Error sending message: {e}")

    def send_with_retry(self, bot, method, max_retries=5, **kwargs):
        for attempt in range(max_retries):
            try:
                result = method(**kwargs)
                time.sleep(self.message_interval)
                return result
            except RetryAfter as e:
                logger.warning(f"Rate limit hit, waiting {e.retry_after} seconds")
                time.sleep(e.retry_after)
            except TelegramError as e:
                logger.error(f"Telegram error on attempt {attempt + 1}: {str(e)}")
                if "too many requests" in str(e).lower():
                    wait_time = (attempt + 1) * 3
                    time.sleep(wait_time)
                else:
                    raise
        raise Exception(f"Failed to send after {max_retries} attempts")

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
            return self.send_to_channel_internal(update, context, channel_username)

    def send_to_channel_internal(self, update, context, channel_username):
        user_id = update.callback_query.from_user.id if update.callback_query else update.message.from_user.id
        
        try:
            # Clear any existing keyboards
            if update.callback_query:
                update.callback_query.edit_message_reply_markup(reply_markup=None)
            else:
                update.message.reply_text("Processing...", reply_markup=ReplyKeyboardRemove())

            questions = self.user_data[user_id]['questions']
            total_questions = len(questions)
            questions_sent = 0
            
            for chunk_start in range(0, total_questions, self.chunk_size):
                chunk_end = min(chunk_start + self.chunk_size, total_questions)
                chunk = questions[chunk_start:chunk_end]
                
                progress_message = f"Processing questions {chunk_start + 1}-{chunk_end} of {total_questions}..."
                self.safe_send_message(update, progress_message)
                
                for question_data in chunk:
                    try:
                        if question_data['image_id']:
                            self.send_with_retry(
                                context.bot,
                                context.bot.send_photo,
                                chat_id=channel_username,
                                photo=question_data['image_id'],
                                caption=question_data['question']
                            )
                        
                        # Ensure correct_answer is 0-based for Telegram API
                        correct_option_id = (question_data['correct_answer'] - 1) if question_data['correct_answer'] >= 1 else 0
                        
                        self.send_with_retry(
                            context.bot,
                            context.bot.send_poll,
                            chat_id=channel_username,
                            question=question_data['question'],
                            options=question_data['options'],
                            type="quiz",
                            correct_option_id=correct_option_id,
                            is_anonymous=True,
                            explanation=question_data['explanation'] if question_data['explanation'] else None
                        )
                        
                        questions_sent += 1
                        
                    except Exception as e:
                        logger.error(f"Error sending question {questions_sent + 1}: {str(e)}")
                        raise
                
                if chunk_end < total_questions:
                    progress_message = f"✅ Sent {questions_sent}/{total_questions} questions. Short pause before next batch..."
                    self.safe_send_message(update, progress_message)
                    time.sleep(self.chunk_interval)
            
            # Clear user data after successful sending
            if user_id in self.user_data:
                del self.user_data[user_id]
            
            success_message = f"✅ Successfully sent all {questions_sent} quizzes to the channel! Press /create_quiz to create more quizzes."
            self.safe_send_message(update, success_message)
            
            return ConversationHandler.END

        except Exception as e:
            logger.error(f"Error in send_to_channel_internal: {str(e)}")
            error_message = (
                f"Failed to send quizzes (sent {questions_sent}/{total_questions}). Please check:\n"
                "1. Channel username is correct\n"
                "2. Bot is an admin in the channel\n"
                "3. Bot has permission to post\n"
                f"4. Error details: {str(e)}\n\n"
                "Please try again with the correct channel username:"
            )
            self.safe_send_message(update, error_message)
            return CHANNEL_USERNAME

    def send_to_channel(self, update: Update, context: CallbackContext):
        channel_username = update.message.text.strip()
        
        if not channel_username.startswith('@'):
            update.message.reply_text(
                "Channel username must start with @. Please try again:",
                reply_markup=ReplyKeyboardRemove()
            )
            return CHANNEL_USERNAME

        return self.send_to_channel_internal(update, context, channel_username)

    def cancel(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        if user_id in self.user_data:
            del self.user_data[user_id]
        update.message.reply_text(
            "Quiz creation canceled. Use /create_quiz to start again.", 
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    def is_user_authorized(self, user_id: int) -> bool:
        return user_id in AUTHORIZED_USERS

    def run(self):
        self.updater.start_polling()
        self.updater.idle()

# Initialize Flask
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=8000)

if __name__ == "__main__":
    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Set your bot token and Gemini API key here
    TOKEN = "7824881467:AAHx59QgJ9OWiAyjd9Vy4up220-kFvQUFDA"
    GEMINI_API_KEY = "AIzaSyAro3Ksun3RQKXg5q-DvUauXUT60e-2xIw"
    bot = QuizPollBot(TOKEN, GEMINI_API_KEY)
    bot.run()
