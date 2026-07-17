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
    logger.error("❌ لم يتم العثور على BOT_TOKEN!")
    sys.exit(1)

# ===================== دالة البحث وتجاوز الحظر =====================
def search_movies_yts(query: str) -> list:
    results = []
    encoded_query = urllib.parse.quote(query)
    
    # استخدام المرايا لتفادي حظر خوادم الاستضافة
    api_urls = [
        f"https://yts.mx/api/v2/list_movies.json?query_term={encoded_query}&limit=4",
        f"https://yts.lt/api/v2/list_movies.json?query_term={encoded_query}&limit=4"
    ]
    
    for url in api_urls:
        try:
            response = requests.get(url, timeout=8)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'ok' and data.get('data', {}).get('movie_count', 0) > 0:
                    movies = data['data']['movies']
                    for movie in movies:
                        torrents = []
                        for t in movie.get('torrents', []):
                            torrents.append({
                                'url': t['url'], # رابط التورنت
                                'hash': t.get('hash'), # الـ Hash الخاص بالتورنت لربطه بمحرك البث
                                'quality': t.get('quality', '720p'),
                                'size': t.get('size', 'N/A')
                            })
                        
                        results.append({
                            'title': movie['title_long'],
                            'torrents': torrents,
                            'rating': movie.get('rating', 'N/A')
                        })
                    break
        except Exception as e:
            logger.error(f"فشل الاتصال بـ {url}: {e}")
            continue

    return results

# ===================== دالة تحميل دفق الفيديو الفعلي =====================
def download_yts_video(torrent_hash: str) -> str:
    """
    تقوم بتحويل هاش التورنت إلى رابط بث مباشر مدعوم ومستقر تمهيداً لتحميله كملف MP4
    """
    out_dir = "downloads"
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
        
    # استخدام خادم دفق وسيط ومجاني لتحويل التورنت إلى رابط تحميل مباشر سريع
    # هذا الرابط يدعمه yt-dlp بشكل كامل وسريع جداً
    stream_url = f"https://server.webtor.io/api/v1/stream/torrent/{torrent_hash}" 
    
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': f'{out_dir}/%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'quiet': True,
        'max_filesize': 1000000000, # حد أقصى 1 جيجابايت لضمان عدم امتلاء ذاكرة ريلواي المؤقتة
    }
    
    try:
        # نقوم بمحاولة التحميل من رابط البث المباشر المولد من الهاش
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(stream_url, download=True)
            filename = ydl.prepare_filename(info)
            return filename
    except Exception as e:
        logger.error(f"فشل التحميل عبر محرك البث: {e}")
        return None

# ===================== معالجات البوت =====================
async def start(update: Update, context) -> None:
    welcome_msg = (
        "🎬 *مرحباً بك في بوت سينما التليجرام العالمية\\!* \n\n"
        "🍿 أرسل اسم الفيلم باللغة الإنجليزية، وسيقوم البوت بجلب جودات التحميل وإرسال الفيديو لك مباشرة داخل الشات بدون روابط خارجية\\!\n\n"
        "💡 *مثال:* `Inception` أو `The Dark Knight`\n\n"
        "👑 *المطور:* @B43lB"
    )
    await update.message.reply_text(welcome_msg, parse_mode='MarkdownV2')


async def handle_message(update: Update, context) -> None:
    try:
        user_query = update.message.text.strip()
        if not user_query:
            return

        processing_msg = await update.message.reply_text("🔍 جاري البحث عن الفيلم في المكتبة وتخطي جدران الحماية المانعة...")
        
        search_results = search_movies_yts(user_query)
        
        if not search_results:
            await processing_msg.edit_text("❌ لم أجد نتائج مطابقة لهذا الاسم. يرجى التأكد من كتابة اسم الفيلم الإنجليزي بشكل صحيح.")
            return

        buttons = []
        for i, movie in enumerate(search_results):
            context.user_data[f"movie_{i}"] = movie
            buttons.append([
                InlineKeyboardButton(f"🎬 {movie['title']} ⭐ {movie['rating']}", callback_data=f"select_movie:{i}")
            ])
            
        reply_markup = InlineKeyboardMarkup(buttons)
        await processing_msg.delete()
        
        await update.message.reply_text(
            f"🍿 *نتائج البحث لـ:* `{user_query}`\n\n"
            f"اختر الفيلم المطلوب لعرض دقات التحميل وإرساله كفيديو مباشر:",
            reply_markup=reply_markup,
            parse_mode='MarkdownV2'
        )
    except Exception as e:
        logger.error(f"خطأ في معالجة البحث: {e}")


async def button_callback(update: Update, context) -> None:
    try:
        query = update.callback_query
        await query.answer()

        data_parts = query.data.split(':')
        if len(data_parts) < 2:
            return

        action, index = data_parts[0], int(data_parts[1])

        if action == "select_movie":
            movie_data = context.user_data.get(f"movie_{index}")
            if not movie_data:
                await query.edit_message_text("❌ انتهت صلاحية الجلسة، يرجى إعادة البحث.")
                return
            
            buttons = []
            for t_idx, torrent in enumerate(movie_data['torrents']):
                # حفظ الهاش بدلاً من رابط التورنت غير المدعوم
                context.user_data[f"t_hash_{index}_{t_idx}"] = torrent['hash']
                buttons.append([
                    InlineKeyboardButton(
                        f"📥 إرسال بجودة {torrent['quality']} ({torrent['size']})", 
                        callback_data=f"send_video:{index}:{t_idx}"
                    )
                ])
                
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(
                f"⚙️ *اختر الجودة المطلوبة للفيلم:* \n🎬 `{movie_data['title']}`",
                reply_markup=reply_markup,
                parse_mode='MarkdownV2'
            )

        elif action == "send_video":
            t_idx = int(data_parts[2])
            movie_data = context.user_data.get(f"movie_{index}")
            torrent_hash = context.user_data.get(f"t_hash_{index}_{t_idx}")

            if not movie_data or not torrent_hash:
                await query.edit_message_text("❌ حدث خطأ في استرجاع هاش الفيلم.")
                return

            await query.edit_message_text("⚡ جاري الاتصال بمحركات البث وسحب الفيلم... يرجى الانتظار قليلاً.")
            
            # إرسال الهاش للتحميل
            video_file_path = download_yts_video(torrent_hash)

            if video_file_path and os.path.exists(video_file_path):
                await query.edit_message_text("🚀 تم اكتمال تحميل الملف بنجاح! جاري رفعه للشات الآن...")
                
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
                await query.edit_message_text("❌ عذراً، تعذر سحب الفيديو لهذه الجودة حالياً (ربما حجم الملف أكبر من المساحة المؤقتة المتاحة على السيرفر). يرجى محاولة اختيار جودة أقل.")

    except Exception as e:
        logger.error(f"خطأ في معالجة إرسال الفيديو: {e}")
        await query.edit_message_text("❌ حدث خطأ غير متوقع أثناء المعالجة.")


# ===================== تشغيل البوت =====================
def main() -> None:
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == '__main__':
    main()
