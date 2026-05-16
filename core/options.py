import yfinance as yf
import pandas as pd
from datetime import datetime
from utils.logger import logger

# S&P 500
WATCHLIST = [
    "MMM", "AOS", "ABT", "ABBV", "ACN", "ADBE", "AMD", "AES", "AFL",
    "A", "APD", "ABNB", "AKAM", "ALB", "ARE", "ALGN", "ALLE", "LNT",
    "ALL", "GOOGL", "GOOG", "MO", "AMZN", "AMCR", "AEE", "AAL", "AEP",
    "AXP", "AIG", "AMT", "AWK", "AMP", "AME", "AMGN", "APH", "ADI",
    "ANSS", "AON", "APA", "AAPL", "AMAT", "APTV", "ACGL", "ADM", "ANET",
    "AJG", "AIZ", "T", "ATO", "ADSK", "ADP", "AZO", "AVB", "AVY",
    "AXON", "BKR", "BALL", "BAC", "BK", "BBWI", "BAX", "BDX", "BRK-B",
    "BBY", "BIO", "TECH", "BIIB", "BLK", "BX", "BA", "BCH", "BSX",
    "BMY", "AVGO", "BR", "BRO", "BF-B", "BLDR", "BG", "BXP", "CHRW",
    "CDNS", "CZR", "CPT", "CPB", "COF", "CAH", "KMX", "CCL", "CARR",
    "CTLT", "CAT", "CBOE", "CBRE", "CDW", "CE", "COR", "CNC", "CNX",
    "CDAY", "CF", "CRL", "SCHW", "CHTR", "CVX", "CMG", "CB", "CHD",
    "CI", "CINF", "CTAS", "CSCO", "C", "CFG", "CLX", "CME", "CMS",
    "KO", "CTSH", "CL", "CMCSA", "CMA", "CAG", "COP", "ED", "STZ",
    "CEG", "COO", "CPRT", "GLW", "CTVA", "CSGP", "COST", "CTRA", "CCI",
    "CSX", "CMI", "CVS", "DHR", "DRI", "DVA", "DE", "DAL", "XRAY",
    "DVN", "DXCM", "FANG", "DLR", "DFS", "DG", "DLTR", "D", "DPZ",
    "DOV", "DOW", "DHI", "DTE", "DUK", "DD", "EMN", "ETN", "EBAY",
    "ECL", "EIX", "EW", "EA", "ELV", "LLY", "EMR", "ENPH", "ETR",
    "EOG", "EPAM", "EQT", "EFX", "EQIX", "EQR", "ESS", "EL", "ETSY",
    "EG", "EVRG", "ES", "EXC", "EXPE", "EXPD", "EXR", "XOM", "FFIV",
    "FDS", "FICO", "FAST", "FRT", "FDX", "FIS", "FITB", "FSLR", "FE",
    "FI", "FLT", "FMC", "F", "FTNT", "FTV", "FOXA", "FOX", "BEN",
    "FCX", "GRMN", "IT", "GEHC", "GEN", "GNRC", "GD", "GE", "GIS",
    "GM", "GPC", "GILD", "GPN", "GL", "GS", "HAL", "HIG", "HAS",
    "HCA", "DOC", "HSIC", "HSY", "HES", "HPE", "HLT", "HOLX", "HD",
    "HON", "HRL", "HST", "HWM", "HPQ", "HUBB", "HUM", "HBAN", "HII",
    "IBM", "IEX", "IDXX", "ITW", "ILMN", "INCY", "IR", "PODD", "INTC",
    "ICE", "IFF", "IP", "IPG", "INTU", "ISRG", "IVZ", "INVH", "IQV",
    "IRM", "JBHT", "JBL", "JKHY", "J", "JNJ", "JCI", "JPM", "JNPR",
    "K", "KVUE", "KDP", "KEY", "KEYS", "KMB", "KIM", "KMI", "KLAC",
    "KHC", "KR", "LHX", "LH", "LRCX", "LW", "LVS", "LDOS", "LEN",
    "LIN", "LYV", "LKQ", "LMT", "L", "LOW", "LULU", "LYB", "MTB",
    "MRO", "MPC", "MKTX", "MAR", "MMC", "MLM", "MAS", "MA", "MTCH",
    "MKC", "MCD", "MCK", "MDT", "MRK", "META", "MET", "MTD", "MGM",
    "MCHP", "MU", "MSFT", "MAA", "MRNA", "MHK", "MOH", "TAP", "MDLZ",
    "MPWR", "MNST", "MCO", "MS", "MOS", "MSI", "MSCI", "NDAQ", "NTAP",
    "NFLX", "NEM", "NWSA", "NWS", "NEE", "NKE", "NI", "NDSN", "NSC",
    "NTRS", "NOC", "NCLH", "NRG", "NUE", "NVDA", "NVR", "NXPI", "ORLY",
    "OXY", "ODFL", "OMC", "ON", "OKE", "ORCL", "OTIS", "PCAR", "PKG",
    "PANW", "PARA", "PH", "PAYX", "PAYC", "PYPL", "PNR", "PEP", "PFE",
    "PCG", "PM", "PSX", "PNW", "PXD", "PNC", "POOL", "PPG", "PPL",
    "PFG", "PG", "PGR", "PLD", "PRU", "PEG", "PTVE", "PTC", "PSA",
    "PHM", "QRVO", "PWR", "QCOM", "DGX", "RL", "RJF", "RTX", "O",
    "REG", "REGN", "RF", "RSG", "RMD", "RVTY", "ROK", "ROL", "ROP",
    "ROST", "RCL", "SPGI", "CRM", "SBAC", "SLB", "STX", "SRE", "NOW",
    "SHW", "SPG", "SWKS", "SJM", "SNA", "SO", "LUV", "SWK", "SBUX",
    "STT", "STLD", "STE", "SYK", "SYF", "SNPS", "SYY", "TMUS", "TROW",
    "TTWO", "TPR", "TRGP", "TGT", "TEL", "TDY", "TFX", "TER", "TSLA",
    "TXN", "TXT", "TMO", "TJX", "TSCO", "TT", "TDG", "TRV", "TRMB",
    "TFC", "TYL", "TSN", "USB", "UDR", "ULTA", "UNP", "UAL", "UPS",
    "URI", "UNH", "UHS", "VLO", "VTR", "VRSN", "VRSK", "VZ", "VRTX",
    "VFC", "VTRS", "VICI", "V", "VMC", "WRB", "GWW", "WAB", "WBA",
    "WMT", "DIS", "WBD", "WM", "WAT", "WEC", "WFC", "WELL", "WST",
    "WDC", "WHR", "WRK", "WY", "WHR", "WLTW", "WYNN", "XEL", "XYL",
    "YUM", "ZBRA", "ZBH", "ZTS"
]

