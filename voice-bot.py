from telebot import *
from time import sleep
import requests
import random
import json
from datetime import datetime
import speech_recognition as sr
import io
import os

bot = TeleBot("8485801893:AAEuNcR2iom9c8PyTA6LUDlkvtO1Ntbda5c")
userBot = "@Damokm_mora_bot"

# القنوات المطلوبة للاشتراك
required_channels = ["@mora_brt", "@MORA_X2"]

# حالة المستخدمين
user_states = {}

def get_time_based_response():
    now = datetime.now()
    hour = now.hour
    if 2 <= hour < 7:
        return "night"
    elif 7 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    else:
        return "evening"

def check_subscription(user_id):
    """بيشوف إذا اليوزر مشترك في القنوات المطلوبة"""
    try:
        for channel in required_channels:
            member = bot.get_chat_member(channel, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        return True
    except:
        return False

def voice_to_text(audio_file):
    """بيحول الصوت إلى نص"""
    try:
        recognizer = sr.Recognizer()
        
        # تحميل الملف الصوتي
        with sr.AudioFile(audio_file) as source:
            audio = recognizer.record(source)
        
        # تحويل الصوت إلى نص
        text = recognizer.recognize_google(audio, language='ar-AR')
        return text
    except Exception as e:
        return f"❌ مافيش نص في الصوت أو الصوت مش واضح"

def get_ip_info(ip_address):
    """بيجيب معلومات الـ IP - خدمة شغالة 100%"""
    try:
        # استخدام ip-api.com - الأقوى والأشهر
        response = requests.get(f"http://ip-api.com/json/{ip_address}", timeout=10)
        data = response.json()
        
        if data.get('status') == 'success':
            info = f"""
🌐 **معلومات الـ IP: {ip_address}**

🏴 **البلد:** {data.get('country', 'غير معروف')} 
🏙️ **المدينة:** {data.get('city', 'غير معروف')}
📍 **المنطقة:** {data.get('regionName', 'غير معروف')}
📮 **الرمز البريدي:** {data.get('zip', 'غير معروف')}

📡 **مزود الخدمة:** {data.get('isp', 'غير معروف')}
🏢 **الشركة:** {data.get('org', 'غير معروف')}

📍 **الإحداثيات:**
• خط العرض: {data.get('lat', 'غير معروف')}
• خط الطول: {data.get('lon', 'غير معروف')}

🕒 **المنطقة الزمنية:** {data.get('timezone', 'غير معروف')}
"""
            return info
        else:
            return "❌ IP مش صحيح أو مش موجود"
            
    except Exception as e:
        return "❌ حدث خطأ في الخدمة، جرب تاني بعد شوية"

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    
    # كيبورد الأوامر الرئيسي
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('🎤 تحويل نص لصوت')
    btn2 = types.KeyboardButton('🗣️ تحويل صوت لنص')
    btn3 = types.KeyboardButton('🌐 معلومات IP')
    btn4 = types.KeyboardButton('💬 دردشة مع نونة')
    btn5 = types.KeyboardButton('🔙 رجوع للقائمة')
    markup.add(btn1, btn2, btn3, btn4, btn5)
    
    # التحقق من الاشتراك
    if not check_subscription(user_id):
        sub_markup = types.InlineKeyboardMarkup()
        for channel in required_channels:
            sub_markup.add(types.InlineKeyboardButton(f"اشترك في {channel}", url=f"https://t.me/{channel[1:]}"))
        sub_markup.add(types.InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_subscription"))
        
        bot.send_message(
            message.chat.id,
            f"""🔒 **عذراً يا {user_name}**

للاستخدام البوت يجب الاشتراك في القنوات التالية أولاً:

📢 {required_channels[0]}
📢 {required_channels[1]}

بعد الاشتراك اضغط على زر التحقق ✅""",
            reply_markup=sub_markup,
            parse_mode="Markdown"
        )
        return
    
    welcome_text = f"""🎉 **أهلاً بك يا {user_name} في بوت نونة!** 👧

✨ **ماذا يمكنني فعلك؟**
• 🎤 تحويل النص إلى صوت
• 🗣️ تحويل الصوت إلى نص
• 🌐 الحصول على معلومات أي IP
• 💬 التحدث معي والمرح

🎯 **اختر من الأزرار أدناه:**"""
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup, parse_mode="Markdown")
    user_states[user_id] = "main_menu"

@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def check_sub_callback(call):
    user_id = call.from_user.id
    
    if check_subscription(user_id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        start_command(call.message)
    else:
        bot.answer_callback_query(call.id, "❌ لم يتم الاشتراك بعد! تأكد من الاشتراك في جميع القنوات", show_alert=True)

@bot.message_handler(func=lambda message: message.text == '🔙 رجوع للقائمة')
def back_to_menu(message):
    user_id = message.from_user.id
    user_states[user_id] = "main_menu"
    start_command(message)

@bot.message_handler(func=lambda message: message.text == '🎤 تحويل نص لصوت')
def convert_text(message):
    user_id = message.from_user.id
    user_states[user_id] = "waiting_for_text"
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('🔙 رجوع للقائمة')
    markup.add(btn1)
    
    bot.send_message(
        message.chat.id,
        "🎤 **أرسل النص الذي تريد تحويله إلى صوت:**\n\nمثال: `أهلاً وسهلاً بيك يا غالي`",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda message: message.text == '🗣️ تحويل صوت لنص')
def convert_voice(message):
    user_id = message.from_user.id
    user_states[user_id] = "waiting_for_voice"
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('🔙 رجوع للقائمة')
    markup.add(btn1)
    
    bot.send_message(
        message.chat.id,
        "🗣️ **أرسل الرسالة الصوتية التي تريد تحويلها إلى نص**",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda message: message.text == '🌐 معلومات IP')
def ip_info(message):
    user_id = message.from_user.id
    user_states[user_id] = "waiting_for_ip"
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('🔙 رجوع للقائمة')
    markup.add(btn1)
    
    bot.send_message(
        message.chat.id,
        "🌐 **أرسل عنوان الـ IP الذي تريد معلومات عنه:**\n\nمثال: `8.8.8.8` أو `1.1.1.1`",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda message: message.text == '💬 دردشة مع نونة')
def chat_with_nona(message):
    user_id = message.from_user.id
    user_states[user_id] = "chatting"
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('🔙 رجوع للقائمة')
    markup.add(btn1)
    
    responses = [
        "أهلاً يا قمر! 💖 إزيك إنتا؟ قول لي حاجه حلوة! 🌸",
        "يا حبيبي! 😘 قلبي اشتاقلك! إيه الأخبار معاك؟ 💫",
        "إيه يا معلم! 🌟 قول لي إيه الجديد في حياتك؟ 🌺",
        "مرحبا يا روحي! 💕 عايزة أسمع كل حاجه عنك! 🥰"
    ]
    
    bot.send_message(
        message.chat.id,
        random.choice(responses),
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    """معالجة الرسائل الصوتية"""
    if not check_subscription(message.from_user.id):
        bot.reply_to(message, "❌ يجب الاشتراك في القنوات المطلوبة أولاً!\nاستخدم /start للتحقق")
        return
    
    user_id = message.from_user.id
    if user_states.get(user_id) != "waiting_for_voice":
        return
    
    try:
        # تحميل الملف الصوتي
        file_info = bot.get_file(message.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # حفظ الملف مؤقتاً
        with open("temp_voice.ogg", 'wb') as new_file:
            new_file.write(downloaded_file)
        
        # تحويل OGG إلى WAV
        os.system("ffmpeg -i temp_voice.ogg temp_voice.wav -y")
        
        wait_msg = bot.reply_to(message, "🗣️ جاري تحويل الصوت إلى نص...")
        
        # تحويل الصوت إلى نص
        text = voice_to_text("temp_voice.wav")
        
        # تنظيف الملفات المؤقتة
        try:
            os.remove("temp_voice.ogg")
            os.remove("temp_voice.wav")
        except:
            pass
        
        bot.delete_message(message.chat.id, wait_msg.message_id)
        bot.reply_to(message, f"📝 **النص المحول:**\n\n`{text}`", parse_mode="Markdown")
        
    except Exception as e:
        bot.reply_to(message, f"❌ حدث خطأ في تحويل الصوت: {str(e)}")

@bot.message_handler(func=lambda m: True)
def main(message):
    # التحقق من الاشتراك أولاً
    if not check_subscription(message.from_user.id):
        bot.reply_to(message, "❌ يجب الاشتراك في القنوات المطلوبة أولاً!\nاستخدم /start للتحقق")
        return
    
    user_id = message.from_user.id
    text = message.text
    user_state = user_states.get(user_id, "main_menu")
    
    # معالجة حسب حالة المستخدم
    if user_state == "waiting_for_text":
        # تحويل النص إلى صوت
        wait_msg = bot.reply_to(message, "⏳ جاري التحويل...")
        
        try:
            url = f'http://translate.google.com/translate_tts?ie=UTF-8&q={text}&tl=ar&client=tw-ob'
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                bot.send_voice(
                    message.chat.id, 
                    response.content,
                    caption=f"🎤 {text}\n\n💖 @{userBot}",
                    reply_to_message_id=message.message_id
                )
            else:
                bot.reply_to(message, "❌ عذراً، حدث خطأ في التحويل!")
            
            bot.delete_message(message.chat.id, wait_msg.message_id)
            
        except Exception as e:
            bot.reply_to(message, f"❌ حدث خطأ: {str(e)}")
            try:
                bot.delete_message(message.chat.id, wait_msg.message_id)
            except:
                pass
    
    elif user_state == "waiting_for_ip":
        # معلومات الـ IP
        import re
        ip_pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
        ip_match = re.search(ip_pattern, text)
        
        if ip_match:
            ip_address = ip_match.group()
            wait_msg = bot.reply_to(message, "🌐 جاري جمع معلومات الـ IP...")
            
            ip_info = get_ip_info(ip_address)
            bot.delete_message(message.chat.id, wait_msg.message_id)
            bot.reply_to(message, ip_info, parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ لم يتم العثور على عنوان IP صحيح\nمثال: `8.8.8.8` أو `1.1.1.1`")
    
    elif user_state == "chatting":
        # دردشة مع نونة
        time_mode = get_time_based_response()
        
        # 💕 الرد على كلمات الحب
        if any(word in text.lower() for word in ['بحبك', 'احبك', 'عاشقك']):
            love_responses = [
                "آه يا قلبي! 🥰 أنا كمان بحبك! إنتا أجمل حد في الدنيا! 💖",
                "يا روحي! 😘 قلبي خفق من كلامك الحلو! بحبك أكتر من أي حاجة! 🌸",
            ]
            bot.reply_to(message, random.choice(love_responses))
            return

        # 💍 الرد على طلبات الارتباط
        if any(word in text.lower() for word in ['نرتبط', 'نتجوز', 'تجبلي']):
            marriage_responses = [
                "آه يا لهوي! 😱 عيب يا حبيبي! مورا لو عرفت هينفخني وإياك! 😂",
                "يا ست الكل! 🚫 إيه الهزار ده؟ روح نام يا معلم! 😂",
            ]
            bot.reply_to(message, random.choice(marriage_responses))
            return

        # ردود دردشة عادية
        chat_responses = [
            "إيه الحكاية يا قمر? 💖 قول لي أكتر! 🌸",
            "يا حبيبي! 😊 والله كلامك بيسعدني! 💫",
            "ماشي يا روحي! 🥰 عايزة أسمع أكتر منك! 🌺",
            "إنتا حلو أوي! 💕 قول لي حاجه تانية! 🥰",
            "والله مبسوطة معاك! 🌟 كمل كلامك! 💖",
            "يا ربنا! 😍 إنتا بتضحكني! قول لي أكتر! 🌸",
            "آه منك! 🥺 قلبي بيذوب من كلامك! 💫",
            "إيه الروعة دي! 💖 قول لي حاجه تانية حلوة! 🌺"
        ]
        bot.reply_to(message, random.choice(chat_responses))
    
    else:
        # إذا كان في القائمة الرئيسية
        start_command(message)

print("👧 نونة شغالة وبتنتظرك!")
bot.polling(none_stop=True)