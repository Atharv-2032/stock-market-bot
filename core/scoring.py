import numpy as np
from datetime import datetime, timezone
from core.stocks import get_return_after_date
from utils.logger import logger   
def calculate_sharpe(returns: list) -> float:
    if len(returns) < 3:
        return 0.0
    arr = np.array(returns, dtype=float)
    std = arr.std()
    if std == 0:
        return 0.0
    return float(arr.mean() / std)


def calculate_win_rate(returns: list) -> float:
    if not returns:
        return 0.0
    wins = sum(1 for r in returns if r > 0)
    return float(wins / len(returns))


def calculate_roi(returns: list) -> float:
    if not returns:
        return 0.0
    return float(np.mean(returns))


def calculate_avg_return(returns: list) -> float:
    if not returns:
        return 0.0
    return float(np.mean(returns))

def score_insider(filings: list, ticker: str, days: int = 30) -> dict:
    if not filings:
        logger.warning(f"No filings to score for {ticker}")
        return {}

    returns = []
    seen_dates = set()  # track dates we've already scored

    for filing in filings:
        date_str = filing.get("trade_date") or filing.get("filing_date") or filing.get("date", "")
        if not date_str:
            continue
        try:
            for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d-%b-%Y"]:
                try:
                    trade_date = datetime.strptime(date_str[:10], fmt)
                    break
                except ValueError:
                    continue
            else:
                continue

            # skip duplicate dates
            date_key = trade_date.strftime("%Y-%m-%d")
            if date_key in seen_dates:
                continue
            seen_dates.add(date_key)

            ret = get_return_after_date(ticker, trade_date, days=days)
            if ret is not None:
                returns.append(ret)
        except Exception as e:
            logger.warning(f"Error processing filing date {date_str}: {e}")
            continue

    if len(returns) < 3:
        logger.info(f"Not enough data points for {ticker} — only {len(returns)} returns")
        return {}

    scores = {
        "sharpe": round(calculate_sharpe(returns), 4),
        "win_rate": round(calculate_win_rate(returns), 4),
        "roi": round(calculate_roi(returns), 4),
        "avg_return": round(calculate_avg_return(returns), 4),
        "total_signals": len(returns),
        "returns": returns
    }

    logger.info(f"Scored {ticker} insider — sharpe: {scores['sharpe']} | win_rate: {scores['win_rate']} | signals: {len(returns)}")
    return scores


def score_options_trader(past_signals: list) -> dict:
    if not past_signals:
        return {}

    returns = []
    for signal in past_signals:
        ret = signal.get("actual_return")
        if ret is not None:
            returns.append(float(ret))

    if len(returns) < 3:
        return {}

    return {
        "sharpe": round(calculate_sharpe(returns), 4),
        "win_rate": round(calculate_win_rate(returns), 4),
        "roi": round(calculate_roi(returns), 4),
        "avg_return": round(calculate_avg_return(returns), 4),
        "total_signals": len(returns)
    }


def score_politician(trades: list, days: int = 30) -> dict:
    if not trades:
        return {}

    returns = []
    for trade in trades:
        ticker = trade.get("ticker", "").strip()
        trade_type = trade.get("trade_type", "").lower()
        date_str = trade.get("trade_date", "")

        if not ticker or not date_str:
            continue
        if "sale" in trade_type or "sell" in trade_type:
            continue

        try:
            for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d-%b-%Y"]:
                try:
                    trade_date = datetime.strptime(date_str[:10], fmt)
                    break
                except ValueError:
                    continue
            else:
                continue

            ret = get_return_after_date(ticker, trade_date, days=days)
            if ret is not None:
                returns.append(ret)
        except Exception as e:
            logger.warning(f"Error scoring politician trade: {e}")
            continue

    if len(returns) < 3:
        return {}

    return {
        "sharpe": round(calculate_sharpe(returns), 4),
        "win_rate": round(calculate_win_rate(returns), 4),
        "roi": round(calculate_roi(returns), 4),
        "avg_return": round(calculate_avg_return(returns), 4),
        "total_signals": len(returns)
    }


def passes_thresholds(scores: dict, config: dict) -> bool:
    if not scores:
        return False
    min_sharpe = config["scout"]["min_sharpe"]
    min_trades = config["scout"]["min_trades"]
    return (
        scores.get("sharpe", 0) >= min_sharpe and
        scores.get("total_signals", 0) >= min_trades
    )