def get_options_chain(ticker:str) -> dict:
    try:
        stock = yf.Ticker(ticker)
        expirations = stock.options
        if not expirations:
            return {}
        
        nearest_expiry = expirations[0]
        chain = stock.option_chain(nearest_expiry)
        return{
            "ticker": ticker,
            "expiry": nearest_expiry,
            "calls": chain.calls,
            "puts": chain.puts
        }
    except Exception as e:
        logger.warning(f"Error fetching options chain for {ticker}: {e}")
        return {}

def calculate_unusual_activity(chain:dict)->list:
    if not chain:
        return []

    unusual = []
    ticker = chain["ticker"]
    expiry = chain["expiry"]

    for option_type, df in [("CALL", chain["calls"]), ("PUT", chain["puts"])]:
        if df is None or df.empty:
            continue
        try:
            for _, row in df.iterrows():
                volume = row.get("volume", 0)
                open_interest = row.get("openInterest", 0)
                strike = row.get("strike", 0)
                last_price = row.get("lastPrice", 0)

                if pd.isna(volume) or pd.isna(open_interest):
                    continue
                if open_interest == 0:
                    continue

                volume = int(volume)
                open_interest = int(open_interest)
                ratio = volume / open_interest

                unusual.append({
                    "ticker": ticker,
                    "option_type": option_type,
                    "strike": strike,
                    "expiry": expiry,
                    "volume": volume,
                    "open_interest": open_interest,
                    "volume_oi_ratio": round(ratio, 2),
                    "last_price": last_price,
                    "direction": "BULLISH" if option_type == "CALL" else "BEARISH",
                    "timestamp": datetime.now().isoformat()
                })
        except Exception as e:
            logger.warning(f"Error processing {option_type} chain for {ticker}: {e}")
            continue

    return unusual

def get_unusual_options_activity(tickers:list = None) -> list:
    if tickers is None:
        tickers = WATCHLIST

    all_unusual = []
    for ticker in tickers:
        try:
            chain = get_options_chain(ticker)
            if not chain:
                continue
            unusual = calculate_unusual_activity(chain)
            all_unusual.extend(unusual)
        except Exception as e:
            logger.warning(f"Error processing {ticker}: {e}")
            continue

    logger.info(f"Fetched {len(all_unusual)} options records across {len(tickers)} tickers")
    return all_unusual

def filter_significant_options(activities: list, min_volume: int = 500, min_ratio: float = 2.0) -> list:
    significant = []
    for activity in activities:
        if not activity:
            continue
        volume = activity.get("volume", 0)
        ratio = activity.get("volume_oi_ratio", 0)
        if volume >= min_volume and ratio >= min_ratio:
            significant.append(activity)
    logger.info(f"Filtered to {len(significant)} significant options signals")
    return significant

def parse_options_signal(activity: dict) -> dict:
    return activity