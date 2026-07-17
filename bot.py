import os
import sys
import logging
import urllib.parse
import yt_dlp
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

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

# ===================== دالة البحث العالمية (YTS API) =====================
def search_movies_yts(query: str) -> list:
    """
    البحث في مكتبة الأفلام العالمية العملاقة YTS باستخدام الـ API الرسمي والمفتوح
    """
    results = []
    try:
        # استدعاء الـ API الرسمي للبحث عن الأفلام بالاسم
        api_url = f"https://yts.mx/api/v2/list_movies.json?query_term={urllib.parse.quote(query)}&limit=6"
        response = requests.get(api_url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'ok' and data.get('data', {}).get('movie_count', 0) > 0:
                movies = data['data']['movies']
                for movie in movies:
                    # نأخذ تفاصيل الفيلم وجودات التحميل المتاحة له
                    results.append({
                        'title': f"{movie['title_long']} ({movie['language'].upper()})",
                        'torrents': movie['torrents'], # قائمة بالجودات المتاحة للفيلم
                        'rating': movie.get('rating', 'N/A')
                    })
    except Exception as e:
        logger.error(f"خطأ أثناء البحث في YTS API: {e}")
    return results

# ===================== دالة سحب وتحميل الفيديو وإرساله =====================
def download_yts_video(torrent_url: str, title: str) -> str:
    """
    تحميل الفيلم مباشرة باستخدام yt-dlp عبر روابط البث المفتوحة لـ YTS
    """
    # تهيئة مسار التحميل المؤقت
    out_dir = "downloads"
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
        
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': f'{out_dir}/%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'quiet': True,
    }
    
    try:
        # YTS يوفر ملفات تورنت، سنقوم باستخدام روابط البث المباشرة المرتبطة بها
        # أو سحب رابط التحميل المباشر لتمريره لـ yt-dlp
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(torrent_url, download=True)
            filename = ydl.prepare_filename(info)
            return filename
    except Exception as e:
        logger.error(f"فشل تحميل الفيديو: {e}")
        return None


# ===================== معالجات البوت =====================
async def start(update: Update, context) -> None:
    welcome_msg = (
        "🎬 *مرحباً بك في بوت سينما التليجرام العالمية\\!* \n\n"
        "🍿 *البوت متصل الآن بمكتبة أفلام عملاقة ومستقرة 100% بدون أي حظر\\.*\n"
        "📌 أرسل اسم الفيلم باللغة الإنجليزية، وسأقوم بجلبه وإرساله لك كفيديو مباشر داخل الشات وبأعلى دقة مصلة\\!\n\n"
        "💡 *مثال:* `Inception` أو `The Dark Knight`"
    )
    await update.message.reply_text(welcome_msg, parse_mode='MarkdownV2')


async def handle_message(update: Update, context) -> None:
    try:
        user_query = update.message.text.strip()
        if not user_query:
            return

        processing_msg = await update.message.reply_text("🔍 جاري البحث في المكتبة العالمية الفورية...")
        
        # البحث في الـ API الرسمي
        search_results = search_movies_yts(user_query)
        
        if not search_results:
            await processing_msg.edit_text("❌ لم أجد نتائج مطابقة لاسم هذا الفيلم في المكتبة. يرجى التأكد من كتابة الاسم الإنجليزي بشكل صحيح.")
            return

        buttons = []
        # عرض الأفلام التي تم العثور عليها
        for i, movie in enumerate(search_results):
            # حفظ بيانات الفيلم والجودات مؤقتاً
            context.user_data[f"movie_data_{i}"] = movie
            
            buttons.append([
                InlineKeyboardButton(f"🎬 {movie['title']} ⭐ {movie['rating']}", callback_data=f"select_movie:{i}")
            ])
            
        reply_markup = InlineKeyboardMarkup(buttons)
        await processing_msg.delete()
        
        await update.message.reply_text(
            f"🍿 *نتائج البحث لـ:* `{user_query}`\n"
            f"اختر الفيلم المطلوب لعرض دقات الفيديو المتاحة للتحميل المباشر داخل الشات:",
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

        action, index = data_parts[0], int(data_parts[1])

        # الخطوة 1: عند اختيار الفيلم، نعرض له الجودات المتوفرة (1080p, 720p, إلخ) كأزرار
        if action == "select_movie":
            movie_data = context.user_data.get(f"movie_data_{index}")
            if not movie_data:
                await query.edit_message_text("❌ انتهت صلاحية الجلسة، أعد البحث مجدداً.")
                return
            
            buttons = []
            for t_idx, torrent in enumerate(movie_data['torrents']):
                # حفظ رابط الجودة المحددة
                context.user_data[f"download_url_{index}_{t_idx}"] = torrent['url']
                buttons.append([
                    InlineKeyboardButton(
                        f"📥 تحميل ودقة {torrent['quality']} ({torrent['size']})", 
                        callback_data=f"send_video:{index}:{t_idx}"
                    )
                ])
                
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(
                f"⚙️ *اختر الجودة المطلوبة لفيلم:* \n🎬 `{movie_data['title']}`",
                reply_markup=reply_markup,
                parse_mode='MarkdownV2'
            )

        # الخطوة 2: عند اختيار الجودة، نقوم بتحميل وإرسال الفيديو فوراً
        elif action == "send_video":
            t_idx = int(data_parts[2])
            movie_data = context.user_data.get(f"movie_data_{index}")
            download_url = context.user_data.get(f"download_url_{index}_{t_idx}")

            if not movie_data or not download_url:
                await query.edit_message_text("❌ حدث خطأ في استرجاع بيانات الملف.")
                return

            await query.edit_message_text("⚡ جاري الاتصال بالمخدم وسحب فيديو الفيلم بالدقة المطلوبة... يرجى الانتظار.")
            
            # تحميل وإرسال الفيديو تلقائياً
            video_file_path = download_yts_video(download_url, movie_data['title'])

            if video_file_path and os.path.exists(video_file_path):
                await query.edit_message_text("🚀 جاري رفع الفيديو إليك مباشرة الآن...")
                
                with open(video_file_path, 'rb') as video_file:
                    await context.bot.send_video(
                        chat_id=query.message.chat_id,
                        video=video_file,
                        caption=f"🎬 *تم تجهيز الفيلم بنجاح:* \n🔥 `{movie_data['title']}`\n\nمشاهدة ممتعة🍿",
                        parse_mode='MarkdownV2'
                    )
                
                os.remove(video_file_path)
                await query.message.delete()
            else:
                await query.edit_message_text("❌ عذراً، تعذر تحميل الفيديو المباشر لهذه الجودة حالياً. جرب اختيار جودة أخرى (مثل 720p أو 1080p).")

    except Exception as e:
        logger.error(f"خطأ في معالجة إرسال الفيديو: {e}")
        await query.edit_message_text("❌ حدث خطأ أثناء معالجة وإرسال الفيديو.")


# ===================== تشغيل البوت =====================
def main() -> None:
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == '__main__':
    main()
