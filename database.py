# database.py - مدیریت دیتابیس SQLite
import sqlite3
from config import DATABASE_PATH

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        
        # جدول بازی‌ها
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT UNIQUE,
                admin_id TEXT,
                period_hours INTEGER DEFAULT 24,
                is_active BOOLEAN DEFAULT 1,
                current_period INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول بازیکنان
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                username TEXT,
                game_id INTEGER,
                role TEXT,
                gold INTEGER DEFAULT 100,
                soldiers INTEGER DEFAULT 50,
                food INTEGER DEFAULT 200,
                minerals INTEGER DEFAULT 30,
                defense_bonus REAL DEFAULT 0,
                is_alive BOOLEAN DEFAULT 1,
                FOREIGN KEY (game_id) REFERENCES games(id)
            )
        ''')
        
        # جدول ساختمان‌ها
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS buildings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER,
                building_type TEXT,
                level INTEGER DEFAULT 1,
                production_multiplier REAL DEFAULT 1.0,
                built_at_period INTEGER DEFAULT 0,
                FOREIGN KEY (player_id) REFERENCES players(id)
            )
        ''')
        
        # جدول معاملات ساده
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS simple_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER,
                from_player_id INTEGER,
                to_player_id INTEGER,
                from_resources TEXT,
                to_resources TEXT,
                period INTEGER,
                is_public BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول قراردادهای پیشرفته
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS advanced_contracts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER,
                from_player_id INTEGER,
                to_player_id INTEGER,
                contract_text TEXT,
                is_accepted BOOLEAN DEFAULT 0,
                is_public BOOLEAN DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                period INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول اتحادها
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alliances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER,
                player1_id INTEGER,
                player2_id INTEGER,
                is_public BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول حملات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attacks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER,
                attacker_id INTEGER,
                defender_id INTEGER,
                attacker_soldiers INTEGER,
                result TEXT,
                loot_gold INTEGER DEFAULT 0,
                loot_food INTEGER DEFAULT 0,
                loot_minerals INTEGER DEFAULT 0,
                attacker_losses INTEGER DEFAULT 0,
                period INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول تکنولوژی‌های دانشمند
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scientist_techs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER,
                building_type TEXT,
                tech_level INTEGER DEFAULT 1,
                FOREIGN KEY (player_id) REFERENCES players(id)
            )
        ''')
        
        # جدول هزینه‌های جاسوسی
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS spy_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER,
                spy_id INTEGER,
                target_id INTEGER,
                action_type TEXT,
                cost INTEGER,
                period INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()
    
    def execute(self, query, params=None):
        cursor = self.conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        self.conn.commit()
        return cursor
    
    def fetchone(self, query, params=None):
        cursor = self.execute(query, params)
        return cursor.fetchone()
    
    def fetchall(self, query, params=None):
        cursor = self.execute(query, params)
        return cursor.fetchall()