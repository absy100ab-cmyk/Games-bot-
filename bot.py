import os
import sys
import logging
import urllib.parse
import re
import yt_dlp
from bs4 import BeautifulSoup
import requests
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
    sys.exit(1)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ===================== دالة البحث عن الأفلام =====================
def search_movies_online(query: str) -> list:
    results = []
    try:
        encoded_query = urllib.parse.quote(query)
        # نستخدم موقعاً مستقراً للبحث عن صفحات الأفلام
        search_url = f"https://cimalight.io/search/{encoded_query}"
        response = requests.get(search_url, headers=HEADERS, timeout=8)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            items = soup.find_all('a', href=True)
            for item in items:
                title = item.get('title') or item.text.strip()
                link = item['href']
                
                if title and len(title) > 3 and ('watch' in link or 'video' in link or 'film' in link or 'series' in link):
                    if not any(r['title'] == title for r in results):
                        results.append({'title': title, 'link': link})
                        if len(results) >= 6:
                            break
    except Exception as e:
        logger.error(f"خطأ أثناء البحث: {e}")
    return results

# ===================== دالة تحميل وإرسال الفيديو المباشر =====================
def download_video_direct(page_url: str) -> str:
    """
    استخراج رابط الفيديو المباشر أو تحميله لإرساله للتليجرام باستخدام yt-dlp
    """
    # إعدادات yt-dlp لجلب أفضل دقة فيديو متاحة وتناسب تليجرام (يفضل دمج الصوت والفيديو تلقائياً)
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', # جلب MP4 بأعلى دقة مدمجة
        'outtmpl': 'downloads/%(title)s.%(ext)s', # مسار الحفظ المؤقت
        'restrictfilenames': True,
        'noplaylist': True,
        'quiet': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # استخراج معلومات الفيديو دون تحميله بالكامل أولاً للتأكد من وجود رابط مباشر
            info = ydl.extract_info(page_url, download=True)
            filename = ydl.prepare_filename(info)
            return filename # نرجع مسار الملف المحمل على السيرفر لإرساله مباشرة
    except Exception as e:
        logger.error(f"فشل استخراج الفيديو عبر yt-dlp: {e}")
        return None


# ===================== معالجات البوت =====================
async def start(update: Update, context) -> None:
    welcome_msg = (
        "🎬 *مرحباً بك في بوت سينما التليجرام المباشر\\!* \n\n"
        "📌 *أرسل اسم الفيلم أو المسلسل* وسأقوم بجلبه وإرساله لك كفيديو مباشر لتشاهده داخل الشات وبأعلى دقة\\!"
    )
    await update.message.reply_text(welcome_msg, parse_mode='MarkdownV2')


async def handle_message(update: Update, context) -> None:
    try:
        user_query = update.message.text.strip()
        if not user_query:
            return

        processing_msg = await update.message.reply_text("🔍 جاري البحث عن الفيلم وتحضير الخيارات...")
        search_results = search_movies_online(user_query)
        
        if not search_results:
            await processing_msg.edit_text("❌ لم أجد نتائج مطابقة لاسم هذا الفيلم حالياً. جرب كتابة الاسم بشكل صحيح.")
            return

        buttons = []
        for i, movie in enumerate(search_results):
            context.user_data[f"movie_link_{i}"] = movie['link']
            context.user_data[f"movie_title_{i}"] = movie['title']
            
            buttons.append([
                InlineKeyboardButton(f"🎬 {movie['title']}", callback_data=f"send_file:{i}")
            ])
            
        reply_markup = InlineKeyboardMarkup(buttons)
        await processing_msg.delete()
        
        await update.message.reply_text(
            f"🍿 *نتائج البحث لـ:* `{user_query}`\n"
            f"اضغط على الفيلم أو الحلقة المطلوبة لتشغيلها وفيديو الفيلم سيصلك جاهزاً فوراً:",
            reply_markup=reply_markup,
            parse_mode='MarkdownV2'
        )
    except Exception as e:
        logger.error(f"خطأ في البحث: {e}")


async def button_callback(update: Update, context) -> None:
    try:
        query = update.callback_query
        await query.answer()

        data_parts = query.data.split(':')
        if len(data_parts) < 2:
            return

        action, movie_index = data_parts[0], data_parts[1]

        if action == "send_file":
            movie_url = context.user_data.get(f"movie_link_{movie_index}")
            movie_title = context.user_data.get(f"movie_title_{movie_index}", "فيديو")

            if not movie_url:
                await query.edit_message_text("❌ انتهت صلاحية الجلسة، أعد البحث مجدداً.")
                return

            await query.edit_message_text("📥 جاري سحب وتجهيز ملف الفيديو بأعلى دقة... قد يستغرق الأمر دقيقة.")
            
            # تحميل الفيديو مؤقتاً على سيرفر ريلواي لإرساله مباشرة
            video_file_path = download_video_direct(movie_url)

            if video_file_path and os.path.exists(video_file_path):
                await query.edit_message_text("🚀 جاري رفع الفيديو وإرساله لك الآن...")
                
                # إرسال الفيديو مباشرة داخل الشات
                with open(video_file_path, 'rb') as video_file:
                    await context.bot.send_video(
                        chat_id=query.message.chat_id,
                        video=video_file,
                        caption=f"🎬 *تم تجهيز الفيلم بنجاح:* \n🔥 `{movie_title}` \n\nمشاهدة ممتعة🍿",
                        parse_mode='MarkdownV2'
                    )
                
                # حذف الملف بعد الرفع لتوفير مساحة السيرفر
                os.remove(video_file_path)
                await query.message.delete() # حذف رسالة التحميل
            else:
                await query.edit_message_text("❌ عذراً، تعذر سحب دقة الفيديو المباشرة لهذا الفيلم تلقائياً من السيرفر.")

    except Exception as e:
        logger.error(f"خطأ أثناء معالجة وإرسال الفيديو: {e}")
        await query.edit_message_text("❌ حدث خطأ غير متوقع أثناء معالجة الفيديو.")


# ===================== تشغيل البوت =====================
def main() -> None:
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == '__main__':
    main()
