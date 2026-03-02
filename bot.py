import asyncio
import logging
import aiosqlite
import re
from typing import Dict, Optional, Tuple
from datetime import datetime

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# ================ НАСТРОЙКА ЛОГИРОВАНИЯ ================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ================ КОНФИГУРАЦИЯ ================
BOT_TOKEN = "8646923068:AAEdgYd6GdqifXBEg5gibYv1_0yglDLYv60"  # Замените на свой токен
PASSWORD = "барбер123"  # Пароль для авторизации
AUTHORIZED_USERS = set()  # Множество авторизованных пользователей

# Филиалы
BRANCHES = ["Щелковская", "Измайловская", "Первомайская"]

# Порог для отображения в "Нужно купить"
LOW_STOCK_THRESHOLD = 5

# ================ ДАННЫЕ О МАТЕРИАЛАХ ================
MATERIALS = [
    {"id": 1, "name": "Туалетная бумага", "category": "Туалет", "unit": "упаковка"},
    {"id": 2, "name": "Освежители воздуха", "category": "Туалет", "unit": "шт"},
    {"id": 3, "name": "Средство для полов", "category": "Уборка", "unit": "шт"},
    {"id": 4, "name": "Средство для стёкол", "category": "Уборка", "unit": "шт"},
    {"id": 5, "name": "Средство для раковины/туалета", "category": "Уборка", "unit": "шт"},
    {"id": 6, "name": "Тряпки", "category": "Уборка", "unit": "шт"},
    {"id": 7, "name": "Стаканчики", "category": "Напитки", "unit": "упаковка"},
    {"id": 8, "name": "Вода", "category": "Напитки", "unit": "шт"},
    {"id": 9, "name": "Лезвия", "category": "Для мастеров", "unit": "упаковка"},
    {"id": 10, "name": "Конфеты", "category": "Для админа", "unit": "упаковка"},
    {"id": 11, "name": "Мята", "category": "Для админа", "unit": "шт"},
    {"id": 12, "name": "Одноразовые полотенца", "category": "Для мастеров", "unit": "упаковка"},
    {"id": 13, "name": "Перчатки", "category": "Для мастеров", "unit": "упаковка"},
    {"id": 14, "name": "Ватные диски", "category": "Для мастеров", "unit": "упаковка"},
    {"id": 15, "name": "Ватные палочки", "category": "Для мастеров", "unit": "упаковка"},
    {"id": 16, "name": "Шпатели для воска", "category": "Доп услуги", "unit": "шт"},
    {"id": 17, "name": "Воск", "category": "Доп услуги", "unit": "упаковка"},
    {"id": 18, "name": "Воротники", "category": "Для мастеров", "unit": "упаковка"},
]

# Словарь для быстрого доступа по имени
MATERIALS_BY_NAME = {m["name"]: m for m in MATERIALS}
MATERIALS_BY_ID = {m["id"]: m for m in MATERIALS}

# ================ FSM СОСТОЯНИЯ ================
class UserStates(StatesGroup):
    """Состояния пользователя"""
    selecting_branch = State()  # Выбор филиала
    branch_selected = State()   # Филиал выбран, работаем

