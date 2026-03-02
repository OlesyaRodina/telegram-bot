import os
import requests
import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import asyncio

# ================ ДАННЫЕ ================
TOKEN = "8646923068:AAFC_GwjFNWMCgPid7j8OZzqWZqD-UU6wNU"  # Ваш токен
PASSWORD = "барбер123"
authorized_users = set()
DATA_FILE = "materials_data.csv"

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

def get_categories():
    cats = set()
    for item in materials.values():
        cats.add(item['category'])
    return sorted(list(cats))

def check_low_stock():
    low = []
    for item in materials.values():
        if item['quantity'] <= item['min_stock']:
            low.append(f"🔴 {item['name']}: {item['quantity']} {item['unit']}")
    return low

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in authorized_users:
        await show_menu(update, context)
    else:
        await update.message.reply_text("🔒 Введите пароль: /login пароль")

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.args[0] == PASSWORD:
            authorized_users.add(update.effective_user.id)
            await update.message.reply_text("✅ Вход выполнен! Используйте /menu")
        else:
            await update.message.reply_text("❌ Неверный пароль")
    except:
        await update.message.reply_text("❌ Используйте: /login пароль")

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in authorized_users:
        await update.message.reply_text("🔒 Сначала войдите: /login пароль")
        return
    
    keyboard = []
    for cat in get_categories():
        keyboard.append([InlineKeyboardButton(cat, callback_data=f"cat_{cat}")])
    
    keyboard.append([InlineKeyboardButton("📦 Всё", callback_data="all")])
    keyboard.append([InlineKeyboardButton("⚠️ Мало", callback_data="low")])
    
    await update.message.reply_text("Меню:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in authorized_users:
        await query.edit_message_text("🔒 Нет доступа")
        return
    
    data = query.data
    
    if data.startswith("cat_"):
        cat = data[4:]
        text = f"📁 {cat}:\n\n"
        for id, item in materials.items():
            if item['category'] == cat:
                text += f"{id}. {item['name']}: {item['quantity']} {item['unit']}\n"
        await query.edit_message_text(text)
    
    elif data == "all":
        text = "📋 Всё:\n\n"
        for id, item in materials.items():
            text += f"{id}. {item['name']}: {item['quantity']} {item['unit']}\n"
        await query.edit_message_text(text)
    
    elif data == "low":
        low = check_low_stock()
        if low:
            await query.edit_message_text("⚠️ Мало:\n\n" + "\n".join(low))
        else:
            await query.edit_message_text("✅ Всё хорошо")

async def main():
    print("Запуск бота...")
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CallbackQueryHandler(button_click))
    
    print("Бот работает! Идите в Telegram: @blackbone_sklad_bot")
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    try:
        while True:
            await asyncio.sleep(3600)
    except:
        await app.stop()
if __name__ == "__main__":
    asyncio.run(main())
