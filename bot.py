import os
import sqlite3
import threading
import asyncio
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, ChatMemberHandler
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL = "@toiettagiadaxx"

app = Flask(__name__)
DB = "referrals.db"
db_lock = threading.Lock()

def db():
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        ref_link TEXT,
        referrals INTEGER DEFAULT 0,
        unlocked INTEGER DEFAULT 0
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS referred (
        inviter_id INTEGER,
        referred_id INTEGER,
        PRIMARY KEY(inviter_id, referred_id)
    )""")
    conn.commit()
    return conn

conn = db()

def get_user(user_id):
    with db_lock:
        row = conn.execute("SELECT user_id, ref_link, referrals, unlocked FROM users WHERE user_id=?",
                           (user_id,)).fetchone()
        return row

def save_link(user_id, link):
    with db_lock:
        conn.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (user_id,))
        conn.execute("UPDATE users SET ref_link=? WHERE user_id=?", (link, user_id))
        conn.commit()

def add_referral(inviter_id, referred_id):
    if inviter_id == referred_id:
        return False
    with db_lock:
        try:
            conn.execute("INSERT INTO referred(inviter_id, referred_id) VALUES(?,?)",
                         (inviter_id, referred_id))
            conn.execute("UPDATE users SET referrals=referrals+1 WHERE user_id=?", (inviter_id,))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    # Referral through the bot itself is not used; channel invite links are tracked
    # through ChatMemberUpdated below.
    row = get_user(user.id)
    if not row:
        with db_lock:
            conn.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (user.id,))
            conn.commit()

    if row and row[3]:
        text = "✅ Hai già completato i 3 inviti."
        keyboard = [[InlineKeyboardButton("🐷 ISCRIVITI A GIADA", url="https://t.me/toiettagiadaxx")]]
    else:
        link = row[1] if row else None
        if not link:
            try:
                invite = await context.bot.create_chat_invite_link(
                    chat_id=CHANNEL,
                    name=f"ref_{user.id}",
                    creates_join_request=False
                )
                link = invite.invite_link
                save_link(user.id, link)
            except Exception as e:
                await update.message.reply_text(
                    "Non riesco a creare il tuo link personale. Controlla che il bot sia amministratore del canale con il permesso di gestire i link d'invito."
                )
                print("create_chat_invite_link error:", e)
                return

        count = get_user(user.id)[2]
        text = (
            "🐷 BENVENUTO!\n\n"
            "Per sbloccare l'accesso devi far entrare 3 persone nel canale "
            "usando il tuo link personale.\n\n"
            f"👥 Inviti completati: {count}/3\n\n"
            "Condividi questo link con i tuoi amici:\n"
            f"{link}\n\n"
            "Quando avrai raggiunto 3/3, premi VERIFICA."
        )
        keyboard = [
            [InlineKeyboardButton("🔄 VERIFICA", callback_data="verify")],
            [InlineKeyboardButton("📤 APRI IL LINK", url=link)]
        ]

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    row = get_user(user_id)
    if not row:
        await q.edit_message_text("Apri prima il bot con /start.")
        return
    if row[2] >= 3:
        with db_lock:
            conn.execute("UPDATE users SET unlocked=1 WHERE user_id=?", (user_id,))
            conn.commit()
        await q.edit_message_text(
            "🎉 3/3 COMPLETATO!\n\nOra puoi iscriverti al canale:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🐷 ISCRIVITI A GIADA LA PORCELLINA",
                                     url="https://t.me/toiettagiadaxx")
            ]])
        )
    else:
        await q.edit_message_text(
            f"👥 Hai invitato {row[2]}/3 persone.\n\n"
            "Fai entrare altre persone tramite il tuo link personale, poi premi VERIFICA.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 VERIFICA", callback_data="verify")
            ]])
        )

async def channel_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cm = update.chat_member
    if not cm or not cm.invite_link:
        return

    new_status = cm.new_chat_member.status
    old_status = cm.old_chat_member.status
    # Count only a genuine new join, not a user who was already a member.
    joined = new_status in ("member", "administrator", "creator") and old_status in (
        "left", "kicked"
    )
    if not joined:
        return

    link_used = cm.invite_link.invite_link
    with db_lock:
        row = conn.execute("SELECT user_id FROM users WHERE ref_link=?", (link_used,)).fetchone()
    if not row:
        return

    inviter_id = row[0]
    referred_id = cm.new_chat_member.user.id
    added = add_referral(inviter_id, referred_id)
    if added:
        row2 = get_user(inviter_id)
        count = row2[2]
        try:
            if count >= 3:
                await context.bot.send_message(
                    inviter_id,
                    "🎉 Hai raggiunto 3/3!\n\n"
                    "Ora puoi iscriverti al canale:",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🐷 ISCRIVITI A GIADA LA PORCELLINA",
                                             url="https://t.me/toiettagiadaxx")
                    ]])
                )
            else:
                await context.bot.send_message(
                    inviter_id,
                    f"✅ Nuovo ingresso verificato!\n\n👥 Inviti completati: {count}/3"
                )
        except Exception as e:
            print("send_message error:", e)

async def error_handler(update, context):
    print("Bot error:", context.error)

async def run_bot_async():
    application = (
    Application.builder()
    .token(BOT_TOKEN)
    .bootstrap_retries(-1)
    .connect_timeout(30)
    .read_timeout(30)
    .write_timeout(30)
    .build()
)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(verify, pattern="^verify$"))
    application.add_handler(ChatMemberHandler(channel_member, ChatMemberHandler.CHAT_MEMBER))
    application.add_error_handler(error_handler)

    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    await asyncio.Event().wait()


def run_bot():
    asyncio.run(run_bot_async())

@app.get("/")
def health():
    return "Giada referral bot OK", 200

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
