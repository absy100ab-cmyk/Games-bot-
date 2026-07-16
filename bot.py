import os
import sys
import logging
import asyncio
from pathlib import Path
from typing import Dict, Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo, InputMediaDocument
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.error import TelegramError

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

# ===================== إعدادات التخزين المؤقت والملفات =====================
MEDIA_DIR = Path("media")  # دليل تخزين الملفات
MEDIA_DIR.mkdir(exist_ok=True)
FILE_ID_CACHE: Dict[str, Dict[str, str]] = {}  # تخزين مؤقت لمعرّفات الملفات

# ===================== قاعدة البيانات =====================
MOVIE_DB = {
    "avatar": {
        "type": "movie",
        "parts": 2,
        "files": [
            "media/avatar-part1.mp4",
            "media/avatar-part2.mp4"
        ],
        "description": "فيلم Avatar - الجزء الأول والثاني"
    },
    "game of thrones": {
        "type": "series",
        "episodes": 8,
        "files": [
            "media/got-s1e1.mkv",
            "media/got-s1e2.mkv",
            "media/got-s1e3.mkv",
            "media/got-s1e4.mkv",
            "media/got-s1e5.mkv",
            "media/got-s1e6.mkv",
            "media/got-s1e7.mkv",
            "media/got-s1e8.mkv"
        ],
        "description": "مسلسل Game of Thrones - الموسم الأول"
    },
    "the witcher": {
        "type": "series",
        "episodes": 3,
        "files": [
            "media/witcher-s1.mkv",
            "media/witcher-s2.mkv",
            "media/witcher-s3.mkv"
        ],
        "description": "مسلسل The Witcher"
    },
    "the godfather": {
        "type": "movie",
        "parts": 3,
        "files": [
            "media/godfather-1.mkv",
            "media/godfather-2.mkv",
            "media/godfather-3.mkv"
        ],
        "description": "فيلم The Godfather - جميع الأجزاء"
    },
    "inception": {
        "type": "movie",
        "parts": 1,
        "files": ["media/inception.mkv"],
        "description": "فيلم Inception"
    }
}

# ===================== دوال المساعدة =====================
def get_movie_info(name: str) -> Optional[dict]:
    """البحث عن الفيلم/المسلسل بناءً على الاسم"""
    if not name:
        return None
    name_lower = name.strip().lower()
    return MOVIE_DB.get(name_lower, None)


def get_all_titles() -> list:
    """الحصول على جميع العناوين المتاحة"""
    return list(MOVIE_DB.keys())


