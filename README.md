# debit&credit

Телеграм-бот для учёта доходов и расходов. Пишешь ему трату одним сообщением, а он записывает её в Excel-табличку `finance.xlsx`.

## Как писать боту

| Сообщение | Что запишется |
|---|---|
| `-450 кофе` | расход 450, категория «кофе» |
| `-1200 еда ужин в кафе` | расход 1200, категория «еда», комментарий «ужин в кафе» |
| `+80000 зарплата` | доход 80 000, категория «зарплата» |
| `450 такси` | без знака считается расходом |

Первое слово после суммы — категория, всё остальное — комментарий. Если всё записалось, бот ставит на сообщение реакцию 👌.

Команды:

- `/week` — итоги за последние 7 дней
- `/month` — итоги текущего месяца
- `/undo` — удалить последнюю запись
- `/file` — прислать табличку

Каждое воскресенье в 21:00 бот сам присылает сводку за неделю и копию всей таблички, так в переписке копится история.

В табличке два листа: «Транзакции» со всеми записями и «Сводка» с доходами, расходами и балансом по месяцам.

## Как запустить

Нужен Python 3.10 или новее.

**1. Заведи своего бота.** В Телеграме открой [@BotFather](https://t.me/BotFather), отправь `/newbot` и придумай имя. В ответ придёт токен — длинная строка вида `123456789:AAH...`.

**2. Узнай свой telegram id.** Напиши [@userinfobot](https://t.me/userinfobot), он ответит числом. Бот будет слушаться только этого id, посторонним он не ответит.

**3. Скачай код и поставь зависимости.**

```bash
git clone https://github.com/curcs/debit-credit.git
cd debit-credit
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

**4. Впиши ключи.** Создай в папке файл `config.py`:

```python
BOT_TOKEN = "123456789:AAH..."   # токен от @BotFather
OWNER_ID = 123456789             # твой id от @userinfobot
```

Этот файл уже добавлен в `.gitignore`, так что токен не попадёт в git. Никому его не показывай: с ним можно управлять твоим ботом.

**5. Запусти.**

```bash
./venv/bin/python finance_bot.py
```

Напиши боту `/start`, он ответит подсказкой. Бот работает, пока открыт терминал и не выключен компьютер.

## Чтобы бот работал в фоне (macOS)

Создай файл `~/Library/LaunchAgents/com.debitcredit.bot.plist` и поменяй в нём `/ПУТЬ/К/debit-credit` на свою папку:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.debitcredit.bot</string>
    <key>ProgramArguments</key>
    <array>
        <string>/ПУТЬ/К/debit-credit/venv/bin/python</string>
        <string>/ПУТЬ/К/debit-credit/finance_bot.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/ПУТЬ/К/debit-credit</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>ThrottleInterval</key>
    <integer>10</integer>
    <key>StandardOutPath</key>
    <string>/ПУТЬ/К/debit-credit/launchd.out.log</string>
    <key>StandardErrorPath</key>
    <string>/ПУТЬ/К/debit-credit/launchd.err.log</string>
</dict>
</plist>
```

Включить:

```bash
launchctl load ~/Library/LaunchAgents/com.debitcredit.bot.plist
```

Перезапустить после изменений:

```bash
launchctl kickstart -k gui/$(id -u)/com.debitcredit.bot
```

Теперь бот запускается сам при входе в систему и поднимается, если упал. Ошибки пишутся в `launchd.err.log`. Компьютер при этом должен быть включён: на выключенном маке бот не ответит. Сообщения, отправленные за последние сутки, он подхватит после включения и запишет с той датой, когда они были отправлены. Более старые Телеграм не хранит.

## Если открываешь табличку в Excel

Закрывай её, прежде чем писать боту новые траты. Иначе при сохранении Excel может затереть записи, которые бот добавил, пока файл был открыт.
