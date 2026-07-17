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
    logger.info("💡 استخدم: export BOT_TOKEN='your_token_here'")
    sys.exit(1)

# الرأس الافتراضي لتجنب حظر السكرابينج من المواقع
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ===================== دالة البحث المطورة والسريعة =====================
def search_movies_online(query: str) -> list:
    """
    البحث السريع والمستقر في محرك بحث سينمائي بديل يضمن جلب العناوين والروابط
    """
    results = []
    try:
        # استخدام صيغة بحث في موقع موثوق ومستقر مثل عائلة Cima (وي سيما البديل أو لودي نت)
        encoded_query = urllib.parse.quote(query)
        # نستخدم رابط محرك بحث مرن ومستقر 
        search_url = f"https://wecima.show/search/{encoded_query}"
        
        response = requests.get(search_url, headers=HEADERS, timeout=8)
        if response.status_code != 200:
            # محاولة بديلة في حال تعطل السيرفر الأول
            search_url = f"https://mycima.tube/search/{encoded_query}"
            response = requests.get(search_url, headers=HEADERS, timeout=8)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # البحث عن الروابط والعناوين داخل الهيكل العام للموقع
            # يبحث عن تصنيفات الأفلام (Grid Class)
            items = soup.find_all('a', href=True)
            for item in items:
                title = item.get('title') or item.text.strip()
                link = item['href']
                
                # التحقق من أن العنصر هو فيلم أو مسلسل وليس رابطاً جانبياً
                if title and len(title) > 3 and ('watch' in link or '/post/' in link or '/video/' in link or 'film' in link or 'series' in link):
                    # تجنب تكرار نفس العنوان في القائمة
                    if not any(r['title'] == title for r in results):
                        results.append({
                            'title': title,
                            'link': link
                        })
                        if len(results) >= 6:  # نكتفي بأول 6 نتائج لسرعة الاستجابة
                            break
    except Exception as e:
        logger.error(f"خطأ أثناء البحث السينمائي: {e}")
    
    return results

# ===================== دالة جلب الروابط المباشرة السريعة =====================
def extract_stream_links(movie_url: str) -> list:
    """
    استخراج روابط التحميل أو المشاهدة المباشرة من صفحة الفيلم
    """
    links = []
    try:
        response = requests.get(movie_url, headers=HEADERS, timeout=8)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # جلب السيرفرات أو روابط الـ watch/download المتاحة
            for a_tag in soup.find_all('a', href=True):
                text = a_tag.text.strip()
                href = a_tag['href']
                
                # فحص الكلمات المفتاحية للتحميل أو المشاهدة
                if any(word in text.lower() or word in href.lower() for word in ['download', 'تحميل', 'مشاهدة', 'watch', 'server', 'سيرفر']):
                    if href.startswith('http') and not any(l['url'] == href for l in links):
                        links.append({
                            'label': text if len(text) < 20 else "سيرفر مشاهدة/تحميل",
                            'url': href
                        })
                        if len(links) >= 4:  # نكتفي بأفضل 4 روابط
                            break
    except Exception as e:
        logger.error(f"خطأ في استخراج الروابط: {e}")
    return links


# ===================== معالجات البوت =====================
async def start(update: Update, context) -> None:
    """رسالة الترحيب الرئيسية"""
    try:
        welcome_msg = (
            "🎬 *مرحباً بك في بوت البحث عن الأفلام والمسلسلات\\!* \n\n"
            "📌 *كل ما عليك فعله هو إرسال اسم الفيلم أو المسلسل مباشرة* وسأقوم بالبحث عنه تلقائياً في المواقع وجلب روابط المشاهدة والتحميل لك\\!\n\n"
            "💡 *مثال للبحث:* `Interstellar` أو `The Witcher`"
        )
        await update.message.reply_text(welcome_msg, parse_mode='MarkdownV2')
    except Exception as e:
        logger.error(f"خطأ في أمر start: {e}")


