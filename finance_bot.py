"""
Телеграм-бот учета доходов и расходов -> один xlsx файл.

Запуск (подробнее в README.md):
    pip install -r requirements.txt
    # рядом со скриптом создать config.py:
    #   BOT_TOKEN = "..."   токен от @BotFather
    #   OWNER_ID = 123456   твой telegram id (можно узнать у @userinfobot)
    python finance_bot.py

Как писать боту:
    -450 кофе            расход 450, категория "кофе"
    -1200 еда ужин в кафе  категория "еда", комментарий "ужин в кафе"
    +80000 зарплата      доход
    450 такси            без знака = расход

Команды: /week, /month, /undo, /file
По воскресеньям в 21:00 сам присылает сводку за неделю и копию таблицы.
"""
import os
import re
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

try:
    import config  # локальный config.py рядом со скриптом (в git не попадает)
except ImportError:
    config = None


def setting(name, default=None):
    value = os.environ.get(name) or getattr(config, name, None) or default
    if value is None:
        raise SystemExit(f"не задан {name}: впиши его в config.py")
    return value


TOKEN = setting("BOT_TOKEN")
OWNER_ID = int(setting("OWNER_ID"))
XLSX = Path(setting("XLSX_PATH", Path(__file__).with_name("finance.xlsx")))

REACTION = "👌"  # боты могут ставить только стандартные реакции телеграма (👍 🔥 ✍ 🙏 и т.д.)

TX_SHEET = "Транзакции"
SUM_SHEET = "Сводка"
HEADERS = ["Дата", "Месяц", "Тип", "Категория", "Сумма", "Комментарий"]

PATTERN = re.compile(r"^\s*([+-])?\s*(\d+(?:[.,]\d{1,2})?)\s*(.*)$", re.DOTALL)

HELP = (
    "пиши так:\n"
    "-450 кофе\n"
    "-1200 еда ужин в кафе\n"
    "+80000 зарплата\n\n"
    "команды: /week (итоги недели), /month (итоги месяца), /undo (удалить последнюю), /file (прислать эксель)"
)


def get_wb() -> Workbook:
    if XLSX.exists():
        return load_workbook(XLSX)
    wb = Workbook()
    ws = wb.active
    ws.title = TX_SHEET
    ws.append(HEADERS)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["D"].width = 18
    ws.column_dimensions["F"].width = 40
    return wb


def rebuild_summary(wb: Workbook) -> None:
    """Пересобирает лист 'Сводка': по строке на месяц, с формулами."""
    if SUM_SHEET in wb.sheetnames:
        del wb[SUM_SHEET]
    ws = wb.create_sheet(SUM_SHEET)
    ws.append(["Месяц", "Доходы", "Расходы", "Баланс"])
    for cell in ws[1]:
        cell.font = Font(bold=True)
    tx = wb[TX_SHEET]
    months = sorted({r[1] for r in tx.iter_rows(min_row=2, values_only=True) if r[1]})
    for i, m in enumerate(months, start=2):
        ws.append(
            [
                m,
                f"=SUMIFS('{TX_SHEET}'!E:E,'{TX_SHEET}'!B:B,A{i},'{TX_SHEET}'!C:C,\"доход\")",
                f"=SUMIFS('{TX_SHEET}'!E:E,'{TX_SHEET}'!B:B,A{i},'{TX_SHEET}'!C:C,\"расход\")",
                f"=B{i}-C{i}",
            ]
        )
    ws.column_dimensions["A"].width = 12


def save(wb: Workbook) -> None:
    rebuild_summary(wb)
    wb.save(XLSX)


