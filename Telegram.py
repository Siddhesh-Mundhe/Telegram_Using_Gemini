# import telethon 
# from teleethon.t1.custom import Button
# from telethon import TelegramClient, events

# import asyncio
##Gemini API Key:AIzaSyDQaJo3awbIBu95al-PSteSBY8LBtN9I4A
# import vertexai
# from vertexai.generative_models._generative_models import HarmCCategory, HarmBlockThreshold
# from vertexai.preview.generative_models import {
#     GenerativeModel,
#     ChatSession,
#     Part
# }pip

import os
import google.generativeai as genai
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from pymongo import MongoClient
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
# load_dotenv()
# TELEGRAM_TOKEN = os.getenv("7832961766:AAHDbptFs8-SRTLUKiS1coLt6ez4FSprrdw")
# GEMINI_API_KEY = os.getenv("AIzaSyDQaJo3awbIBu95al-PSteSBY8LBtN9I4A")
# MONGO_URI = os.getenv("mongodb+srv://siddheshmundhe499:Qwerty12345@newcluster.41cv4.mongodb.net/")

import os
from dotenv import load_dotenv

# Load the .env file explicitly
dotenv_path = os.path.join(os.path.dirname(__file__), "files.env")
load_dotenv(dotenv_path)

# Retrieve tokens
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

# Debugging: Check if variables are loaded
if not TELEGRAM_TOKEN:
    print("❌ ERROR: TELEGRAM_TOKEN is not set! Check your .env file path.")
    exit()

print("✅ TELEGRAM_TOKEN loaded successfully.")

from pymongo import MongoClient

MONGO_URI = "mongodb+srv://siddheshmundhe499:Qwerty12345@newcluster.41cv4.mongodb.net/"

client = MongoClient(MONGO_URI)

try:
    client.admin.command("ping")
    print("✅ Connected to MongoDB successfully!")
except Exception as e:
    print("❌ MongoDB Connection Failed:", e)


# Initialize MongoDB
client = MongoClient(MONGO_URI)
db = client["telegram_bot"]
users_collection = db["users"]
chat_history_collection = db["chat_history"]
files_collection = db["files"]

# Initialize Gemini AI
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-pro")

async def start(update: Update, context: CallbackContext):
    """Handles the /start command"""
    user = update.message.from_user
    chat_id = update.message.chat_id

    existing_user = users_collection.find_one({"chat_id": chat_id})

    if not existing_user:
        users_collection.insert_one({
            "first_name": user.first_name,
            "username": user.username,
            "chat_id": chat_id,
            "phone_number": None
        })
        await update.message.reply_text(f"Hello {user.first_name}! Please share your phone number.")

        # Request phone number
        keyboard = [[KeyboardButton("Share Contact", request_contact=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        await update.message.reply_text("Click below to share your contact.", reply_markup=reply_markup)
    else:
        await update.message.reply_text(f"Welcome back, {user.first_name}!")

async def save_contact(update: Update, context: CallbackContext):
    """Handles contact sharing"""
    user = update.message.from_user
    chat_id = update.message.chat_id
    phone_number = update.message.contact.phone_number

    users_collection.update_one({"chat_id": chat_id}, {"$set": {"phone_number": phone_number}})
    await update.message.reply_text(f"Phone number saved: {phone_number}")

async def chat_with_gemini(update: Update, context: CallbackContext):
    """Handles AI chat using Gemini"""
    user = update.message.from_user
    chat_id = update.message.chat_id
    user_message = update.message.text

    # Get AI response
    response = model.generate_content([user_message])
    bot_response = response.text

    # Save to MongoDB
    chat_history_collection.insert_one({
        "chat_id": chat_id,
        "user_message": user_message,
        "bot_response": bot_response,
        "timestamp": datetime.utcnow()
    })

    await update.message.reply_text(bot_response)

async def analyze_file(update: Update, context: CallbackContext):
    """Handles file and image analysis"""
    user = update.message.from_user
    chat_id = update.message.chat_id
    document = update.message.document or update.message.photo[-1]

    file_id = document.file_id
    file_name = document.file_name if hasattr(document, 'file_name') else "image"
    file_info = await context.bot.get_file(file_id)
    file_path = file_info.file_path

    # Analyze with Gemini
    response = model.generate_content(["Describe the contents of this file/image.", file_path])
    description = response.text

    # Save file metadata
    files_collection.insert_one({
        "chat_id": chat_id,
        "file_name": file_name,
        "description": description,
        "timestamp": datetime.utcnow()
    })

    await update.message.reply_text(f"File analyzed: {file_name}\nDescription: {description}")

async def web_search(update: Update, context: CallbackContext):
    """Handles web search"""
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("Usage: /websearch <query>")
        return

    # Perform AI-powered web search
    response = model.generate_content([f"Summarize web search results for: {query}"])
    search_summary = response.text

    await update.message.reply_text(f"🔎 Web Search Results:\n{search_summary}")

async def chat_with_gemini(update: Update, context: CallbackContext):
    """Handles AI chat using Gemini with context awareness."""
    user_message = update.message.text
    chat_id = update.message.chat_id

    # Retrieve last 5 messages from history for context
    past_messages = chat_history_collection.find({"chat_id": chat_id}).sort("timestamp", -1).limit(5)
    history = "\n".join([f"User: {msg['user_message']}\nBot: {msg['bot_response']}" for msg in past_messages])

    # Use history as context
    prompt = f"Context:\n{history}\n\nUser: {user_message}\nBot:"
    response = model.generate_content([prompt])
    bot_response = response.text

    # Save new message in MongoDB
    chat_history_collection.insert_one({
        "chat_id": chat_id,
        "user_message": user_message,
        "bot_response": bot_response,
        "timestamp": datetime.now(timezone.utc) 
    })

    # Send response
    await update.message.reply_text(bot_response)


def main():
    """Main function to run the bot"""
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("websearch", web_search))
    app.add_handler(MessageHandler(filters.CONTACT, save_contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_with_gemini))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, analyze_file))

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
