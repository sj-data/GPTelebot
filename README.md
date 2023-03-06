# OpenAI Chatbot

This is a simple chatbot created using OpenAI's GPT-3.5 Turbo model and integrated with Telegram. The bot can answer questions and provide assistance with various topics.

## Requirements

To use this chatbot, you will need the following:

- Python 3.8 or later
- OpenAI API key
- Telegram bot token

## Installation

1. Clone this repository to your local machine
2. Install the required dependencies using the following command: `pip install -r requirements.txt`
3. Set up environment variables by creating a `.env` file in the root directory of the project and adding the following lines:
    ```
    OPENAI_TOKEN=<your OpenAI API key>
    TELEGRAM_TOKEN=<your Telegram bot token>
    ```
4. Run the following command to start the chatbot: `python chatbot.py`

## Usage

To use the chatbot, simply start a conversation with it on Telegram. The chatbot will introduce itself and you can start asking questions or requesting assistance.

The chatbot uses the OpenAI GPT-3.5 Turbo model to generate responses, so it should be able to provide helpful answers to a wide range of questions. Additionally, the chatbot keeps a log of recent messages for each chat, so it can use context from previous messages to generate more accurate responses.

## Limitations

This is designed to be used with as many instances as required. It connects each user chat history to their group or account using nested dictionaries. If you wanted to use this method to deploy for large scale production you would likely need to replace this with a database.

## Variables

OPENAI_MODEL = "gpt-3.5-turbo"
This variable holds the name of the OpenAI model used to generate responses. In this case, we're using the GPT-3.5 Turbo model, which is a powerful language model capable of generating human-like text.

MAX_TOKENS = 128
This variable determines the maximum number of tokens to use when generating a response. The number of tokens affects the length and complexity of the generated response. In this case, we're using a maximum of 128 tokens.

MAX_LOG = 10
This variable determines the maximum number of messages to remember in the chat history. The chatbot keeps track of recent messages to provide context for generating responses. In this case, we're keeping a maximum of 10 messages in the chat history.
