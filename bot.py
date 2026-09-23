import logging
import os
import random
import sqlite3
from html import escape

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

TOKEN = os.environ["BOT_TOKEN"]
SUPER_ADMIN_ID = int(os.getenv("ADMIN_ID", "6972892558"))
DB_PATH = os.getenv("DB_PATH", "users.db")
CHANNEL_URL = "https://t.me/BOT10L"
CHECK_COST = 1

TEAM_ADMINS = {
    "bot6574": 7169392055,
    "bot9709": 7304476892,
    "bot6401": 7112838213,
    "bot7603": 7913559561,
    "bot7579": 8148420065,
}

TABLES = [f"BÀN {i}" for i in range(1, 10)] + [f"C{i:02d}" for i in range(1, 16)]

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT NOT NULL DEFAULT '',
                username TEXT,
                team_code TEXT,
                approved INTEGER NOT NULL DEFAULT 0,
                balance INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                approved_at TEXT
            )
            """
        )
        old_table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='approved_users'"
        ).fetchone()
        if old_table:
            connection.execute(
                """
                INSERT OR IGNORE INTO users(user_id, approved, approved_at)
                SELECT user_id, 1, approved_at FROM approved_users
                """
            )


def get_user(user_id: int):
    with connect() as connection:
        return connection.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()


def save_user(user, team_code: str | None = None) -> None:
    with connect() as connection:
        current = connection.execute(
            "SELECT team_code FROM users WHERE user_id = ?", (user.id,)
        ).fetchone()
        locked_team = current["team_code"] if current and current["team_code"] else team_code
        connection.execute(
            """
            INSERT INTO users(user_id, full_name, username, team_code)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                full_name = excluded.full_name,
                username = excluded.username,
                team_code = COALESCE(users.team_code, excluded.team_code)
            """,
            (user.id, user.full_name, user.username or None, locked_team),
        )


def is_approved(user_id: int) -> bool:
    row = get_user(user_id)
    return bool(row and row["approved"])


def set_approved(user_id: int) -> None:
    with connect() as connection:
        connection.execute(
            "UPDATE users SET approved = 1, approved_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (user_id,),
        )


def change_balance(user_id: int, amount: int) -> int | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT balance FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not row or row["balance"] + amount < 0:
            return None
        balance = row["balance"] + amount
        connection.execute(
            "UPDATE users SET balance = ? WHERE user_id = ?", (balance, user_id)
        )
        return balance


def admin_team(admin_id: int) -> str | None:
    return next((code for code, value in TEAM_ADMINS.items() if value == admin_id), None)


def can_manage(admin_id: int, user_row) -> bool:
    if admin_id == SUPER_ADMIN_ID:
        return True
    team = admin_team(admin_id)
    return team is not None and team == user_row["team_code"]


def channel_keyboard(extra_rows=None) -> InlineKeyboardMarkup:
    rows = list(extra_rows or [])
    rows.append([InlineKeyboardButton("📢 THAM GIA KÊNH THÔNG BÁO", url=CHANNEL_URL)])
    return InlineKeyboardMarkup(rows)


def table_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(name, callback_data=f"table:{name}") for name in TABLES[i:i + 3]]
        for i in range(0, len(TABLES), 3)
    ])


def number_keyboard(prefix: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(str(n), callback_data=f"{prefix}:{n}") for n in range(i, i + 3)]
        for i in range(0, 9, 3)
    ]
    rows.append([InlineKeyboardButton("9", callback_data=f"{prefix}:9")])
    return InlineKeyboardMarkup(rows)


async def show_home(message, user_id: int, full_name: str) -> None:
    row = get_user(user_id)
    balance = row["balance"] if row else 0
    await message.reply_text(
        f"👤 TÊN: {full_name}\n💰 SỐ DƯ: {balance} xu",
        reply_markup=channel_keyboard(
            [[InlineKeyboardButton("🔍 BẮT ĐẦU KIỂM TRA", callback_data="begin_check")]]
        ),
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    requested_team = context.args[0].lower() if context.args else None
    team_code = requested_team if requested_team in TEAM_ADMINS else None
    save_user(user, team_code)
    row = get_user(user.id)

    if is_approved(user.id):
        await show_home(update.message, user.id, user.full_name)
        return
    if not row["team_code"]:
        await update.message.reply_text(
            "⚠️ LINK ĐĂNG NHẬP KHÔNG HỢP LỆ.\n"
            "Vui lòng liên hệ người giới thiệu để nhận đúng link của team."
        )
        return

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("Đồng ý", callback_data="consent_yes"),
        InlineKeyboardButton("Từ chối", callback_data="consent_no"),
    ]])
    await update.message.reply_text(
        "🌇 CHÀO MỪNG BẠN ĐẾN VỚI BOT BÁO LỆNH BCR\n"
        "____________________________\n"
        "📎 HỖ TRỢ PHÂN TÍCH VÀ BÁO LỆNH\n\n"
        "🔒 THÔNG TIN NGƯỜI DÙNG ĐƯỢC BẢO MẬT. VUI LÒNG SỬ DỤNG CÔNG CỤ "
        "THEO HƯỚNG DẪN CỦA ĐỘI NGŨ ADMIN ĐỂ HẠN CHẾ RỦI RO.",
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
    await query.message.reply_text(
        f"Xin chào {query.from_user.full_name}\n"
        "____________________________\n📣 Vui lòng đăng nhập để được sử dụng.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Đăng nhập", callback_data="request_login")
        ]]),
    )


async def request_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = query.from_user
    save_user(user)
    row = get_user(user.id)
    if is_approved(user.id):
        await show_home(query.message, user.id, user.full_name)
        return
    if not row or not row["team_code"]:
        await query.message.reply_text("⚠️ Không xác định được team. Vui lòng mở lại đúng link giới thiệu.")
        return

    username = f"@{user.username}" if user.username else "Không có"
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Kích hoạt", callback_data=f"approve:{user.id}"),
        InlineKeyboardButton("❌ Từ chối", callback_data=f"reject:{user.id}"),
    ]])
    text = (
        "🔔 YÊU CẦU KÍCH HOẠT TÀI KHOẢN\n\n"
        f"Team: {row['team_code'].upper()}\n"
        f"Tên: {escape(user.full_name)}\n"
        f"Username: {escape(username)}\n"
        f"Telegram ID: <code>{user.id}</code>"
    )
    for admin_id in {TEAM_ADMINS[row["team_code"]], SUPER_ADMIN_ID}:
        try:
            await context.bot.send_message(
                chat_id=admin_id, text=text, parse_mode="HTML", reply_markup=keyboard
            )
        except Exception:
            logging.exception("Không thể gửi yêu cầu đến admin %s", admin_id)
    await query.message.reply_text("⏳ Đã gửi yêu cầu đến admin. Vui lòng chờ kích hoạt.")


async def admin_decision(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    action, raw_user_id = query.data.split(":", 1)
    user_id = int(raw_user_id)
    row = get_user(user_id)
    if not row or not can_manage(query.from_user.id, row):
        await query.answer("Bạn không có quyền xử lý khách này.", show_alert=True)
        return
    await query.answer()
    if action == "approve":
        set_approved(user_id)
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                "✅ TÀI KHOẢN ĐÃ ĐƯỢC ADMIN KÍCH HOẠT THÀNH CÔNG.\n\n"
                "💰 VUI LÒNG LIÊN HỆ ADMIN ĐỂ NẠP XU VÀO TÀI KHOẢN."
            ),
            reply_markup=channel_keyboard(),
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


def parse_amount(context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        return None
    try:
        return int(context.args[0]), int(context.args[1])
    except ValueError:
        return None


async def napxu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    parsed = parse_amount(context)
    if not parsed or parsed[1] <= 0:
        await update.message.reply_text("Cách dùng: /napxu TELEGRAM_ID SO_XU")
        return
    user_id, amount = parsed
    row = get_user(user_id)
    if not row or not can_manage(update.effective_user.id, row):
        await update.message.reply_text("❌ Không tìm thấy khách hoặc bạn không có quyền quản lý.")
        return
    balance = change_balance(user_id, amount)
    await update.message.reply_text(f"✅ Đã nạp {amount} xu cho {row['full_name']}. Số dư: {balance} xu.")
    await context.bot.send_message(
        chat_id=user_id,
        text=f"✅ NẠP XU THÀNH CÔNG\n\n👤 TÊN: {row['full_name']}\n💰 SỐ DƯ: {balance} xu",
        reply_markup=channel_keyboard(
            [[InlineKeyboardButton("🔍 BẮT ĐẦU KIỂM TRA", callback_data="begin_check")]]
        ),
    )


async def truxu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    parsed = parse_amount(context)
    if not parsed or parsed[1] <= 0:
        await update.message.reply_text("Cách dùng: /truxu TELEGRAM_ID SO_XU")
        return
    user_id, amount = parsed
    row = get_user(user_id)
    if not row or not can_manage(update.effective_user.id, row):
        await update.message.reply_text("❌ Không tìm thấy khách hoặc bạn không có quyền quản lý.")
        return
    balance = change_balance(user_id, -amount)
    await update.message.reply_text(
        "❌ Số dư không đủ để trừ." if balance is None
        else f"✅ Đã trừ {amount} xu. Số dư mới: {balance} xu."
    )


async def kiemtra_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("Cách dùng: /kiemtra TELEGRAM_ID")
        return
    row = get_user(int(context.args[0]))
    if not row or not can_manage(update.effective_user.id, row):
        await update.message.reply_text("❌ Không tìm thấy khách hoặc bạn không có quyền quản lý.")
        return
    username = f"@{row['username']}" if row["username"] else "Không có"
    await update.message.reply_text(
        f"👤 {row['full_name']}\nUsername: {username}\nID: {row['user_id']}\n"
        f"Team: {row['team_code']}\nKích hoạt: {'Có' if row['approved'] else 'Chưa'}\n"
        f"Số dư: {row['balance']} xu"
    )


async def sodu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    row = get_user(update.effective_user.id)
    await update.message.reply_text(f"💰 SỐ DƯ: {row['balance'] if row else 0} xu")


async def begin_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_approved(query.from_user.id):
        await query.message.reply_text("❌ Tài khoản chưa được kích hoạt.")
        return
    await query.message.reply_text("✨ VUI LÒNG CHỌN SỐ BÀN", reply_markup=table_keyboard())


async def choose_table(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    context.user_data["table"] = query.data.split(":", 1)[1]
    await query.message.reply_text("✨ CHỌN CÁI", reply_markup=number_keyboard("cai"))


async def choose_cai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    context.user_data["cai"] = int(query.data.split(":", 1)[1])
    await query.message.reply_text("✨ CHỌN CON", reply_markup=number_keyboard("con"))


async def choose_con(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    context.user_data["con"] = int(query.data.split(":", 1)[1])
    await query.message.reply_text(
        f"📋 Bàn: {context.user_data.get('table', '-')}\n"
        f"Cái: {context.user_data.get('cai', '-')} | Con: {context.user_data['con']}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔍 KIỂM TRA (1 XU)", callback_data="run_check")
        ]]),
    )


async def run_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    row = get_user(query.from_user.id)
    if not row or not row["approved"]:
        await query.message.reply_text("❌ Tài khoản chưa được kích hoạt.")
        return
    balance = change_balance(query.from_user.id, -CHECK_COST)
    if balance is None:
        await query.message.reply_text(
            "❌ SỐ DƯ KHÔNG ĐỦ. VUI LÒNG LIÊN HỆ ADMIN ĐỂ NẠP THÊM XU."
        )
        return
    selected = random.choice(["CÁI", "CON"])
    await query.message.reply_text(
        "✅ ĐÃ HOÀN THÀNH\n\n📊 KẾT QUẢ MÔ PHỎNG NGẪU NHIÊN\n"
        f"🎯 {selected}: {random.randint(71, 99)}%\n"
        f"🤝 HÒA: {random.randint(0, 14)}%\n"
        f"🐉 LONG BẢO: {random.randint(0, 19)}%\n"
        f"🎲 BÀN: {context.user_data.get('table', '-')}\n"
        "____________________________\n"
        "⚠️ Kết quả chỉ mang tính mô phỏng, không bảo đảm kết quả thực tế.\n"
        f"💰 Số dư: {balance} xu",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Kiểm tra lại (1 xu)", callback_data="run_check"),
            InlineKeyboardButton("Đổi bàn", callback_data="begin_check"),
        ]]),
    )


def main() -> None:
    init_db()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("napxu", napxu))
    application.add_handler(CommandHandler("truxu", truxu))
    application.add_handler(CommandHandler("kiemtra", kiemtra_user))
    application.add_handler(CommandHandler("sodu", sodu))
    application.add_handler(CallbackQueryHandler(consent, pattern="^consent_(yes|no)$"))
    application.add_handler(CallbackQueryHandler(request_login, pattern="^request_login$"))
    application.add_handler(CallbackQueryHandler(admin_decision, pattern="^(approve|reject):[0-9]+$"))
    application.add_handler(CallbackQueryHandler(begin_check, pattern="^begin_check$"))
    application.add_handler(CallbackQueryHandler(choose_table, pattern="^table:"))
    application.add_handler(CallbackQueryHandler(choose_cai, pattern="^cai:[0-9]$"))
    application.add_handler(CallbackQueryHandler(choose_con, pattern="^con:[0-9]$"))
    application.add_handler(CallbackQueryHandler(run_check, pattern="^run_check$"))
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
