from core.stocks import get_average_daily_volume, get_stock_price
from utils.config import load_config
from utils.logger import logger


def calculate_price_drift(entry_price: float, current_price: float) -> float:
    if entry_price == 0:
        return 1.0
    return abs(current_price - entry_price) / entry_price


def calculate_conviction_score(trade_size: float, avg_daily_volume: float, price: float) -> float:
    if avg_daily_volume == 0 or price == 0:
        return 0.0
    daily_dollar_volume = avg_daily_volume * price
    return trade_size / daily_dollar_volume if daily_dollar_volume > 0 else 0.0


def calculate_max_safe_size(ticker: str, max_impact_pct: float = 0.02) -> float:
    try:
        avg_volume = get_average_daily_volume(ticker)
        price = get_stock_price(ticker)
        if not avg_volume or not price:
            return 0.0
        daily_dollar_volume = avg_volume * price
        return daily_dollar_volume * max_impact_pct
    except Exception as e:
        logger.error(f"Error calculating safe size for {ticker}: {e}")
        return 0.0


def calculate_position_size(budget: float, safe_size: float, risk_ceiling: float) -> float:
    return min(budget, safe_size, risk_ceiling)


def calculate_stop_loss(entry_price: float, stop_loss_pct: float) -> float:
    return entry_price * (1 - stop_loss_pct)


def calculate_take_profit(entry_price: float, take_profit_pct: float) -> float:
    return entry_price * (1 + take_profit_pct)


def check_stop_loss(current_price: float, stop_loss: float) -> bool:
    return current_price <= stop_loss


def check_take_profit(current_price: float, take_profit: float) -> bool:
    return current_price >= take_profit


def calculate_risk_ceiling(open_positions: int, max_positions: int, total_budget: float) -> float:
    if open_positions >= max_positions:
        return 0.0
    remaining_slots = max_positions - open_positions
    return total_budget / max_positions