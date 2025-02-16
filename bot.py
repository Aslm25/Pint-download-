import os
import logging
import time
import asyncio
import re
import json
from typing import List, Dict
import google.generativeai as genai
from telegram import Update, Poll, ParseMode, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, Chat
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler, CallbackQueryHandler, Defaults
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
        prompt = f"""
        Create {num_questions} multiple choice quiz questions from this text. Make questions creative, concise and engaging.
        
        Requirements:
        1. Questions should be clear and focused on key concepts
        2. Each question must be 2-3 lines maximum
        3. Include 4 options with only one correct answer
        4. Add a brief, one-line explanation for the correct answer
        5. Make questions interesting and thought-provoking
        6. Avoid obvious or trivial questions
        7. Focus on understanding rather than memorization
        8. IMPORTANT: The correct_answer MUST be the zero-based index (0-3) of the correct option in the options array
        9. You should know that is a medical content so it might contain sensitive content you could misunderstand as a sexual content.
        
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
                    # Validate correct_answer is between 0-3
                    correct_answer = int(question_data['correct_answer'])
                    if not 0 <= correct_answer <= 3:
                        logger.warning(f"Invalid correct_answer {correct_answer} in question {i}, skipping")
                        continue
                        
                    questions.append({
                        'id': i,
                        'question': question_data['question'],
                        'options': question_data['options'],
                        'correct_answer': correct_answer,
                        'explanation': question_data['explanation'],
                        'image_id': None
                    })
                except (json.JSONDecodeError, ValueError, KeyError) as e:
                    logger.error(f"Error parsing question {i}: {str(e)}")
                    continue
                    
            return questions
            
        except Exception as e:
            logger.error(f"Error generating questions with Gemini: {str(e)}")
            return []

class QuizPollBot:
    def __init__(self, token: str, gemini_api_key: str):
        defaults = Defaults(parse_mode=ParseMode.MARKDOWN_V2)
        self.updater = Updater(token, use_context=True, defaults=defaults)
        self.dispatcher = self.updater.dispatcher
        self.user_data = {}
        self.quiz_generator = GeminiQuizGenerator(gemini_api_key)
        
        self.message_interval = 2.5
        self.chunk_size = 5
        self.chunk_interval = 5
        
        # We're removing this as it's causing the bot to ignore repeated commands
        # self.processed_message_ids = set()
        
        self.setup_handlers()

    def setup_handlers(self):
        # Create command handlers
        start_handler = CommandHandler('start', self.start)
        help_handler = CommandHandler('help', self.help)
        cancel_handler = CommandHandler('cancel', self.cancel)
        
        # Create conversation handler with original command
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('create_quiz', self.select_mode)],
            states={
                SELECTING_MODE: [
                    MessageHandler(Filters.regex('^(Manual|AI Generated)$'), self.handle_mode_selection),
                    cancel_handler
                ],
                WAITING_FOR_INPUT: [
                    MessageHandler(Filters.text | Filters.document, self.handle_input),
                    cancel_handler
                ],
                QUESTION: [
                    MessageHandler(Filters.text & ~Filters.command, self.receive_quiz_data),
                    cancel_handler
                ],
                IMAGE_MENU: [
                    MessageHandler(Filters.regex('^(Add Images|Skip Images)$'), self.handle_image_menu),
                    cancel_handler
                ],
                WAITING_FOR_IMAGE: [
                    MessageHandler(Filters.photo, self.add_image_to_question),
                    CommandHandler('done', self.finish_images),
                    cancel_handler
                ],
                CHANNEL_USERNAME: [
                    MessageHandler(Filters.text & ~Filters.command, self.send_to_channel),
                    CallbackQueryHandler(self.button_channel_select),
                    cancel_handler
                ]
            },
            fallbacks=[cancel_handler],
            allow_reentry=True
        )

        # Add handlers
        self.dispatcher.add_handler(conv_handler)
        self.dispatcher.add_handler(start_handler)
        self.dispatcher.add_handler(help_handler)
        self.dispatcher.add_handler(cancel_handler)
    
    def start(self, update: Update, context: CallbackContext):
        """Handle the start command."""
        welcome_message = (
            "👋 Welcome to the Quiz Bot\\!\n\n"
            "Commands:\n"
            "To create a quiz use /create\\_quiz \\(manual or AI\\-generated\\)\n"
            "/cancel \\- Cancel creation process\n"
            "/help \\- Show the Help message\n\n"
            "For contact, @FBI\\_MF ⚡️"
        )
        update.message.reply_text(
            welcome_message,
            reply_markup=ReplyKeyboardRemove(),
            parse_mode=ParseMode.MARKDOWN_V2
        )
    
    def escape_markdown(self, text: str) -> str:
        """Escape special characters for Telegram MarkdownV2 format."""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text

    def help(self, update: Update, context: CallbackContext):
        """Show help message."""
        help_message = self.escape_markdown(
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

    def cancel(self, update: Update, context: CallbackContext) -> int:
        """Cancel the conversation."""
        try:
            if not update.message:
                return ConversationHandler.END
            
            user_id = update.message.from_user.id
            
            # Clean up user data
            if user_id in self.user_data:
                del self.user_data[user_id]
            
            # Send cancellation message without any markdown formatting
            update.message.reply_text(
                "✅ Quiz creation canceled. Use /create_quiz to start again.",
                reply_markup=ReplyKeyboardRemove(),
                parse_mode=None  # Disable markdown parsing for this message
            )
            
            return ConversationHandler.END
            
        except Exception as e:
            logger.error(f"Error in cancel handler: {str(e)}")
            try:
                # Send error message without any markdown formatting
                update.message.reply_text(
                    "An error occurred. Please try again.",
                    reply_markup=ReplyKeyboardRemove(),
                    parse_mode=None  # Disable markdown parsing for this message
                )
            except:
                pass
            return ConversationHandler.END

    def select_mode(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        
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
        ("Manual" if mode == "Manual" else "AI Generated") + " mode selected.",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode=None
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
        "---",
        parse_mode=None
    )
    return QUESTION
else:
    update.message.reply_text(
        "Please send me either:\n"
        "1. A PDF file containing the lecture material, or\n"
        "2. Paste the lecture text directly\n\n"
        "I'll generate quiz questions from it.",
        parse_mode=None
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
            
            # Split questions list into chunks to avoid message length limit
            questions_chunks = [questions[i:i+10] for i in range(0, len(questions), 10)]
            
            for i, chunk in enumerate(questions_chunks):
                chunk_text = "\n".join([
                    f"{q['id']}. {q['question']}" for q in chunk
                ])
                if i == 0:
                    update.message.reply_text(
                        f"✅ Successfully generated {len(questions)} questions!\n\n"
                        f"Questions (Part {i+1}):\n\n{chunk_text}"
                    )
                else:
                    update.message.reply_text(
                        f"Questions (Part {i+1}):\n\n{chunk_text}"
                    )
            
            keyboard = ReplyKeyboardMarkup(
                [['Add Images', 'Skip Images']], 
                one_time_keyboard=True,
                resize_keyboard=True
            )
            
            update.message.reply_text(
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
                has_errors = True
                break

            try:
                correct_answer = int(lines[5])
                if not 1 <= correct_answer <= 4:
                    raise ValueError
                # Convert to 0-based index for Telegram API
                correct_answer -= 1
            except ValueError:
                update.message.reply_text(
                    f"❌ Question {idx}: Correct answer must be a number between 1 and 4"
                )
                has_errors = True
                break

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
        
        # Split questions list into chunks to avoid message length limit
        questions_chunks = [valid_questions[i:i+10] for i in range(0, len(valid_questions), 10)]
        
        for i, chunk in enumerate(questions_chunks):
            chunk_text = "\n".join([
                f"{q['id']}. {q['question']}" for q in chunk
            ])
            if i == 0:
                update.message.reply_text(
                    f"✅ Successfully parsed {len(valid_questions)} questions!\n\n"
                    f"Questions (Part {i+1}):\n\n{chunk_text}"
                )
            else:
                update.message.reply_text(
                    f"Questions (Part {i+1}):\n\n{chunk_text}"
                )
        
        keyboard = ReplyKeyboardMarkup(
            [['Add Images', 'Skip Images']], 
            one_time_keyboard=True,
            resize_keyboard=True
        )
        
        update.message.reply_text(
            "Would you like to add images to any questions?",
            reply_markup=keyboard
        )
        return IMAGE_MENU

    def get_admin_channels_and_groups(self, bot, user_id: int):
        try:
            channels = []
            
            # Only add BASMGA for authorized users
            if user_id in AUTHORIZED_USERS:
                channels.append({"username": "@BASMGA", "title": "BASMGA Channel"})
                
            # Try to get groups where bot is admin - available to all users
            try:
                updates = bot.get_updates(timeout=1)
                for update in updates:
                    if update.message and update.message.chat.type in ['group', 'supergroup']:
                        chat_id = update.message.chat.id
                        chat_member = bot.get_chat_member(chat_id, bot.id)
                        if chat_member.status in ['administrator', 'creator']:
                            chat = bot.get_chat(chat_id)
                            channels.append({
                                "username": f"@{chat.username}" if chat.username else str(chat_id),
                                "title": chat.title
                            })
            except Exception as e:
                logger.error(f"Error getting groups: {e}")
                    
            return channels
        except Exception as e:
            logger.error(f"Error getting admin channels and groups: {e}")
            return []

    def create_channel_keyboard(self, user_id: int):
        channels = self.get_admin_channels_and_groups(self.updater.bot, user_id)
        keyboard = []
        
        for channel in channels:
            keyboard.append([InlineKeyboardButton(
                channel['title'], 
                callback_data=f"channel:{channel['username']}"
            )])
            
        keyboard.append([InlineKeyboardButton(
            "Enter Channel/Group Username", 
            callback_data="channel:manual"
        )])
        return InlineKeyboardMarkup(keyboard)

    def safe_send_message(self, update, text):
        try:
            if len(text) > 4096:
                chunks = [text[i:i+4096] for i in range(0, len(text), 4096)]
                for chunk in chunks:
                    if update.callback_query:
                        update.callback_query.message.reply_text(chunk)
                    else:
                        update.message.reply_text(chunk)
            else:
                if update.callback_query:
                    update.callback_query.edit_message_text(text)
                else:
                    update.message.reply_text(text)
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
            channels = self.get_admin_channels_and_groups(context.bot, user_id)
            if channels:
                update.message.reply_text(
                    "Please select a channel or group to send the quizzes:",
                    reply_markup=reply_markup
                )
            else:
                update.message.reply_text(
                    "Please enter the channel/group username (including @) or ID where you want to send the quizzes:"
                )
            return CHANNEL_USERNAME
        else:
            # Split questions list into chunks to avoid message length limit
            questions = self.user_data[user_id]['questions']
            questions_chunks = [questions[i:i+10] for i in range(0, len(questions), 10)]
            
            for i, chunk in enumerate(questions_chunks):
                chunk_text = "\n".join([
                    f"{q['id']}. {q['question']}" for q in chunk
                ])
                if i == 0:
                    update.message.reply_text(
                        f"Questions (Part {i+1}):\n\n{chunk_text}"
                    )
                else:
                    update.message.reply_text(
                        f"Questions (Part {i+1}):\n\n{chunk_text}"
                    )
            
            update.message.reply_text(
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
            "Send another image with a question number as caption, or type /done to finish."
        )
        return WAITING_FOR_IMAGE

    def finish_images(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        reply_markup = self.create_channel_keyboard(user_id)
        
        channels = self.get_admin_channels_and_groups(context.bot, user_id)
        if channels:
            update.message.reply_text(
                "Please select a channel or group to send the quizzes:",
                reply_markup=reply_markup
            )
        else:
            update.message.reply_text(
                "Please enter the channel/group username (including @) or ID where you want to send the quizzes:"
            )
        return CHANNEL_USERNAME

    def button_channel_select(self, update: Update, context: CallbackContext):
        query = update.callback_query
        query.answer()

        if query.data == "channel:manual":
            query.edit_message_text(
                "Please enter the channel/group username (including @) or ID where you want to send the quizzes:"
            )
            return CHANNEL_USERNAME

        if query.data.startswith("channel:"):
            channel_username = query.data.split(":")[1]
            return self.send_to_channel_internal(update, context, channel_username)

    def send_to_channel_internal(self, update, context, channel_username):
        user_id = update.callback_query.from_user.id if update.callback_query else update.message.from_user.id
        
        try:
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
                        
                        self.send_with_retry(
                            context.bot,
                            context.bot.send_poll,
                            chat_id=channel_username,
                            question=question_data['question'],
                            options=question_data['options'],
                            type="quiz",
                            correct_option_id=question_data['correct_answer'],
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
            
            if user_id in self.user_data:
                del self.user_data[user_id]
            
            success_message = f"✅ Successfully sent all {questions_sent} quizzes! Press /create_quiz to create more quizzes."
            self.safe_send_message(update, success_message)
            
            return ConversationHandler.END

        except Exception as e:
            logger.error(f"Error in send_to_channel_internal: {str(e)}")
            
            # Initialize questions_sent if it doesn't exist
            if 'questions_sent' not in locals():
                questions_sent = 0
                
            # Initialize total_questions if it doesn't exist
            if 'total_questions' not in locals():
                if user_id in self.user_data and 'questions' in self.user_data[user_id]:
                    total_questions = len(self.user_data[user_id]['questions'])
                else:
                    total_questions = 0
            
            error_message = (
                f" to send quizzes (sent {questions_sent}/{total_questions}). Please check:\n"
                "1. Channel/group username/ID is correct\n"
                "2. Bot is an admin in the channel/group\n"
                "3. Bot has permission to post\n"
                f"4. Error details: {str(e)}\n\n"
                "Please try again with the correct channel/group username or ID:"
            )
            self.safe_send_message(update, error_message)
            return CHANNEL_USERNAME

    def send_to_channel(self, update: Update, context: CallbackContext):
        channel_username = update.message.text.strip()
        
        if not (channel_username.startswith('@') or channel_username.startswith('-') or channel_username.isdigit()):
            update.message.reply_text(
                "Please enter a valid channel/group username (starting with @) or ID.",
                reply_markup=ReplyKeyboardRemove()
            )
            return CHANNEL_USERNAME

        return self.send_to_channel_internal(update, context, channel_username)
        
    def is_user_authorized(self, user_id: int) -> bool:
        return user_id in AUTHORIZED_USERS

    def run(self):
        self.updater.start_polling(allowed_updates=['message', 'callback_query'])
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
    TOKEN = "7824881467:AAHbwaDdGX1gJOLt-hVYVzwBFc6udGv_IYU"
    GEMINI_API_KEY = "AIzaSyAro3Ksun3RQKXg5q-DvUauXUT60e-2xIw"
    bot = QuizPollBot(TOKEN, GEMINI_API_KEY)
    bot.run()
