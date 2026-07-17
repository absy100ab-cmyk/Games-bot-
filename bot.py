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

# ===================== دالة البحث في مواقع الأفلام =====================
def search_movies_online(query: str) -> list:
    """
    البحث عن الأفلام والمسلسلات في موقع أكوام / سيما كلوب بشكل مباشر 
    وتحليل نتائج البحث لجلب العناوين وروابط صفحاتها.
    """
    results = []
    try:
        # قمنا باستخدام محرّك بحث موقع أكوام (Akoam) كمثال قوي ومستقر ومفتوح للبحث
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://ak.sv/search?q={encoded_query}"
        
        response = requests.get(search_url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return results
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # البحث عن كروت الأفلام في صفحة نتائج البحث
        # (ملاحظة: قد تحتاج لتحديث الـ selectors إذا تغير تصميم الموقع المستهدف)
        movie_cards = soup.find_all('div', class_='entry-box') or soup.find_all('div', class_='widget-body')
        
        for card in movie_cards[:6]:  # جلب أول 6 نتائج لتفادي بطء البوت
            title_tag = card.find('a') or card.find('h3')
            link_tag = card.find('a', href=True)
            
            if title_tag and link_tag:
                title = title_tag.text.strip()
                link = link_tag['href']
                
                # تصفية العناوين الفارغة والتأكد من جودة الرابط
                if title and link.startswith('http'):
                    results.append({
                        'title': title,
                        'link': link
                    })
    except Exception as e:
        logger.error(f"خطأ أثناء البحث في موقع الأفلام: {e}")
    
    return results

# ===================== دالة جلب روابط التشغيل المباشرة =====================
def extract_stream_links(movie_url: str) -> list:
    """
    الدخول لصفحة الفيلم واستخراج روابط التحميل أو المشاهدة المباشرة
    """
    links = []
    try:
        response = requests.get(movie_url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # البحث عن أزرار التحميل أو روابط الـ watch/download المباشرة داخل الصفحة
            # نقوم بالبحث عن أي رابط يحتوي على كلمات تحميل أو مشاهدة دلالية
            for a_tag in soup.find_all('a', href=True):
                text = a_tag.text.strip().lower()
                href = a_tag['href']
                if 'download' in text or 'تحميل' in text or 'watch' in text or 'مشاهدة' in text:
                    if href.startswith('http'):
                        links.append({
                            'label': a_tag.text.strip() or "رابط مباشر",
                            'url': href
                        })
    except Exception as e:
        logger.error(f"خطأ في استخراج الروابط المباشرة: {e}")
    return links[:3] # جلب أفضل 3 روابط فقط

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
            # نقوم بحفظ روابط الأفلام مؤقتاً في الـ user_data للوصول إليها عند الضغط على الزر
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
                
                # إضافة زر العودة أو البحث الجديد
                reply_markup = InlineKeyboardMarkup(buttons)
                await query.edit_message_text(msg, reply_markup=reply_markup, parse_mode='MarkdownV2')
            else:
                # إذا لم نجد روابط مباشرة، نرسل له رابط صفحة الفيلم مباشرة ليدخل ويشاهد منها
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