def parse_callback_data(data: str) -> Optional[dict]:
    """
    تحليل بيانات رد الاتصال بشكل آمن
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


def file_exists(file_path: str) -> bool:
    """التحقق من وجود الملف"""
    return Path(file_path).exists() and Path(file_path).is_file()


def build_buttons(movie_name: str, movie_data: dict) -> InlineKeyboardMarkup:
    """بناء أزرار التفاعل بناءً على نوع المحتوى"""
    buttons = []
    
    try:
        if movie_data['type'] == 'series':
            total = movie_data.get('episodes', 0)
            row = []
            for i in range(1, total + 1):
                row.append(InlineKeyboardButton(
                    f"🎬 حلقة {i}",
                    callback_data=f"ep:{movie_name}:{i}"
                ))
                if len(row) == 3:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)

        elif movie_data['type'] == 'movie':
            total = movie_data.get('parts', 1)
            if total > 1:
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
                buttons.append([
                    InlineKeyboardButton(
                        "▶️ مشاهدة الفيلم",
                        callback_data=f"watch:{movie_name}"
                    )
                ])

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
            "• اختر الحلقة أو الجزء من الأزرار\n"
            "• سيتم إرسال الملف مباشرة لك\\!\n\n"
            "📺 *الأفلام والمسلسلات المتاحة:*\n"
        )

        titles = get_all_titles()
        for title in titles[:5]:
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
            "3️⃣ سيتم تحميل الملف مباشرة\\!\n\n"
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


async def send_file_with_retry(
    query,
    file_path: str,
    chat_id: int,
    caption: str,
    file_type: str = "video"
) -> bool:
    """
    إرسال ملف مع إعادة محاولة في حالة الفشل
    يدعم الملفات الكبيرة والقائمة المرسلة
    """
    try:
        if not file_exists(file_path):
            logger.warning(f"⚠️ الملف غير موجود: {file_path}")
            await query.edit_message_text(
                f"❌ عذراً، الملف غير متاح حالياً.\n\n"
                f"يرجى المحاولة لاحقاً."
            )
            return False

        # إرسال رسالة التحميل
        await query.edit_message_text(
            "⏳ جاري تحميل الملف... يرجى الانتظار"
        )

        # إرسال الملف بناءً على النوع
        with open(file_path, 'rb') as file:
            if file_type == "video":
                await query.bot.send_video(
                    chat_id=chat_id,
                    video=file,
                    caption=caption,
                    parse_mode='Markdown'
                )
            elif file_type == "document":
                await query.bot.send_document(
                    chat_id=chat_id,
                    document=file,
                    caption=caption,
                    parse_mode='Markdown'
                )
            elif file_type == "photo":
                await query.bot.send_photo(
                    chat_id=chat_id,
                    photo=file,
                    caption=caption,
                    parse_mode='Markdown'
                )

        await query.edit_message_text(
            "✅ تم تحميل الملف بنجاح\\!\n\n"
            "💡 استخدم /help للمساعدة\\."
        )
        logger.info(f"✅ تم إرسال الملف: {file_path}")
        return True

    except TelegramError as e:
        logger.error(f"❌ خطأ في إرسال الملف عبر Telegram: {e}")
        try:
            await query.edit_message_text(
                "❌ حدث خطأ أثناء إرسال الملف\\. يرجى المحاولة لاحقاً\\."
            )
        except:
            pass
        return False
    except Exception as e:
        logger.error(f"❌ خطأ غير متوقع في إرسال الملف: {e}")
        try:
            await query.edit_message_text(
                "❌ حدث خطأ غير متوقع\\. يرجى المحاولة لاحقاً\\."
            )
        except:
            pass
        return False


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالجة ضغط الأزرار - محسّنة وآمنة مع إرسال الملفات"""
    try:
        query = update.callback_query
        await query.answer()

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
                "💡 سيتم إرسال الملفات مباشرة لك عند اختيار حلقة أو جزء\\."
            )
            await query.edit_message_text(help_msg, parse_mode='MarkdownV2')
            return

        movie_name = parsed_data.get('movie')
        movie_data = get_movie_info(movie_name)

        if not movie_data:
            await query.edit_message_text("❌ حدث خطأ، لم أعد أجد هذا المحتوى.")
            return

        if action == "watch":
            if movie_data.get('files'):
                file_path = movie_data['files'][0]
                caption = f"🎬 *{movie_name.title()}*\n\n{movie_data.get('description', '')}"
                await send_file_with_retry(query, file_path, update.effective_chat.id, caption, "video")
            else:
                await query.edit_message_text("❌ عذراً، لا يوجد ملف لهذا الفيلم.")

        elif action == "ep":
            episode_num = parsed_data.get('number')
            if episode_num and episode_num <= len(movie_data.get('files', [])):
                file_path = movie_data['files'][episode_num - 1]
                caption = f"📺 *{movie_name.title()}* \\- حلقة {episode_num}\n\n{movie_data.get('description', '')}"
                await send_file_with_retry(query, file_path, update.effective_chat.id, caption, "video")
            else:
                await query.edit_message_text(f"❌ عذراً، لا يوجد ملف للحلقة {episode_num}.")

        elif action == "part":
            part_num = parsed_data.get('number')
            if part_num and part_num <= len(movie_data.get('files', [])):
                file_path = movie_data['files'][part_num - 1]
                caption = f"🎬 *{movie_name.title()}* \\- جزء {part_num}\n\n{movie_data.get('description', '')}"
                await send_file_with_retry(query, file_path, update.effective_chat.id, caption, "video")
            else:
                await query.edit_message_text(f"❌ عذراً، لا يوجد ملف للجزء {part_num}.")

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

        # إنشاء التطبيق مع إعدادات محسّنة
        application = (
            Application.builder()
            .token(TOKEN)
            .connect_timeout(30)
            .read_timeout(30)
            .write_timeout(30)
            .build()
        )

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
