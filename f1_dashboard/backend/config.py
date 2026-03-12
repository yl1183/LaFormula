"""Single source of truth for all configuration."""
import os
from dotenv import load_dotenv
load_dotenv()

# === Kalshi API ===
KALSHI_API_KEY = os.getenv("KALSHI_API_KEY", "")
KALSHI_PEM_PATH = os.getenv("KALSHI_PEM_PATH", "")
KALSHI_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"

# === Kill Switch PIN ===
KILL_PIN = os.getenv("CONFIRM_PIN", "483291")  # 6-digit PIN for kill switch

# === Bankroll ===
INITIAL_BANKROLL = 100.0
STOP_LOSS_FLOOR = 50.0          # halt if bankroll drops below this
MAX_PER_TRADE_PCT = 0.07        # 7% of bankroll per trade
MAX_PER_WEEKEND_PCT = 0.15      # 15% of bankroll per weekend
FLAT_BET_SIZE = 5.0             # flat $5/trade (first 4 races: $2.50)
CALIBRATION_RACES = 4           # half-size for first N races

# === Strategy Thresholds ===
# Sleeve A: Buy YES podium for underpriced drivers (any grid position - threshold handles filtering)
SLEEVE_A_MIN_EDGE = 0.15       # base_rate - price >= 15%
SLEEVE_A_GRID_RANGE = (1, 20)  # Any position; the edge threshold naturally filters

# Sleeve B: Sell overpriced P2/P3 winner (buy NO)
SLEEVE_B_MIN_EDGE = 0.08       # price - base_rate >= 8%
SLEEVE_B_GRID_RANGE = (2, 3)

# Sleeve E: Sell any overpriced winner priced 15-50%
SLEEVE_E_MIN_EDGE = 0.10       # price - base_rate >= 10%
SLEEVE_E_PRICE_RANGE = (0.15, 0.50)

# === Base Rates (2019-2024, ~2500 results) ===
PODIUM_BASE_RATES = {
    1: 0.740, 2: 0.567, 3: 0.433, 4: 0.280, 5: 0.217,
    6: 0.150, 7: 0.117, 8: 0.083, 9: 0.067, 10: 0.050,
    11: 0.040, 12: 0.030, 13: 0.020, 14: 0.015, 15: 0.010,
    16: 0.008, 17: 0.005, 18: 0.003, 19: 0.002, 20: 0.001
}

WINNER_BASE_RATES = {
    1: 0.450, 2: 0.230, 3: 0.120, 4: 0.067, 5: 0.050,
    6: 0.033, 7: 0.020, 8: 0.013, 9: 0.008, 10: 0.005,
    11: 0.003, 12: 0.002, 13: 0.001, 14: 0.001, 15: 0.001,
    16: 0.000, 17: 0.000, 18: 0.000, 19: 0.000, 20: 0.000
}

# === 2026 Calendar (official F1 calendar, 24 races) ===
RACES_2026 = [
    # Code = Kalshi slug prefix. Confirmed format: KXF1RACE-{code}GP26-{DRIVER}
    # Australian GP confirmed as "AUSGP26" from live API testing
    {"round": 1,  "name": "Australian GP",      "date": "2026-03-08", "circuit": "Albert Park",  "code": "AUS"},
    {"round": 2,  "name": "Chinese GP",          "date": "2026-03-15", "circuit": "Shanghai",     "code": "CHN"},
    {"round": 3,  "name": "Japanese GP",         "date": "2026-03-29", "circuit": "Suzuka",       "code": "JPN"},
    {"round": 4,  "name": "Bahrain GP",          "date": "2026-04-12", "circuit": "Sakhir",       "code": "BHR"},
    {"round": 5,  "name": "Saudi Arabian GP",    "date": "2026-04-19", "circuit": "Jeddah",       "code": "SAU"},
    {"round": 6,  "name": "Miami GP",            "date": "2026-05-03", "circuit": "Miami",        "code": "MIA"},
    {"round": 7,  "name": "Canadian GP",         "date": "2026-05-24", "circuit": "Montreal",     "code": "CAN"},
    {"round": 8,  "name": "Monaco GP",           "date": "2026-06-07", "circuit": "Monaco",       "code": "MON"},
    {"round": 9,  "name": "Spanish GP",          "date": "2026-06-14", "circuit": "Madrid",       "code": "ESP"},
    {"round": 10, "name": "Austrian GP",         "date": "2026-06-28", "circuit": "Spielberg",    "code": "AUT"},
    {"round": 11, "name": "British GP",          "date": "2026-07-05", "circuit": "Silverstone",  "code": "GBR"},
    {"round": 12, "name": "Belgian GP",          "date": "2026-07-19", "circuit": "Spa",          "code": "BEL"},
    {"round": 13, "name": "Hungarian GP",        "date": "2026-07-26", "circuit": "Budapest",     "code": "HUN"},
    {"round": 14, "name": "Dutch GP",            "date": "2026-08-23", "circuit": "Zandvoort",    "code": "NED"},
    {"round": 15, "name": "Italian GP",          "date": "2026-09-06", "circuit": "Monza",        "code": "ITA"},
    {"round": 16, "name": "Azerbaijan GP",       "date": "2026-09-13", "circuit": "Baku",         "code": "AZE"},
    {"round": 17, "name": "Singapore GP",        "date": "2026-09-26", "circuit": "Marina Bay",   "code": "SGP"},
    {"round": 18, "name": "United States GP",    "date": "2026-10-11", "circuit": "COTA",         "code": "USA"},
    {"round": 19, "name": "Mexico City GP",      "date": "2026-10-25", "circuit": "Mexico City",  "code": "MEX"},
    {"round": 20, "name": "São Paulo GP",        "date": "2026-11-01", "circuit": "Interlagos",   "code": "BRA"},
    {"round": 21, "name": "Las Vegas GP",        "date": "2026-11-08", "circuit": "Las Vegas",    "code": "LVG"},
    {"round": 22, "name": "Qatar GP",            "date": "2026-11-22", "circuit": "Lusail",       "code": "QAT"},
    {"round": 23, "name": "Abu Dhabi GP",        "date": "2026-11-29", "circuit": "Yas Marina",   "code": "ABU"},
]
# Note: Round 24 TBC — the 24th date (Dec 6) may be Abu Dhabi or a replacement.
# Will update when official confirmation is available. Using 23 confirmed races.
RACES_2026 = RACES_2026[:23]  # Use only confirmed 23 for now

# === Polling ===
POLL_INTERVAL_SECONDS = 300  # 5 minutes