async def handle_message(update: Update, context) -> None:
    """معالجة الرسائل والبحث الفوري عن الفيلم"""
    try:
        user_query = update.message.text.strip()
        if not user_query:
            return

        processing_msg = await update.message.reply_text("🔍 جاري البحث في المواقع، يرجى الانتظار ثواني...")
        
        # البحث الفوري برمجياً في الموقع
        search_results = search_movies_online(user_query)
        
        if not search_results:
            await processing_msg.edit_text("❌ عذراً، لم أجد نتائج مطابقة لاسم هذا الفيلم حالياً. جرب كتابة الاسم باللغة الإنجليزية أو بطريقة أخرى.")
            return

        # بناء أزرار بالنتائج التي تم العثور عليها
        buttons = []
        for i, movie in enumerate(search_results):
            # حفظ الروابط مؤقتاً في الـ user_data
            context.user_data[f"movie_link_{i}"] = movie['link']
            context.user_data[f"movie_title_{i}"] = movie['title']
            
            buttons.append([
                InlineKeyboardButton(
                    f"🎬 {movie['title']}",
                    callback_data=f"get_links:{i}"
                )
            ])
            
        reply_markup = InlineKeyboardMarkup(buttons)
        await processing_msg.delete()
        
        await update.message.reply_text(
            f"🍿 *نتائج البحث لـ:* `{user_query}`\n"
            f"اختر الفيلم/المسلسل المطلوب لعرض الروابط المباشرة:",
            reply_markup=reply_markup,
            parse_mode='MarkdownV2'
        )

    except Exception as e:
        logger.error(f"خطأ في معالجة رسالة البحث: {e}")
        await update.message.reply_text("❌ حدث خطأ أثناء عملية البحث.")


async def button_callback(update: Update, context) -> None:
    """معالجة ضغط المستخدم على الفيلم المختار وجلب روابط التحميل له"""
    try:
        query = update.callback_query
        await query.answer()

        data_parts = query.data.split(':')
        if len(data_parts) < 2:
            return

        action = data_parts[0]
        movie_index = data_parts[1]

        if action == "get_links":
            movie_url = context.user_data.get(f"movie_link_{movie_index}")
            movie_title = context.user_data.get(f"movie_title_{movie_index}", "الفيلم المختار")

            if not movie_url:
                await query.edit_message_text("❌ انتهت صلاحية الجلسة، يرجى إعادة البحث من جديد.")
                return

            await query.edit_message_text("📥 جاري استخراج روابط التحميل والمشاهدة...")
            
            # استخراج روابط التحميل من صفحة الفيلم
            download_links = extract_stream_links(movie_url)
            
            # تنظيف العنوان لتوافقه مع ماركداون
            safe_title = movie_title.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')

            if download_links:
                msg = f"✅ *تم تجهيز روابط الفيلم:* \n🎬 `{safe_title}`\n\n"
                buttons = []
                for link in download_links:
                    buttons.append([InlineKeyboardButton(f"📥 {link['label']}", url=link['url'])])
                
                reply_markup = InlineKeyboardMarkup(buttons)
                await query.edit_message_text(msg, reply_markup=reply_markup, parse_mode='MarkdownV2')
            else:
                # إذا لم نجد روابط مباشرة، نرسل له رابط صفحة الفيلم ليدخل ويشاهد منها
                msg = (
                    f"✅ *تم العثور على صفحة الفيلم:*\n"
                    f"🎬 `{safe_title}`\n\n"
                    f"🔗 [اضغط هنا للمشاهدة والتحميل المباشر من الموقع]({movie_url})"
                )
                await query.edit_message_text(msg, parse_mode='MarkdownV2', disable_web_page_preview=False)

    except Exception as e:
        logger.error(f"خطأ في معالجة الأزرار: {e}")
        await query.edit_message_text("❌ حدث خطأ أثناء جلب روابط هذا الفيلم.")


# ===================== تشغيل البوت =====================
def main() -> None:
    try:
        logger.info("🚀 بدء تشغيل بوت البحث التلقائي السريع...")
        
        application = (
            Application.builder()
            .token(TOKEN)
            .build()
        )

        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(CallbackQueryHandler(button_callback))

        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

    except Exception as e:
        logger.error(f"❌ فشل تشغيل البوت: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
