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
            subprocess.check_call([sys.executable, "-m", "pip", "install", package, "--quiet", "--no-cache-dir"])
            print(f"✅ تم تثبيت {package}")
        except:
            print(f"⚠️ فشل تثبيت {package}")

install_requirements()

# ================ استيراد المكتبات ================
import io
import asyncio
import logging
import tempfile
import signal
from PIL import Image, ImageDraw, ImageFont, ImageSequence
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ParseMode

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ================ الإعدادات ================
TOKEN = os.getenv("BOT_TOKEN")
DEVELOPER = "@B43lB"

if not TOKEN:
    logger.error("❌ لم يتم العثور على BOT_TOKEN!")
    sys.exit(1)

logger.info(f"✅ تم العثور على التوكن: {TOKEN[:10]}...")
logger.info(f"👨‍💻 المطور: {DEVELOPER}")

# ================ أوامر البوت ================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🎨 *مرحباً بك في بوت صنع الملصقات!*\n\n"
        f"📌 *الأوامر المتاحة:*\n"
        f"/sticker - تحويل صورة إلى ملصق\n"
        f"/circle - ملصق دائري\n"
        f"/text - إضافة نص على ملصق\n"
        f"/gif - تحويل فيديو إلى GIF\n"
        f"/animate - تأثير حركي\n"
        f"/dev - معلومات المطور\n\n"
        f"📤 *أرسل صورة* لتجربة الأوامر",
        parse_mode=ParseMode.MARKDOWN
    )

async def dev_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"👨‍💻 *المطور:* {DEVELOPER}\n"
        f"✅ *الحالة:* شغال\n"
        f"📦 *الإصدار:* 2.0",
        parse_mode=ParseMode.MARKDOWN
    )

# ================ معالجة الصور ================
async def process_sticker(image_bytes: bytes) -> io.BytesIO:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    img.thumbnail((512, 512), Image.Resampling.LANCZOS)
    
    sticker = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    x = (512 - img.width) // 2
    y = (512 - img.height) // 2
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
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_x = (512 - text_width) // 2
    text_y = 440
    
    draw.rectangle([(text_x-10, text_y-5), (text_x+text_width+10, text_y+45)], fill=(255,255,255,200))
    draw.text((text_x, text_y), text, font=font, fill=(0,0,0,255))
    
    dev_text = f"@{DEVELOPER.replace('@', '')}"
    draw.text((5, 5), dev_text, font=small_font, fill=(255,255,255,150))
    
    output = io.BytesIO()
    sticker.save(output, format="WEBP")
    output.seek(0)
    return output

async def process_gif(image_bytes: bytes) -> io.BytesIO:
    img = Image.open(io.BytesIO(image_bytes))
    frames = []
    
    if getattr(img, "is_animated", False):
        for frame in ImageSequence.Iterator(img):
            frame = frame.convert("RGBA")
            frame.thumbnail((320, 320), Image.Resampling.LANCZOS)
            frames.append(frame.copy())
    else:
        img = img.convert("RGBA")
        img.thumbnail((320, 320), Image.Resampling.LANCZOS)
        for _ in range(10):
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
        
        clip = VideoFileClip(video_path)
        if clip.duration > 5:
            clip = clip.subclip(0, 5)
        
        clip = clip.resize(width=320)
        
        output = io.BytesIO()
        clip.write_gif(output, fps=10, program="imageio")
        output.seek(0)
        clip.close()
        os.unlink(video_path)
        return output
    except:
        return await process_gif(video_bytes)

# ================ معالجات الرسائل ================
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    image_bytes = await file.download_as_bytearray()
    context.user_data["last_image"] = bytes(image_bytes)
    context.user_data["is_video"] = False
    
    await update.message.reply_text(
        "✅ الصورة محفوظة!\n"
        "/sticker | /circle | /text نص | /animate"
    )

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video
    file = await context.bot.get_file(video.file_id)
    video_bytes = await file.download_as_bytearray()
    context.user_data["last_video"] = bytes(video_bytes)
    context.user_data["is_video"] = True
    
    await update.message.reply_text("✅ الفيديو محفوظ! استخدم /gif")

