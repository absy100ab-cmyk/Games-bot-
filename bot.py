import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# تمكين التسجيل للأخطاء
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ===================== المتغيرات البيئية =====================
TOKEN = os.getenv("BOT_TOKEN")  # توكن البوت من Railway
if not TOKEN:
    raise ValueError("❌ لم يتم العثور على BOT_TOKEN في المتغيرات البيئية!")

# ===================== قاعدة بيانات مؤقتة (قاموس) =====================
# هيكل البيانات:
# المفاتيح: اسم الفيلم/المسلسل
# القيم: {
#   "type": "movie" أو "series",
#   "parts": عدد الأجزاء (للفيلم),
#   "episodes": عدد الحلقات (للمسلسل),
#   "links": قائمة روابط التحميل أو المشاهدة (اختياري)
# }

MOVIE_DB = {
    "avatar": {
        "type": "movie",
        "parts": 2,
        "links": ["رابط الجزء الأول", "رابط الجزء الثاني"]
    },
    "game of thrones": {
        "type": "series",
        "episodes": 8,
        "links": ["رابط الحلقة 1", "رابط الحلقة 2", "..."]
    },
    "the witcher": {
        "type": "series",
        "episodes": 3,
        "links": ["رابط الموسم 1", "رابط الموسم 2", "رابط الموسم 3"]
    },
    "the godfather": {
        "type": "movie",
        "parts": 3,
        "links": ["رابط الجزء الأول", "رابط الجزء الثاني", "رابط الجزء الثالث"]
    }
}

# ===================== دوال المساعدة =====================
def get_movie_info(name: str):
    """البحث عن الفيلم/المسلسل في قاعدة البيانات"""
    name_lower = name.strip().lower()
    return MOVIE_DB.get(name_lower, None)

def build_buttons(movie_name: str, movie_data: dict):
    """بناء أزرار التفاعل حسب نوع المحتوى"""
    buttons = []
    if movie_data["type"] == "series":
        total = movie_data["episodes"]
        # نضيف أزرار للحلقات (مثال: 8 حلقات)
        for i in range(1, total + 1):
            buttons.append([InlineKeyboardButton(f"🎬 حلقة {i}", callback_data=f"ep_{movie_name}_{i}")])
    elif movie_data["type"] == "movie":
        total = movie_data["parts"]
        if total > 1:
            for i in range(1, total + 1):
                buttons.append([InlineKeyboardButton(f"📽️ جزء {i}", callback_data=f"part_{movie_name}_{i}")])
        else:
            # فيلم واحد بدون أجزاء -> نرسل الرابط مباشرة
            buttons.append([InlineKeyboardButton("▶️ مشاهدة", callback_data=f"watch_{movie_name}")])
    return InlineKeyboardMarkup(buttons)

# ===================== أوامر البوت =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب"""
    await update.message.reply_text(
        "🎬 مرحباً! أرسل لي اسم فيلم أو مسلسل وسأبحث عنه لك.\n"
        "مثال: `Avatar` أو `Game of Thrones`",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل النصية (أسماء الأفلام/المسلسلات)"""
    user_text = update.message.text
    movie_data = get_movie_info(user_text)
    
    if not movie_data:
        await update.message.reply_text("❌ عذراً، لم أجد هذا الفيلم/المسلسل في قاعدة البيانات.")
        return
    
    # حفظ اسم الفيلم في السياق للاستخدام لاحقاً
    context.user_data["current_movie"] = user_text.strip().lower()
    
    # بناء الأزرار
    reply_markup = build_buttons(user_text.strip().lower(), movie_data)
    
    # رسالة توضيحية
    msg = f"✅ وجدت `{user_text}`!\n"
    if movie_data["type"] == "series":
        msg += f"📺 عدد الحلقات: {movie_data['episodes']}\nاختر الحلقة:"
    elif movie_data["type"] == "movie":
        if movie_data["parts"] > 1:
            msg += f"🎬 عدد الأجزاء: {movie_data['parts']}\nاختر الجزء:"
        else:
            msg += "🎬 فيلم واحد، اضغط على مشاهدة."
    
    await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="Markdown")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة ضغط الأزرار"""
    query = update.callback_query
    await query.answer()  # لإعلام تلغرام بأننا استجبنا
    
    data = query.data
    parts = data.split("_")
    action = parts[0]  # ep / part / watch
    movie_name = parts[1]
    movie_data = get_movie_info(movie_name)
    
    if not movie_data:
        await query.edit_message_text("❌ حدث خطأ، لم أعد أجد هذا المحتوى.")
        return
    
    if action == "watch":
        # فيلم واحد بدون أجزاء
        link = movie_data["links"][0] if movie_data["links"] else "رابط غير متوفر"
        await query.edit_message_text(f"🎬 **{movie_name}**\n▶️ [مشاهدة]({link})", parse_mode="Markdown")
    
    elif action == "ep":
        # حلقة من مسلسل
        episode_num = int(parts[2])
        if episode_num <= len(movie_data["links"]):
            link = movie_data["links"][episode_num - 1]
        else:
            link = "رابط غير متوفر"
        await query.edit_message_text(
            f"📺 **{movie_name}** - حلقة {episode_num}\n▶️ [مشاهدة]({link})",
            parse_mode="Markdown"
        )
    
    elif action == "part":
        # جزء من فيلم
        part_num = int(parts[2])
        if part_num <= len(movie_data["links"]):
            link = movie_data["links"][part_num - 1]
        else:
            link = "رابط غير متوفر"
        await query.edit_message_text(
            f"🎬 **{movie_name}** - جزء {part_num}\n▶️ [مشاهدة]({link})",
            parse_mode="Markdown"
        )

# ===================== تشغيل البوت =====================
def main():
    """الوظيفة الرئيسية لتشغيل البوت"""
    print("🚀 بدء تشغيل البوت...")
    app = Application.builder().token(TOKEN).build()
    
    # إضافة المعالجات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # بدء البوت (استخدام Polling)
    print("✅ البوت يعمل الآن...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
