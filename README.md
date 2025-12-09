# KIE (Knowledge Is Everything) Telegram Bot

A Telegram bot designed to help users find and share knowledge. The bot allows users to search for information, ask questions, and contribute new knowledge to a growing knowledge base.

## Features

- `/search [query]` - Search for knowledge in the database
- `/ask [question]` - Ask a question and get relevant information
- `/add [knowledge]` - Contribute new knowledge to the database
- `/help` - Show available commands
- `/start` - Start interaction with the bot

## Setup

1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in your Telegram bot token
4. (Optional) Configure KIE AI integration in `.env`:
	- `KIE_API_KEY` — your KIE API key
	- `KIE_API_URL` — base URL of the KIE API (default: `https://api.kie.ai`)
	- `KIE_DEFAULT_MODEL` — model id to use for `/ask` when no local answer found
4. Run the bot: `python bot.py`

## Prerequisites

- Python 3.8+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

## Current Status

The core functionality is implemented:
- Knowledge storage with JSON-based persistence
- Search functionality to find entries
- Ability to add new knowledge
- Question answering based on existing knowledge
- Proper error handling and user feedback

## Project Structure

```
kie-telegram-bot/
├── bot.py              # Main bot implementation
├── knowledge_storage.py # Knowledge storage module
├── requirements.txt    # Project dependencies
├── .env.example       # Environment variables template
├── setup.py           # Setup script
├── demo.py            # Demo of bot functionality
├── test_storage.py    # Knowledge storage tests
├── load_initial_knowledge.py # Initial data loader
├── run_bot.py         # Bot runner with validation
├── knowledge_store/   # JSON storage directory
│   └── entries.json
└── README.md
```

## Running the Bot Locally

### Prerequisites
- Python 3.8+
- Telegram bot token (get from [@BotFather](https://t.me/BotFather))
- KIE API key (from KIE AI platform)

### Quick Start

1. **Install dependencies:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Create and configure `.env` file:**
   ```bash
   cp .env.example .env
   # Edit .env and fill in your values
   ```
   
   Required variables:
   - `TELEGRAM_BOT_TOKEN` - Your Telegram bot token
   - `KIE_API_KEY` - Your KIE API key
   - `KIE_API_URL` - KIE API endpoint (default: `https://api.kie.ai`)
   - `KIE_DEFAULT_MODEL` - (Optional) Default model ID for /ask command

3. **Run the bot:**
   ```bash
   python run_bot.py
   ```

### Important Notes
- **Only one instance** of the bot can use the same token simultaneously
- The bot uses **polling** to check for messages
- User data is stored in `knowledge_store/` directory

## Usage Examples

- `/start` - Initialize bot
- `/search Python` - Find entries containing "Python" in local knowledge base
- `/ask What is photosynthesis?` - Get relevant information
- `/add The sky is blue` - Add new knowledge to the database
- `/help` - Display available commands
- `/models` - List available models from KIE AI

## Development

The project is structured with:
- A modular knowledge storage system
- Asynchronous Telegram bot handlers
- Environment-based configuration
- Proper error handling
- Test scripts for functionality verification