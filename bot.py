import os
import sys
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===================== المتغيرات البيئية =====================
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    logger.error("❌ لم يتم العثور على BOT_TOKEN في المتغيرات البيئية!")
    sys.exit(1)

# ===================== قاعدة البيانات =====================
MOVIE_DB = {
    "avatar": {
        "type": "movie",
        "parts": 2,
        "links": [
            "https://example.com/avatar-part1",
            "https://example.com/avatar-part2"
        ]
    },
    "game of thrones": {
        "type": "series",
        "episodes": 8,
        "links": [
            "https://example.com/got-s1e1",
            "https://example.com/got-s1e2",
            "https://example.com/got-s1e3",
            "https://example.com/got-s1e4",
            "https://example.com/got-s1e5",
            "https://example.com/got-s1e6",
            "https://example.com/got-s1e7",
            "https://example.com/got-s1e8"
        ]
    },
    "the witcher": {
        "type": "series",
        "episodes": 3,
        "links": [
            "https://example.com/witcher-s1",
            "https://example.com/witcher-s2",
            "https://example.com/witcher-s3"
        ]
    },
    "the godfather": {
        "type": "movie",
        "parts": 3,
        "links": [
            "https://example.com/godfather-1",
            "https://example.com/godfather-2",
            "https://example.com/godfather-3"
        ]
    },
    "inception": {
        "type": "movie",
        "parts": 1,
        "links": ["https://example.com/inception"]
    }
}

# ===================== دوال المساعدة =====================
def get_movie_info(name: str):
    """البحث عن الفيلم/المسلسل"""
    if not name:
        return None
    name_lower = name.strip().lower()
    return MOVIE_DB.get(name_lower, None)

def get_all_titles():
    """الحصول على جميع العناوين المتاحة"""
    return list(MOVIE_DB.keys())

# ===================== معالجات البوت =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب"""
    welcome_msg = (
        "🎬 **مرحباً بك في بوت الأفلام والمسلسلات!**\n\n"
        "📌 **كيفية الاستخدام:**\n"
        "• أرسل اسم فيلم أو مسلسل للبحث عنه\n"
        "• اختر الحلقة أو الجزء من الأزرار\n\n"
        "📺 **الأفلام والمسلسلات المتاحة:**\n"
    )
    
    # عرض بعض العناوين المتاحة
    titles = get_all_titles()
    for title in titles[:5]:  # عرض أول 5 عناوين
        welcome_msg += f"• `{title.title()}`\n"
    
    if len(titles) > 5:
        welcome_msg += f"\nو {len(titles) - 5} عناوين أخرى..."
    
    welcome_msg += "\n\n💡 *جرب إرسال: `Avatar`*"
    
    await update.message.reply_text(
        welcome_msg,
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر المساعدة"""
    help_msg = (
        "🆘 **كيفية استخدام البوت:**\n\n"
        "1️⃣ أرسل اسم فيلم أو مسلسل\n"
        "2️⃣ اختر الحلقة أو الجزء من الأزرار\n"
        "3️⃣ سيظهر لك رابط المشاهدة\n\n"
        "📌 **الأوامر المتاحة:**\n"
        "/start - عرض رسالة الترحيب\n"
        "/help - عرض هذه المساعدة\n"
        "/list - عرض جميع العناوين المتاحة\n"
        "/search [اسم] - البحث عن فيلم/مسلسل"
    )
    await update.message.reply_text(help_msg, parse_mode='Markdown')

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض جميع العناوين المتاحة"""
    titles = get_all_titles()
    if not titles:
        await update.message.reply_text("❌ لا توجد عناوين متاحة حالياً.")
        return
    
    msg = "📚 **جميع العناوين المتاحة:**\n\n"
    for i, title in enumerate(titles, 1):
        movie_data = MOVIE_DB[title]
        type_emoji = "🎬" if movie_data["type"] == "movie" else "📺"
        msg += f"{i}. {type_emoji} `{title.title()}`\n"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """البحث عن فيلم/مسلسل باستخدام الأمر"""
    if not context.args:
        await update.message.reply_text("❌ يرجى إدخال اسم الفيلم/المسلسل.\nمثال: `/search avatar`")
        return
    
    search_query = ' '.join(context.args)
    movie_data = get_movie_info(search_query)
    
    if not movie_data:
        await update.message.reply_text(f"❌ لم أجد `{search_query}` في قاعدة البيانات.", parse_mode='Markdown')
        return
    
    context.user_data['current_movie'] = search_query.strip().lower()
    reply_markup = build_buttons(search_query.strip().lower(), movie_data)
    
    msg = f"✅ **تم العثور على:** `{search_query}`\n"
    if movie_data['type'] == 'series':
        msg += f"📺 عدد الحلقات: {movie_data['episodes']}"
    else:
        msg += f"🎬 عدد الأجزاء: {movie_data['parts']}"
    
    await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode='Markdown')

