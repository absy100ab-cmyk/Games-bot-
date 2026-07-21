import subprocess
import sys
import os

# ================ تثبيت المكتبات تلقائياً ================
def install_requirements():
    packages = [
        "python-telegram-bot==20.7",
        "Pillow==10.2.0",
        "moviepy==1.0.3"
    ]
    
    for package in packages:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package, "--quiet"])
        except subprocess.CalledProcessError:
            print(f"⚠️ فشل تثبيت {package}")

install_requirements()

# ================ استيراد المكتبات ================
import io
import asyncio
import logging
import tempfile
from typing import Union
from PIL import Image, ImageDraw, ImageFont, ImageSequence
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ParseMode

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ================ الإعدادات ================
TOKEN = os.getenv("BOT_TOKEN")
DEVELOPER = "@B43lB"

if not TOKEN:
    logger.error("❌ لم يتم العثور على BOT_TOKEN في متغيرات البيئة!")
    sys.exit(1)

# ================ إنشاء خط افتراضي للطوارئ ================
def get_font(size=16, bold=False):
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    
    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except:
            continue
    
    return ImageFont.load_default()

# ================ أوامر البوت ================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎨 *مرحباً بك في بوت صنع الملصقات!*\n\n"
        "📌 *الأوامر المتاحة:*\n"
        "/sticker - تحويل صورة إلى ملصق شفاف\n"
        "/circle - ملصق دائري\n"
        "/text - إضافة نص على ملصق\n"
        "/gif - تحويل فيديو إلى GIF\n"
        "/animate - تحويل صورة إلى GIF متحرك\n"
        "/dev - معلومات المطور\n\n"
        "📤 *أرسل صورة* لتجربة الأوامر عليها مباشرة",
        parse_mode=ParseMode.MARKDOWN
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔍 *طريقة الاستخدام:*\n\n"
        "1️⃣ أرسل صورة أو فيديو للبوت\n"
        "2️⃣ استخدم الأوامر لتحويلها\n\n"
        "• /sticker مع صورة = ملصق 512x512\n"
        "• /circle مع صورة = ملصق دائري\n"
        "• /text <نص> مع صورة = ملصق مكتوب\n"
        "• /gif مع فيديو = GIF متحرك\n"
        "• /animate مع صورة = تأثير حركي\n"
        "/dev - معلومات المطور",
        parse_mode=ParseMode.MARKDOWN
    )

async def dev_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"👨‍💻 *معلومات المطور*\n\n"
        f"• المطور: {DEVELOPER}\n"
        f"• البوت مفتوح المصدر\n"
        f"• للتواصل: {DEVELOPER}\n\n"
        "⚡ *شكراً لاستخدامك البوت!*",
        parse_mode=ParseMode.MARKDOWN
    )

# ================ معالجة الصور ================
async def process_sticker(image_bytes: bytes, size: int = 512) -> io.BytesIO:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    img.thumbnail((size, size), Image.Resampling.LANCZOS)
    
    sticker = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    x = (size - img.width) // 2
    y = (size - img.height) // 2
    sticker.paste(img, (x, y), img)
    
    output = io.BytesIO()
    sticker.save(output, format="WEBP")
    output.seek(0)
    return output

async def process_circle_sticker(image_bytes: bytes) -> io.BytesIO:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    img.thumbnail((512, 512), Image.Resampling.LANCZOS)
    
    mask = Image.new("L", (512, 512), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, 511, 511), fill=255)
    
    sticker = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    x = (512 - img.width) // 2
    y = (512 - img.height) // 2
    sticker.paste(img, (x, y))
    
    result = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    result.paste(sticker, (0, 0), mask)
    
    output = io.BytesIO()
    result.save(output, format="WEBP")
    output.seek(0)
    return output

