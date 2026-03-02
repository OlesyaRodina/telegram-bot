import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import asyncio
import json
from datetime import datetime

# ================ ДАННЫЕ ================
TOKEN = "8646923068:AAFC_GwjFNWMCgPid7j8OZzqWZqD-UU6wNU"  # Ваш токен
PASSWORD = "барбер123"
OWNER_ID = None 
authorized_users = set()
DATA_FILE = "materials.json"

ALERT_USER_ID = 1007254983

# Материалы
materials = {
    1: {'name': 'Туалетная бумага', 'category': 'Туалет', 'unit': 'упаковка', 'quantity': 1, 'min_stock': 1},
    2: {'name': 'Освежители воздуха', 'category': 'Туалет', 'unit': 'шт', 'quantity': 1, 'min_stock': 2},
    3: {'name': 'Средство для полов', 'category': 'Уборка', 'unit': 'шт', 'quantity': 3, 'min_stock': 1},
    4: {'name': 'Средство для стекол', 'category': 'Уборка', 'unit': 'шт', 'quantity': 1, 'min_stock': 1},
    5: {'name': 'Средство для раковины/туалета', 'category': 'Уборка', 'unit': 'шт', 'quantity': 0, 'min_stock': 1},
    6: {'name': 'Тряпки', 'category': 'Уборка', 'unit': 'шт', 'quantity': 2, 'min_stock': 1},
    7: {'name': 'Стаканчики', 'category': 'Напитки', 'unit': 'упаковка', 'quantity': 2, 'min_stock': 2},
    8: {'name': 'Вода', 'category': 'Напитки', 'unit': 'шт', 'quantity': 1, 'min_stock': 1},
    9: {'name': 'Лезвия', 'category': 'Для мастеров', 'unit': 'упаковка', 'quantity': 1, 'min_stock': 2},
    10: {'name': 'Конфеты', 'category': 'Для админа', 'unit': 'упаковка', 'quantity': 1, 'min_stock': 1},
    11: {'name': 'Мята', 'category': 'Для админа', 'unit': 'шт', 'quantity': 5, 'min_stock': 2},
    12: {'name': 'Одноразовые полотенца', 'category': 'Для мастеров', 'unit': 'упаковка', 'quantity': 2, 'min_stock': 2},
    13: {'name': 'Перчатки', 'category': 'Для мастеров', 'unit': 'упаковка', 'quantity': 1, 'min_stock': 2},
    14: {'name': 'Ватные диски', 'category': 'Для мастеров', 'unit': 'упаковка', 'quantity': 1, 'min_stock': 2},
    15: {'name': 'Ватные палочки', 'category': 'Для мастеров', 'unit': 'упаковка', 'quantity': 3, 'min_stock': 2},
    16: {'name': 'Шпатели для воска', 'category': 'Доп услуги', 'unit': 'шт', 'quantity': 15, 'min_stock': 20},
    17: {'name': 'Воск', 'category': 'Доп услуги', 'unit': 'упаковка', 'quantity': 1, 'min_stock': 1},
    18: {'name': 'Воротники', 'category': 'Для мастеров', 'unit': 'упаковка', 'quantity': 4, 'min_stock': 4},
}

# Загрузка данных
def load_materials():
    global materials
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                # Преобразуем ключи обратно в int
                materials = {int(k): v for k, v in loaded.items()}
                print("✅ Данные загружены")
    except:
        print("📁 Создаем новые данные")
        save_materials()