def fmt(x: float) -> str:
    return f"{x:,.2f}".replace(",", " ").rstrip("0").rstrip(".")


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    await update.message.reply_text(HELP)


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    m = PATTERN.match(update.message.text or "")
    if not m:
        await update.message.reply_text(HELP)
        return

    sign, num, rest = m.groups()
    amount = float(num.replace(",", "."))
    kind = "доход" if sign == "+" else "расход"
    parts = rest.split(maxsplit=1)
    category = parts[0].lower() if parts else "без категории"
    comment = parts[1] if len(parts) > 1 else ""

    # время отправки сообщения (а не обработки), чтобы запись из очереди попала в правильный день
    now = update.message.date.astimezone()
    wb = get_wb()
    wb[TX_SHEET].append(
        [now.strftime("%Y-%m-%d"), now.strftime("%Y-%m"), kind, category, amount, comment]
    )
    save(wb)
    # ставим реакцию вместо ответа (нужен python-telegram-bot >= 20.8)
    try:
        await update.message.set_reaction(REACTION)
    except Exception:
        await update.message.reply_text(f"записал: {kind} {fmt(amount)}, {category}")


def summary(title: str, keep) -> str:
    """Итоги по строкам, для которых keep(строка) истинно."""
    income = expense = 0.0
    by_cat = defaultdict(float)
    for r in get_wb()[TX_SHEET].iter_rows(min_row=2, values_only=True):
        if not keep(r):
            continue
        if r[2] == "доход":
            income += r[4]
        else:
            expense += r[4]
            by_cat[r[3]] += r[4]
    top = sorted(by_cat.items(), key=lambda kv: -kv[1])[:5]
    lines = [
        title,
        f"доходы: {fmt(income)}",
        f"расходы: {fmt(expense)}",
        f"баланс: {fmt(income - expense)}",
    ]
    if top:
        lines.append("\nтоп расходов:")
        lines += [f"{c}: {fmt(v)}" for c, v in top]
    return "\n".join(lines)


def week_summary() -> str:
    today = date.today()
    start = today - timedelta(days=6)
    lo, hi = start.isoformat(), today.isoformat()
    return summary(
        f"неделя {start:%d.%m}–{today:%d.%m}", lambda r: r[0] and lo <= r[0] <= hi
    )


async def month(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    if not XLSX.exists():
        await update.message.reply_text("пока пусто")
        return
    cur = datetime.now().strftime("%Y-%m")
    await update.message.reply_text(summary(cur, lambda r: r[1] == cur))


async def week(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    if not XLSX.exists():
        await update.message.reply_text("пока пусто")
        return
    await update.message.reply_text(week_summary())


async def weekly_report(ctx: ContextTypes.DEFAULT_TYPE):
    """По воскресеньям: сводка за неделю + копия всей таблицы для истории."""
    if not XLSX.exists():
        return
    await ctx.bot.send_message(OWNER_ID, week_summary())
    with XLSX.open("rb") as f:
        await ctx.bot.send_document(
            OWNER_ID, f, filename=f"finance_{date.today():%Y-%m-%d}.xlsx"
        )


async def undo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    if not XLSX.exists():
        await update.message.reply_text("нечего удалять")
        return
    wb = get_wb()
    ws = wb[TX_SHEET]
    if ws.max_row < 2:
        await update.message.reply_text("нечего удалять")
        return
    last = [c.value for c in ws[ws.max_row]]
    ws.delete_rows(ws.max_row)
    save(wb)
    await update.message.reply_text(f"удалила: {last[2]} {fmt(last[4])}, {last[3]}")


async def send_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    if not XLSX.exists():
        await update.message.reply_text("файла пока нет")
        return
    with XLSX.open("rb") as f:
        await update.message.reply_document(f, filename=XLSX.name)


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("month", month))
    app.add_handler(CommandHandler("week", week))
    app.add_handler(CommandHandler("undo", undo))
    app.add_handler(CommandHandler("file", send_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    # воскресенье (6) в 21:00 по местному времени
    local_tz = datetime.now().astimezone().tzinfo
    app.job_queue.run_daily(weekly_report, time(21, 0, tzinfo=local_tz), days=(6,))
    app.run_polling()


if __name__ == "__main__":
    main()
