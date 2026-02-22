from aiogram.fsm.state import StatesGroup, State

class CreateQuiz(StatesGroup):
    title = State()
    question = State()
    option1 = State()
    option2 = State()
    option3 = State()
    option4 = State()
    correct = State()
    timer = State()
