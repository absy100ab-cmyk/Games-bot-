import os
import sys
import logging
import urllib.parse
import re
import yt_dlp
from bs4 import BeautifulSoup
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# ===================== إعداد التسجيل =====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===================== المتغيرات البيئية ورؤوس الطلبات =====================
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    logger.error("❌ لم يتم العثور على BOT_TOKEN في المتغيرات البيئية!")
    sys.exit(1)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ar,en-US;q=0.7,en;q=0.3",
    "Referer": "https://google.com"
}

# ===================== دالة البحث العالمية الهجينة (أفلام + مسلسلات) =====================
def search_movies_yts(query: str) -> list:
    """
    البحث الهجين: يبحث في YTS للأفلام، وفي سيرفرات البث المفتوحة للمسلسلات
    """
    results = []
    
    # 1. محاولة البحث كفيلم في مكتبة YTS العالمية
    try:
        api_url = f"https://yts.mx/api/v2/list_movies.json?query_term={urllib.parse.quote(query)}&limit=4"
        response = requests.get(api_url, timeout=7)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'ok' and data.get('data', {}).get('movie_count', 0) > 0:
                movies = data['data']['movies']
                for movie in movies:
                    results.append({
                        'title': f"🎬 {movie['title_long']} (فيلم)",
                        'torrents': movie['torrents'],
                        'rating': movie.get('rating', 'N/A'),
                        'type': 'movie'
                    })
    except Exception as e:
        logger.error(f"خطأ في بحث الأفلام YTS: {e}")

    # 2. إذا لم نجد نتائج (أو كان مسلسلاً)، نبحث في سيرفر المسلسلات المفتوح والمستقر
    if not results or len(results) < 3:
        try:
            encoded_query = urllib.parse.quote(query)
            search_url = f"https://cinemaclub.vip/search?q={encoded_query}"
            response = requests.get(search_url, headers=HEADERS, timeout=7)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                items = soup.find_all('a', href=True)
                for item in items:
                    title = item.get('title') or item.text.strip()
                    link = item['href']
                    
                    if title and len(title) > 4 and any(x in link for x in ['series', 'season', 'episode', 'watch', 'post']):
                        if not any(r['title'] == title for r in results):
                            results.append({
                                'title': f"📺 {title} (مسلسل/حلقة)",
                                'torrents': [{'url': link, 'quality': 'Direct', 'size': 'تلقائي'}],
                                'rating': '⭐',
                                'type': 'series'
                            })
                            if len(results) >= 6:
                                break
        except Exception as e:
            logger.error(f"خطأ في بحث المسلسلات البديل: {e}")

    return results

# ===================== دالة سحب وتحميل الفيديو وإرساله =====================
def download_yts_video(torrent_url: str, title: str) -> str:
    """
    تحميل الفيلم مباشرة باستخدام yt-dlp عبر روابط البث المفتوحة لـ YTS أو روابط المسلسلات
    """
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
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(torrent_url, download=True)
            filename = ydl.prepare_filename(info)
            return filename
    except Exception as e:
        logger.error(f"فشل تحميل الفيديو عبر yt-dlp: {e}")
        return None


# ===================== معالجات البوت =====================
async def start(update: Update, context) -> None:
    welcome_msg = (
        "🎬 *مرحباً بك في بوت سينما التليجرام العالمية\\!* \n\n"
        "🍿 *البوت يدعم الآن الأفلام والمسلسلات معاً في مكتبة موحدة ومستقرة\\.*\n"
        "📌 أرسل اسم الفيلم أو المسلسل باللغة الإنجليزية، وسأقوم بجلبه وإرساله لك كفيديو مباشر داخل الشات وبأعلى دقة\\!\n\n"
        "💡 *مثال:* `Inception` أو `Game of Thrones`"
    )
    await update.message.reply_text(welcome_msg, parse_mode='MarkdownV2')


async def handle_message(update: Update, context) -> None:
    try:
        user_query = update.message.text.strip()
        if not user_query:
            return

        processing_msg = await update.message.reply_text("🔍 جاري البحث في المكتبة العالمية والمحلية الفورية...")
        
        # البحث الفوري الهجين
        search_results = search_movies_yts(user_query)
        
        if not search_results:
            await processing_msg.edit_text("❌ لم أجد نتائج مطابقة لهذا الاسم. يرجى التأكد من كتابة الاسم الإنجليزي بشكل صحيح.")
            return

        buttons = []
        for i, movie in enumerate(search_results):
            context.user_data[f"movie_data_{i}"] = movie
            buttons.append([
                InlineKeyboardButton(f"{movie['title']} ⭐ {movie['rating']}", callback_data=f"select_movie:{i}")
            ])
            
        reply_markup = InlineKeyboardMarkup(buttons)
        await processing_msg.delete()
        
        await update.message.reply_text(
            f"🍿 *نتائج البحث لـ:* `{user_query}`\n"
            f"اختر الفيلم أو المسلسل المطلوب لعرض دقات الفيديو المتاحة للتحميل والمشاهدة الفورية داخل الشات:",
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

        # الخطوة 1: عرض جودات التحميل المتوفرة
        if action == "select_movie":
            movie_data = context.user_data.get(f"movie_data_{index}")
            if not movie_data:
                await query.edit_message_text("❌ انتهت صلاحية الجلسة، أعد البحث مجدداً.")
                return
            
            buttons = []
            for t_idx, torrent in enumerate(movie_data['torrents']):
                context.user_data[f"download_url_{index}_{t_idx}"] = torrent['url']
                buttons.append([
                    InlineKeyboardButton(
                        f"📥 تشغيل وإرسال بدقة {torrent['quality']} ({torrent['size']})", 
                        callback_data=f"send_video:{index}:{t_idx}"
                    )
                ])
                
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(
                f"⚙️ *اختر الجودة المطلوبة:* \n🎬 `{movie_data['title']}`",
                reply_markup=reply_markup,
                parse_mode='MarkdownV2'
            )

        # الخطوة 2: تحميل الفيديو وإرساله مباشرة للمستخدم داخل الشات
        elif action == "send_video":
            t_idx = int(data_parts[2])
            movie_data = context.user_data.get(f"movie_data_{index}")
            download_url = context.user_data.get(f"download_url_{index}_{t_idx}")

            if not movie_data or not download_url:
                await query.edit_message_text("❌ حدث خطأ في استرجاع بيانات الملف.")
                return

            await query.edit_message_text("⚡ جاري سحب فيديو الفيلم بالدقة المطلوبة... يرجى الانتظار دقيقة.")
            
            video_file_path = download_yts_video(download_url, movie_data['title'])

            if video_file_path and os.path.exists(video_file_path):
                await query.edit_message_text("🚀 جاري رفع ملف الفيديو إليك مباشرة الآن...")
                
                with open(video_file_path, 'rb') as video_file:
                    await context.bot.send_video(
                        chat_id=query.message.chat_id,
                        video=video_file,
                        caption=f"🎬 *تم تجهيز الفيديو بنجاح:* \n🔥 `{movie_data['title']}`\n\nمشاهدة ممتعة🍿",
                        parse_mode='MarkdownV2'
                    )
                
                os.remove(video_file_path)
                await query.message.delete()
            else:
                await query.edit_message_text("❌ عذراً، تعذر تحميل وإرسال الفيديو المباشر لهذه الجودة حالياً. جرب اختيار جودة أخرى أو ابحث باسم آخر.")

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
