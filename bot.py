import logging
from telegram import Update, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from flask import Flask
from threading import Thread

# States for conversation
QUESTION, OPTIONS, CORRECT_ANSWER, EXPLANATION, MEDIA = range(5)
QUIZ_TYPE = "quiz"
POLL_TYPE = "poll"

# Set up logging for the bot
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app for health check endpoint
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

class QuizPollBot:
    def __init__(self, token: str):
        # Initialize the application with the token
        self.application = Application.builder().token(token).build()

        # Add conversation handlers
        quiz_handler = ConversationHandler(
            entry_points=[CommandHandler('create_quiz', self.start_quiz)],
            states={
                QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_question)],
                OPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_options)],
                CORRECT_ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_correct_answer)],
                EXPLANATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_explanation)],
                MEDIA: [MessageHandler(filters.PHOTO, self.receive_media)]  # Media state
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )

        self.application.add_handler(quiz_handler)
        self.application.add_handler(CommandHandler('start', self.start))
        self.application.add_handler(CommandHandler('help', self.help))

        # Store temporary data
        self.user_data = {}

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        welcome_message = (
            "👋 Welcome to the Quiz & Poll Bot!\n\n"
            "Commands:\n"
            "/create_quiz - Create a quiz with correct answers\n"
            "/create_poll - Create a regular poll\n"
            "/cancel - Cancel creation process\n"
            "/help - Show this help message\n\n"
            "For contact @FBI_MF ⚡️"
        )
        await update.message.reply_text(welcome_message)

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await update.message.reply_text(help_message)

    async def start_quiz(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        self.user_data[user_id] = {'type': QUIZ_TYPE, 'questions': []}
        await update.message.reply_text("Please send me your quiz questions in the format mentioned in /help.")
        return QUESTION

    async def receive_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        text = update.message.text.strip()

        # Split the message by '---' to process each question
        questions_data = text.split('---')
        questions_list = []

        for question_data in questions_data:
            parts = question_data.strip().split('\n')

            # Ensure we have at least a question, two options, a correct answer, and an explanation
            if len(parts) < 5:
                await update.message.reply_text("Invalid format! Please follow this structure:\n\n"
                                                "Question\nOption 1\nOption 2\nCorrect Answer (1 or 2)\nExplanation\n\n"
                                                "Separate multiple questions using '---'.")
                return QUESTION

            question = parts[0]
            options = parts[1:3]

            # Validate correct answer is a number
            if not parts[3].strip().isdigit():
                await update.message.reply_text("The correct answer must be a number (e.g., 1 or 2). Please try again.")
                return QUESTION
            
            correct_answer = int(parts[3].strip()) - 1  # Convert to zero-based index

            if correct_answer < 0 or correct_answer >= len(options):
                await update.message.reply_text("Invalid correct answer number! It must be within the range of provided options.")
                return QUESTION

            explanation = parts[4].strip()

            questions_list.append({
                'question': question,
                'options': options,
                'correct_option_id': correct_answer,
                'explanation': explanation,
                'media': None  # Placeholder for media
            })

        self.user_data[user_id]['questions'] = questions_list
        await update.message.reply_text(f"I've received {len(questions_list)} questions! Now I'll process them.")

        # Process each question sequentially
        await self.ask_for_media(update, context, user_id, questions_list[0])
        return MEDIA

    async def ask_for_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, question_data: dict):
        await update.message.reply_text("Please send a picture for this question, or type 'skip' if you don't want to include one.")
        return MEDIA

    async def receive_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        if update.message.photo:
            media_file = update.message.photo[-1].file_id  # Get the highest resolution photo
            self.user_data[user_id]['questions'][0]['media'] = media_file
            await self.receive_options(update, context)
            return OPTIONS
        elif update.message.text.lower() == 'skip':
            await self.receive_options(update, context)
            return OPTIONS

    async def receive_options(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        options = self.user_data[user_id]['questions'][0]['options']
        
        if len(options) < 2:
            await update.message.reply_text("Please provide at least 2 options.")
            return OPTIONS

        await self.receive_correct_answer(update, context)

    async def receive_correct_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        try:
            correct_answer = int(update.message.text) - 1
            if 0 <= correct_answer < len(self.user_data[user_id]['questions'][0]['options']):
                self.user_data[user_id]['questions'][0]['correct_option_id'] = correct_answer
                await update.message.reply_text("Great! Now, please provide an explanation for the correct answer:")
                return EXPLANATION
            else:
                raise ValueError()
        except ValueError:
            await update.message.reply_text("Please send a valid number between 1 and the number of options.")
            return CORRECT_ANSWER

    async def receive_explanation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        self.user_data[user_id]['questions'][0]['explanation'] = update.message.text

        # Send the quiz with the explanation
        await self.send_quiz(update, context, user_id, self.user_data[user_id]['questions'][0])
        return ConversationHandler.END

    async def send_quiz(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, question_data: dict):
        explanation = question_data.get('explanation', "No explanation provided.")
        media = question_data.get('media')

        # Prepare media if exists
        media_to_send = None
        if media:
            media_to_send = InputMediaPhoto(media)

        # Send the quiz question with or without media
        await context.bot.send_poll(
            chat_id=update.effective_chat.id,
            question=question_data['question'],
            options=question_data['options'],
            type=Poll.QUIZ,
            correct_option_id=question_data['correct_option_id'],
            is_anonymous=True,
            explanation=explanation  # Include the explanation here
        )

        if media_to_send:
            await context.bot.send_media_group(
                chat_id=update.effective_chat.id,
                media=[media_to_send]
            )
        
        # After sending the question, process the next one (if any)
        self.user_data[user_id]['questions'].pop(0)  # Remove the processed question
        if len(self.user_data[user_id]['questions']) > 0:
            # Ask for media for the next question
            await self.ask_for_media(update, context, user_id, self.user_data[user_id]['questions'][0])
        else:
            await update.message.reply_text("Quiz created! You can create another with /create_quiz")

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        if user_id in self.user_data:
            del self.user_data[user_id]
        await update.message.reply_text("Creation cancelled. You can start over with /create_quiz or /create_poll")
        return ConversationHandler.END

    def run(self):
        self.application.run_polling()

def run_flask():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    bot_thread = Thread(target=bot.run)
    bot_thread.start()

if __name__ == "__main__":
    TOKEN = '7824881467:AAGk0Bv8Ubos6RAy6tDM1jK8KfEkDFrFfLE'  # Replace with your bot's token
    bot = QuizPollBot(TOKEN)
    print("Bot is running...")
    keep_alive()