async def process_text_sticker(image_bytes: bytes, text: str) -> io.BytesIO:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    img.thumbnail((512, 400), Image.Resampling.LANCZOS)
    
    sticker = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    x = (512 - img.width) // 2
    y = 20
    sticker.paste(img, (x, y), img)
    
    draw = ImageDraw.Draw(sticker)
    font = get_font(40, bold=True)
    small_font = get_font(12)
    
    # إضافة النص الرئيسي
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_x = (512 - text_width) // 2
    text_y = 440
    
    draw.rectangle([(text_x-10, text_y-5), (text_x+text_width+10, text_y+45)], fill=(255,255,255,200))
    draw.text((text_x, text_y), text, font=font, fill=(0,0,0,255))
    
    # إضافة حقوق المطور
    dev_text = f"@{DEVELOPER.replace('@', '')}"
    dev_bbox = draw.textbbox((0, 0), dev_text, font=small_font)
    dev_width = dev_bbox[2] - dev_bbox[0]
    draw.text((512-dev_width-5, 495), dev_text, font=small_font, fill=(255,255,255,150))
    
    output = io.BytesIO()
    sticker.save(output, format="WEBP")
    output.seek(0)
    return output

# ================ معالجة GIF ================
async def process_gif(image_bytes: bytes) -> io.BytesIO:
    img = Image.open(io.BytesIO(image_bytes))
    frames = []
    
    font = get_font(10)
    dev_text = f"@{DEVELOPER.replace('@', '')}"
    
    if getattr(img, "is_animated", False):
        for frame in ImageSequence.Iterator(img):
            frame = frame.convert("RGBA")
            frame.thumbnail((320, 320), Image.Resampling.LANCZOS)
            
            draw = ImageDraw.Draw(frame)
            draw.text((5, frame.height-15), dev_text, font=font, fill=(255,255,255,150))
            
            frames.append(frame.copy())
    else:
        img = img.convert("RGBA")
        img.thumbnail((320, 320), Image.Resampling.LANCZOS)
        
        for _ in range(10):
            draw = ImageDraw.Draw(img)
            draw.text((5, img.height-15), dev_text, font=font, fill=(255,255,255,150))
            frames.append(img.copy())
    
    output = io.BytesIO()
    frames[0].save(output, format="GIF", save_all=True, append_images=frames[1:], duration=100, loop=0)
    output.seek(0)
    return output

async def process_video_to_gif(video_bytes: bytes) -> io.BytesIO:
    try:
        from moviepy.editor import VideoFileClip
        
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_video:
            tmp_video.write(video_bytes)
            video_path = tmp_video.name
        
        try:
            clip = VideoFileClip(video_path)
            if clip.duration > 5:
                clip = clip.subclip(0, 5)
            
            clip = clip.resize(width=320)
            
            output = io.BytesIO()
            clip.write_gif(output, fps=10, program="ffmpeg" if self._check_ffmpeg() else "imageio")
            output.seek(0)
            clip.close()
            return output
        finally:
            os.unlink(video_path)
    except ImportError:
        # إذا فشل استيراد moviepy، نرجع GIF بسيط
        return await process_gif(video_bytes)

# ================ معالجات الرسائل ================
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    image_bytes = await file.download_as_bytearray()
    context.user_data["last_image"] = bytes(image_bytes)
    context.user_data["is_video"] = False
    
    await update.message.reply_text(
        "✅ الصورة محفوظة! استخدم الأوامر:\n"
        "/sticker | /circle | /text <نص> | /animate"
    )

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video
    file = await context.bot.get_file(video.file_id)
    video_bytes = await file.download_as_bytearray()
    context.user_data["last_video"] = bytes(video_bytes)
    context.user_data["is_video"] = True
    
    await update.message.reply_text("✅ الفيديو محفوظ! استخدم /gif لتحويله")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    
    if doc.mime_type and (doc.mime_type.startswith("image/") or doc.mime_type.startswith("video/")):
        file = await context.bot.get_file(doc.file_id)
        file_bytes = await file.download_as_bytearray()
        
        if doc.mime_type.startswith("image/"):
            context.user_data["last_image"] = bytes(file_bytes)
            context.user_data["is_video"] = False
            await update.message.reply_text("✅ الصورة محفوظة! استخدم /sticker | /circle | /text")
        else:
            context.user_data["last_video"] = bytes(file_bytes)
            context.user_data["is_video"] = True
            await update.message.reply_text("✅ الفيديو محفوظ! استخدم /gif")

