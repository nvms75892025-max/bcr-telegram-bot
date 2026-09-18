import logging
import os
import sqlite3

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes


TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.getenv("ADMIN_ID", "6972892558"))
DB_PATH = os.getenv("DB_PATH", "users.db")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS approved_users "
            "(user_id INTEGER PRIMARY KEY, approved_at TEXT DEFAULT CURRENT_TIMESTAMP)"
        )


def is_approved(user_id: int) -> bool:
    with sqlite3.connect(DB_PATH) as connection:
        row = connection.execute(
            "SELECT 1 FROM approved_users WHERE user_id = ?", (user_id,)
        ).fetchone()
    return row is not None


def approve_user(user_id: int) -> None:
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            "INSERT OR IGNORE INTO approved_users(user_id) VALUES (?)", (user_id,)
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if is_approved(user.id):
        await update.message.reply_text(
            f"✅ Xin chào {user.full_name}\nTài khoản của bạn đã được kích hoạt."
        )
        return

    keyboard = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("Đồng ý", callback_data="consent_yes"),
            InlineKeyboardButton("Từ chối", callback_data="consent_no"),
        ]]
    )
    await update.message.reply_text(
        "🌇 CHÀO MỪNG BẠN ĐẾN VỚI BOT BÁO LỆNH BCR\n"
        "____________________________\n"
        "📎 Bot cung cấp thông tin hỗ trợ và hướng dẫn sử dụng. "
        "Vui lòng bảo mật thông tin cá nhân và tự chịu trách nhiệm với quyết định của mình.",
        reply_markup=keyboard,
    )


async def consent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "consent_no":
        await query.message.reply_text(
            "❌ BẠN ĐÃ TỪ CHỐI\nVUI LÒNG LIÊN HỆ ADMIN ĐỂ ĐƯỢC HƯỚNG DẪN"
        )
        return

    user = query.from_user
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Đăng nhập", callback_data="request_login")]]
    )
    await query.message.reply_text(
        f"Xin chào {user.full_name}\n"
        "____________________________\n"
        "📣 Vui lòng đăng nhập để được sử dụng.",
        reply_markup=keyboard,
    )


async def request_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = query.from_user

    if is_approved(user.id):
        await query.message.reply_text("✅ Tài khoản của bạn đã được kích hoạt.")
        return

    username = f"@{user.username}" if user.username else "Không có"
    admin_keyboard = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("✅ Kích hoạt", callback_data=f"approve:{user.id}"),
            InlineKeyboardButton("❌ Từ chối", callback_data=f"reject:{user.id}"),
        ]]
    )
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            "🔔 YÊU CẦU KÍCH HOẠT TÀI KHOẢN\n\n"
            f"Tên: {user.full_name}\n"
            f"Username: {username}\n"
            f"Telegram ID: {user.id}"
        ),
        reply_markup=admin_keyboard,
    )
    await query.message.reply_text("⏳ Đã gửi yêu cầu đến admin. Vui lòng chờ kích hoạt.")


async def admin_decision(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        await query.answer("Bạn không có quyền thực hiện thao tác này.", show_alert=True)
        return

    action, raw_user_id = query.data.split(":", 1)
    user_id = int(raw_user_id)

    if action == "approve":
        approve_user(user_id)
        await context.bot.send_message(
            chat_id=user_id,
            text="✅ TÀI KHOẢN ĐÃ ĐƯỢC ADMIN KÍCH HOẠT THÀNH CÔNG.",
        )
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(f"✅ Đã kích hoạt ID {user_id}.")
    else:
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ YÊU CẦU ĐĂNG NHẬP ĐÃ BỊ TỪ CHỐI.\nVUI LÒNG LIÊN HỆ ADMIN.",
        )
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(f"❌ Đã từ chối ID {user_id}.")


def main() -> None:
    init_db()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(consent, pattern="^consent_(yes|no)$"))
    application.add_handler(CallbackQueryHandler(request_login, pattern="^request_login$"))
    application.add_handler(
        CallbackQueryHandler(admin_decision, pattern="^(approve|reject):[0-9]+$")
    )
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
