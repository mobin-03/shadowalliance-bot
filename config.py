# config.py - تنظیمات بازی
import os

# توکن ربات تلگرام - از BotFather بگیر
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TOKEN_HERE")

# دیتابیس
DATABASE_PATH = "game.db"

# منابع اولیه هر بازیکن
INITIAL_RESOURCES = {
    "gold": 100,
    "soldiers": 50,
    "food": 200,
    "minerals": 30
}

# ضرایب پایه تولید ساختمان‌ها (در هر دوره)
BUILDING_PRODUCTION = {
    "farm": {"food": 50},
    "mine": {"minerals": 30},
    "barracks": {"soldiers": 20},
    "market": {"gold": 40},
    "wall": {"defense": 30}
}

# هزینه ساخت ساختمان‌ها
BUILDING_COST = {
    "farm": {"gold": 30, "minerals": 10},
    "mine": {"gold": 40, "minerals": 20},
    "barracks": {"gold": 50, "minerals": 30},
    "market": {"gold": 40, "minerals": 0},
    "wall": {"gold": 30, "minerals": 40}
}

# زمان ساخت (دوره)
BUILDING_TIME = {
    "farm": 1,
    "mine": 1,
    "barracks": 1,
    "market": 1,
    "wall": 2
}

# نقش‌های بازی و تخصصشون
ROLES = {
    "merchant": {"name": "تاجر", "specialty": "gold", "bonus": 1.2},
    "general": {"name": "ژنرال", "specialty": "soldiers", "bonus": 1.2},
    "farmer": {"name": "کشاورز", "specialty": "food", "bonus": 1.2},
    "miner": {"name": "معدنچی", "specialty": "minerals", "bonus": 1.2},
    "architect": {"name": "معمار", "specialty": "build_speed", "bonus": 1.2},
    "scientist": {"name": "دانشمند", "specialty": "upgrade", "bonus": 0},
    "spy": {"name": "جاسوس", "specialty": "intel", "bonus": 0}
}

# درصد غارت در حمله موفق
LOOT_PERCENT = 0.4

# ضریب دفاع سرباز
DEFENSE_MULTIPLIER = 1.3

# هزینه‌های جاسوس
SPY_COST = {
    "resources": 20,
    "simple_trades": 30,
    "advanced_contract": 50
}

# هزینه ارسال قرارداد پیشرفته
ADVANCED_CONTRACT_COST = 20

# هزینه یادگیری تکنولوژی دانشمند
SCIENTIST_LEARN_COST = 100
# هزینه اجرای ارتقا
SCIENTIST_UPGRADE_COST = 50