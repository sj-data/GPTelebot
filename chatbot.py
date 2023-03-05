#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import os

import openai
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# Constants and configuration values
OPENAI_MODEL = "gpt-3.5-turbo"
MAX_TOKENS = 128
MAX_LOG = 10  # How many messages will be "Remembered", Keep even number


# Load environment variables from .env file
def load_environment_variables() -> None:
    load_dotenv()


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


async def respond(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate a response to a user message."""
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
                     {"role": "system", "content": f"You are a bot designed to answer questions for {name}"},
                     {"role": "user", "content": "Where is Paris?"},
                     {"role": "assistant", "content": f"Paris is in France {name}, what else can I help you with?"},
                     {"role": "user", "content": f"{user_message}"}
                 ] + unique_messages,
        max_tokens=MAX_TOKENS,
    )

    # Extract the response message from the OpenAI response
    response_message = response["choices"][0]["message"]["content"]
    response_message_obj = {"role": "assistant", "content": response_message}
    messages_dict.setdefault(chat_id, []).append(response_message_obj)

    # Send the response to the user
    await context.bot.send_message(chat_id=chat_id, text=response_message)


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle unknown commands."""
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I AM ERROR")


def main() -> None:
    load_environment_variables()
    configure()

    # Create the Telegram bot application
    application = ApplicationBuilder().token(os.getenv("TELEGRAM_TOKEN")).build()

    # Add handlers for commands and messages
    unknown_handler = MessageHandler(filters.COMMAND, unknown)
    response_handler = MessageHandler(filters.ALL, respond)
    application.add_handler(unknown_handler)
    application.add_handler(response_handler)

    # Start the bot
    application.run_polling()


if __name__ == "__main__":
    main()