# ================ ИНИЦИАЛИЗАЦИЯ БОТА ================
# Исправленная инициализация для новой версии aiogram
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# ================ РАБОТА С БАЗОЙ ДАННЫХ ================
async def init_db():
    """Инициализация базы данных"""
    async with aiosqlite.connect('materials.db') as db:
        # Создаём таблицу для остатков
        await db.execute('''
            CREATE TABLE IF NOT EXISTS stock (
                location TEXT,
                material_id INTEGER,
                quantity INTEGER DEFAULT 0,
                min_stock INTEGER DEFAULT 5,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (location, material_id)
            )
        ''')
        
        # Создаём таблицу для истории операций
        await db.execute('''
            CREATE TABLE IF NOT EXISTS operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                location TEXT,
                material_id INTEGER,
                operation_type TEXT,
                quantity INTEGER,
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Заполняем начальными данными, если таблица пуста
        for location in BRANCHES:
            for material in MATERIALS:
                await db.execute('''
                    INSERT OR IGNORE INTO stock (location, material_id, quantity, min_stock)
                    VALUES (?, ?, 0, 5)
                ''', (location, material["id"]))
        
        await db.commit()
        logger.info("База данных инициализирована")

async def get_stock(location: str, material_id: int = None) -> Dict:
    """Получить остатки по локации"""
    async with aiosqlite.connect('materials.db') as db:
        if material_id:
            async with db.execute(
                'SELECT quantity FROM stock WHERE location = ? AND material_id = ?',
                (location, material_id)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0
        else:
            async with db.execute(
                'SELECT material_id, quantity FROM stock WHERE location = ?',
                (location,)
            ) as cursor:
                rows = await cursor.fetchall()
                return {row[0]: row[1] for row in rows}

async def update_stock(location: str, material_id: int, change: int, user_id: int, operation: str):
    """Обновить остатки и записать операцию"""
    async with aiosqlite.connect('materials.db') as db:
        # Получаем текущее количество
        async with db.execute(
            'SELECT quantity FROM stock WHERE location = ? AND material_id = ?',
            (location, material_id)
        ) as cursor:
            row = await cursor.fetchone()
            current = row[0] if row else 0
        
        new_quantity = max(0, current + change)  # Не даём уйти в минус
        
        # Обновляем остаток
        await db.execute('''
            UPDATE stock 
            SET quantity = ?, updated_at = CURRENT_TIMESTAMP
            WHERE location = ? AND material_id = ?
        ''', (new_quantity, location, material_id))
        
        # Записываем операцию
        await db.execute('''
            INSERT INTO operations (location, material_id, operation_type, quantity, user_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (location, material_id, operation, abs(change), user_id))
        
        await db.commit()
        return new_quantity

async def get_low_stock(location: str) -> list:
    """Получить материалы с низким остатком"""
    async with aiosqlite.connect('materials.db') as db:
        async with db.execute('''
            SELECT material_id, quantity FROM stock 
            WHERE location = ? AND quantity < ?
        ''', (location, LOW_STOCK_THRESHOLD)) as cursor:
            rows = await cursor.fetchall()
            return rows

# ================ КЛАВИАТУРЫ ================
def get_main_keyboard() -> ReplyKeyboardMarkup:
    """
    Главная клавиатура (вертикальный столбик)
    Кнопки:
    📦 Склад
    🛒 Нужно купить
    📍 Точка
    """
    builder = ReplyKeyboardBuilder()
    
    # Добавляем кнопки вертикально (каждая на новой строке)
    builder.row(KeyboardButton(text="📦 Склад"))
    builder.row(KeyboardButton(text="🛒 Нужно купить"))
    builder.row(KeyboardButton(text="📍 Точка"))
    
    return builder.as_markup(
        resize_keyboard=True,
        is_persistent=True,      # Клавиатура всегда видна
        one_time_keyboard=False  # Не скрывается после нажатия
    )

def get_branches_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавиатура выбора филиала
    """
    builder = ReplyKeyboardBuilder()
    
    for branch in BRANCHES:
        builder.row(KeyboardButton(text=branch))
    
    builder.row(KeyboardButton(text="◀️ Назад"))
    
    return builder.as_markup(
        resize_keyboard=True,
        is_persistent=True,
        one_time_keyboard=False
    )

# ================ ПРОВЕРКА АВТОРИЗАЦИИ ================
def is_authorized(user_id: int) -> bool:
    """Проверка, авторизован ли пользователь"""
    return user_id in AUTHORIZED_USERS

# ================ ХЭНДЛЕРЫ ================
@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    
    if is_authorized(user_id):
        await message.answer(
            "👋 <b>Добро пожаловать в систему учёта расходных материалов!</b>\n\n"
            "Выберите действие с помощью кнопок ниже ⬇️\n\n"
            "📦 <b>Склад</b> — посмотреть все материалы\n"
            "🛒 <b>Нужно купить</b> — что заканчивается\n"
            "📍 <b>Точка</b> — выбрать филиал",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.answer(
            "🔒 <b>Требуется авторизация</b>\n\n"
            "Введите пароль: /login <пароль>"
        )

@router.message(Command("login"))
async def cmd_login(message: Message):
    """Авторизация по паролю"""
    user_id = message.from_user.id
    args = message.text.split()
    
    if len(args) < 2:
        await message.answer("❌ Используйте: /login пароль")
        return
    
    if args[1] == PASSWORD:
        AUTHORIZED_USERS.add(user_id)
        await message.answer(
            "✅ <b>Авторизация успешна!</b>\n\n"
            "Отправьте /start для начала работы"
        )
    else:
        await message.answer("❌ Неверный пароль")

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Сброс состояния"""
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("👌 Нет активного действия")
        return
    
    await state.clear()
    await message.answer(
        "✅ Действие отменено",
        reply_markup=get_main_keyboard()
    )

@router.message(F.text == "📍 Точка")
async def cmd_branch(message: Message, state: FSMContext):
    """Выбор филиала"""
    if not is_authorized(message.from_user.id):
        await message.answer("🔒 Сначала авторизуйтесь: /login пароль")
        return
    
    await state.set_state(UserStates.selecting_branch)
    await message.answer(
        "📍 <b>Выберите филиал:</b>",
        reply_markup=get_branches_keyboard()
    )

@router.message(UserStates.selecting_branch, F.text.in_(BRANCHES))
async def branch_selected(message: Message, state: FSMContext):
    """Филиал выбран"""
    branch = message.text
    
    # Сохраняем выбранный филиал
    await state.update_data(selected_branch=branch)
    await state.set_state(UserStates.branch_selected)
    
    await message.answer(
        f"✅ Выбран филиал: <b>{branch}</b>\n\n"
        f"Теперь вы можете:\n"
        f"📦 Склад — посмотреть остатки на {branch}\n"
        f"🛒 Нужно купить — что заканчивается на {branch}\n\n"
        f"Или написать:\n"
        f"<code>приход Материал 10</code> — добавить\n"
        f"<code>расход Материал 3</code> — списать",
        reply_markup=get_main_keyboard()
    )

@router.message(UserStates.selecting_branch, F.text == "◀️ Назад")
async def back_from_branch_selection(message: Message, state: FSMContext):
    """Назад из выбора филиала"""
    await state.clear()
    await message.answer(
        "👋 Возврат в главное меню",
        reply_markup=get_main_keyboard()
    )

@router.message(UserStates.selecting_branch)
async def invalid_branch(message: Message):
    """Неверный выбор филиала"""
    await message.answer(
        "❌ Пожалуйста, выберите филиал из списка кнопок",
        reply_markup=get_branches_keyboard()
    )

@router.message(F.text == "📦 Склад")
async def cmd_sklad(message: Message, state: FSMContext):
    """Показать все материалы на выбранной точке"""
    if not is_authorized(message.from_user.id):
        await message.answer("🔒 Сначала авторизуйтесь: /login пароль")
        return
    
    # Получаем состояние
    data = await state.get_data()
    branch = data.get("selected_branch")
    
    if not branch:
        await message.answer(
            "❌ Сначала выберите филиал через меню «📍 Точка»"
        )
        return
    
    # Получаем остатки
    stock = await get_stock(branch)
    
    # Формируем сообщение
    text = f"📦 <b>Склад — {branch}</b>\n\n"
    
    for material in MATERIALS:
        quantity = stock.get(material["id"], 0)
        status = "✅" if quantity >= LOW_STOCK_THRESHOLD else "⚠️"
        text += f"{status} <b>{material['name']}</b>: {quantity} {material['unit']}\n"
    
    await message.answer(text, reply_markup=get_main_keyboard())

@router.message(F.text == "🛒 Нужно купить")
async def cmd_nuzhno(message: Message, state: FSMContext):
    """Показать материалы, которые заканчиваются"""
    if not is_authorized(message.from_user.id):
        await message.answer("🔒 Сначала авторизуйтесь: /login пароль")
        return
    
    # Получаем состояние
    data = await state.get_data()
    branch = data.get("selected_branch")
    
    if not branch:
        await message.answer(
            "❌ Сначала выберите филиал через меню «📍 Точка»"
        )
        return
    
    # Получаем материалы с низким остатком
    low_stock = await get_low_stock(branch)
    
    if not low_stock:
        await message.answer(
            f"✅ На <b>{branch}</b> все материалы в достатке!",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Формируем сообщение
    text = f"🛒 <b>Нужно купить — {branch}</b>\n\n"
    
    for material_id, quantity in low_stock:
        material = MATERIALS_BY_ID[material_id]
        text += f"⚠️ <b>{material['name']}</b>: осталось {quantity} {material['unit']}\n"
        text += f"   Нужно докупить минимум {LOW_STOCK_THRESHOLD - quantity} {material['unit']}\n\n"
    
    await message.answer(text, reply_markup=get_main_keyboard())

@router.message(F.text.regexp(r'^(приход|расход)\s+(.+?)\s+(\d+)$'))
async def process_operation(message: Message, state: FSMContext):
    """
    Обработка операций прихода/расхода
    Формат: приход Материал 10
            расход Перчатки 3
    """
    if not is_authorized(message.from_user.id):
        await message.answer("🔒 Сначала авторизуйтесь: /login пароль")
        return
    
    # Получаем состояние
    data = await state.get_data()
    branch = data.get("selected_branch")
    
    if not branch:
        await message.answer(
            "❌ Сначала выберите филиал через меню «📍 Точка»"
        )
        return
    
    # Парсим сообщение
    match = re.match(r'^(приход|расход)\s+(.+?)\s+(\d+)$', message.text)
    if not match:
        return
    
    operation = match.group(1)  # приход или расход
    material_name = match.group(2).strip()
    quantity = int(match.group(3))
    
    # Ищем материал
    material = None
    for m in MATERIALS:
        if m["name"].lower() == material_name.lower() or material_name.lower() in m["name"].lower():
            material = m
            break
    
    if not material:
        await message.answer(
            f"❌ Материал «{material_name}» не найден.\n\n"
            f"Проверьте название или используйте /sklad для просмотра списка"
        )
        return
    
    # Обновляем остатки
    change = quantity if operation == "приход" else -quantity
    new_quantity = await update_stock(
        branch, material["id"], change, 
        message.from_user.id, operation
    )
    
    await message.answer(
        f"✅ <b>Операция выполнена!</b>\n\n"
        f"📍 {branch}\n"
        f"📦 {material['name']}\n"
        f"{'➕' if operation == 'приход' else '➖'} {operation}: {quantity} {material['unit']}\n"
        f"💰 Новый остаток: {new_quantity} {material['unit']}",
        reply_markup=get_main_keyboard()
    )
    
    # Проверяем, не упал ли остаток ниже порога
    if new_quantity < LOW_STOCK_THRESHOLD:
        await message.answer(
            f"⚠️ Внимание! {material['name']} заканчивается!\n"
            f"Осталось: {new_quantity} {material['unit']}"
        )

@router.message()
async def handle_unknown(message: Message, state: FSMContext):
    """Обработка неизвестных сообщений"""
    if not is_authorized(message.from_user.id):
        await message.answer("🔒 Сначала авторизуйтесь: /login пароль")
        return
    
    await message.answer(
        "❌ Я вас не понял.\n\n"
        "Используйте кнопки ниже или команды:\n"
        "/start — главное меню\n"
        "/cancel — отменить текущее действие",
        reply_markup=get_main_keyboard()
    )

# ================ ЗАПУСК БОТА ================
async def main():
    """Главная функция запуска"""
    print("🚀 Запуск бота...")
    
    # Инициализируем базу данных
    await init_db()
    
    print(f"✅ Бот готов к работе!")
    print(f"📱 Username: @blackbone_sklad_bot")
    print("📊 Для остановки нажмите Ctrl+C\n")
    
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
