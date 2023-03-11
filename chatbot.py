#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import os
from datetime import datetime

import psycopg2
from psycopg2 import sql
import openai
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv("DATABASE_HOST"),
    database=os.getenv("DATABASE_NAME"),
    user=os.getenv("DATABASE_USER"),
    password=os.getenv("DATABASE_PASSWORD")
)
# Constants and configuration values
OPENAI_MODEL = "gpt-3.5-turbo"
MAX_TOKENS = 128
MAX_LOG = 4  # How many messages will be "Remembered", Keep even number

Alinks = [{'NVMe SSD': 'https://amzn.to/40gnHqz', 'USB Keyboard': 'https://amzn.to/3ZzT0MS',
           'Portable SSD': 'https://amzn.to/3YFPjEe', '3060 GPU': 'https://amzn.to/3JaB2td',
           'usb hub': 'https://amzn.to/3mA1Ewa'}]


# Set up OpenAI API key and Telegram bot token
def configure() -> None:
    openai.api_key = os.getenv("OPENAI_TOKEN")
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    if not telegram_token:
        raise ValueError("TELEGRAM_TOKEN environment variable is not set")


# Keep track of messages for each chat
messages_dict = {}

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


def get_user_status(conn, user_id):
    """Get the user's current status from the database."""
    cur = conn.cursor()
    query = sql.SQL("SELECT respond_enabled FROM messages WHERE user_id = %s")
    cur.execute(query, (user_id,))
    result = cur.fetchone()
    if result is None:
        return False
    return result[0]

def insert_user_message(conn, message, response_message):
    """Insert user message into PostgreSQL database."""
    cur = conn.cursor()

    user_id = message.from_user.id
    username = message.from_user.username
    message_text = message.text
    bot_response = response_message  # store the bot response in a variable
    timestamp = datetime.now()

    insert_query = """
        INSERT INTO messages (user_id, username, message, bot_response, timestamp)
        VALUES (%s, %s, %s, %s, %s)
    """
    cur.execute(insert_query, (user_id, username, message_text, bot_response, timestamp))

    conn.commit()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message to the user."""
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    name = update.message.from_user.first_name

    current_status = get_user_status(conn, user_id)
    new_status = not current_status

    with conn:
        with conn.cursor() as cur:
            query = sql.SQL("UPDATE messages SET respond_enabled = %s WHERE user_id = %s")
            cur.execute(query, (new_status, user_id))

    status = "on" if new_status else "off"
    welcome_message = f"Hi {name}! I'm a bot designed to answer questions. I will now respond to each message, " \
                      f"stop by sending /stop. status is {status}"
    await context.bot.send_message(chat_id=chat_id, text=welcome_message)


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a goodbye message to the user."""
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    name = update.message.from_user.first_name

    current_status = get_user_status(conn, user_id)
    new_status = False

    with conn:
        with conn.cursor() as cur:
            query = sql.SQL("UPDATE messages SET respond_enabled = %s WHERE user_id = %s")
            cur.execute(query, (new_status, user_id))

    goodbye_message = f"Bye {name}! I will no longer respond to your messages. " \
                      f"Send /start to start the bot again."
    await context.bot.send_message(chat_id=chat_id, text=goodbye_message)

async def respond(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate a response to a user message."""
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    message_text = update.message.text

    with psycopg2.connect(
            host=os.getenv("DATABASE_HOST"),
            database=os.getenv("DATABASE_NAME"),
            user=os.getenv("DATABASE_USER"),
            password=os.getenv("DATABASE_PASSWORD")
    ) as conn:
        with conn.cursor() as cur:
            query = sql.SQL("SELECT respond_enabled FROM messages WHERE user_id = %s")
            cur.execute(query, (user_id,))
            row = cur.fetchone()

            if row is None or not row[0]:
                # respond_enabled is False for this user
                return

    name: str = update.message.from_user.first_name
    chat_id: int = update.message.chat_id
    user_message: str = update.message.text

    # Add the message to the list for the current chat, remove old messages
    latest_message = {"role": "user", "content": user_message}
    messages_dict.setdefault(chat_id, []).append(latest_message)
    if len(messages_dict.get(chat_id, [])) >= MAX_LOG:
        messages_dict[chat_id] = messages_dict[chat_id][2:]

    # Retrieve the unique message for the current chat
    unique_messages = messages_dict.get(chat_id, [])

    # Call OpenAI to generate a response
    response = openai.ChatCompletion.create(
        model=OPENAI_MODEL,
        messages=[
                     {"role": "system",
                      "content": f"You are a bot designed to answer questions for {name} and share the Amazon "
                                 f"the affiliate links in this list as frequently as possible:{Alinks}. Do not change the links!"
                                 f"Do not send links not in the list!"},
                     {"role": "user", "content": "What's the best NVMe SSD deal?"},
                     {"role": "assistant", "content": f"Check out the SAMSUNG 980 https://amzn.to/40gnHqz"},
                     {"role": "user", "content": f"{user_message}"}
                 ] + unique_messages,
        max_tokens=MAX_TOKENS,
    )

    # Extract the response message from the OpenAI response
    response_message = response["choices"][0]["message"]["content"]
    response_message_obj = {"role": "assistant", "content": response_message}
    messages_dict.setdefault(chat_id, []).append(response_message_obj)

    # Insert the user message and bot response into the database
    with conn:
        insert_user_message(conn, update.message, response_message)
    # Send the response to the user
    await context.bot.send_message(chat_id=chat_id, text=response_message)


def main() -> None:
    configure()

    # Create the Telegram bot application
    application = ApplicationBuilder().token(os.getenv("TELEGRAM_TOKEN")).build()

    # Add handlers for commands and messages
    response_handler = MessageHandler(filters.TEXT, respond)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(response_handler)

    # Start the bot
    application.run_polling()


if __name__ == "__main__":
    main()
