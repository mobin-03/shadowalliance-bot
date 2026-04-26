# trade.py - سیستم معاملات و قراردادها
from database import Database
from config import ADVANCED_CONTRACT_COST

db = Database()

class Trade:
    @staticmethod
    def simple_trade(from_player, to_player, offer, request, game_id, current_period, is_public=False):
        """
        معامله ساده
        offer: {"gold": 100, "soldiers": 0, ...}
        request: {"gold": 0, "soldiers": 50, ...}
        """
        # بررسی موجودی
        for resource, amount in offer.items():
            if from_player.resources.get(resource, 0) < amount:
                return False, f"منبع {resource} کافی نداری!"
        
        for resource, amount in request.items():
            if to_player.resources.get(resource, 0) < amount:
                return False, f"طرف مقابل منبع {resource} کافی نداره!"
        
        # انجام معامله
        for resource, amount in offer.items():
            from_player.resources[resource] -= amount
            to_player.resources[resource] += amount
        
        for resource, amount in request.items():
            to_player.resources[resource] -= amount
            from_player.resources[resource] += amount
        
        from_player.update_resources()
        to_player.update_resources()
        
        # ذخیره در دیتابیس
        db.execute('''
            INSERT INTO simple_trades 
            (game_id, from_player_id, to_player_id, from_resources, to_resources, period, is_public)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (game_id, from_player.player_id, to_player.player_id,
              str(offer), str(request), current_period, int(is_public)))
        
        return True, "معامله با موفقیت انجام شد!"
    
    @staticmethod
    def propose_advanced_contract(from_player, to_player, contract_text, game_id, current_period, is_public=False):
        """پیشنهاد قرارداد پیشرفته"""
        if from_player.resources["gold"] < ADVANCED_CONTRACT_COST:
            return False, "طلا کافی برای ثبت قرارداد نداری! (نیاز: ۲۰ طلا)"
        
        from_player.resources["gold"] -= ADVANCED_CONTRACT_COST
        from_player.update_resources()
        
        db.execute('''
            INSERT INTO advanced_contracts
            (game_id, from_player_id, to_player_id, contract_text, is_public, period)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (game_id, from_player.player_id, to_player.player_id,
              contract_text, int(is_public), current_period))
        
        contract_id = db.fetchone("SELECT last_insert_rowid()")[0]
        
        return True, contract_id
    
    @staticmethod
    def accept_contract(contract_id, player_id):
        """پذیرش قرارداد پیشرفته"""
        contract = db.fetchone(
            "SELECT * FROM advanced_contracts WHERE id=? AND is_active=1",
            (contract_id,))
        
        if not contract:
            return False, "قرارداد پیدا نشد!"
        
        if contract[3] != player_id:
            return False, "این قرارداد برای تو نیست!"
        
        db.execute('''
            UPDATE advanced_contracts SET is_accepted=1
            WHERE id=?
        ''', (contract_id,))
        
        return True, "قرارداد پذیرفته شد! متن قرارداد ذخیره گردید."
    
    @staticmethod
    def report_violation(contract_id, reporter_id, game_admin_id):
        """گزارش نقض قرارداد به ادمین"""
        contract = db.fetchone(
            "SELECT * FROM advanced_contracts WHERE id=? AND is_active=1",
            (contract_id,))
        
        if not contract:
            return False, "قرارداد معتبر نیست!"
        
        # اینجا می‌تونیم یک نوتیفیکیشن به ادمین بفرستیم
        # فعلاً اطلاعات رو برمی‌گردونیم
        return True, {
            "contract_text": contract[4],
            "from_player": contract[2],
            "to_player": contract[3],
            "period": contract[8]
        }