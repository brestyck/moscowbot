import telebot
from telebot import types
from telebot.util import quick_markup
from langus import default_phrases
from PIL import Image
from io import BytesIO
import pymongo
import base64
from time import time

# Settings
ADMIN = [752690137, 1023881495]
db = pymongo.MongoClient("mongodb+srv://xerox:alphabeta@cluster0.gm6w2.mongodb.net/minkoshdb?retryWrites=true&w=majority")["moscow_stamps"]
token='7063470321:AAEiwuTu3RlKsersyg3_cMrkSjWfZlRQ3wQ'
bot=telebot.TeleBot(token)
users = db["users"]
districts = db["districts"]


# The very beginning
@bot.message_handler(commands=['start'])
def start_message(message: types.Message):
    user = message.chat.id
    acc = users.find_one({"_id": user})
    if not acc:
        users.insert_one({
            "_id": user,
            "name": f"{message.chat.first_name} {message.chat.username}",
            "customGreeting": None,
            "visited": [],
            "lastActiv": int(time())
        })

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(default_phrases["point_visit"])
    markup.add(default_phrases["just_districts"])
    if message.chat.id in ADMIN:
        markup.add(default_phrases["admin_panel"])
    bot.send_message(message.chat.id,default_phrases["greet"], reply_markup=markup)
    if acc and acc["customGreeting"] != None:
        bot.send_message(message.chat.id, acc["customGreeting"])

# Add new district next step handler
# we already wait for district name
dist_name = ""
dist_desc = ""
dist_coat = ""

def new_district_next_step1(message):
    global dist_name
    dist_name = message.text
    bot.send_message(message.chat.id, f"Краткое описание для района {message.text}?")
    bot.register_next_step_handler(message, new_district_next_step2)
def new_district_next_step2(message):
    global dist_desc
    dist_desc = message.text
    bot.send_message(message.chat.id, f"Отправьте мне фото герба района {dist_name}")
    bot.register_next_step_handler(message, new_district_next_step3)

# Get and process photo
def new_district_next_step3(message: types.Message):
    global dist_coat
    fID = message.photo[-1].file_id
    fData = bot.get_file(fID)
    downloaded_file = bot.download_file(fData.file_path)
    dist_coat = base64.b64encode(downloaded_file)
    # Add to database
    districts.insert_one({
        "name": dist_name.upper(),
        "desc": dist_desc,
        "coat": dist_coat
    })
    bot.send_message(message.chat.id, f"Добавлен в базу район {dist_name}.")

def add_custom_greeting(message: types.Message, ident):
    greet = message.text if message.text != "None" else None
    users.update_one({"_id":ident}, {"$set":{"customGreeting":greet}})
    bot.send_message(message.chat.id, "Приветствие обновлено")

# Callback query handler
@bot.callback_query_handler(func = lambda callback: callback.data)
def check_callback(callback: types.CallbackQuery):
    if callback.data == 'add_district':
        bot.send_message(callback.message.chat.id, "Название района?")
        bot.register_next_step_handler(callback.message, new_district_next_step1)
    elif callback.data == 'manage_users':
        markup = types.InlineKeyboardMarkup()
        for i in list(users.find()):
            ident = i["_id"]
            name = i["name"]
            markup.add(types.InlineKeyboardButton(f"{name}", callback_data=f"custgreet_{ident}"))
        bot.send_message(callback.message.chat.id, "Кого?", reply_markup=markup)
    elif callback.data[0:9] == "custgreet":
        bot.send_message(callback.message.chat.id, "Пишите приветствие. Если хотите его удалить, напишите None.")
        bot.register_next_step_handler(callback.message, add_custom_greeting, int(callback.data[10:]))


# General chatting
@bot.message_handler(content_types="text")
def answerer(message):
    if message.text == default_phrases["point_visit"]:
        bot.send_message(message.chat.id, default_phrases["point_visit_reply"])
    elif message.text == default_phrases["just_districts"]:
        all_districts = ""
        x = 0
        for i in list(districts.find()):
            name = i["name"]
            x += 1
            all_districts += f"{x}. {name}\n"
        bot.send_message(message.chat.id,
                        default_phrases["just_districts_reply"] + all_districts,
                        parse_mode="Markdown"
                        )
    elif message.text == default_phrases["admin_panel"]:
        markup = quick_markup({
            "Добавить район": {"callback_data": "add_district"},
            "Пользователи": {"callback_data": "manage_users"}
        })
        bot.send_message(message.chat.id, "Вот, что можно сделать, будучи админом", reply_markup=markup)
    else:
        res = districts.find_one({"name": message.text.upper()})
        if res:
            name = res["name"]
            desc = res["desc"]
            imageData = Image.open(BytesIO(base64.b64decode(res["coat"])))
            bot.send_photo(message.chat.id, imageData, caption=f"*{name}*\n\n{desc}", parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, default_phrases["not_found"])
    # Update activity
    user = users.find_one_and_update({"_id": message.chat.id}, {"$set": {"lastActiv": int(time())}})
    if int(time()) - user["lastActiv"] > 56400 and user["customGreeting"] != None:
        bot.send_message(message.chat.id, user["customGreeting"])

bot.infinity_polling()