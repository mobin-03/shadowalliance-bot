# models.py - کلاس‌های بازیکن و بازی
from database import Database
from config import INITIAL_RESOURCES, ROLES
import random

db = Database()

class Player:
    def __init__(self, user_id, username, game_id, role=None):
        self.user_id = user_id
        self.username = username
        self.game_id = game_id
        self.role = role
        self.resources = INITIAL_RESOURCES.copy()
        self.is_alive = True
        self.player_id = None
    
    def save(self):
        db.execute('''
            INSERT INTO players (user_id, username, game_id, role, gold, soldiers, food, minerals)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (self.user_id, self.username, self.game_id, self.role,
              self.resources["gold"], self.resources["soldiers"],
              self.resources["food"], self.resources["minerals"]))
        self.player_id = db.fetchone("SELECT last_insert_rowid()")[0]
    
    @staticmethod
    def get_by_user_game(user_id, game_id):
        row = db.fetchone(
            "SELECT * FROM players WHERE user_id=? AND game_id=? AND is_alive=1",
            (str(user_id), game_id))
        if row:
            p = Player(row[1], row[2], row[3], row[4])
            p.player_id = row[0]
            p.resources = {"gold": row[5], "soldiers": row[6], "food": row[7], "minerals": row[8]}
            p.is_alive = bool(row[10])
            return p
        return None
    
    def update_resources(self):
        db.execute('''
            UPDATE players SET gold=?, soldiers=?, food=?, minerals=?
            WHERE id=?
        ''', (self.resources["gold"], self.resources["soldiers"],
              self.resources["food"], self.resources["minerals"], self.player_id))
    
    def kill(self):
        self.is_alive = False
        db.execute("UPDATE players SET is_alive=0 WHERE id=?", (self.player_id,))

class Game:
    def __init__(self, group_id, admin_id, period_hours=24):
        self.group_id = group_id
        self.admin_id = admin_id
        self.period_hours = period_hours
        self.players = []
        self.available_roles = list(ROLES.keys())
        self.is_active = True
        self.current_period = 0
    
    def save(self):
        db.execute('''
            INSERT INTO games (group_id, admin_id, period_hours)
            VALUES (?, ?, ?)
        ''', (self.group_id, self.admin_id, self.period_hours))
        self.game_id = db.fetchone("SELECT last_insert_rowid()")[0]
    
    @staticmethod
    def get_active_game(group_id):
        row = db.fetchone(
            "SELECT * FROM games WHERE group_id=? AND is_active=1", (group_id,))
        if row:
            g = Game(row[1], row[2], row[3])
            g.game_id = row[0]
            g.current_period = row[5]
            return g
        return None
    
    def get_players(self):
        rows = db.fetchall(
            "SELECT * FROM players WHERE game_id=? AND is_alive=1", (self.game_id,))
        self.players = []
        for row in rows:
            p = Player(row[1], row[2], self.game_id, row[4])
            p.player_id = row[0]
            p.resources = {"gold": row[5], "soldiers": row[6], "food": row[7], "minerals": row[8]}
            p.is_alive = bool(row[10])
            self.players.append(p)
        return self.players
    
    def role_selection_order(self):
        """قرعه‌کشی ترتیب انتخاب نقش"""
        players = self.get_players()
        random.shuffle(players)
        return players