# ================ أوامر التحويل ================
async def sticker_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "last_image" not in context.user_data:
        await update.message.reply_text("⚠️ أرسل صورة أولاً!")
        return
    
    msg = await update.message.reply_text("⏳ جاري صنع الملصق...")
    sticker = await process_sticker(context.user_data["last_image"])
    await update.message.reply_sticker(sticker=sticker)
    await msg.delete()

async def circle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "last_image" not in context.user_data:
        await update.message.reply_text("⚠️ أرسل صورة أولاً!")
        return
    
    msg = await update.message.reply_text("⏳ جاري الصنع...")
    sticker = await process_circle_sticker(context.user_data["last_image"])
    await update.message.reply_sticker(sticker=sticker)
    await msg.delete()

async def text_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "last_image" not in context.user_data:
        await update.message.reply_text("⚠️ أرسل صورة أولاً!")
        return
    
    text = " ".join(context.args) if context.args else "مرحباً 👋"
    msg = await update.message.reply_text("⏳ جاري الإضافة...")
    sticker = await process_text_sticker(context.user_data["last_image"], text)
    await update.message.reply_sticker(sticker=sticker)
    await msg.delete()

async def gif_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("is_video"):
        msg = await update.message.reply_text("⏳ جاري تحويل الفيديو...")
        gif = await process_video_to_gif(context.user_data["last_video"])
        await update.message.reply_animation(animation=gif, caption=f"🎬 {DEVELOPER}")
        await msg.delete()
    elif "last_image" in context.user_data:
        msg = await update.message.reply_text("⏳ جاري إنشاء GIF...")
        gif = await process_gif(context.user_data["last_image"])
        await update.message.reply_animation(animation=gif, caption=f"🎬 {DEVELOPER}")
        await msg.delete()
    else:
        await update.message.reply_text("⚠️ أرسل صورة أو فيديو أولاً!")

async def animate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "last_image" not in context.user_data:
        await update.message.reply_text("⚠️ أرسل صورة أولاً!")
        return
    
    msg = await update.message.reply_text("⏳ جاري صنع الحركة...")
    
    img = Image.open(io.BytesIO(context.user_data["last_image"])).convert("RGBA")
    img.thumbnail((320, 320), Image.Resampling.LANCZOS)
    
    frames = []
    for angle in range(0, 360, 36):
        rotated = img.rotate(angle, expand=False, resample=Image.Resampling.BICUBIC)
        frames.append(rotated.copy())
    
    output = io.BytesIO()
    frames[0].save(output, format="GIF", save_all=True, append_images=frames[1:], duration=80, loop=0)
    output.seek(0)
    
    await update.message.reply_animation(animation=output, caption=f"🔄 {DEVELOPER}")
    await msg.delete()

# ================ التشغيل الآمن ================
def main():
    logger.info("🚀 بدء تشغيل البوت...")
    
    # بناء التطبيق
    app = Application.builder().token(TOKEN).build()
    
    # إضافة الأوامر
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("dev", dev_command))
    app.add_handler(CommandHandler("sticker", sticker_command))
    app.add_handler(CommandHandler("circle", circle_command))
    app.add_handler(CommandHandler("text", text_command))
    app.add_handler(CommandHandler("gif", gif_command))
    app.add_handler(CommandHandler("animate", animate_command))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    
    logger.info("✅ البوت جاهز للعمل...")
    
    # تشغيل البوت مع معالجة الإيقاف
    try:
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            close_loop=False
        )
    except KeyboardInterrupt:
        logger.info("👋 تم إيقاف البوت")
    except Exception as e:
        logger.error(f"❌ خطأ: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
