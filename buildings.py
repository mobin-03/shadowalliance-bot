# buildings.py - مدیریت ساختمان‌ها
from database import Database
from config import BUILDING_COST, BUILDING_TIME, BUILDING_PRODUCTION, ROLES
import math

db = Database()

class Building:
    @staticmethod
    def can_build(player, building_type):
        """بررسی آیا بازیکن می‌تونه ساختمان بسازه"""
        cost = BUILDING_COST[building_type]
        return (player.resources["gold"] >= cost["gold"] and 
                player.resources["minerals"] >= cost.get("minerals", 0))
    
    @staticmethod
    def build(player, building_type, current_period):
        """ساخت ساختمان جدید"""
        cost = BUILDING_COST[building_type]
        player.resources["gold"] -= cost["gold"]
        player.resources["minerals"] -= cost.get("minerals", 0)
        
        # محاسبه زمان ساخت با توجه به نقش معمار
        build_time = BUILDING_TIME[building_type]
        if player.role == "architect":
            build_time = math.floor(build_time / 1.2)
        
        ready_period = current_period + build_time
        
        db.execute('''
            INSERT INTO buildings (player_id, building_type, built_at_period)
            VALUES (?, ?, ?)
        ''', (player.player_id, building_type, ready_period))
        
        player.update_resources()
        return build_time
    
    @staticmethod
    def get_player_buildings(player_id, current_period):
        """دریافت ساختمان‌های آماده یک بازیکن"""
        rows = db.fetchall('''
            SELECT id, building_type, level, production_multiplier
            FROM buildings
            WHERE player_id=? AND built_at_period <= ?
        ''', (player_id, current_period))
        return rows
    
    @staticmethod
    def calculate_production(player, current_period):
        """محاسبه تولید منابع در هر دوره"""
        buildings = Building.get_player_buildings(player.player_id, current_period)
        
        production = {"gold": 0, "soldiers": 0, "food": 0, "minerals": 0, "defense": 0}
        
        role_bonus = ROLES.get(player.role, {}).get("specialty", "")
        
        for b in buildings:
            b_type = b[1]
            level = b[2]
            multiplier = b[3]
            
            base_prod = BUILDING_PRODUCTION.get(b_type, {})
            for resource, amount in base_prod.items():
                prod_amount = amount * level * multiplier
                
                # اعمال بونوس نقش
                if role_bonus == resource:
                    prod_amount *= 1.2
                
                production[resource] += prod_amount
        
        return production
    
    @staticmethod
    def scientist_can_upgrade(player, building_type):
        """بررسی آیا دانشمند می‌تونه این ساختمان رو ارتقا بده"""
        if player.role != "scientist":
            return False
        
        # بررسی هزینه
        if player.resources["gold"] < 50:  # SCIENTIST_UPGRADE_COST
            return False
        
        # بررسی یادگیری تکنولوژی
        tech = db.fetchone('''
            SELECT tech_level FROM scientist_techs
            WHERE player_id=? AND building_type=?
        ''', (player.player_id, building_type))
        
        if not tech:
            return False  # هنوز یاد نگرفته
        
        return True
    
    @staticmethod
    def scientist_learn_tech(player, building_type):
        """دانشمند تکنولوژی جدید یاد می‌گیره"""
        if player.resources["gold"] < 100:
            return False
        
        player.resources["gold"] -= 100
        player.update_resources()
        
        existing = db.fetchone('''
            SELECT id FROM scientist_techs
            WHERE player_id=? AND building_type=?
        ''', (player.player_id, building_type))
        
        if existing:
            db.execute('''
                UPDATE scientist_techs SET tech_level = tech_level + 1
                WHERE player_id=? AND building_type=?
            ''', (player.player_id, building_type))
        else:
            db.execute('''
                INSERT INTO scientist_techs (player_id, building_type, tech_level)
                VALUES (?, ?, 1)
            ''', (player.player_id, building_type))
        
        return True
    
    @staticmethod
    def scientist_upgrade_building(player, building_id, building_type):
        """ارتقای ساختمان توسط دانشمند"""
        if not Building.scientist_can_upgrade(player, building_type):
            return False
        
        player.resources["gold"] -= 50
        player.update_resources()
        
        db.execute('''
            UPDATE buildings SET production_multiplier = production_multiplier + 0.1
            WHERE id=?
        ''', (building_id,))
        
        return True