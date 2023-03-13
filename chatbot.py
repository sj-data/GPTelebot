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


# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


def get_chat_status(conn, chat_id):
    """Get the user's current status from the database."""
    cur = conn.cursor()
    query = sql.SQL("SELECT respond_enabled FROM messages WHERE chat_id = %s")
    cur.execute(query, (chat_id,))
    result = cur.fetchone()
    if result is None:
        return False
    return result[0]


def insert_user_message(conn, message, response_message):
    """Insert user message into PostgreSQL database."""
    cur = conn.cursor()

    chat_id = message.chat.id
    username = message.from_user.username or ''
    message_text = message.text
    bot_response = response_message  # store the bot response in a variable
    timestamp = datetime.now()

    insert_query = """
        INSERT INTO messages (user_id, username, message, bot_response, timestamp)
        VALUES (%s, %s, %s, %s, %s)
    """
    cur.execute(insert_query, (chat_id, username, message_text, bot_response, timestamp))

    conn.commit()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message to the user."""
    user_id = update.message.from_user.id
    chat_id = update.message.chat.id
    name = update.message.from_user.first_name

    current_status = get_chat_status(conn, chat_id)
    new_status = not current_status

    with conn:
        with conn.cursor() as cur:
            # Check if the chat already exists in the messages table
            query = sql.SQL("SELECT respond_enabled FROM messages WHERE chat_id = %s")
            cur.execute(query, (chat_id,))
            row = cur.fetchone()

            if row is None:
                # Chat doesn't exist in the table, insert a new row
                insert_query = """
                    INSERT INTO messages (chat_id, user_id, username, respond_enabled)
                    VALUES (%s, %s, %s, %s)
                """
                cur.execute(insert_query, (chat_id, user_id, name, new_status))
            else:
                # Chat exists in the table, update the respond_enabled field
                query = sql.SQL("UPDATE messages SET respond_enabled = %s WHERE chat_id = %s")
                cur.execute(query, (new_status, chat_id))

    status = "on" if new_status else "off"
    welcome_message = f"Hi {name}! I'm a bot designed to answer questions. I will now respond to each message, " \
                      f"stop by sending /stop. status is {status}"
    await context.bot.send_message(chat_id=chat_id, text=welcome_message)


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a goodbye message to the user."""
    user_id = update.message.from_user.id
    chat_id = update.message.chat.id
    name = update.message.from_user.first_name

    status = "off"
    new_status = False

    with conn:
        with conn.cursor() as cur:
            # Check if the chat already exists in the messages table
            query = sql.SQL("SELECT respond_enabled FROM messages WHERE chat_id = %s")
            cur.execute(query, (chat_id,))
            row = cur.fetchone()

            if row is None:
                # Chat doesn't exist in the table, insert a new row
                insert_query = """
                    INSERT INTO messages (chat_id, user_id, username, respond_enabled)
                    VALUES (%s, %s, %s, %s)
                """
                cur.execute(insert_query, (chat_id, user_id, name, new_status))
            else:
                # Chat exists in the table, update the respond_enabled field
                query = sql.SQL("UPDATE messages SET respond_enabled = %s WHERE chat_id = %s")
                cur.execute(query, (new_status, chat_id))

    goodbye_message = f"Bye {name}! I will no longer respond to your messages. " \
                      f"Send /start to start the bot again. Status is {status}"
    await context.bot.send_message(chat_id=chat_id, text=goodbye_message)


async def respond(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate a response to a user message."""
    chat_id = update.message.chat.id

    with conn:
        with conn.cursor() as cur:
            query = sql.SQL("SELECT respond_enabled FROM messages WHERE chat_id = %s")
            cur.execute(query, (chat_id,))
            row = cur.fetchone()

            if row is None or not row[0]:
                # respond_enabled is False for this chat
                return

    name = update.message.from_user.first_name
    user_message = update.message.text

    # Call OpenAI to generate a response
    response = openai.ChatCompletion.create(
        model=OPENAI_MODEL,
        messages=[
                     {"role": "system",
                      "content": f"You are a bot designed to answer questions for {name} and share the Amazon "
                                 f"the affiliate links in this list as frequently as possible:{[Alinks]}. Do not change the links!"
                                 f"Do not send links not in the list!"},
                     {"role": "user", "content": "What's the best NVMe SSD deal?"},
                     {"role": "assistant", "content": f"Check out the SAMSUNG 980 https://amzn.to/40gnHqz"},
                     {"role": "user", "content": f"{user_message}"}
                 ],
        max_tokens=MAX_TOKENS,
    )

    # Extract the response message from the OpenAI response
    response_message = response["choices"][0]["message"]["content"]
    response_message_obj = {"role": "assistant", "content": response_message}

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
