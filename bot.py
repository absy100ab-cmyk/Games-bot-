import os
import sys
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ===================== إعداد التسجيل =====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===================== المتغيرات البيئية =====================
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    logger.error("❌ لم يتم العثور على BOT_TOKEN في المتغيرات البيئية!")
    logger.info("💡 استخدم: export BOT_TOKEN='your_token_here'")
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
def get_movie_info(name: str) -> dict or None:
    """البحث عن الفيلم/المسلسل بناءً على الاسم"""
    if not name:
        return None
    name_lower = name.strip().lower()
    return MOVIE_DB.get(name_lower, None)


def get_all_titles() -> list:
    """الحصول على جميع العناوين المتاحة"""
    return list(MOVIE_DB.keys())


def parse_callback_data(data: str) -> dict or None:
    """
    تحليل بيانات رد الاتصال بشكل آمن
    يتعامل مع أسماء الأفلام التي قد تحتوي على مسافات وشرطات سفلية
    
    الصيغ المتوقعة:
    - "help" → {'action': 'help'}
    - "watch:avatar" → {'action': 'watch', 'movie': 'avatar'}
    - "ep:game of thrones:3" → {'action': 'ep', 'movie': 'game of thrones', 'number': 3}
    - "part:the godfather:2" → {'action': 'part', 'movie': 'the godfather', 'number': 2}
    """
    try:
        if data == "help":
            return {'action': 'help'}
        
        parts = data.split(':', 2)
        if len(parts) < 2:
            return None
        
        action = parts[0]
        
        if action == "watch":
            return {
                'action': 'watch',
                'movie': parts[1]
            }
        elif action in ["ep", "part"]:
            if len(parts) < 3:
                return None
            try:
                number = int(parts[2])
                return {
                    'action': action,
                    'movie': parts[1],
                    'number': number
                }
            except ValueError:
                return None
        
        return None
    except Exception as e:
        logger.error(f"خطأ في تحليل البيانات: {e}")
        return None


def build_buttons(movie_name: str, movie_data: dict) -> InlineKeyboardMarkup:
    """بناء أزرار التفاعل بناءً على نوع المحتوى"""
    buttons = []
    
    try:
        if movie_data['type'] == 'series':
            # عرض الحلقات في صفوف (كل صف يحتوي على 3 أزرار)
            total = movie_data.get('episodes', 0)
            row = []
            for i in range(1, total + 1):
                row.append(InlineKeyboardButton(
                    f"🎬 حلقة {i}",
                    callback_data=f"ep:{movie_name}:{i}"
                ))
                if len(row) == 3:  # 3 أزرار في كل صف
                    buttons.append(row)
                    row = []
            if row:  # إضافة الأزرار المتبقية
                buttons.append(row)

        elif movie_data['type'] == 'movie':
            total = movie_data.get('parts', 1)
            if total > 1:
                # فيلم بأجزاء متعددة
                row = []
                for i in range(1, total + 1):
                    row.append(InlineKeyboardButton(
                        f"📽️ جزء {i}",
                        callback_data=f"part:{movie_name}:{i}"
                    ))
                    if len(row) == 3:
                        buttons.append(row)
                        row = []
                if row:
                    buttons.append(row)
            else:
                # فيلم واحد بدون أجزاء
                buttons.append([
                    InlineKeyboardButton(
                        "▶️ مشاهدة الفيلم",
                        callback_data=f"watch:{movie_name}"
                    )
                ])

        # زر المساعدة
        buttons.append([
            InlineKeyboardButton("🆘 مساعدة", callback_data="help")
        ])

        return InlineKeyboardMarkup(buttons)
    except Exception as e:
        logger.error(f"خطأ في بناء الأزرار: {e}")
        return InlineKeyboardMarkup([[InlineKeyboardButton("❌ خطأ", callback_data="help")]])


