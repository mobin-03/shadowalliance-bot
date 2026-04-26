import os
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['NO_PROXY'] = '*'
# main.py - ربات تلگرام
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from config import BOT_TOKEN, ROLES, BUILDING_COST, BUILDING_TIME, SPY_COST
from database import Database
from game import GameManager
from models import Game, Player
from buildings import Building
from battle import Battle
from trade import Trade
import json

db = Database()
gm = GameManager()

# ========== Auto Period System ==========

async def auto_period_callback(context: ContextTypes.DEFAULT_TYPE):
    """اجرای خودکار هر دوره - تولید منابع و اعلام"""
    job_data = context.job.data
    game_id = job_data["game_id"]
    group_id = job_data["group_id"]
    period_minutes = job_data["period_minutes"]

    # چک کن بازی هنوز فعاله
    game_row = db.fetchone("SELECT * FROM games WHERE id=? AND is_active=1", (game_id,))
    if not game_row:
        return

    # آپدیت دوره
    new_period = game_row[5] + 1
    db.execute("UPDATE games SET current_period=? WHERE id=?", (new_period, game_id))

    # تولید منابع برای همه بازیکنا
    players = db.fetchall("SELECT * FROM players WHERE game_id=? AND is_alive=1", (game_id,))

    for p_row in players:
        player = Player(p_row[1], p_row[2], game_id, p_row[4])
        player.player_id = p_row[0]
        player.resources = {"gold": p_row[5], "soldiers": p_row[6], "food": p_row[7], "minerals": p_row[8]}
        player.is_alive = bool(p_row[10])

        production = Building.calculate_production(player, new_period)
        for resource, amount in production.items():
            player.resources[resource] = player.resources.get(resource, 0) + int(amount)
        player.update_resources()

    # اعلام تو گروه
    alive_count = len([p for p in players if p[10] == 1])
    await context.bot.send_message(
        chat_id=group_id,
        text=f"⏰ دوره {new_period} شروع شد!\n"
             f"💰 منابع تولید شد\n"
             f"👥 بازیکنان زنده: {alive_count} نفر\n"
             f"🕐 دوره بعدی: {period_minutes} دقیقه دیگه"
    )