# ================ أوامر التحويل ================
async def sticker_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "last_image" not in context.user_data:
        await update.message.reply_text("⚠️ أرسل صورة أولاً!")
        return
    
    processing_msg = await update.message.reply_text("⏳ جاري صنع الملصق...")
    try:
        sticker = await process_sticker(context.user_data["last_image"])
        await update.message.reply_sticker(sticker=sticker)
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {str(e)}")
    finally:
        await processing_msg.delete()

async def circle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "last_image" not in context.user_data:
        await update.message.reply_text("⚠️ أرسل صورة أولاً!")
        return
    
    processing_msg = await update.message.reply_text("⏳ جاري صنع الملصق الدائري...")
    try:
        sticker = await process_circle_sticker(context.user_data["last_image"])
        await update.message.reply_sticker(sticker=sticker)
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {str(e)}")
    finally:
        await processing_msg.delete()

async def text_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "last_image" not in context.user_data:
        await update.message.reply_text("⚠️ أرسل صورة أولاً!")
        return
    
    text = " ".join(context.args) if context.args else "مرحباً 👋"
    processing_msg = await update.message.reply_text("⏳ جاري إضافة النص...")
    try:
        sticker = await process_text_sticker(context.user_data["last_image"], text)
        await update.message.reply_sticker(sticker=sticker)
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {str(e)}")
    finally:
        await processing_msg.delete()

async def gif_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("is_video"):
        processing_msg = await update.message.reply_text("⏳ جاري تحويل الفيديو إلى GIF...")
        try:
            gif = await process_video_to_gif(context.user_data["last_video"])
            caption = f"🎬 تم التحويل بواسطة {DEVELOPER}"
            await update.message.reply_animation(animation=gif, caption=caption)
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ: {str(e)}")
        finally:
            await processing_msg.delete()
    elif "last_image" in context.user_data:
        processing_msg = await update.message.reply_text("⏳ جاري إنشاء GIF...")
        try:
            gif = await process_gif(context.user_data["last_image"])
            caption = f"🎬 تم الإنشاء بواسطة {DEVELOPER}"
            await update.message.reply_animation(animation=gif, caption=caption)
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ: {str(e)}")
        finally:
            await processing_msg.delete()
    else:
        await update.message.reply_text("⚠️ أرسل صورة أو فيديو أولاً!")

async def animate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "last_image" not in context.user_data:
        await update.message.reply_text("⚠️ أرسل صورة أولاً!")
        return
    
    processing_msg = await update.message.reply_text("⏳ جاري صنع الحركة...")
    
    try:
        img = Image.open(io.BytesIO(context.user_data["last_image"])).convert("RGBA")
        img.thumbnail((320, 320), Image.Resampling.LANCZOS)
        
        font = get_font(10)
        dev_text = f"@{DEVELOPER.replace('@', '')}"
        
        frames = []
        for angle in range(0, 360, 36):
            rotated = img.rotate(angle, expand=False, resample=Image.Resampling.BICUBIC)
            
            draw = ImageDraw.Draw(rotated)
            draw.text((5, rotated.height-15), dev_text, font=font, fill=(255,255,255,150))
            
            frames.append(rotated.copy())
        
        output = io.BytesIO()
        frames[0].save(output, format="GIF", save_all=True, append_images=frames[1:], duration=80, loop=0)
        output.seek(0)
        
        caption = f"🔄 تم الإنشاء بواسطة {DEVELOPER}"
        await update.message.reply_animation(animation=output, caption=caption)
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {str(e)}")
    finally:
        await processing_msg.delete()

# ================ التشغيل ================
def main():
    logger.info(f"🚀 بدء تشغيل بوت {DEVELOPER}...")
    
    app = Application.builder().token(TOKEN).build()
    
    # الأوامر
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("dev", dev_command))
    app.add_handler(CommandHandler("sticker", sticker_command))
    app.add_handler(CommandHandler("circle", circle_command))
    app.add_handler(CommandHandler("text", text_command))
    app.add_handler(CommandHandler("gif", gif_command))
    app.add_handler(CommandHandler("animate", animate_command))
    
    # استقبال الصور والفيديوهات
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    app.add_handler(MessageHandler(filters.Document.IMAGE | filters.Document.VIDEO, handle_document))
    
    logger.info("✅ البوت جاهز للعمل...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