# ===================== معالجات البوت =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """رسالة الترحيب الرئيسية"""
    try:
        welcome_msg = (
            "🎬 *مرحباً بك في بوت الأفلام والمسلسلات\\!*\n\n"
            "📌 *كيفية الاستخدام:*\n"
            "• أرسل اسم فيلم أو مسلسل للبحث عنه\n"
            "• اختر الحلقة أو الجزء من الأزرار\n\n"
            "📺 *الأفلام والمسلسلات المتاحة:*\n"
        )

        titles = get_all_titles()
        for title in titles[:5]:  # عرض أول 5 عناوين
            welcome_msg += f"• `{title.title()}`\n"

        if len(titles) > 5:
            welcome_msg += f"\nو {len(titles) - 5} عناوين أخرى\\.\\.\\."

        welcome_msg += "\n\n💡 *جرب إرسال:* `Avatar`"

        await update.message.reply_text(
            welcome_msg,
            parse_mode='MarkdownV2'
        )
    except Exception as e:
        logger.error(f"خطأ في أمر start: {e}")
        await update.message.reply_text("❌ حدث خطأ في معالجة الطلب.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """أمر المساعدة"""
    try:
        help_msg = (
            "🆘 *كيفية استخدام البوت:*\n\n"
            "1️⃣ أرسل اسم فيلم أو مسلسل\n"
            "2️⃣ اختر الحلقة أو الجزء من الأزرار\n"
            "3️⃣ سيظهر لك رابط المشاهدة\n\n"
            "📌 *الأوامر المتاحة:*\n"
            "/start \\- عرض رسالة الترحيب\n"
            "/help \\- عرض هذه المساعدة\n"
            "/list \\- عرض جميع العناوين المتاحة\n"
            "/search \\[اسم\\] \\- البحث عن فيلم/مسلسل"
        )
        await update.message.reply_text(help_msg, parse_mode='MarkdownV2')
    except Exception as e:
        logger.error(f"خطأ في أمر help: {e}")
        await update.message.reply_text("❌ حدث خطأ في معالجة الطلب.")


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض جميع العناوين المتاحة"""
    try:
        titles = get_all_titles()
        if not titles:
            await update.message.reply_text("❌ لا توجد عناوين متاحة حالياً.")
            return

        msg = "📚 *جميع العناوين المتاحة:*\n\n"
        for i, title in enumerate(titles, 1):
            movie_data = MOVIE_DB[title]
            type_emoji = "🎬" if movie_data["type"] == "movie" else "📺"
            msg += f"{i}\\. {type_emoji} `{title.title()}`\n"

        await update.message.reply_text(msg, parse_mode='MarkdownV2')
    except Exception as e:
        logger.error(f"خطأ في أمر list: {e}")
        await update.message.reply_text("❌ حدث خطأ في معالجة الطلب.")


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """البحث عن فيلم/مسلسل باستخدام الأمر"""
    try:
        if not context.args:
            await update.message.reply_text(
                "❌ يرجى إدخال اسم الفيلم/المسلسل\\.\n\nمثال: `/search avatar`",
                parse_mode='MarkdownV2'
            )
            return

        search_query = ' '.join(context.args)
        movie_data = get_movie_info(search_query)

        if not movie_data:
            await update.message.reply_text(
                f"❌ لم أجد `{search_query}` في قاعدة البيانات.",
                parse_mode='MarkdownV2'
            )
            return

        context.user_data['current_movie'] = search_query.strip().lower()
        reply_markup = build_buttons(search_query.strip().lower(), movie_data)

        msg = f"✅ *تم العثور على:* `{search_query}`\n"
        if movie_data['type'] == 'series':
            msg += f"📺 عدد الحلقات: {movie_data['episodes']}"
        else:
            msg += f"🎬 عدد الأجزاء: {movie_data['parts']}"

        await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode='MarkdownV2')
    except Exception as e:
        logger.error(f"خطأ في أمر search: {e}")
        await update.message.reply_text("❌ حدث خطأ في معالجة الطلب.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالجة الرسائل النصية"""
    try:
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
                await update.message.reply_text(msg, parse_mode='MarkdownV2')
            else:
                await update.message.reply_text(
                    f"❌ عذراً، لم أجد `{user_text}` في قاعدة البيانات\\.\n\n"
                    f"استخدم /list لعرض جميع العناوين المتاحة\\.",
                    parse_mode='MarkdownV2'
                )
            return

        context.user_data['current_movie'] = user_text.strip().lower()
        reply_markup = build_buttons(user_text.strip().lower(), movie_data)

        msg = f"✅ *تم العثور على:* `{user_text.title()}`\n\n"
        if movie_data['type'] == 'series':
            msg += f"📺 *مسلسل* \\- عدد الحلقات: {movie_data['episodes']}\n"
            msg += "اختر الحلقة المناسبة:"
        else:
            if movie_data['parts'] > 1:
                msg += f"🎬 *فيلم* \\- عدد الأجزاء: {movie_data['parts']}\n"
                msg += "اختر الجزء المناسب:"
            else:
                msg += "🎬 *فيلم*\nاضغط على زر المشاهدة أدناه\\."

        await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode='MarkdownV2')
    except Exception as e:
        logger.error(f"خطأ في معالجة الرسالة: {e}")
        await update.message.reply_text("❌ حدث خطأ أثناء معالجة رسالتك.")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالجة ضغط الأزرار - محسّنة وآمنة"""
    try:
        query = update.callback_query
        await query.answer()

        # تحليل بيانات رد الاتصال بشكل آمن
        parsed_data = parse_callback_data(query.data)

        if parsed_data is None:
            await query.edit_message_text("❌ حدث خطأ في البيانات.")
            return

        action = parsed_data.get('action')

        if action == "help":
            help_msg = (
                "🆘 *مساعدة سريعة:*\n\n"
                "• أرسل اسم فيلم أو مسلسل للبحث\n"
                "• استخدم /list لعرض جميع العناوين\n"
                "• استخدم /search \\[اسم\\] للبحث المباشر\n\n"
                "💡 *ملاحظة:* بعض الروابط قد تكون تجريبية\\."
            )
            await query.edit_message_text(help_msg, parse_mode='MarkdownV2')
            return

        movie_name = parsed_data.get('movie')
        movie_data = get_movie_info(movie_name)

        if not movie_data:
            await query.edit_message_text("❌ حدث خطأ، لم أعد أجد هذا المحتوى.")
            return

        if action == "watch":
            # فيلم واحد
            if movie_data.get('links'):
                link = movie_data['links'][0]
                await query.edit_message_text(
                    f"🎬 *{movie_name.title()}*\n\n"
                    f"▶️ [اضغط للمشاهدة]({link})\n\n"
                    "💡 إذا لم يعمل الرابط، يمكنك البحث عن الفيلم يدوياً\\.",
                    parse_mode='MarkdownV2',
                    disable_web_page_preview=True
                )
            else:
                await query.edit_message_text("❌ عذراً، لا يوجد رابط لهذا الفيلم.")

        elif action == "ep":
            # حلقة من مسلسل
            episode_num = parsed_data.get('number')
            if episode_num and episode_num <= len(movie_data.get('links', [])):
                link = movie_data['links'][episode_num - 1]
                await query.edit_message_text(
                    f"📺 *{movie_name.title()}* \\- حلقة {episode_num}\n\n"
                    f"▶️ [اضغط للمشاهدة]({link})\n\n"
                    "💡 إذا لم يعمل الرابط، يمكنك البحث عن الحلقة يدوياً\\.",
                    parse_mode='MarkdownV2',
                    disable_web_page_preview=True
                )
            else:
                await query.edit_message_text(f"❌ عذراً، لا يوجد رابط للحلقة {episode_num}.")

        elif action == "part":
            # جزء من فيلم
            part_num = parsed_data.get('number')
            if part_num and part_num <= len(movie_data.get('links', [])):
                link = movie_data['links'][part_num - 1]
                await query.edit_message_text(
                    f"🎬 *{movie_name.title()}* \\- جزء {part_num}\n\n"
                    f"▶️ [اضغط للمشاهدة]({link})\n\n"
                    "💡 إذا لم يعمل الرابط، يمكنك البحث عن الجزء يدوياً\\.",
                    parse_mode='MarkdownV2',
                    disable_web_page_preview=True
                )
            else:
                await query.edit_message_text(f"❌ عذراً، لا يوجد رابط للجزء {part_num}.")

        else:
            await query.edit_message_text("❌ إجراء غير معروف.")

    except Exception as e:
        logger.error(f"خطأ في معالجة الزر: {e}")
        try:
            await query.edit_message_text("❌ حدث خطأ أثناء معالجة طلبك.")
        except:
            logger.error("فشل إرسال رسالة الخطأ")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالج الأخطاء العام"""
    logger.error(f"تحديث: {update}")
    logger.error(f"حدث خطأ: {context.error}")

    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ حدث خطأ غير متوقع\\. يرجى المحاولة مرة أخرى لاحقاً\\.",
                parse_mode='MarkdownV2'
            )
    except Exception as e:
        logger.error(f"فشل إرسال رسالة الخطأ: {e}")


# ===================== تشغيل البوت =====================
def main() -> None:
    """الوظيفة الرئيسية - بدء تشغيل البوت"""
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
        logger.info("💡 اضغط Ctrl+C للإيقاف")
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )

    except Exception as e:
        logger.error(f"❌ فشل تشغيل البوت: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