def build_buttons(movie_name: str, movie_data: dict):
    """بناء أزرار التفاعل"""
    buttons = []
    
    if movie_data['type'] == 'series':
        # عرض الحلقات في صفوف (كل صف يحتوي على 3 أزرار)
        total = movie_data['episodes']
        row = []
        for i in range(1, total + 1):
            row.append(InlineKeyboardButton(
                f"🎬 حلقة {i}", 
                callback_data=f"ep_{movie_name}_{i}"
            ))
            if len(row) == 3:  # 3 أزرار في كل صف
                buttons.append(row)
                row = []
        if row:  # إضافة الأزرار المتبقية
            buttons.append(row)
    
    elif movie_data['type'] == 'movie':
        total = movie_data['parts']
        if total > 1:
            row = []
            for i in range(1, total + 1):
                row.append(InlineKeyboardButton(
                    f"📽️ جزء {i}", 
                    callback_data=f"part_{movie_name}_{i}"
                ))
                if len(row) == 3:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)
        else:
            # فيلم واحد بدون أجزاء
            buttons.append([
                InlineKeyboardButton("▶️ مشاهدة الفيلم", callback_data=f"watch_{movie_name}")
            ])
    
    # زر المساعدة
    buttons.append([
        InlineKeyboardButton("🆘 مساعدة", callback_data="help")
    ])
    
    return InlineKeyboardMarkup(buttons)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل النصية"""
    user_text = update.message.text.strip()
    if not user_text:
        await update.message.reply_text("❌ يرجى إدخال اسم صحيح.")
        return
    
    movie_data = get_movie_info(user_text)
    
    if not movie_data:
        # البحث عن تطابق جزئي
        all_titles = get_all_titles()
        suggestions = [title for title in all_titles if user_text.lower() in title]
        
        if suggestions:
            msg = f"❌ لم أجد `{user_text}`، لكن وجدت هذه العناوين المشابهة:\n\n"
            for title in suggestions[:5]:
                msg += f"• `{title.title()}`\n"
            msg += "\n💡 أرسل أحد الأسماء أعلاه للبحث."
            await update.message.reply_text(msg, parse_mode='Markdown')
        else:
            await update.message.reply_text(
                f"❌ عذراً، لم أجد `{user_text}` في قاعدة البيانات.\n"
                f"استخدم /list لعرض جميع العناوين المتاحة.",
                parse_mode='Markdown'
            )
        return
    
    context.user_data['current_movie'] = user_text.strip().lower()
    reply_markup = build_buttons(user_text.strip().lower(), movie_data)
    
    msg = f"✅ **تم العثور على:** `{user_text.title()}`\n\n"
    if movie_data['type'] == 'series':
        msg += f"📺 **مسلسل** - عدد الحلقات: {movie_data['episodes']}\n"
        msg += "اختر الحلقة المناسبة:"
    else:
        if movie_data['parts'] > 1:
            msg += f"🎬 **فيلم** - عدد الأجزاء: {movie_data['parts']}\n"
            msg += "اختر الجزء المناسب:"
        else:
            msg += "🎬 **فيلم**\nاضغط على زر المشاهدة أدناه."
    
    await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة ضغط الأزرار"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "help":
        help_msg = (
            "🆘 **مساعدة سريعة:**\n\n"
            "• أرسل اسم فيلم أو مسلسل للبحث\n"
            "• استخدم /list لعرض جميع العناوين\n"
            "• استخدم /search [اسم] للبحث المباشر\n\n"
            "💡 **ملاحظة:** بعض الروابط قد تكون تجريبية."
        )
        await query.edit_message_text(help_msg, parse_mode='Markdown')
        return
    
    parts = data.split('_')
    if len(parts) < 2:
        await query.edit_message_text("❌ حدث خطأ في البيانات.")
        return
    
    action = parts[0]
    movie_name = parts[1]
    movie_data = get_movie_info(movie_name)
    
    if not movie_data:
        await query.edit_message_text("❌ حدث خطأ، لم أعد أجد هذا المحتوى.")
        return
    
    try:
        if action == "watch":
            # فيلم واحد
            if movie_data['links']:
                link = movie_data['links'][0]
                await query.edit_message_text(
                    f"🎬 **{movie_name.title()}**\n\n"
                    f"▶️ [اضغط للمشاهدة]({link})\n\n"
                    "💡 إذا لم يعمل الرابط، يمكنك البحث عن الفيلم يدوياً.",
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
            else:
                await query.edit_message_text("❌ عذراً، لا يوجد رابط لهذا الفيلم.")
        
        elif action == "ep":
            episode_num = int(parts[2])
            if episode_num <= len(movie_data['links']):
                link = movie_data['links'][episode_num - 1]
                await query.edit_message_text(
                    f"📺 **{movie_name.title()}** - حلقة {episode_num}\n\n"
                    f"▶️ [اضغط للمشاهدة]({link})\n\n"
                    "💡 إذا لم يعمل الرابط، يمكنك البحث عن الحلقة يدوياً.",
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
            else:
                await query.edit_message_text(f"❌ عذراً، لا يوجد رابط للحلقة {episode_num}.")
        
        elif action == "part":
            part_num = int(parts[2])
            if part_num <= len(movie_data['links']):
                link = movie_data['links'][part_num - 1]
                await query.edit_message_text(
                    f"🎬 **{movie_name.title()}** - جزء {part_num}\n\n"
                    f"▶️ [اضغط للمشاهدة]({link})\n\n"
                    "💡 إذا لم يعمل الرابط، يمكنك البحث عن الجزء يدوياً.",
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
            else:
                await query.edit_message_text(f"❌ عذراً، لا يوجد رابط للجزء {part_num}.")
        
        else:
            await query.edit_message_text("❌ إجراء غير معروف.")
    
    except Exception as e:
        logger.error(f"خطأ في معالجة الزر: {e}")
        await query.edit_message_text("❌ حدث خطأ أثناء معالجة طلبك.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الأخطاء العام"""
    logger.error(f"حدث خطأ: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى لاحقاً."
        )

# ===================== تشغيل البوت =====================
def main():
    """الوظيفة الرئيسية"""
    try:
        logger.info("🚀 بدء تشغيل البوت...")
        logger.info(f"✅ Token موجود: {bool(TOKEN)}")
        logger.info(f"📚 عدد العناوين في قاعدة البيانات: {len(MOVIE_DB)}")
        
        # إنشاء التطبيق
        application = Application.builder().token(TOKEN).build()
        
        # إضافة المعالجات
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("list", list_command))
        application.add_handler(CommandHandler("search", search_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(CallbackQueryHandler(button_callback))
        
        # إضافة معالج الأخطاء
        application.add_error_handler(error_handler)
        
        # بدء البوت
        logger.info("✅ البوت يعمل الآن...")
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        
    except Exception as e:
        logger.error(f"❌ فشل تشغيل البوت: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
