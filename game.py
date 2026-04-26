# game.py - مدیریت اصلی بازی
from database import Database
from models import Game, Player
from buildings import Building
from battle import Battle
from trade import Trade
from config import ROLES, SPY_COST
import random

db = Database()

class GameManager:
    @staticmethod
    def start_new_game(group_id, admin_id, period_hours):
        """شروع بازی جدید"""
        existing = Game.get_active_game(group_id)
        if existing:
            return None, "یه بازی فعال توی این گروه هست!"
        
        game = Game(group_id, admin_id, period_hours)
        game.save()
        return game, "بازی جدید ساخته شد! بازیکنا با /join بیان تو بازی."
    
    @staticmethod
    def join_game(user_id, username, group_id):
        """عضویت در بازی"""
        game = Game.get_active_game(group_id)
        if not game:
            return None, "بازی فعالی تو این گروه نیست!"
        
        existing = Player.get_by_user_game(user_id, game.game_id)
        if existing:
            return None, "تو بازی هستی که!"
        
        player = Player(user_id, username, game.game_id)
        player.save()
        return player, "به بازی پیوستی! صبر کن تا ادمین انتخاب نقش رو شروع کنه."
    
    @staticmethod
    def start_role_selection(group_id):
        """شروع فرآیند انتخاب نقش"""
        game = Game.get_active_game(group_id)
        if not game:
            return None, "بازی فعالی نیست!"
        
        players = game.get_players()
        if len(players) < 2:
            return None, "حداقل ۲ بازیکن لازمه!"
        
        random.shuffle(players)
        return players, "لیست بازیکنا به ترتیب انتخاب نقش (قرعه‌کشی شده)"
    
    @staticmethod
    def select_role(user_id, game_id, role):
        """انتخاب نقش توسط بازیکن"""
        player = Player.get_by_user_game(user_id, game_id)
        if not player:
            return False, "تو بازی نیستی!"
        
        if player.role:
            return False, "نقش رو قبلاً انتخاب کردی!"
        
        if role not in ROLES:
            return False, "این نقش وجود نداره!"
        
        # بررسی اینکه نقش قبلاً انتخاب نشده باشه
        taken = db.fetchone(
            "SELECT id FROM players WHERE game_id=? AND role=? AND is_alive=1",
            (game_id, role))
        if taken:
            return False, "این نقش قبلاً انتخاب شده!"
        
        player.role = role
        db.execute("UPDATE players SET role=? WHERE id=?", (role, player.player_id))
        
        return True, f"نقش {ROLES[role]['name']} رو انتخاب کردی!"
    
    @staticmethod
    def produce_resources(game_id, current_period):
        """تولید منابع در شروع دوره"""
        game = Game.get_active_game(None)
        game.game_id = game_id
        players = game.get_players()
        
        for player in players:
            if not player.is_alive:
                continue
            
            production = Building.calculate_production(player, current_period)
            
            for resource, amount in production.items():
                player.resources[resource] = player.resources.get(resource, 0) + amount
            
            player.update_resources()
    
    @staticmethod
    def spy_action(spy_player, target_player, action_type, game_id, current_period):
        """عملیات جاسوسی"""
        if spy_player.role != "spy":
            return None, "فقط جاسوس می‌تونه جاسوسی کنه!"
        
        cost = SPY_COST.get(action_type)
        if not cost:
            return None, "نوع عملیات نامعتبره!"
        
        if spy_player.resources["gold"] < cost:
            return None, f"طلا کافی نداری! نیاز: {cost} طلا"
        
        spy_player.resources["gold"] -= cost
        spy_player.update_resources()
        
        # ذخیره لاگ
        db.execute('''
            INSERT INTO spy_logs (game_id, spy_id, target_id, action_type, cost, period)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (game_id, spy_player.player_id, target_player.player_id, action_type, cost, current_period))
        
        if action_type == "resources":
            return target_player.resources, "منابع بازیکن هدف"
        
        elif action_type == "simple_trades":
            trades = db.fetchall('''
                SELECT from_resources, to_resources, period FROM simple_trades
                WHERE game_id=? AND (from_player_id=? OR to_player_id=?)
                AND period >= ? - 3
            ''', (game_id, target_player.player_id, target_player.player_id, current_period))
            return trades, "معاملات ساده ۳ دور اخیر"
        
        elif action_type == "advanced_contract":
            contracts = db.fetchall('''
                SELECT id, from_player_id, to_player_id FROM advanced_contracts
                WHERE game_id=? AND (from_player_id=? OR to_player_id=?)
                AND is_active=1
            ''', (game_id, target_player.player_id, target_player.player_id))
            return contracts, "قراردادهای پیشرفته فعال"