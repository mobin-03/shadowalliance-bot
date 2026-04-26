# battle.py - سیستم نبرد
from database import Database
from models import Player
from config import LOOT_PERCENT, DEFENSE_MULTIPLIER

db = Database()

class Battle:
    @staticmethod
    def calculate_attack_power(attacker, soldiers_used):
        """محاسبه قدرت حمله"""
        return soldiers_used * 1.0  # پایه حمله
    
    @staticmethod
    def calculate_defense_power(defender):
        """محاسبه قدرت دفاع"""
        base_defense = defender.resources["soldiers"] * DEFENSE_MULTIPLIER
        
        # دریافت دیوارهای دفاعی
        walls = db.fetchall('''
            SELECT level, production_multiplier FROM buildings
            WHERE player_id=? AND building_type='wall'
        ''', (defender.player_id,))
        
        wall_bonus = 0
        for w in walls:
            wall_bonus += 30 * w[0] * w[1]  # هر دیوار ۳۰ دفاع
        
        return base_defense + wall_bonus
    
    @staticmethod
    def calculate_losses(attack_power, defense_power, soldiers_used):
        """محاسبه تلفات مهاجم"""
        if attack_power == 0:
            return soldiers_used
        losses = (defense_power / attack_power) * soldiers_used * 0.3
        return round(min(losses, soldiers_used))
    
    @staticmethod
    def attack(attacker, defender, soldiers_used, game_id, current_period):
        """اجرای حمله"""
        if soldiers_used > attacker.resources["soldiers"]:
            return None, "سرباز کافی نداری!"
        
        attack_power = Battle.calculate_attack_power(attacker, soldiers_used)
        defense_power = Battle.calculate_defense_power(defender)
        
        losses = Battle.calculate_losses(attack_power, defense_power, soldiers_used)
        remaining = soldiers_used - losses
        
        # کاهش سربازان مهاجم
        attacker.resources["soldiers"] -= soldiers_used
        attacker.resources["soldiers"] += remaining
        
        if attack_power > defense_power:
            # حمله موفق
            loot_gold = round(defender.resources["gold"] * LOOT_PERCENT)
            loot_food = round(defender.resources["food"] * LOOT_PERCENT)
            loot_minerals = round(defender.resources["minerals"] * LOOT_PERCENT)
            
            attacker.resources["gold"] += loot_gold
            attacker.resources["food"] += loot_food
            attacker.resources["minerals"] += loot_minerals
            
            # حذف مدافع
            defender.kill()
            
            attacker.update_resources()
            
            # ذخیره لاگ حمله
            db.execute('''
                INSERT INTO attacks (game_id, attacker_id, defender_id, attacker_soldiers,
                                   result, loot_gold, loot_food, loot_minerals,
                                   attacker_losses, period)
                VALUES (?, ?, ?, ?, 'win', ?, ?, ?, ?, ?)
            ''', (game_id, attacker.player_id, defender.player_id, soldiers_used,
                  loot_gold, loot_food, loot_minerals, losses, current_period))
            
            return {
                "win": True,
                "losses": losses,
                "loot": {"gold": loot_gold, "food": loot_food, "minerals": loot_minerals},
                "defender_eliminated": True
            }, None
        else:
            # حمله ناموفق
            attacker.update_resources()
            
            db.execute('''
                INSERT INTO attacks (game_id, attacker_id, defender_id, attacker_soldiers,
                                   result, attacker_losses, period)
                VALUES (?, ?, ?, ?, 'lose', ?, ?)
            ''', (game_id, attacker.player_id, defender.player_id, soldiers_used,
                  losses, current_period))
            
            return {
                "win": False,
                "losses": losses,
                "loot": {"gold": 0, "food": 0, "minerals": 0},
                "defender_eliminated": False
            }, None
    
    @staticmethod
    def joint_attack(attackers_dict, defender, game_id, current_period):
        """حمله مشترک - attackers_dict: {player: soldiers_count}"""
        total_attack_power = 0
        total_soldiers = 0
        
        for player, soldiers in attackers_dict.items():
            if soldiers > player.resources["soldiers"]:
                return None, f"{player.username} سرباز کافی نداره!"
            total_attack_power += Battle.calculate_attack_power(player, soldiers)
            total_soldiers += soldiers
        
        defense_power = Battle.calculate_defense_power(defender)
        
        if total_attack_power > defense_power:
            # حمله موفق
            total_loot = {
                "gold": round(defender.resources["gold"] * LOOT_PERCENT),
                "food": round(defender.resources["food"] * LOOT_PERCENT),
                "minerals": round(defender.resources["minerals"] * LOOT_PERCENT)
            }
            
            # تقسیم غارت بر اساس سهم سربازان
            for player, soldiers in attackers_dict.items():
                player.resources["soldiers"] -= soldiers
                
                # محاسبه تلفات به نسبت
                losses = Battle.calculate_losses(
                    Battle.calculate_attack_power(player, soldiers),
                    defense_power * (soldiers / total_soldiers),
                    soldiers
                )
                player.resources["soldiers"] += (soldiers - losses)
                
                # سهم از غارت
                share = soldiers / total_soldiers
                player.resources["gold"] += round(total_loot["gold"] * share)
                player.resources["food"] += round(total_loot["food"] * share)
                player.resources["minerals"] += round(total_loot["minerals"] * share)
                
                player.update_resources()
            
            defender.kill()
            
            return {"win": True, "total_loot": total_loot, "defender_eliminated": True}, None
        else:
            # حمله ناموفق - همه سربازان از دست می‌رن
            for player, soldiers in attackers_dict.items():
                player.resources["soldiers"] -= soldiers
                player.update_resources()
            
            return {"win": False, "defender_eliminated": False}, None