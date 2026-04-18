import os
import json
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- КОНФИГУРАЦИЯ ---
# ВСТАВЬТЕ СЮДА ВАШ ТОКЕН ОТ @BotFather
TOKEN = "ВАШ_ТОКЕН_ОТ_BOTFATHER" 

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config', 'world.json')
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- ЗАГРУЗКА МИРА ---
def load_world():
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки мира: {e}")
        return None

world_data = load_world()
if not world_data:
    raise Exception("Не удалось загрузить world.json. Проверьте путь и формат файла.")

# Хранилище состояний игроков: {user_id: {...}}
players = {}

def get_player_state(user_id):
    if user_id not in players:
        start_data = world_data['player_start']
        players[user_id] = {
            'name': start_data['name'],
            'health': start_data['health'],
            'location_id': start_data['location_id'],
            'skills': start_data['skills'].copy(),
            'inventory': start_data['inventory'].copy(),
            'history': [] 
        }
    return players[user_id]

def get_location(location_id):
    for loc in world_data['locations']:
        if loc['id'] == location_id:
            return loc
    return None

def get_npcs_in_location(location_id):
    return [npc for npc in world_data['npcs'] if npc['location_id'] == location_id]

def get_shop_for_location(location_id):
    # Ищем лавки, привязанные к локации через NPC или напрямую (упрощенно по имени локации или NPC)
    shops = []
    loc = get_location(location_id)
    if not loc:
        return []
    
    # Проверяем магазин торговца
    if 'merchant' in world_data.get('shop', {}):
        # Находим торговца в этой локации
        merchant_npc = next((n for n in world_data['npcs'] if n['id'] == 'merchant' and n['location_id'] == location_id), None)
        if merchant_npc:
            shops.append({'type': 'merchant', 'data': world_data['shop']['merchant']})
            
    # Проверяем кузницу
    if 'blacksmith' in world_data.get('shop', {}):
        blacksmith_npc = next((n for n in world_data['npcs'] if n['id'] == 'blacksmith' and n['location_id'] == location_id), None)
        if blacksmith_npc:
            shops.append({'type': 'blacksmith', 'data': world_data['shop']['blacksmith']})
            
    # Проверяем храм
    if 'priest' in world_data.get('shop', {}):
        priest_npc = next((n for n in world_data['npcs'] if n['id'] == 'priest' and n['location_id'] == location_id), None)
        if priest_npc:
            shops.append({'type': 'priest', 'data': world_data['shop']['priest']})
            
    return shops

# --- LLM ИНТЕГРАЦИЯ (GROQ) ---
def ask_llm(prompt, system_context=""):
    api_key = world_data.get('api_key')
    model = world_data.get('llm_model', 'llama3-70b-8192')
    
    if not api_key:
        return "Ошибка: API ключ не найден в конфигурации."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    messages = [
        {"role": "system", "content": system_context or "Ты мастер подземелий в средневековом фэнтези мире. Отвечай кратко, атмосферно и на русском языке."},
        {"role": "user", "content": prompt}
    ]

    data = {
        "model": model,
        "messages": messages,
        "max_tokens": 300,
        "temperature": 0.7
    }

    try:
        response = requests.post(GROQ_API_URL, json=data, headers=headers, timeout=15)
        
        # ВАЖНО: Печатаем полный ответ ошибки в консоль для отладки
        if response.status_code != 200:
            logger.error(f"Groq API Error {response.status_code}")
            logger.error(f"RESPONSE BODY: {response.text}") # <-- Вот здесь будет точная причина!
            return f"(Ошибка магии: {response.status_code}. См. консоль.)"
            
        result = response.json()
        return result['choices'][0]['message']['content']
    except Exception as e:
        logger.error(f"LLM Connection Error: {e}")
        return f"(Магия дала сбой... Ошибка соединения: {str(e)})"

