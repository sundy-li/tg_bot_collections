from os import environ
import re

import google.generativeai as genai
from google.generativeai.types.generation_types import StopCandidateException
from telebot import TeleBot
from telebot.types import Message
import telegramify_markdown
from telegramify_markdown.customize import markdown_symbol

markdown_symbol.head_level_1 = "📌"  # If you want, Customizing the head level 1 symbol
markdown_symbol.link = "🔗"  # If you want, Customizing the link symbol

GOOGLE_GEMINI_KEY = environ.get("GOOGLE_GEMINI_KEY")

genai.configure(api_key=GOOGLE_GEMINI_KEY)
generation_config = {
    "temperature": 0.7,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 2048,
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

# Global history cache
gemini_player_dict = {}


def make_new_gemini_convo():
    model = genai.GenerativeModel(
        model_name="gemini-pro",
        generation_config=generation_config,
        safety_settings=safety_settings,
    )
    convo = model.start_chat()
    return convo


def gemini_handler(message: Message, bot: TeleBot) -> None:
    """Gemini : /gemini <question>"""
    m = message.text.strip()
    player = None
    # restart will lose all TODO
    if str(message.from_user.id) not in gemini_player_dict:
        player = make_new_gemini_convo()
        gemini_player_dict[str(message.from_user.id)] = player
    else:
        player = gemini_player_dict[str(message.from_user.id)]
    if m.strip() == "clear":
        bot.reply_to(
            message,
            "just clear you gemini messages history",
        )
        player.history.clear()
        return
    # keep the last 5, every has two ask and answer.
    if len(player.history) > 10:
        player.history = player.history[2:]

    try:
        player.send_message(m)
        gemini_reply_text = player.last.text.strip()
    except StopCandidateException as e:
        match = re.search(r'content\s*{\s*parts\s*{\s*text:\s*"([^"]+)"', str(e))
        if match:
            gemini_reply_text = match.group(1)
            gemini_reply_text = re.sub(r"\\n", "\n", gemini_reply_text)
        else:
            print("No meaningful text was extracted from the exception.")
            bot.reply_to(
                message,
                "Google gemini encountered an error while generating an answer. Please check the log.",
            )
            return

    try:
        bot.reply_to(
            message,
            "Gemini answer:\n" + telegramify_markdown.convert(gemini_reply_text),
            parse_mode="MarkdownV2",
        )
    except:
        print("wrong markdown format")
        bot.reply_to(
            message,
            "Gemini answer:\n\n" + gemini_reply_text,
        )


def gemini_photo_handler(message: Message, bot: TeleBot) -> None:
    s = message.caption
    reply_message = bot.reply_to(
        message,
        "Generating google gemini vision answer please wait.",
    )
    prompt = s.strip()
    # get the high quaility picture.
    max_size_photo = max(message.photo, key=lambda p: p.file_size)
    file_path = bot.get_file(max_size_photo.file_id).file_path
    downloaded_file = bot.download_file(file_path)
    with open("gemini_temp.jpg", "wb") as temp_file:
        temp_file.write(downloaded_file)

    model = genai.GenerativeModel("gemini-pro-vision")
    with open("gemini_temp.jpg", "rb") as image_file:
        image_data = image_file.read()
    contents = {
        "parts": [{"mime_type": "image/jpeg", "data": image_data}, {"text": prompt}]
    }
    try:
        response = model.generate_content(contents=contents)
        bot.reply_to(message, "Gemini vision answer:\n" + response.text)
    finally:
        bot.delete_message(reply_message.chat.id, reply_message.message_id)


def register(bot: TeleBot) -> None:
    bot.register_message_handler(gemini_handler, commands=["gemini"], pass_bot=True)
    bot.register_message_handler(gemini_handler, regexp="^gemini:", pass_bot=True)
    bot.register_message_handler(
        gemini_photo_handler,
        content_types=["photo"],
        func=lambda m: m.caption and m.caption.startswith(("gemini:", "/gemini")),
        pass_bot=True,
    )
