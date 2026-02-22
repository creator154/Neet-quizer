import asyncio
import logging
import random
import aiosqlite

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, PollAnswer
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import init_db, DB_NAME
from states import CreateQuiz

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

active_sessions = {}

# START
@dp.message(Command("start"))
async def start(message: Message):
    await message.answer("Welcome!\nUse /create to create quiz")

# CREATE QUIZ
@dp.message(Command("create"))
async def create_quiz(message: Message, state: FSMContext):
    await state.set_state(CreateQuiz.title)
    await message.answer("Send Quiz Title")

@dp.message(CreateQuiz.title)
async def set_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(CreateQuiz.question)
    await message.answer("Send Question")

@dp.message(CreateQuiz.question)
async def set_question(message: Message, state: FSMContext):
    await state.update_data(question=message.text)
    await state.set_state(CreateQuiz.option1)
    await message.answer("Option 1")

@dp.message(CreateQuiz.option1)
async def set_o1(message: Message, state: FSMContext):
    await state.update_data(option1=message.text)
    await state.set_state(CreateQuiz.option2)
    await message.answer("Option 2")

@dp.message(CreateQuiz.option2)
async def set_o2(message: Message, state: FSMContext):
    await state.update_data(option2=message.text)
    await state.set_state(CreateQuiz.option3)
    await message.answer("Option 3")

@dp.message(CreateQuiz.option3)
async def set_o3(message: Message, state: FSMContext):
    await state.update_data(option3=message.text)
    await state.set_state(CreateQuiz.option4)
    await message.answer("Option 4")

@dp.message(CreateQuiz.option4)
async def set_o4(message: Message, state: FSMContext):
    await state.update_data(option4=message.text)
    await state.set_state(CreateQuiz.correct)
    await message.answer("Correct option number (1-4)")

@dp.message(CreateQuiz.correct)
async def set_correct(message: Message, state: FSMContext):
    await state.update_data(correct=int(message.text)-1)
    await state.set_state(CreateQuiz.timer)
    await message.answer("Timer in seconds")

@dp.message(CreateQuiz.timer)
async def save_quiz(message: Message, state: FSMContext):
    data = await state.get_data()
    timer = int(message.text)

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO quizzes (creator_id,title,timer,shuffle) VALUES (?,?,?,?)",
            (message.from_user.id, data["title"], timer, 0)
        )
        quiz_id = (await db.execute("SELECT last_insert_rowid()")).fetchone()
        quiz_id = (await quiz_id)[0]

        await db.execute("""
        INSERT INTO questions (quiz_id,question,option1,option2,option3,option4,correct)
        VALUES (?,?,?,?,?,?,?)
        """, (quiz_id,data["question"],data["option1"],data["option2"],
              data["option3"],data["option4"],data["correct"]))
        await db.commit()

    await state.clear()
    await message.answer(f"Quiz Created!\nStart in group using:\n/startquiz {quiz_id}")

# START QUIZ IN GROUP
@dp.message(Command("startquiz"))
async def start_group_quiz(message: Message):
    if message.chat.type == "private":
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer("Usage: /startquiz quiz_id")
        return

    quiz_id = int(args[1])

    async with aiosqlite.connect(DB_NAME) as db:
        quiz = await db.execute("SELECT timer FROM quizzes WHERE id=?", (quiz_id,))
        quiz = await quiz.fetchone()

        question = await db.execute("SELECT * FROM questions WHERE quiz_id=?", (quiz_id,))
        question = await question.fetchone()

    if not quiz:
        await message.answer("Quiz not found")
        return

    timer = quiz[0]

    active_sessions[message.chat.id] = {
        "correct": question[7],
        "scores": {}
    }

    await bot.send_poll(
        chat_id=message.chat.id,
        question=question[2],
        options=[question[3],question[4],question[5],question[6]],
        type="quiz",
        correct_option_id=question[7],
        open_period=timer
    )

# HANDLE ANSWERS
@dp.poll_answer()
async def handle_answer(poll_answer: PollAnswer):
    for session in active_sessions.values():
        correct = session["correct"]
        if poll_answer.option_ids[0] == correct:
            session["scores"][poll_answer.user.id] = session["scores"].get(poll_answer.user.id,0)+1

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
