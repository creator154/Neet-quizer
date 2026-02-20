# bot.py - Complete NEET Quizer Bot (Telegram Quiz Style)
import logging
import os
from dotenv import load_dotenv
from telegram import Update, Poll, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    PollAnswerHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# In-memory storage (per user quiz data)
users = {}  # user_id → {'title', 'desc', 'questions', 'current_q', 'score', 'state'}

# ────────────────────────────────────────────────
# Helper: Send next question as quiz poll
# ────────────────────────────────────────────────
async def send_next_question(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    if user_id not in users:
        return

    data = users[user_id]

    if data['current_q'] >= len(data['questions']):
        percentage = (data['score'] / len(data['questions'])) * 100 if data['questions'] else 0
        msg = (
            f"🎉 Quiz Complete!\n\n"
            f"Title: {data['title']}\n"
            f"Correct: {data['score']} / {len(data['questions'])}\n"
            f"Score: {percentage:.1f}%"
        )
        await context.bot.send_message(chat_id, msg)
        data['state'] = 'idle'
        return

    q = data['questions'][data['current_q']]
    await context.bot.send_poll(
        chat_id=chat_id,
        question=q['text'],
        options=q['options'],
        type=Poll.QUIZ,
        correct_option_id=q['correct_id'],
        is_anonymous=False,
        allows_multiple_answers=False,
        protect_content=False
    )


# ────────────────────────────────────────────────
# /start – Welcome with buttons
# ────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("➕ Create New Quiz", callback_data='create')],
        [InlineKeyboardButton("▶️ Start My Quiz", callback_data='start_quiz')],
        [InlineKeyboardButton("❓ Help", callback_data='help')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        "🚀 **Welcome to NEET Quizer Bot!**\n\n"
        "Custom NEET-style quizzes banao aur practice karo.\n"
        "Group ya DM dono mein chalega.\n\n"
        "Shuru karne ke liye button dabao 👇"
    )
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')


# ────────────────────────────────────────────────
# Button clicks (create, start, help)
# ────────────────────────────────────────────────
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == 'create':
        users[user_id] = {
            'title': None,
            'desc': None,
            'questions': [],
            'current_q': 0,
            'score': 0,
            'state': 'title'
        }
        await query.edit_message_text("Quiz ka title bhejo (jaise: NEET Biology Mock 2026)")

    elif data == 'start_quiz':
        if user_id not in users or not users[user_id].get('questions'):
            await query.edit_message_text("Pehle quiz banao questions ke saath!")
            return
        users[user_id]['state'] = 'quiz'
        users[user_id]['current_q'] = 0
        users[user_id]['score'] = 0
        await query.edit_message_text(f"Starting **{users[user_id]['title']}** 🔥 Good luck!")
        await send_next_question(query.message.chat_id, user_id, context)

    elif data == 'help':
        help_text = (
            "Commands:\n"
            "/start - Yeh message\n"
            "/create - Naya quiz shuru karo (button se bhi)\n"
            "Poll bhej ke questions add karo (Quiz mode on)\n"
            "/done - Quiz creation finish\n"
            "/startquiz - Quiz chalao\n\n"
            "Group mein add karke sab saath practice kar sakte ho."
        )
        await query.edit_message_text(help_text)


# ────────────────────────────────────────────────
# Text messages (title, desc, skip)
# ────────────────────────────────────────────────
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_id not in users or users[user_id]['state'] in ['idle', 'quiz']:
        return

    state = users[user_id]['state']

    if state == 'title':
        users[user_id]['title'] = text
        users[user_id]['state'] = 'desc'
        await update.message.reply_text(
            f"Title set: {text}\n\n"
            "Description bhejo (optional) ya /skip"
        )
        return

    if state == 'desc':
        if text.lower() in ['/skip', 'skip']:
            users[user_id]['desc'] = None
        else:
            users[user_id]['desc'] = text

        users[user_id]['state'] = 'questions'
        await update.message.reply_text(
            "Ab questions add karo:\n"
            "• Telegram mein Poll banao → Type: Quiz\n"
            "• Sahi option select karo\n"
            "• Question + options daalo\n\n"
            "Jab khatam ho to /done likh do"
        )
        return


# ────────────────────────────────────────────────
# Receive poll during creation
# ────────────────────────────────────────────────
async def handle_poll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.poll is None:
        return

    user_id = update.effective_user.id
    if user_id not in users or users[user_id]['state'] != 'questions':
        return

    poll = update.message.poll

    if poll.type != Poll.QUIZ or poll.correct_option_id is None:
        await update.message.reply_text("Quiz type poll bhejo aur sahi option select karna mat bhoolna!")
        return

    users[user_id]['questions'].append({
        'text': poll.question,
        'options': [opt.text for opt in poll.options],
        'correct_id': poll.correct_option_id
    })

    count = len(users[user_id]['questions'])
    await update.message.reply_text(f"Question {count} add ho gaya! 🎯\nAgla poll bhejo ya /done")


# ────────────────────────────────────────────────
# Finish creation
# ────────────────────────────────────────────────
async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id not in users or users[user_id]['state'] != 'questions':
        return

    if not users[user_id]['questions']:
        await update.message.reply_text("Koi question add nahi kiya!")
        return

    users[user_id]['state'] = 'idle'
    q_count = len(users[user_id]['questions'])
    text = f"Quiz taiyar hai!\n\nTitle: {users[user_id]['title']}\nQuestions: {q_count}\n\n/startquiz se shuru kar sakte ho."
    await update.message.reply_text(text)


# ────────────────────────────────────────────────
# Handle user's answer during quiz
# ────────────────────────────────────────────────
async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    poll_answer = update.poll_answer
    user_id = poll_answer.user.id

    if user_id not in users or users[user_id]['state'] != 'quiz':
        return

    data = users[user_id]
    selected = poll_answer.option_ids[0] if poll_answer.option_ids else -1

    if selected == data['questions'][data['current_q']]['correct_id']:
        data['score'] += 1
        await context.bot.send_message(user_id, "Sahiii! ✅ +1")
    else:
        await context.bot.send_message(user_id, "Galat! ❌")

    data['current_q'] += 1
    await send_next_question(poll_answer.user.id, user_id, context)


# ────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(MessageHandler(filters.TEXT & \~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.POLL, handle_poll))
    app.add_handler(PollAnswerHandler(handle_poll_answer))

    print("NEET Quizer Bot chal raha hai...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
