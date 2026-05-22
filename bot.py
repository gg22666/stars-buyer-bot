import asyncio
import aiosqlite
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command

TOKEN = "8565687936:AAHZ-lh_tErI85VKAI9d2v3jlCSAxlWgdk4"
ADMIN_ID = 6628776632
POST_LINK = "https://t.me/theatra1ka/1901"
RATE = 0.89
SUPPORT_USERNAME = "@intellectual_sabotage"

class SellForm(StatesGroup):
    waiting_for_amount = State()
    waiting_for_payment = State()
    waiting_for_confirm = State()
    waiting_for_support = State()
    waiting_for_calculator = State()

async def init_db():
    async with aiosqlite.connect("stars_requests.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                stars INTEGER NOT NULL,
                payment TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_payments (
                user_id INTEGER PRIMARY KEY,
                payment TEXT NOT NULL
            )
        """)
        await db.commit()

async def add_request(user_id: int, username: str, stars: int, payment: str) -> int:
    async with aiosqlite.connect("stars_requests.db") as db:
        await db.execute(
            "INSERT INTO requests (user_id, username, stars, payment, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, username or "no_username", stars, payment, datetime.now().isoformat())
        )
        await db.commit()
        cursor = await db.execute("SELECT last_insert_rowid()")
        return (await cursor.fetchone())[0]

async def get_user_stats(user_id: int):
    async with aiosqlite.connect("stars_requests.db") as db:
        cursor = await db.execute(
            "SELECT COUNT(*), SUM(stars), SUM(CASE WHEN status = 'paid' THEN stars ELSE 0 END) FROM requests WHERE user_id = ?",
            (user_id,)
        )
        total_requests, total_stars, paid_stars = await cursor.fetchone()
        return total_requests or 0, total_stars or 0, paid_stars or 0

async def get_user_payment(user_id: int):
    async with aiosqlite.connect("stars_requests.db") as db:
        cursor = await db.execute("SELECT payment FROM user_payments WHERE user_id = ?", (user_id,))
        result = await cursor.fetchone()
        return result[0] if result else None

async def save_user_payment(user_id: int, payment: str):
    async with aiosqlite.connect("stars_requests.db") as db:
        await db.execute(
            "INSERT OR REPLACE INTO user_payments (user_id, payment) VALUES (?, ?)",
            (user_id, payment)
        )
        await db.commit()

async def get_pending_requests():
    async with aiosqlite.connect("stars_requests.db") as db:
        cursor = await db.execute(
            "SELECT * FROM requests WHERE status IN ('pending', 'sent') ORDER BY created_at DESC"
        )
        return await cursor.fetchall()

async def get_request(req_id: int):
    async with aiosqlite.connect("stars_requests.db") as db:
        cursor = await db.execute("SELECT * FROM requests WHERE id = ?", (req_id,))
        return await cursor.fetchone()

async def update_status(req_id: int, new_status: str):
    async with aiosqlite.connect("stars_requests.db") as db:
        await db.execute("UPDATE requests SET status = ? WHERE id = ?", (new_status, req_id))
        await db.commit()

async def get_user_requests(user_id: int, limit: int = 5):
    async with aiosqlite.connect("stars_requests.db") as db:
        cursor = await db.execute(
            "SELECT id, stars, status, created_at FROM requests WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        )
        return await cursor.fetchall()

async def main():
    await init_db()
    bot = Bot(token=TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    def get_main_menu():
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="💰 Продать звезды")],
                [KeyboardButton(text="📊 Мой кабинет"), KeyboardButton(text="💳 Мои реквизиты")],
                [KeyboardButton(text="❓ Как это работает"), KeyboardButton(text="🛠 Техподдержка")],
                [KeyboardButton(text="📈 Курс"), KeyboardButton(text="🧮 Калькулятор")]
            ],
            resize_keyboard=True
        )

    # ================== ГЛОБАЛЬНЫЙ ОБРАБОТЧИК МЕНЮ (АВТОМАТИЧЕСКОЕ ЗАКРЫТИЕ КАЛЬКУЛЯТОРА) ==================
    @dp.message(F.text.in_(["💰 Продать звезды", "📊 Мой кабинет", "💳 Мои реквизиты", 
                            "❓ Как это работает", "🛠 Техподдержка", "📈 Курс", "🧮 Калькулятор"]))
    async def handle_menu_buttons(message: Message, state: FSMContext):
        current_state = await state.get_state()
        
        # Если пользователь был в калькуляторе — автоматически закрываем его
        if current_state == SellForm.waiting_for_calculator:
            await state.clear()
        
        # Теперь обрабатываем нажатую кнопку
        if message.text == "💰 Продать звезды":
            await state.set_state(SellForm.waiting_for_amount)
            await message.answer("Сколько звёзд хочешь продать?\n<b>Минимум 2 звезды</b>", parse_mode="HTML")
        
        elif message.text == "📊 Мой кабинет":
            total_requests, total_stars, paid_stars = await get_user_stats(message.from_user.id)
            earned = round(paid_stars * RATE, 2)
            recent = await get_user_requests(message.from_user.id, 3)
            text = f"📊 <b>Твой личный кабинет</b>\n\n⭐ Продал: <b>{total_stars}</b> звёзд\n💰 Получил: <b>{earned} ₽</b>\n📋 Заявок: <b>{total_requests}</b>\n\n────────────────────\n<b>Последние:</b>\n"
            for r in recent:
                text += f"#{r[0]} — {r[1]}⭐ — {r[2]}\n"
            await message.answer(text, parse_mode="HTML")
        
        elif message.text == "💳 Мои реквизиты":
            saved = await get_user_payment(message.from_user.id)
            if saved:
                await message.answer(f"💳 <b>Сохранённые реквизиты:</b>\n\n<code>{saved}</code>", parse_mode="HTML")
            else:
                await message.answer("💳 У тебя пока нет сохранённых реквизитов.", parse_mode="HTML")
        
        elif message.text == "❓ Как это работает":
            await message.answer(
                "❓ <b>Как это работает</b>\n\n"
                "1. Нажми «💰 Продать звезды»\n"
                "2. Введи количество звёзд (минимум 2)\n"
                "3. Введи или выбери реквизиты\n"
                "4. Подтверди заявку\n"
                "5. Отправь звёзды реакцией на пост\n"
                "6. Нажми «Я отправил»\n"
                "7. Получи деньги после модерации",
                parse_mode="HTML"
            )
        
        elif message.text == "🛠 Техподдержка":
            await state.set_state(SellForm.waiting_for_support)
            await message.answer(
                f"🛠 <b>Техподдержка</b>\n\n"
                f"Опиши свою проблему одним сообщением.\n"
                f"Контакт: {SUPPORT_USERNAME}\n\n"
                f"Чтобы отменить — /cancel",
                parse_mode="HTML"
            )
        
        elif message.text == "📈 Курс":
            await message.answer(f"📈 <b>Курс:</b> 1 ⭐ = <b>{RATE} ₽</b>", parse_mode="HTML")
        
        elif message.text == "🧮 Калькулятор":
            await state.set_state(SellForm.waiting_for_calculator)
            await message.answer(
                "🧮 <b>Калькулятор</b>\n\n"
                "Введи количество звёзд, и я покажу сумму.\n"
                "Чтобы отменить — /cancel",
                parse_mode="HTML"
            )

    # ================== КАЛЬКУЛЯТОР ==================
    @dp.message(SellForm.waiting_for_calculator)
    async def calculator_process(message: Message, state: FSMContext):
        if message.text == "/cancel":
            await state.clear()
            await message.answer("✅ Калькулятор закрыт.", reply_markup=get_main_menu())
            return

        try:
            stars = int(message.text)
            if stars < 2:
                await message.answer("Минимум 2 звезды.")
                return
            total = round(stars * RATE, 2)
            await message.answer(
                f"🧮 <b>Расчёт:</b>\n\n"
                f"⭐ Звёзд: <b>{stars}</b>\n"
                f"💰 Получишь: <b>{total} ₽</b>\n"
                f"Курс: {RATE} ₽ за 1 ⭐",
                parse_mode="HTML"
            )
        except:
            await message.answer("Введи только число.")

    # ================== ПРОДАТЬ ЗВЁЗДЫ ==================
    @dp.message(SellForm.waiting_for_amount)
    async def process_amount(message: Message, state: FSMContext):
        if message.text == "/cancel":
            await state.clear()
            await message.answer("✅ Отменено.", reply_markup=get_main_menu())
            return

        try:
            amount = int(message.text)
            if amount < 2:
                await message.answer("❌ Минимум 2 звезды. Попробуй ещё раз.")
                return
            await state.update_data(stars=amount)
            await state.set_state(SellForm.waiting_for_payment)
            
            saved_payment = await get_user_payment(message.from_user.id)
            if saved_payment:
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Использовать сохранённые", callback_data="use_saved_payment")],
                    [InlineKeyboardButton(text="✏️ Ввести новые", callback_data="enter_new_payment")]
                ])
                await message.answer(f"💳 У тебя сохранены реквизиты:\n<code>{saved_payment}</code>", reply_markup=kb, parse_mode="HTML")
            else:
                await message.answer("💳 Введи реквизиты для выплаты:")
        except:
            await message.answer("Введи только число.")

    @dp.callback_query(F.data == "use_saved_payment")
    async def use_saved_payment(callback: CallbackQuery, state: FSMContext):
        saved_payment = await get_user_payment(callback.from_user.id)
        if saved_payment:
            await state.update_data(payment=saved_payment)
            data = await state.get_data()
            stars = data["stars"]
            total = round(stars * RATE, 2)
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Создать заявку", callback_data="confirm_sell")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
            ])
            await state.set_state(SellForm.waiting_for_confirm)
            await callback.message.edit_text(
                f"📋 <b>Проверь данные:</b>\n\n"
                f"⭐ Звёзд: <b>{stars}</b>\n"
                f"💰 Сумма: <b>{total} ₽</b>\n"
                f"💳 Реквизиты: <code>{saved_payment}</code>",
                reply_markup=kb, parse_mode="HTML"
            )
        await callback.answer()

    @dp.callback_query(F.data == "enter_new_payment")
    async def enter_new_payment(callback: CallbackQuery, state: FSMContext):
        await state.set_state(SellForm.waiting_for_payment)
        await callback.message.edit_text("💳 Введи новые реквизиты:")
        await callback.answer()

    @dp.message(SellForm.waiting_for_payment)
    async def process_payment(message: Message, state: FSMContext):
        if message.text == "/cancel":
            await state.clear()
            await message.answer("✅ Отменено.", reply_markup=get_main_menu())
            return

        payment = message.text.strip()
        await state.update_data(payment=payment)
        data = await state.get_data()
        stars = data["stars"]
        total = round(stars * RATE, 2)

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Создать заявку", callback_data="confirm_sell")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
        ])
        await state.set_state(SellForm.waiting_for_confirm)
        await message.answer(
            f"📋 <b>Проверь данные:</b>\n\n"
            f"⭐ Звёзд: <b>{stars}</b>\n"
            f"💰 Сумма: <b>{total} ₽</b>\n"
            f"💳 Реквизиты: <code>{payment}</code>",
            reply_markup=kb, parse_mode="HTML"
        )

    @dp.callback_query(F.data == "confirm_sell", SellForm.waiting_for_confirm)
    async def confirm_sell(callback: CallbackQuery, state: FSMContext):
        data = await state.get_data()
        req_id = await add_request(callback.from_user.id, callback.from_user.username, data["stars"], data["payment"])
        await state.clear()

        await callback.message.edit_text(
            f"✅ <b>Заявка #{req_id} создана!</b>\n\n"
            f"Отправь <b>{data['stars']} звёзд</b> на пост:\n{POST_LINK}\n\n"
            f"После отправки нажми кнопку ниже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚀 Я отправил звёзды", callback_data=f"sent_{req_id}")]
            ]), parse_mode="HTML"
        )

        try:
            await callback.bot.send_message(ADMIN_ID, f"🆕 Новая заявка #{req_id}")
        except:
            pass
        await callback.answer()

    @dp.callback_query(F.data.startswith("sent_"))
    async def user_sent_stars(callback: CallbackQuery):
        req_id = int(callback.data.split("_")[1])
        await update_status(req_id, "sent")
        await callback.message.edit_text("✅ Спасибо! Заявка отправлена на модерацию.\nОжидай выплату.")

        await asyncio.sleep(1800)
        try:
            await callback.bot.send_message(callback.from_user.id, 
                f"⏰ Напоминание: Заявка #{req_id} всё ещё в обработке.\n"
                f"Если нужно — напиши в техподдержку.")
        except:
            pass

        try:
            await callback.bot.send_message(ADMIN_ID, f"📤 Пользователь подтвердил отправку #{req_id}")
        except:
            pass
        await callback.answer()

    # ================== ТЕХПОДДЕРЖКА ==================
    @dp.message(SellForm.waiting_for_support)
    async def support_message(message: Message, state: FSMContext):
        if message.text == "/cancel":
            await state.clear()
            await message.answer("✅ Обращение отменено.", reply_markup=get_main_menu())
            return

        try:
            await message.bot.send_message(
                ADMIN_ID,
                f"🛠 <b>Обращение в техподдержку</b>\n\n"
                f"От: @{message.from_user.username}\n\n"
                f"{message.text}"
            )
            await message.answer(
                f"✅ <b>Сообщение отправлено!</b>\n\n"
                f"Мы ответим скоро.\n"
                f"Контакт: {SUPPORT_USERNAME}",
                reply_markup=get_main_menu()
            )
        except:
            await message.answer("❌ Ошибка. Попробуй позже.")
        await state.clear()

    # ================== АДМИН ==================
    @dp.message(Command("pending"), F.from_user.id == ADMIN_ID)
    async def admin_pending(message: Message):
        requests = await get_pending_requests()
        if not requests:
            await message.answer("✅ Нет активных заявок.")
            return
        text = "📋 <b>Активные заявки</b>\n\n"
        for req in requests:
            req_id, uid, uname, stars, pay, status, created = req
            text += f"#{req_id} | @{uname} | {stars}⭐ | {status}\n💳 {pay}\n\n"
        await message.answer(text, parse_mode="HTML")

    @dp.message(Command("setrate"), F.from_user.id == ADMIN_ID)
    async def set_rate(message: Message):
        global RATE
        try:
            new_rate = float(message.text.split()[1])
            RATE = new_rate
            await message.answer(f"✅ Курс изменён на <b>{RATE} ₽</b>")
        except:
            await message.answer("Используй: /setrate 0.95")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
