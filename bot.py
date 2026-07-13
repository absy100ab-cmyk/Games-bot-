"""
bot.py
البوت الرئيسي - بوت تنظيم بطولات الألعاب على تلغرام.

تشغيل البوت:
    1) حط التوكن كمتغير بيئة اسمه BOT_TOKEN (شوف .env.example)
    2) pip install -r requirements.txt
    3) python bot.py

ملاحظة أمنية: هذا الملف لا يحتوي على أي توكن. التوكن يُقرأ حصراً
من متغير البيئة BOT_TOKEN ولا يُطبع أو يُسجَّل بأي لوق.
"""

import logging
import os

from dotenv import load_dotenv
load_dotenv()  # يقرأ ملف .env المحلي إذا موجود (ما يأثر على السيرفرات اللي تحط المتغير مباشرة)

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ChatMemberHandler,
)

import database as db
import bracket

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """يتأكد إن الشخص اللي مرسل الأمر هو أدمن بالجروب (أو صاحب محادثة خاصة)."""
    chat = update.effective_chat
    user = update.effective_user
    if chat.type == "private":
        return True
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        return member.status in ("administrator", "creator")
    except Exception as e:
        logger.warning(f"Failed admin check: {e}")
        return False


def display_name(user) -> str:
    if user.username:
        return f"@{user.username}"
    return user.full_name


async def reply(update: Update, text: str, **kwargs):
    await update.effective_message.reply_text(
        text, parse_mode=ParseMode.MARKDOWN, **kwargs
    )


# ---------------------------------------------------------------------------
# أوامر أساسية
# ---------------------------------------------------------------------------

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎮 *أهلاً بيك ببوت تنظيم بطولات الألعاب!*\n\n"
        "أوامر البوت:\n"
        "• `/newtournament <اسم اللعبة>` — الأدمن يفتح بطولة جديدة\n"
        "• `/join` — سجل نفسك باللعبة\n"
        "• `/players` — شوف قائمة اللاعبين المسجلين\n"
        "• `/closereg` — الأدمن يقفل التسجيل ويبدأ القرعة\n"
        "• `/startbracket` — الأدمن يبدأ الجولة الأولى (نفس وظيفة closereg)\n"
        "• `/win @اسم_اللاعب` — الأدمن يسجل نتيجة مباراة (رد على رسالة اللاعب أو منشن)\n"
        "• `/bracket` — شوف حالة الجولة الحالية\n"
        "• `/cancel` — الأدمن يلغي البطولة الحالية\n"
        "• `/help` — عرض هذي القائمة"
    )
    await reply(update, text)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_cmd(update, context)


# ---------------------------------------------------------------------------
# فتح بطولة
# ---------------------------------------------------------------------------

async def new_tournament_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not await is_admin(update, context):
        await reply(update, "❌ بس الأدمن يقدر يفتح بطولة جديدة.")
        return

    if not context.args:
        await reply(update, "استخدم الأمر بهذا الشكل:\n`/newtournament Mobile Legends`")
        return

    existing = db.get_active_tournament(chat.id)
    if existing:
        await reply(
            update,
            f"⚠️ فيه بطولة مفتوحة حالياً *{existing['game_name']}*.\n"
            "لازم تلغيها بـ `/cancel` أو تخلصها قبل ما تفتح وحدة جديدة.",
        )
        return

    game_name = " ".join(context.args)
    tid = db.create_tournament(chat.id, game_name, update.effective_user.id)

    await reply(
        update,
        f"🏆 *تم فتح بطولة جديدة: {game_name}!*\n\n"
        "🔥 التسجيل مفتوح الحين! أرسل `/join` عشان تسجل اسمك.\n"
        "الأدمن يسكر التسجيل بأمر `/closereg` وقت ما يريد يبدي البطولة.",
    )
    logger.info(f"Tournament {tid} created in chat {chat.id}: {game_name}")


# ---------------------------------------------------------------------------
# تسجيل اللاعبين
# ---------------------------------------------------------------------------

async def join_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    t = db.get_active_tournament(chat.id)
    if not t:
        await reply(update, "ماكو بطولة مفتوحة حالياً بهذا الجروب. اطلب من الأدمن يفتح وحدة بـ `/newtournament`.")
        return

    if t["status"] != "registration":
        await reply(update, "⚠️ التسجيل مسكر، البطولة بدأت أو خلصت.")
        return

    added = db.add_player(t["id"], user.id, user.username, display_name(user))
    if not added:
        await reply(update, "✅ أنت مسجل بالفعل بهذي البطولة.")
        return

    players = db.get_players(t["id"])
    await reply(
        update,
        f"✅ {display_name(user)} انضم للبطولة!\n"
        f"👥 عدد اللاعبين المسجلين الحين: *{len(players)}*",
    )


async def players_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    t = db.get_active_tournament(chat.id)
    if not t:
        await reply(update, "ماكو بطولة مفتوحة حالياً.")
        return

    players = db.get_players(t["id"])
    if not players:
        await reply(update, "ماكو لاعبين مسجلين لحد الحين.")
        return

    lines = [f"👥 *لاعبين بطولة {t['game_name']}* ({len(players)}):\n"]
    for i, p in enumerate(players, start=1):
        lines.append(f"{i}. {p['display_name']}")
    await reply(update, "\n".join(lines))


# ---------------------------------------------------------------------------
# بدء البطولة (Bracket)
# ---------------------------------------------------------------------------

