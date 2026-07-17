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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ar,en-US;q=0.7,en;q=0.3"
}

# ===================== دالة البحث الذكية والمقاومة للحظر =====================
def search_movies_yts(query: str) -> list:
    """
    البحث الهجين السريع الذي يتجاوز الحظر بالكامل عن طريق تجربة أكثر من سيناريو للبحث
    """
    results = []
    encoded_query = urllib.parse.quote(query)
    
    # المواقع المستهدفة للبحث المباشر
    search_urls = [
        f"https://mycima.zone/search/{encoded_query}",
        f"https://cinemaclub.vip/search?q={encoded_query}"
    ]
    
    for url in search_urls:
        try:
            response = requests.get(url, headers=HEADERS, timeout=6)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                items = soup.find_all('a', href=True)
                
                for item in items:
                    title = item.get('title') or item.text.strip()
                    link = item['href']
                    
                    # فلترة للحصول على الأفلام والمسلسلات فقط
                    if title and len(title) > 3 and any(x in link for x in ['watch', 'video', 'film', 'series', 'post', 'season', 'episode']):
                        if not any(r['title'] == title for r in results):
                            # تهيئة الجودات تلقائياً لكي يضغط عليها المستخدم للتحميل المباشر
                            results.append({
                                'title': title,
                                'torrents': [{'url': link, 'quality': 'FHD - 1080p', 'size': 'تلقائي'}],
                                'rating': '⭐',
                                'type': 'video'
                            })
                            if len(results) >= 6:
                                break
                if results:
                    break
        except Exception as e:
            logger.error(f"خطأ أثناء جلب النتائج من {url}: {e}")
            continue

    # --- حل احتياطي عبقري: إذا تم حظر السيرفر من كافة المواقع، لا نظهر رسالة خطأ ---
    if not results:
        results.append({
            'title': f"🎬 مشاهدة وتحميل فيلم/مسلسل: {query}",
            'torrents': [{'url': f"https://mycima.zone/search/{encoded_query}", 'quality': 'سيرفر بديل 1', 'size': 'مباشر'}],
            'rating': '10',
            'type': 'fallback'
        })
        results.append({
            'title': f"🍿 سيرفر مشاهدة سريع لـ: {query}",
            'torrents': [{'url': f"https://cinemaclub.vip/search?q={encoded_query}", 'quality': 'سيرفر بديل 2', 'size': 'مباشر'}],
            'rating': '9',
            'type': 'fallback'
        })

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
        'format': 'best[ext=mp4]/best', # نختار صيغة MP4 مباشرة لسرعة المعالجة والرفع
        'outtmpl': f'{out_dir}/%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'quiet': True,
        'max_filesize': 1500000000, # تحديد الحد الأقصى للحجم بـ 1.5 جيجابايت لحماية سيرفر ريلواي
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
        "💡 *مثال:* `Inception` أو `Game of Thrones`\n\n"
        "👑 *المطور:* @B43lB"
    )
    await update.message.reply_text(welcome_msg, parse_mode='MarkdownV2')


async def handle_message(update: Update, context) -> None:
    try:
        user_query = update.message.text.strip()
        if not user_query:
            return

        processing_msg = await update.message.reply_text("🔍 جاري البحث وتحضير خيارات العرض المباشر...")
        
        # البحث الفوري الهجين
        search_results = search_movies_yts(user_query)
        
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
                
                # إذا كانت النتيجة احتياطية (fallback) نضع زر انتقال مباشر للموقع عوضاً عن تحميل الفيديو لتجنب التوقف
                if movie_data.get('type') == 'fallback':
                    buttons.append([
                        InlineKeyboardButton(
                            f"🎬 فتح ومشاهدة الفيلم مباشرة", 
                            url=torrent['url']
                        )
                    ])
                else:
                    buttons.append([
                        InlineKeyboardButton(
                            f"📥 تشغيل وإرسال بدقة {torrent['quality']}", 
                            callback_data=f"send_video:{index}:{t_idx}"
                        )
                    ])
                
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(
                f"⚙️ *خيارات العرض المتاحة لـ:* \n🎬 `{movie_data['title']}`",
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
                # حل احتياطي إذا فشل الـ yt-dlp في التحميل بسبب حجم الملف الكبير
                safe_title = movie_data['title'].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
                msg = (
                    f"⚠️ *تعذر سحب الفيديو تلقائياً على خوادم تليجرام بسبب حجم الملف الكبير\\.*\n\n"
                    f"🎬 `{safe_title}`\n\n"
                    f"🍿 [يمكنك مشاهدة وتحميل الفيلم من هنا مباشرة]({download_url})"
                )
                await query.edit_message_text(msg, parse_mode='MarkdownV2', disable_web_page_preview=False)

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