# ========== Main Menu ==========

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش منوی اصلی با دکمه‌های شیشه‌ای"""
    keyboard = [
        [InlineKeyboardButton("🏰 وضعیت من", callback_data="menu_status")],
        [InlineKeyboardButton("🏗 ساخت ساختمان", callback_data="menu_build")],
        [InlineKeyboardButton("⚔️ حمله", callback_data="menu_attack")],
        [InlineKeyboardButton("🤝 معامله ساده", callback_data="menu_trade")],
        [InlineKeyboardButton("📜 قرارداد پیشرفته", callback_data="menu_contract")],
        [InlineKeyboardButton("🕵️ جاسوسی", callback_data="menu_spy")],
        [InlineKeyboardButton("🤝 اتحاد", callback_data="menu_ally")],
        [InlineKeyboardButton("🔬 ارتقا دانشمند", callback_data="menu_scientist")],
        [InlineKeyboardButton("📊 امتیازات", callback_data="menu_scores")],
        [InlineKeyboardButton("❌ لغو بازی", callback_data="menu_cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            "🎮 منوی اصلی - چیکار می‌خوای بکنی؟",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "🎮 منوی اصلی - چیکار می‌خوای بکنی؟",
            reply_markup=reply_markup
        )

# ========== Button Handler ==========

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت کلیک روی همه دکمه‌ها"""
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = str(query.from_user.id)
    chat_id = str(query.message.chat_id)

    # Back to menu
    if data == "menu_back":
        await menu(update, context)
        return

    game = Game.get_active_game(chat_id)
    if not game:
        await query.edit_message_text("❌ بازی فعالی نیست! با /newgame [دقیقه] بساز")
        return

    player = Player.get_by_user_game(user_id, game.game_id)
    if not player:
        await query.edit_message_text("❌ تو این بازی نیستی! با /join بیا تو بازی")
        return

    # ===== Status =====
    if data == "menu_status":
        buildings = Building.get_player_buildings(player.player_id, game.current_period)
        text = f"🏰 وضعیت @{player.username}\n"
        text += f"🎭 نقش: {ROLES.get(player.role, {}).get('name', 'نداره')}\n"
        text += f"📊 دوره: {game.current_period}\n\n"
        text += "💰 منابع:\n"
        text += f"• طلا: {player.resources['gold']}\n"
        text += f"• سرباز: {player.resources['soldiers']}\n"
        text += f"• غذا: {player.resources['food']}\n"
        text += f"• مواد معدنی: {player.resources['minerals']}\n\n"
        text += "🏗 ساختمان‌ها:\n"
        if buildings:
            for b in buildings:
                text += f"• {b[1]} (سطح {b[2]}, ضریب {b[3]:.1f})\n"
        else:
            text += "• هنوز نساختی!\n"

        keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="menu_back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    # ===== Build Menu =====
    elif data == "menu_build":
        keyboard = [
            [InlineKeyboardButton("🌾 زمین کشاورزی (30ط,10م)", callback_data="build_farm")],
            [InlineKeyboardButton("⛏️ معدن (40ط,20م)", callback_data="build_mine")],
            [InlineKeyboardButton("⚔️ سربازخانه (50ط,30م)", callback_data="build_barracks")],
            [InlineKeyboardButton("🏪 بازار (40ط)", callback_data="build_market")],
            [InlineKeyboardButton("🧱 دیوار دفاعی (30ط,40م)", callback_data="build_wall")],
            [InlineKeyboardButton("🔙 برگشت", callback_data="menu_back")]
        ]
        await query.edit_message_text("🏗 انتخاب ساختمان:", reply_markup=InlineKeyboardMarkup(keyboard))

    # ===== Execute Build =====
    elif data.startswith("build_"):
        building_type = data.replace("build_", "")
        if building_type not in BUILDING_COST:
            await query.edit_message_text("❌ ساختمان نامعتبر!")
            return

        if not Building.can_build(player, building_type):
            cost = BUILDING_COST[building_type]
            await query.edit_message_text(
                f"❌ منابع کافی نداری!\n"
                f"نیاز: {cost['gold']} طلا, {cost.get('minerals', 0)} مواد معدنی",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="menu_back")]])
            )
            return

        build_time = Building.build(player, building_type, game.current_period)
        if build_time == 0:
            await query.edit_message_text(
                f"✅ {building_type} در لحظه ساخته شد! (معمار)",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="menu_back")]])
            )
        else:
            await query.edit_message_text(
                f"🏗 ساخت {building_type} شروع شد!\n⏰ آماده در دوره {game.current_period + build_time}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="menu_back")]])
            )

    # ===== Attack Menu =====
    elif data == "menu_attack":
        players = game.get_players()
        keyboard = []
        for p in players:
            if p.player_id != player.player_id:
                keyboard.append([InlineKeyboardButton(f"⚔️ @{p.username}", callback_data=f"attack_select_{p.player_id}")])
        keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="menu_back")])

        if len(keyboard) == 1:
            await query.edit_message_text("❌ کسی برای حمله نیست!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="menu_back")]]))
        else:
            await query.edit_message_text("⚔️ کی رو می‌خوای بزنی؟", reply_markup=InlineKeyboardMarkup(keyboard))

    # ===== Attack with soldiers =====
    elif data.startswith("attack_select_"):
        target_id = int(data.replace("attack_select_", ""))
        context.user_data['attack_target'] = target_id

        keyboard = [
            [InlineKeyboardButton("۱۰ سرباز", callback_data="attack_go_10")],
            [InlineKeyboardButton("۲۵ سرباز", callback_data="attack_go_25")],
            [InlineKeyboardButton("۵۰ سرباز", callback_data="attack_go_50")],
            [InlineKeyboardButton("همه سربازا", callback_data="attack_go_all")],
            [InlineKeyboardButton("🔙 برگشت", callback_data="menu_back")]
        ]
        await query.edit_message_text(f"⚔️ چندتا سرباز بفرستم؟ (داری: {player.resources['soldiers']})", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("attack_go_"):
        soldiers_str = data.replace("attack_go_", "")
        target_id = context.user_data.get('attack_target')

        if not target_id:
            await query.edit_message_text("❌ خطا! دوباره تلاش کن")
            return

        if soldiers_str == "all":
            soldiers = player.resources['soldiers']
        else:
            soldiers = int(soldiers_str)

        # پیدا کردن مدافع
        all_players = game.get_players()
        defender = None
        for p in all_players:
            if p.player_id == target_id:
                defender = p
                break

        if not defender:
            await query.edit_message_text("❌ بازیکن هدف پیدا نشد!")
            return

        result, error = Battle.attack(player, defender, soldiers, game.game_id, game.current_period)

        if error:
            await query.edit_message_text(f"❌ {error}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="menu_back")]]))
            return

        if result["win"]:
            text = f"⚔️ @{player.username} به @{defender.username} حمله کرد و برد!\n"
            text += f"💀 @{defender.username} از بازی حذف شد!\n"
            text += f"📉 تلفات تو: {result['losses']} سرباز\n"
            text += f"💰 غارت: {result['loot']['gold']} طلا, {result['loot']['food']} غذا, {result['loot']['minerals']} مواد معدنی"

            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚔️ @{player.username} شهر @{defender.username} رو فتح کرد و حذفش کرد!"
            )
        else:
            text = f"💔 حمله ناموفق! {soldiers} سرباز از دست دادی"

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="menu_back")]]))

    # ===== Simple Trade =====
    elif data == "menu_trade":
        players = game.get_players()
        keyboard = []
        for p in players:
            if p.player_id != player.player_id:
                keyboard.append([InlineKeyboardButton(f"🤝 @{p.username}", callback_data=f"trade_with_{p.player_id}")])
        keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="menu_back")])

        await query.edit_message_text("🤝 با کی می‌خوای معامله کنی؟", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("trade_with_"):
        target_id = int(data.replace("trade_with_", ""))
        context.user_data['trade_target'] = target_id
        context.user_data['trade_offer'] = {}
        context.user_data['trade_request'] = {}
        context.user_data['trade_step'] = 'offer_gold'

        await query.edit_message_text(
            "💰 چقدر طلا می‌دی؟ (عدد بفرست)",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لغو", callback_data="menu_back")]])
        )

    # ===== Spy =====
    elif data == "menu_spy":
        if player.role != "spy":
            await query.edit_message_text("❌ فقط جاسوس می‌تونه جاسوسی کنه!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="menu_back")]]))
            return

        players = game.get_players()
        keyboard = []
        for p in players:
            if p.player_id != player.player_id:
                keyboard.append([InlineKeyboardButton(f"🕵️ @{p.username}", callback_data=f"spy_on_{p.player_id}")])
        keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="menu_back")])

        await query.edit_message_text("🕵️ کی رو می‌خوای جاسوسی کنی؟", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("spy_on_"):
        target_id = int(data.replace("spy_on_", ""))
        context.user_data['spy_target'] = target_id

        keyboard = [
            [InlineKeyboardButton("💰 دیدن منابع (۲۰ طلا)", callback_data="spy_action_resources")],
            [InlineKeyboardButton("📋 معاملات ساده (۳۰ طلا)", callback_data="spy_action_simple_trades")],
            [InlineKeyboardButton("📜 قرارداد پیشرفته (۵۰ طلا)", callback_data="spy_action_advanced_contract")],
            [InlineKeyboardButton("🔙 برگشت", callback_data="menu_back")]
        ]
        await query.edit_message_text("🕵️ چی می‌خوای بدونی؟", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("spy_action_"):
        action = data.replace("spy_action_", "")
        target_id = context.user_data.get('spy_target')

        if not target_id:
            await query.edit_message_text("❌ خطا!")
            return

        all_players = game.get_players()
        target_player = None
        for p in all_players:
            if p.player_id == target_id:
                target_player = p
                break

        if not target_player:
            await query.edit_message_text("❌ هدف پیدا نشد!")
            return

        result, msg = gm.spy_action(player, target_player, action, game.game_id, game.current_period)

        if result is None:
            await query.edit_message_text(f"❌ {msg}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="menu_back")]]))
            return

        if action == "resources":
            text = f"🕵️ منابع @{target_player.username}:\n"
            for k, v in result.items():
                text += f"• {k}: {v}\n"
        elif action == "simple_trades":
            if not result:
                text = "🔍 معامله‌ای تو ۳ دور اخیر نداشته!"
            else:
                text = f"🕵️ معاملات @{target_player.username}:\n"
                for t in result:
                    text += f"• داده: {t[0]}, گرفته: {t[1]} (دوره {t[2]})\n"
        elif action == "advanced_contract":
            if not result:
                text = "🔍 قرارداد پیشرفته فعالی نداره!"
            else:
                text = f"🕵️ @{target_player.username} این قراردادها رو داره:\n"
                for c in result:
                    text += f"• قرارداد #{c[0]}\n"

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="menu_back")]]))

    # ===== Ally =====
    elif data == "menu_ally":
        players = game.get_players()
        keyboard = []
        for p in players:
            if p.player_id != player.player_id:
                keyboard.append([InlineKeyboardButton(f"🤝 @{p.username}", callback_data=f"ally_with_{p.player_id}")])
        keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="menu_back")])

        await query.edit_message_text("🤝 با کی می‌خوای متحد شی؟", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("ally_with_"):
        target_id = int(data.replace("ally_with_", ""))

        all_players = game.get_players()
        target_player = None
        for p in all_players:
            if p.player_id == target_id:
                target_player = p
                break

        if not target_player:
            await query.edit_message_text("❌ بازیکن پیدا نشد!")
            return

        db.execute('''
            INSERT INTO alliances (game_id, player1_id, player2_id, is_public)
            VALUES (?, ?, ?, 1)
        ''', (game.game_id, player.player_id, target_player.player_id))

        await query.edit_message_text(
            f"🤝 @{player.username} با @{target_player.username} متحد شد!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="menu_back")]])
        )

    # ===== Scientist =====
    elif data == "menu_scientist":
        if player.role != "scientist":
            await query.edit_message_text("❌ فقط دانشمند می‌تونه ارتقا بده!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="menu_back")]]))
            return

        keyboard = [
            [InlineKeyboardButton("📚 یادگیری تکنولوژی (۱۰۰ طلا)", callback_data="sci_learn")],
            [InlineKeyboardButton("🔬 ارتقای ساختمان (۵۰ طلا)", callback_data="sci_upgrade")],
            [InlineKeyboardButton("🔙 برگشت", callback_data="menu_back")]
        ]
        await query.edit_message_text("🔬 چیکار می‌خوای بکنی دانشمند؟", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "sci_learn":
        keyboard = [
            [InlineKeyboardButton("🌾 کشاورزی", callback_data="sci_learn_farm")],
            [InlineKeyboardButton("⛏️ معدن", callback_data="sci_learn_mine")],
            [InlineKeyboardButton("⚔️ نظامی", callback_data="sci_learn_barracks")],
            [InlineKeyboardButton("🏪 اقتصاد", callback_data="sci_learn_market")],
            [InlineKeyboardButton("🧱 دفاع", callback_data="sci_learn_wall")],
            [InlineKeyboardButton("🔙 برگشت", callback_data="menu_back")]
        ]
        await query.edit_message_text("📚 کدوم تکنولوژی رو یاد بگیری؟ (۱۰۰ طلا)", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("sci_learn_"):
        building_type = data.replace("sci_learn_", "")
        if Building.scientist_learn_tech(player, building_type):
            await query.edit_message_text(f"✅ تکنولوژی {building_type} یاد گرفته شد!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="menu_back")]]))
        else:
            await query.edit_message_text("❌ طلا کافی نداری! (۱۰۰ طلا نیازه)", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="menu_back")]]))

    elif data == "sci_upgrade":
        buildings = Building.get_player_buildings(player.player_id, game.current_period)
        keyboard = []
        for b in buildings:
            keyboard.append([InlineKeyboardButton(f"{b[1]} (سطح {b[2]})", callback_data=f"sci_upgrade_{b[0]}_{b[1]}")])
        keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="menu_back")])
        await query.edit_message_text("🔬 کدوم ساختمان رو ارتقا بدی؟ (۵۰ طلا)", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("sci_upgrade_"):
        parts = data.split("_")
        building_id = int(parts[2])
        building_type = parts[3]
        if Building.scientist_upgrade_building(player, building_id, building_type):
            await query.edit_message_text(f"✅ {building_type} ارتقا یافت!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="menu_back")]]))
        else:
            await query.edit_message_text("❌ نشد! یا طلا کم داری یا یاد نگرفتی", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="menu_back")]]))

    # ===== Scores =====
    elif data == "menu_scores":
        players = game.get_players()
        text = "📊 امتیازات:\n\n"
        for p in players:
            score = p.resources['gold'] + p.resources['soldiers']*2 + p.resources['food'] + p.resources['minerals']*1.5
            text += f"@{p.username}: {int(score)} امتیاز\n"

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="menu_back")]]))

    # ===== Cancel Game =====
    elif data == "menu_cancel":
        member = await context.bot.get_chat_member(chat_id, int(user_id))
        if member.status not in ['creator', 'administrator']:
            await query.edit_message_text("❌ فقط ادمین می‌تونه بازی رو لغو کنه!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="menu_back")]]))
            return

        keyboard = [
            [InlineKeyboardButton("✅ آره، لغو کن", callback_data="cancel_confirm")],
            [InlineKeyboardButton("🔙 برگشت", callback_data="menu_back")]
        ]
        await query.edit_message_text("⚠️ مطمئنی می‌خوای بازی رو لغو کنی؟ همه چی پاک میشه!", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "cancel_confirm":
        db.execute("UPDATE games SET is_active=0 WHERE id=?", (game.game_id,))

        # حذف job زمان‌بندی
        current_jobs = context.job_queue.jobs()
        for job in current_jobs:
            if hasattr(job, 'data') and job.data and job.data.get('game_id') == game.game_id:
                job.schedule_removal()

        await query.edit_message_text("🛑 بازی لغو شد! با /newgame [دقیقه] بازی جدید بسازید")

# ========== دستورات پایه ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🎮 باز کردن منو", callback_data="menu_back")]]
    await update.message.reply_text(
        "🎮 به بازی استراتژیک شهرسازی خوش اومدی!\n\n"
        "برای شروع:\n"
        "۱. ادمین: /newgame [دقیقه]\n"
        "۲. بازیکنا: /join\n"
        "۳. ادمین: /roles\n"
        "۴. انتخاب نقش: /pickrole [اسم]\n\n"
        "یا از دکمه زیر منو رو باز کن:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def new_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ساخت بازی جدید با دوره دقیقه‌ای"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    member = await context.bot.get_chat_member(chat_id, user_id)
    if member.status not in ['creator', 'administrator']:
        await update.message.reply_text("❌ فقط ادمین گروه می‌تونه بازی بسازه!")
        return

    period = 30  # پیش‌فرض ۳۰ دقیقه
    if context.args:
        try:
            period = int(context.args[0])
        except:
            pass

    game, msg = gm.start_new_game(str(chat_id), str(user_id), period)
    if game:
        # زمان‌بندی اجرای خودکار دوره
        context.job_queue.run_repeating(
            auto_period_callback,
            interval=period * 60,  # دقیقه به ثانیه
            first=period * 60,
            chat_id=chat_id,
            data={"game_id": game.game_id, "group_id": str(chat_id), "period_minutes": period}
        )

        keyboard = [[InlineKeyboardButton("🎮 باز کردن منو", callback_data="menu_back")]]
        await update.message.reply_text(
            f"✅ {msg}\n⏰ طول هر دوره: {period} دقیقه\n🔄 منابع به صورت خودکار تولید میشن",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(f"❌ {msg}")

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عضویت در بازی"""
    user_id = update.effective_user.id
    username = update.effective_user.username or str(user_id)
    chat_id = update.effective_chat.id

    player, msg = gm.join_game(str(user_id), username, str(chat_id))
    if player:
        await update.message.reply_text(f"✅ {username} {msg}")
    else:
        await update.message.reply_text(f"❌ {msg}")

async def start_roles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع انتخاب نقش"""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    member = await context.bot.get_chat_member(chat_id, user_id)
    if member.status not in ['creator', 'administrator']:
        await update.message.reply_text("❌ فقط ادمین!")
        return

    players, msg = gm.start_role_selection(str(chat_id))
    if players:
        text = "📋 ترتیب انتخاب نقش (قرعه‌کشی):\n\n"
        for i, p in enumerate(players, 1):
            text += f"{i}. @{p.username}\n"
        text += "\nنقش‌های موجود:\n"
        for role, info in ROLES.items():
            text += f"• {info['name']} ({role})\n"
        text += "\nبا دستور /pickrole [اسم نقش] انتخاب کن"
        await update.message.reply_text(text)
    else:
        await update.message.reply_text(f"❌ {msg}")

async def pick_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """انتخاب نقش"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not context.args:
        await update.message.reply_text("❌ نقش رو مشخص کن: /pickrole merchant")
        return

    role = context.args[0].lower()
    game = Game.get_active_game(str(chat_id))
    if not game:
        await update.message.reply_text("❌ بازی فعالی نیست!")
        return

    success, msg = gm.select_role(str(user_id), game.game_id, role)
    if success:
        keyboard = [[InlineKeyboardButton("🎮 باز کردن منو", callback_data="menu_back")]]
        await update.message.reply_text(f"✅ {msg}", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(f"❌ {msg}")

# ========== Keep original commands for backward compatibility ==========

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مشاهده وضعیت خود"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    game = Game.get_active_game(str(chat_id))
    if not game:
        await update.message.reply_text("❌ بازی فعالی نیست!")
        return

    player = Player.get_by_user_game(str(user_id), game.game_id)
    if not player:
        await update.message.reply_text("❌ تو این بازی نیستی!")
        return

    buildings = Building.get_player_buildings(player.player_id, game.current_period)

    text = f"🏰 وضعیت @{player.username}\n"
    text += f"🎭 نقش: {ROLES.get(player.role, {}).get('name', 'نداره')}\n"
    text += f"📊 دوره: {game.current_period}\n\n"
    text += "💰 منابع:\n"
    text += f"• طلا: {player.resources['gold']}\n"
    text += f"• سرباز: {player.resources['soldiers']}\n"
    text += f"• غذا: {player.resources['food']}\n"
    text += f"• مواد معدنی: {player.resources['minerals']}\n\n"
    text += "🏗 ساختمان‌ها:\n"

    for b in buildings:
        text += f"• {b[1]} (سطح {b[2]}, ضریب {b[3]:.1f})\n"

    if not buildings:
        text += "• هنوز ساختمانی نساختی!\n"

    await update.message.reply_text(text)

async def build(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ساخت ساختمان"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not context.args:
        await update.message.reply_text(
            "🏗 ساختمان‌های قابل ساخت:\n"
            "• farm - زمین کشاورزی (غذا)\n"
            "• mine - معدن (مواد معدنی)\n"
            "• barracks - سربازخانه (سرباز)\n"
            "• market - بازار (طلا)\n"
            "• wall - دیوار دفاعی (دفاع)\n\n"
            "مثال: /build farm"
        )
        return

    building_type = context.args[0].lower()
    if building_type not in BUILDING_COST:
        await update.message.reply_text("❌ ساختمان نامعتبر!")
        return

    game = Game.get_active_game(str(chat_id))
    if not game:
        await update.message.reply_text("❌ بازی فعالی نیست!")
        return

    player = Player.get_by_user_game(str(user_id), game.game_id)
    if not player:
        await update.message.reply_text("❌ تو این بازی نیستی!")
        return

    if not Building.can_build(player, building_type):
        cost = BUILDING_COST[building_type]
        await update.message.reply_text(
            f"❌ منابع کافی نداری!\n"
            f"نیاز: {cost['gold']} طلا و {cost.get('minerals', 0)} مواد معدنی"
        )
        return

    build_time = Building.build(player, building_type, game.current_period)

    if build_time == 0:
        await update.message.reply_text(f"✅ ساختمان {building_type} در لحظه ساخته شد! (معمار)")
    else:
        await update.message.reply_text(
            f"🏗 ساخت {building_type} شروع شد!\n"
            f"⏰ آماده در دوره {game.current_period + build_time}"
        )

async def attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حمله به بازیکن دیگه"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if len(context.args) < 2:
        await update.message.reply_text("❌ استفاده: /attack @username تعداد_سرباز")
        return

    target_username = context.args[0].replace("@", "")
    try:
        soldiers = int(context.args[1])
    except:
        await update.message.reply_text("❌ تعداد سرباز رو درست وارد کن!")
        return

    game = Game.get_active_game(str(chat_id))
    if not game:
        await update.message.reply_text("❌ بازی فعالی نیست!")
        return

    attacker = Player.get_by_user_game(str(user_id), game.game_id)
    if not attacker:
        await update.message.reply_text("❌ تو این بازی نیستی!")
        return

    all_players = game.get_players()
    defender = None
    for p in all_players:
        if p.username == target_username:
            defender = p
            break

    if not defender:
        await update.message.reply_text("❌ بازیکن هدف پیدا نشد!")
        return

    if attacker.player_id == defender.player_id:
        await update.message.reply_text("❌ نمی‌تونی به خودت حمله کنی!")
        return

    result, error = Battle.attack(attacker, defender, soldiers, game.game_id, game.current_period)

    if error:
        await update.message.reply_text(f"❌ {error}")
        return

    if result["win"]:
        text = f"⚔️ @{attacker.username} به @{defender.username} حمله کرد و برد!\n"
        text += f"💀 @{defender.username} از بازی حذف شد!\n"
        text += f"📉 تلفات مهاجم: {result['losses']} سرباز\n"
        text += f"💰 غارت: {result['loot']['gold']} طلا, {result['loot']['food']} غذا, {result['loot']['minerals']} مواد معدنی"
        await update.message.reply_text(text)

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⚔️ @{attacker.username} شهر @{defender.username} رو فتح کرد و از بازی حذفش کرد!"
        )
    else:
        await update.message.reply_text(
            f"💔 حمله ناموفق! تمام {soldiers} سربازت از دست رفتن."
        )

# ========== معامله ساده ==========

async def trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معامله ساده: /trade @username gold:100 soldiers:50"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if len(context.args) < 3:
        await update.message.reply_text(
            "❌ استفاده: /trade @username gold:100 soldiers:0 food:0 minerals:0\n"
            "این یعنی تو ۱۰۰ طلا می‌دی، طرف ۵۰ سرباز میده"
        )
        return

    target_username = context.args[0].replace("@", "")
    offer = {"gold": 0, "soldiers": 0, "food": 0, "minerals": 0}
    request = {"gold": 0, "soldiers": 0, "food": 0, "minerals": 0}

    for arg in context.args[1:]:
        if ":" in arg:
            parts = arg.split(":")
            resource = parts[0].lower()
            amount = int(parts[1])
            if resource in offer:
                offer[resource] = amount
        elif "=" in arg:
            parts = arg.split("=")
            resource = parts[0].lower()
            amount = int(parts[1])
            if resource in request:
                request[resource] = amount

    game = Game.get_active_game(str(chat_id))
    if not game:
        await update.message.reply_text("❌ بازی فعالی نیست!")
        return

    from_player = Player.get_by_user_game(str(user_id), game.game_id)
    if not from_player:
        await update.message.reply_text("❌ تو این بازی نیستی!")
        return

    all_players = game.get_players()
    to_player = None
    for p in all_players:
        if p.username == target_username:
            to_player = p
            break

    if not to_player:
        await update.message.reply_text("❌ بازیکن هدف پیدا نشد!")
        return

    success, msg = Trade.simple_trade(from_player, to_player, offer, request, game.game_id, game.current_period, is_public=True)

    if success:
        await update.message.reply_text(f"✅ {msg}")
        await context.bot.send_message(
            chat_id=to_player.user_id,
            text=f"🤝 @{from_player.username} باهات معامله کرد:\n"
                 f"داده: {offer}\nگرفته: {request}"
        )
    else:
        await update.message.reply_text(f"❌ {msg}")

# ========== قرارداد پیشرفته ==========

async def contract(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """قرارداد پیشرفته: /contract @username متن قرارداد"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if len(context.args) < 2:
        await update.message.reply_text("❌ استفاده: /contract @username متن_قرارداد")
        return

    target_username = context.args[0].replace("@", "")
    contract_text = " ".join(context.args[1:])

    game = Game.get_active_game(str(chat_id))
    if not game:
        await update.message.reply_text("❌ بازی فعالی نیست!")
        return

    from_player = Player.get_by_user_game(str(user_id), game.game_id)
    if not from_player:
        await update.message.reply_text("❌ تو این بازی نیستی!")
        return

    all_players = game.get_players()
    to_player = None
    for p in all_players:
        if p.username == target_username:
            to_player = p
            break

    if not to_player:
        await update.message.reply_text("❌ بازیکن هدف پیدا نشد!")
        return

    # پرسیدن علنی یا محرمانه
    keyboard = [
        [
            InlineKeyboardButton("علنی 📢", callback_data=f"contract_public_{to_player.player_id}_{game.game_id}"),
            InlineKeyboardButton("محرمانه 🤫", callback_data=f"contract_private_{to_player.player_id}_{game.game_id}")
        ]
    ]

    context.user_data['contract_text'] = contract_text
    context.user_data['contract_to'] = to_player.player_id

    await update.message.reply_text(
        "📜 قراردادت علنی باشه یا محرمانه؟",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def contract_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """کالبک انتخاب علنی/محرمانه"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data.split("_")

    if len(data) < 4:
        return

    is_public = data[1] == "public"
    to_player_id = int(data[2])
    game_id = int(data[3])
    contract_text = context.user_data.get('contract_text', '')

    from_player = Player.get_by_user_game(str(user_id), game_id)
    if not from_player:
        await query.edit_message_text("❌ خطا!")
        return

    game = Game.get_active_game(None)
    game.game_id = game_id

    success, result = Trade.propose_advanced_contract(
        from_player, None, contract_text, game_id, 0, is_public
    )

    if not success:
        await query.edit_message_text(f"❌ {result}")
        return

    # آپدیت با to_player_id
    db.execute(
        "UPDATE advanced_contracts SET to_player_id=? WHERE id=?",
        (to_player_id, result)
    )

    if is_public:
        await context.bot.send_message(
            chat_id=game.group_id if hasattr(game, 'group_id') else update.effective_chat.id,
            text=f"📜 قرارداد جدید بین @{from_player.username} و یک بازیکن دیگه ثبت شد!"
        )

    await query.edit_message_text(
        f"✅ قرارداد با موفقیت ثبت شد!\n"
        f"🆔 شناسه: {result}\n"
        f"💰 هزینه ثبت: ۲۰ طلا"
    )

# ========== پذیرش قرارداد ==========

async def accept_contract(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پذیرش قرارداد: /accept contract_id"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not context.args:
        await update.message.reply_text("❌ /accept [شناسه قرارداد]")
        return

    contract_id = int(context.args[0])

    game = Game.get_active_game(str(chat_id))
    if not game:
        await update.message.reply_text("❌ بازی فعالی نیست!")
        return

    player = Player.get_by_user_game(str(user_id), game.game_id)
    if not player:
        await update.message.reply_text("❌ تو این بازی نیستی!")
        return

    success, msg = Trade.accept_contract(contract_id, player.player_id)
    await update.message.reply_text(f"{'✅' if success else '❌'} {msg}")

# ========== جاسوسی ==========

async def spy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """جاسوسی: /spy @username resources/simple_trades/advanced_contract"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if len(context.args) < 2:
        await update.message.reply_text(
            "🕵️ انواع جاسوسی:\n"
            "• resources (۲۰ طلا) - دیدن منابع\n"
            "• simple_trades (۳۰ طلا) - معاملات ۳ دور اخیر\n"
            "• advanced_contract (۵۰ طلا) - وجود قرارداد پیشرفته\n\n"
            "مثال: /spy @username resources"
        )
        return

    target_username = context.args[0].replace("@", "")
    action = context.args[1].lower()

    game = Game.get_active_game(str(chat_id))
    if not game:
        await update.message.reply_text("❌ بازی فعالی نیست!")
        return

    spy_player = Player.get_by_user_game(str(user_id), game.game_id)
    if not spy_player:
        await update.message.reply_text("❌ تو این بازی نیستی!")
        return

    all_players = game.get_players()
    target_player = None
    for p in all_players:
        if p.username == target_username:
            target_player = p
            break

    if not target_player:
        await update.message.reply_text("❌ هدف پیدا نشد!")
        return

    result, msg = gm.spy_action(spy_player, target_player, action, game.game_id, game.current_period)

    if result is None:
        await update.message.reply_text(f"❌ {msg}")
        return

    if action == "resources":
        text = f"🕵️ منابع @{target_player.username}:\n"
        for k, v in result.items():
            text += f"• {k}: {v}\n"
        await update.message.reply_text(text)

    elif action == "simple_trades":
        if not result:
            await update.message.reply_text("🔍 معامله ساده‌ای تو ۳ دور اخیر نداشته!")
        else:
            text = f"🕵️ معاملات @{target_player.username}:\n"
            for trade in result:
                text += f"• داده: {trade[0]}, گرفته: {trade[1]} (دوره {trade[2]})\n"
            await update.message.reply_text(text)

    elif action == "advanced_contract":
        if not result:
            await update.message.reply_text("🔍 قرارداد پیشرفته فعالی نداره!")
        else:
            text = f"🕵️ @{target_player.username} این قراردادهای پیشرفته رو داره:\n"
            for c in result:
                text += f"• قرارداد #{c[0]}\n"
            await update.message.reply_text(text)

# ========== اتحاد ==========

async def ally(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پیشنهاد اتحاد"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not context.args:
        await update.message.reply_text("❌ /ally @username")
        return

    target_username = context.args[0].replace("@", "")

    game = Game.get_active_game(str(chat_id))
    if not game:
        await update.message.reply_text("❌ بازی فعالی نیست!")
        return

    from_player = Player.get_by_user_game(str(user_id), game.game_id)
    if not from_player:
        await update.message.reply_text("❌ تو این بازی نیستی!")
        return

    all_players = game.get_players()
    to_player = None
    for p in all_players:
        if p.username == target_username:
            to_player = p
            break

    if not to_player:
        await update.message.reply_text("❌ بازیکن هدف پیدا نشد!")
        return

    db.execute('''
        INSERT INTO alliances (game_id, player1_id, player2_id, is_public)
        VALUES (?, ?, ?, 1)
    ''', (game.game_id, from_player.player_id, to_player.player_id))

    await update.message.reply_text(
        f"🤝 @{from_player.username} با @{to_player.username} متحد شد!"
    )

# ========== Handle trade text input ==========

async def handle_trade_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت عدد برای معامله"""
    if 'trade_step' not in context.user_data:
        return

    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)

    game = Game.get_active_game(chat_id)
    if not game:
        return

    player = Player.get_by_user_game(user_id, game.game_id)
    if not player:
        return

    try:
        amount = int(update.message.text)
    except:
        await update.message.reply_text("❌ عدد وارد کن!")
        return

    step = context.user_data['trade_step']

    if step == 'offer_gold':
        context.user_data['trade_offer']['gold'] = amount
        context.user_data['trade_step'] = 'offer_soldiers'
        await update.message.reply_text("⚔️ چندتا سرباز می‌دی؟ (عدد بفرست)")

    elif step == 'offer_soldiers':
        context.user_data['trade_offer']['soldiers'] = amount
        context.user_data['trade_step'] = 'offer_food'
        await update.message.reply_text("🌾 چقدر غذا می‌دی؟ (عدد بفرست)")

    elif step == 'offer_food':
        context.user_data['trade_offer']['food'] = amount
        context.user_data['trade_step'] = 'offer_minerals'
        await update.message.reply_text("⛏️ چقدر مواد معدنی می‌دی؟ (عدد بفرست)")

    elif step == 'offer_minerals':
        context.user_data['trade_offer']['minerals'] = amount
        context.user_data['trade_step'] = 'request_gold'
        await update.message.reply_text("💰 چقدر طلا می‌خوای بگیری؟ (عدد بفرست)")

    elif step == 'request_gold':
        context.user_data['trade_request']['gold'] = amount
        context.user_data['trade_step'] = 'request_soldiers'
        await update.message.reply_text("⚔️ چندتا سرباز می‌خوای؟ (عدد بفرست)")

    elif step == 'request_soldiers':
        context.user_data['trade_request']['soldiers'] = amount
        context.user_data['trade_step'] = 'request_food'
        await update.message.reply_text("🌾 چقدر غذا می‌خوای؟ (عدد بفرست)")

    elif step == 'request_food':
        context.user_data['trade_request']['food'] = amount
        context.user_data['trade_step'] = 'request_minerals'
        await update.message.reply_text("⛏️ چقدر مواد معدنی می‌خوای؟ (عدد بفرست)")

    elif step == 'request_minerals':
        context.user_data['trade_request']['minerals'] = amount

        # انجام معامله
        target_id = context.user_data.get('trade_target')
        offer = context.user_data.get('trade_offer', {})
        request = context.user_data.get('trade_request', {})

        all_players = game.get_players()
        to_player = None
        for p in all_players:
            if p.player_id == target_id:
                to_player = p
                break

        if not to_player:
            await update.message.reply_text("❌ بازیکن هدف پیدا نشد!")
            context.user_data.clear()
            return

        success, msg = Trade.simple_trade(player, to_player, offer, request, game.game_id, game.current_period, is_public=True)

        if success:
            await update.message.reply_text(f"✅ {msg}")
            await context.bot.send_message(
                chat_id=to_player.user_id,
                text=f"🤝 @{player.username} باهات معامله کرد:\nداده: {offer}\nگرفته: {request}"
            )
        else:
            await update.message.reply_text(f"❌ {msg}")

        context.user_data.clear()

# ========== اصلی ==========

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("newgame", new_game))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("roles", start_roles))
    app.add_handler(CommandHandler("pickrole", pick_role))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("build", build))
    app.add_handler(CommandHandler("attack", attack))
    app.add_handler(CommandHandler("trade", trade))
    app.add_handler(CommandHandler("contract", contract))
    app.add_handler(CommandHandler("accept", accept_contract))
    app.add_handler(CommandHandler("spy", spy))
    app.add_handler(CommandHandler("ally", ally))

    # Button handlers
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^(menu_|build_|attack_|trade_|ally_|spy_|sci_|cancel_)"))

    # Contract callbacks
    app.add_handler(CallbackQueryHandler(contract_callback, pattern="^contract_"))

    # Trade text input
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_trade_input))

    import logging
    import sys

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )

    print("🤖 ربات بازی استراتژیک روشن شد!", flush=True)
    sys.stdout.flush()

    app.run_polling(drop_pending_updates=True)