# --- ГЕНЕРАЦИЯ КЛАВИАТУРЫ ---
def build_keyboard(player, mode='main'):
    keyboard = []
    loc = get_location(player['location_id'])
    if not loc:
        return InlineKeyboardMarkup([])

    if mode == 'main':
        # Кнопки перемещения
        move_row = []
        for adj_id in loc['adjacent_location_ids']:
            adj_loc = get_location(adj_id)
            if adj_loc:
                # Эмодзи для направлений можно добавить по желанию
                move_row.append(InlineKeyboardButton(f"🚶‍♂️ {adj_loc['name']}", callback_data=f"go_{adj_id}"))
        
        if move_row:
            # Разбиваем на строки по 1-2 кнопки, если много
            for i in range(0, len(move_row), 2):
                keyboard.append(move_row[i:i+2])

        # Кнопки действий
        action_row = [
            InlineKeyboardButton("👀 Осмотреться", callback_data="action_look"),
            InlineKeyboardButton("🎒 Инвентарь", callback_data="action_inv"),
            InlineKeyboardButton("📊 Статус", callback_data="action_status")
        ]
        keyboard.append(action_row)

        # Кнопки NPC (Разговор)
        npcs = get_npcs_in_location(loc['id'])
        if npcs:
            keyboard.append([InlineKeyboardButton("💬 Говорить с NPC", callback_data="menu_npcs")])
        
        # Кнопки Торговли
        shops = get_shop_for_location(loc['id'])
        if shops:
            keyboard.append([InlineKeyboardButton("⚖️ Торговля / Услуги", callback_data="menu_shops")])

    elif mode == 'npcs':
        npcs = get_npcs_in_location(loc['id'])
        for npc in npcs:
            keyboard.append([InlineKeyboardButton(f"🗣️ {npc['name']}", callback_data=f"talk_{npc['id']}")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_main")])

    elif mode == 'shops':
        shops = get_shop_for_location(loc['id'])
        for shop in shops:
            name = shop['data']['name']
            s_type = shop['type']
            keyboard.append([InlineKeyboardButton(f"🛒 {name}", callback_data=f"shop_{s_type}")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_main")])
    
    elif mode == 'shop_items':
        shop_type = getattr(build_keyboard, 'current_shop_type', None)
        if shop_type:
            # Здесь можно вывести список товаров, но для простоты пока просто сообщение
            # В полной версии нужно генерировать кнопки покупки
            keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="menu_shops")])

    return InlineKeyboardMarkup(keyboard)

# --- ОБРАБОТЧИКИ КОМАНД И СОБЫТИЙ ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    player = get_player_state(user_id)
    loc = get_location(player['location_id'])
    
    text = (
        f"👋 Добро пожаловать, {player['name']}!\n\n"
        f"📍 Вы находитесь: **{loc['name']}**\n"
        f"_{loc['atmosphere']}_\n\n"
        f"Используйте кнопки внизу для действий или напишите текстом, что хотите сделать."
    )
    
    reply_markup = build_keyboard(player, mode='main')
    
    if update.message:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    player = get_player_state(user_id)
    data = query.data
    
    # --- ПЕРЕМЕЩЕНИЕ ---
    if data.startswith("go_"):
        target_id = data.split("_")[1]
        current_loc = get_location(player['location_id'])
        
        if target_id in current_loc['adjacent_location_ids']:
            old_loc_name = current_loc['name']
            player['location_id'] = target_id
            new_loc = get_location(target_id)
            
            prompt = f"Игрок перешел из '{old_loc_name}' в '{new_loc['name']}'. Опиши это переход одним предложением, создавая атмосферу."
            llm_response = ask_llm(prompt, "Ты описываешь перемещения игрока в текстовой RPG. Кратко и атмосферно.")
            
            text = f"🚶 Вы отправились в **{new_loc['name']}**...\n\n{llm_response}\n\n📍 **{new_loc['name']}**\n_{new_loc['atmosphere']}_"
            
            reply_markup = build_keyboard(player, mode='main')
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)
        else:
            await query.answer("Сюда нельзя пройти!", show_alert=True)

    # --- ОСМОТР ---
    elif data == "action_look":
        loc = get_location(player['location_id'])
        npcs = get_npcs_in_location(loc['id'])
        
        npcs_text = ""
        if npcs:
            npcs_text = "\n\n👥 **Здесь находятся:**\n" + "\n".join([f"- {npc['name']}" for npc in npcs])
            
        prompt = f"Ты в локации '{loc['name']}'. {loc['atmosphere']} {npcs_text}. Что ты видишь примечательного? Опиши кратко."
        llm_response = ask_llm(prompt)
        
        text = f"👀 **Осмотр:**\n{llm_response}{npcs_text}"
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=query.message.reply_markup)

    # --- ИНВЕНТАРЬ ---
    elif data == "action_inv":
        inv_list = "\n".join([f"- {item}" for item in player['inventory']])
        text = f"🎒 **Инвентарь:**\n{inv_list if inv_list else 'Пусто'}"
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=query.message.reply_markup)

    # --- СТАТУС ---
    elif data == "action_status":
        skills_str = "\n".join([f"{k}: {v}" for k, v in player['skills'].items()])
        text = (
            f"📊 **Статус:**\n"
            f"❤️ Здоровье: {player['health']}\n"
            f"📍 Локация: {get_location(player['location_id'])['name']}\n\n"
            f"🛠️ **Навыки:**\n{skills_str}"
        )
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=query.message.reply_markup)

    # --- МЕНЮ NPC ---
    elif data == "menu_npcs":
        loc = get_location(player['location_id'])
        npcs = get_npcs_in_location(loc['id'])
        if not npcs:
            await query.answer("Здесь никого нет!", show_alert=True)
            return
        
        text = "Выберите, с кем поговорить:"
        reply_markup = build_keyboard(player, mode='npcs')
        await query.edit_message_text(text, reply_markup=reply_markup)

    # --- МЕНЮ ТОРГОВЛИ ---
    elif data == "menu_shops":
        shops = get_shop_for_location(player['location_id'])
        if not shops:
            await query.answer("Здесь нечем торговать!", show_alert=True)
            return
        
        text = "Выберите лавку или услугу:"
        reply_markup = build_keyboard(player, mode='shops')
        await query.edit_message_text(text, reply_markup=reply_markup)

    # --- РАЗГОВОР С NPC ---
    elif data.startswith("talk_"):
        npc_id = data.split("_")[1]
        npc = next((n for n in world_data['npcs'] if n['id'] == npc_id), None)
        
        if npc:
            loc = get_location(player['location_id'])
            prompt = (
                f"Ты NPC '{npc['name']}' в мире фэнтези. Твои цели: {', '.join(npc['goals'])}. "
                f"Ты находишься в '{loc['name']}'. Игрок подошел к тебе и хочет поговорить. "
                f"Приветствуй его кратко (1-2 предложения) в своем характере и спроси, чего он хочет."
            )
            response = ask_llm(prompt)
            text = f"🗣️ **{npc['name']}**:\n{response}"
            
            # Возвращаем главное меню после разговора
            reply_markup = build_keyboard(player, mode='main')
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)
        else:
            await query.answer("Персонаж не найден", show_alert=True)

    # --- ТОРГОВЛЯ (УПРОЩЕННО) ---
    elif data.startswith("shop_"):
        shop_type = data.split("_")[1]
        shop_data = world_data['shop'].get(shop_type)
        
        if shop_data:
            items_list = "\n".join([f"- {item['name']}: {item['price']} монет" for item in shop_data['items']])
            text = f"🛒 **{shop_data['name']}**:\n\n{items_list}\n\n_(Пока покупка не реализована, но вы можете написать текстом 'Купить зелье')_"
            
            reply_markup = build_keyboard(player, mode='main')
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)
        else:
            await query.answer("Лавка не найдена", show_alert=True)

    # --- НАЗАД ---
    elif data == "back_main":
        await start_command(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка свободного текста"""
    user_id = update.effective_user.id
    player = get_player_state(user_id)
    text = update.message.text
    loc = get_location(player['location_id'])
    
    # Системный контекст для LLM
    system_prompt = (
        f"Ты мастер игры в мире '{world_data['epoch']}'. Тон: {world_data['narrative_tone']}. "
        f"Игрок: {player['name']}. Здоровье: {player['health']}. Навыки: {player['skills']}. "
        f"Локация: {loc['name']}. Атмосфера: {loc['atmosphere']}."
    )
    
    prompt = f"Игрок говорит/делает: '{text}'. Опиши результат этого действия в мире игры. Реагируй на окружение и NPC."
    
    # Отправляем "печатает..."
    await update.message.reply_chat_action(action='typing')
    
    response = ask_llm(prompt, system_prompt)
    
    # Если ответ содержит Markdown, пытаемся его отрендерить, иначе просто текст
    try:
        await update.message.reply_text(response, parse_mode='Markdown')
    except:
        await update.message.reply_text(response)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.warning(f'Update {update} caused error {context.error}')

# --- ЗАПУСК ---
def main():
    if TOKEN == "ВАШ_ТОКЕН_ОТ_BOTFATHER":
        print("❌ ОШИБКА: Не забудьте вставить токен бота в переменную TOKEN!")
        return

    app = Application.builder().token(TOKEN).build()
    
    # Обработчики
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Обработка ошибок
    app.add_error_handler(error_handler)

    print("✅ Бот запущен! Ожидание сообщений...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