def save_materials():
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(materials, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

load_materials()

# ================ ФУНКЦИИ ================
def get_categories():
    cats = set()
    for item in materials.values():
        cats.add(item['category'])
    return sorted(list(cats))

def check_low_stock():
    low = []
    for id, item in materials.items():
        if item['quantity'] <= item['min_stock']:
            low.append((id, f"🔴 {item['name']}: {item['quantity']} {item['unit']}"))
    return low

async def send_alert(context):
    """Отправка предупреждения владельцу о мало материалов"""
    if not ALERT_USER_ID:
        return
    
    low_items = check_low_stock()
    if low_items:
        text = "⚠️ **ВНИМАНИЕ! Закончились материалы:**\n\n"
        for _, msg in low_items:
            text += msg + "\n"
        try:
            await context.bot.send_message(chat_id=ALERT_USER_ID, text=text)
        except:
            pass

# ================ ОБРАБОТЧИКИ ================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # Главное меню с кнопками
    keyboard = [
        [InlineKeyboardButton("📦 Посмотреть материалы", callback_data="main_menu")],
        [InlineKeyboardButton("➕ Добавить материалы", callback_data="add_menu")],
        [InlineKeyboardButton("➖ Списать материалы", callback_data="remove_menu")],
        [InlineKeyboardButton("⚠️ Проверить остатки", callback_data="check_low")]
    ]
    
    if user_id in authorized_users:
        await update.message.reply_text(
            f"👋 Привет, {user.first_name}!\nВыбери действие:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text("🔒 Введите пароль: /login пароль")

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global OWNER_ID, ALERT_USER_ID
    
    user_id = update.effective_user.id
    
    try:
        if context.args[0] == PASSWORD:
            authorized_users.add(user_id)
            
            # Запоминаем владельца
            if OWNER_ID is None:
                OWNER_ID = user_id
                ALERT_USER_ID = user_id
                await update.message.reply_text("✅ Вы назначены владельцем бота!")
            
            await update.message.reply_text(
                "✅ Вход выполнен!\n"
                "Используйте /start для главного меню"
            )
            
            # Проверяем остатки при входе
            await send_alert(context)
        else:
            await update.message.reply_text("❌ Неверный пароль")
    except:
        await update.message.reply_text("❌ Используйте: /login пароль")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if user_id not in authorized_users:
        await query.edit_message_text("🔒 Нет доступа")
        return
    
    data = query.data
    
    # Главное меню
    if data == "main_menu":
        keyboard = []
        for cat in get_categories():
            keyboard.append([InlineKeyboardButton(cat, callback_data=f"cat_{cat}")])
        keyboard.append([InlineKeyboardButton("📦 Всё", callback_data="all")])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")])
        
        await query.edit_message_text(
            "📋 Выберите категорию:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # Меню добавления
    elif data == "add_menu":
        keyboard = []
        for id, item in materials.items():
            keyboard.append([InlineKeyboardButton(
                f"+ {item['name']} ({item['quantity']} {item['unit']})", 
                callback_data=f"add_{id}"
            )])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")])
        
        await query.edit_message_text(
            "➕ Выберите материал для добавления:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # Меню списания
    elif data == "remove_menu":
        keyboard = []
        for id, item in materials.items():
            if item['quantity'] > 0:
                keyboard.append([InlineKeyboardButton(
                    f"- {item['name']} ({item['quantity']} {item['unit']})", 
                    callback_data=f"remove_{id}"
                )])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")])
        
        await query.edit_message_text(
            "➖ Выберите материал для списания:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # Добавление количества
    elif data.startswith("add_"):
        item_id = int(data.split("_")[1])
        item = materials[item_id]
        
        keyboard = [
            [InlineKeyboardButton("➕ 1", callback_data=f"addq_{item_id}_1")],
            [InlineKeyboardButton("➕ 2", callback_data=f"addq_{item_id}_2")],
            [InlineKeyboardButton("➕ 5", callback_data=f"addq_{item_id}_5")],
            [InlineKeyboardButton("➕ 10", callback_data=f"addq_{item_id}_10")],
            [InlineKeyboardButton("◀️ Назад", callback_data="add_menu")]
        ]
        
        await query.edit_message_text(
            f"📦 {item['name']}\n"
            f"Текущее количество: {item['quantity']} {item['unit']}\n"
            f"Минимум: {item['min_stock']} {item['unit']}\n\n"
            f"Сколько добавить?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # Списание количества
    elif data.startswith("remove_"):
        item_id = int(data.split("_")[1])
        item = materials[item_id]
        
        max_amount = min(item['quantity'], 10)  # Не больше чем есть, и не больше 10
        keyboard = []
        row = []
        for i in range(1, max_amount + 1):
            row.append(InlineKeyboardButton(f"- {i}", callback_data=f"removeq_{item_id}_{i}"))
            if len(row) == 3:  # По 3 кнопки в ряд
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="remove_menu")])
        
        await query.edit_message_text(
            f"📦 {item['name']}\n"
            f"Текущее количество: {item['quantity']} {item['unit']}\n"
            f"Минимум: {item['min_stock']} {item['unit']}\n\n"
            f"Сколько списать?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # Подтверждение добавления
    elif data.startswith("addq_"):
        parts = data.split("_")
        item_id = int(parts[1])
        amount = int(parts[2])
        
        item = materials[item_id]
        old_qty = item['quantity']
        item['quantity'] += amount
        save_materials()
        
        await query.edit_message_text(
            f"✅ Добавлено: +{amount} {item['unit']}\n"
            f"📦 {item['name']}\n"
            f"Было: {old_qty} {item['unit']}\n"
            f"Стало: {item['quantity']} {item['unit']}"
        )
        
        # Проверяем остатки после добавления
        await asyncio.sleep(1)
        await send_alert(context)
    
    # Подтверждение списания
    elif data.startswith("removeq_"):
        parts = data.split("_")
        item_id = int(parts[1])
        amount = int(parts[2])
        
        item = materials[item_id]
        if item['quantity'] >= amount:
            old_qty = item['quantity']
            item['quantity'] -= amount
            save_materials()
            
            await query.edit_message_text(
                f"✅ Списано: -{amount} {item['unit']}\n"
                f"📦 {item['name']}\n"
                f"Было: {old_qty} {item['unit']}\n"
                f"Стало: {item['quantity']} {item['unit']}"
            )
            
            # Проверяем остатки после списания
            await asyncio.sleep(1)
            await send_alert(context)
    
    # Просмотр категории
    elif data.startswith("cat_"):
        cat = data[4:]
        text = f"📁 {cat}:\n\n"
        for id, item in materials.items():
            if item['category'] == cat:
                status = "✅" if item['quantity'] > item['min_stock'] else "⚠️"
                text += f"{status} {item['name']}: {item['quantity']} {item['unit']}\n"
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # Всё
    elif data == "all":
        text = "📋 Все материалы:\n\n"
        for id, item in materials.items():
            status = "✅" if item['quantity'] > item['min_stock'] else "⚠️"
            text += f"{status} {item['name']}: {item['quantity']} {item['unit']}\n"
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # Проверка остатков
    elif data == "check_low":
        low = check_low_stock()
        if low:
            text = "⚠️ Мало материалов:\n\n"
            for _, msg in low:
                text += msg + "\n"
        else:
            text = "✅ Все материалы в норме!"
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # Назад в главное меню
    elif data == "back_to_main":
        keyboard = [
            [InlineKeyboardButton("📦 Посмотреть материалы", callback_data="main_menu")],
            [InlineKeyboardButton("➕ Добавить материалы", callback_data="add_menu")],
            [InlineKeyboardButton("➖ Списать материалы", callback_data="remove_menu")],
            [InlineKeyboardButton("⚠️ Проверить остатки", callback_data="check_low")]
        ]
        await query.edit_message_text(
            "📋 Главное меню:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ================ ЗАПУСК ================
async def main():
    print("Запуск бота...")
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CallbackQueryHandler(button_click))
    
    print("Бот работает! Идите в Telegram: @blackbone_sklad_bot")
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    try:
        while True:
            await asyncio.sleep(3600)
            # Проверяем остатки каждый час
            await send_alert(app)
    except:
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())