async def close_reg_and_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not await is_admin(update, context):
        await reply(update, "❌ بس الأدمن يقدر يبدي البطولة.")
        return

    t = db.get_active_tournament(chat.id)
    if not t:
        await reply(update, "ماكو بطولة مفتوحة حالياً.")
        return

    if t["status"] != "registration":
        await reply(update, "⚠️ البطولة بدأت بالفعل.")
        return

    players = db.get_players(t["id"])
    if len(players) < 2:
        await reply(update, "🚫 لازم يكون فيه لاعبين اثنين على الأقل عشان تبدأ البطولة.")
        return

    db.update_tournament_status(t["id"], "in_progress")
    bracket.generate_first_round(t["id"], [dict(p) for p in players])

    announcement = bracket.format_round_announcement(t["id"], 1, t["game_name"])
    await reply(update, "🔒 تم قفل التسجيل! هذي مواجهات الجولة الأولى:\n\n" + announcement)


# ---------------------------------------------------------------------------
# تسجيل نتيجة مباراة
# ---------------------------------------------------------------------------

async def win_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not await is_admin(update, context):
        await reply(update, "❌ بس الأدمن يقدر يسجل نتيجة المباراة.")
        return

    t = db.get_active_tournament(chat.id)
    if not t or t["status"] != "in_progress":
        await reply(update, "ماكو بطولة شغالة حالياً.")
        return

    # تحديد الفايز: إما رد (reply) على رسالة اللاعب، أو منشن @username كـ argument
    winner_user_id = None
    winner_name = None

    if update.message.reply_to_message:
        winner_user_id = update.message.reply_to_message.from_user.id
        winner_name = display_name(update.message.reply_to_message.from_user)
    elif context.args:
        uname = context.args[0].lstrip("@")
        # نبحث عنه بين اللاعبين المسجلين بالاسم
        players = db.get_active_players(t["id"])
        for p in players:
            if p["username"] and p["username"].lower() == uname.lower():
                winner_user_id = p["user_id"]
                winner_name = p["display_name"]
                break
        if winner_user_id is None:
            await reply(update, f"❌ ما لقيت لاعب باسم @{uname} بين المتأهلين بالجولة الحالية.")
            return
    else:
        await reply(
            update,
            "استخدم الأمر إما بالرد على رسالة اللاعب الفايز، أو بهذا الشكل:\n`/win @اسم_اللاعب`",
        )
        return

    round_number = t["round_number"]
    match = db.find_pending_match_for_player(t["id"], round_number, winner_user_id)
    if not match:
        await reply(update, "❌ ما لقيت مباراة معلقة بهذا اللاعب بالجولة الحالية.")
        return

    db.set_match_winner(match["id"], winner_user_id)
    db.increment_wins(t["id"], winner_user_id)

    loser_id = match["player2_id"] if match["player1_id"] == winner_user_id else match["player1_id"]
    if loser_id:
        db.eliminate_player(t["id"], loser_id)

    await reply(update, f"✅ تم تسجيل *{winner_name}* كفايز بالمباراة!")

    if bracket.round_is_complete(t["id"], round_number):
        result = bracket.generate_next_round(t["id"], round_number)
        if "champion" in result:
            champ = result["champion"]
            await reply(
                update,
                f"🎉🏆 *مبروك!* 🏆🎉\n\n"
                f"بطل بطولة *{t['game_name']}* هو: *{champ['display_name']}* 👑\n\n"
                "شكراً لكل المشاركين، بانتظار البطولة الجاية! 🔥",
            )
            db.update_tournament_status(t["id"], "finished")
        else:
            next_round = result["round"]
            announcement = bracket.format_round_announcement(t["id"], next_round, t["game_name"])
            await reply(update, "🔥 خلصت الجولة! هذي مواجهات الجولة الجاية:\n\n" + announcement)


async def bracket_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    t = db.get_active_tournament(chat.id)
    if not t:
        await reply(update, "ماكو بطولة مفتوحة حالياً.")
        return

    if t["status"] == "registration":
        players = db.get_players(t["id"])
        await reply(
            update,
            f"📋 بطولة *{t['game_name']}* بمرحلة التسجيل.\n"
            f"👥 عدد اللاعبين المسجلين: {len(players)}",
        )
        return

    status_text = bracket.format_bracket_status(t["id"], t["game_name"], t["round_number"])
    await reply(update, status_text)


# ---------------------------------------------------------------------------
# إلغاء البطولة
# ---------------------------------------------------------------------------

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not await is_admin(update, context):
        await reply(update, "❌ بس الأدمن يقدر يلغي البطولة.")
        return

    t = db.get_active_tournament(chat.id)
    if not t:
        await reply(update, "ماكو بطولة مفتوحة حالياً عشان تُلغى.")
        return

    db.update_tournament_status(t["id"], "cancelled")
    await reply(update, f"🚫 تم إلغاء بطولة *{t['game_name']}*.")


# ---------------------------------------------------------------------------
# تشغيل البوت
# ---------------------------------------------------------------------------

def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "ماكو متغير بيئة BOT_TOKEN! حط التوكن كمتغير بيئة قبل تشغيل البوت.\n"
            "مثال (لينكس/ماك): export BOT_TOKEN='xxxx'\n"
            "أو استخدم ملف .env (شوف .env.example)."
        )

    db.init_db()

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("newtournament", new_tournament_cmd))
    app.add_handler(CommandHandler("join", join_cmd))
    app.add_handler(CommandHandler("players", players_cmd))
    app.add_handler(CommandHandler("closereg", close_reg_and_start))
    app.add_handler(CommandHandler("startbracket", close_reg_and_start))
    app.add_handler(CommandHandler("win", win_cmd))
    app.add_handler(CommandHandler("bracket", bracket_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))

    logger.info("Bot is starting (polling mode)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
