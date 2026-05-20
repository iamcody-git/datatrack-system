"""Shared business logic for Data Track (desktop + web)."""

from __future__ import annotations

import datetime
import io
import math
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

try:
    import requests
except ImportError:
    requests = None

try:
    import openpyxl
except ImportError:
    openpyxl = None

APP_NAME = "Data Track Software"
APP_CREDIT = "by pravin"
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR)))
DB_FILE = DATA_DIR / "data_track.db"
UPLOAD_DIR = DATA_DIR / "uploads"


def open_data_folder() -> tuple[bool, str]:
    """Open DATA_DIR in the OS file manager (database + uploads)."""
    if os.environ.get("RENDER"):
        return False, "On Render, data lives on the server — use Download database below."
    folder = DATA_DIR.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = str(folder)
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return True, f"Opened folder: {path}"
    except OSError as exc:
        return False, f"Could not open folder: {exc}"


LEVERAGE = 25
MIN_UNITS = 1000
RISK_WARN = 3.0
ASSETS = ["EUR/USD", "GBP/USD", "USD/JPY", "DXY"]
FALLBACK_FX = {"EUR/USD": 1.0820, "GBP/USD": 1.2540, "USD/JPY": 155.0, "DXY": 104.50}
NEPSE_FALLBACK = {"index": 2085.42, "change": 12.34, "change_pct": 0.60, "_src": "Static fallback"}
RESULTS = ["WIN", "LOSS", "BE"]
DIRECTIONS = ["LONG", "SHORT"]
JOURNAL_CATEGORIES = ["daily", "weekly", "monthly", "review", "other"]
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv"}
GROUP_MODES = {
    "overall": "Overall",
    "per20": "20-trade blocks",
    "weekly": "Weekly",
    "monthly": "Monthly",
    "yearly": "Yearly",
    "time": "NY time window",
}


class NewYorkFallback(datetime.tzinfo):
    def _dst_bounds(self, year):
        march_8 = datetime.datetime(year, 3, 8, 2)
        second_sunday_march = march_8 + datetime.timedelta(days=(6 - march_8.weekday()) % 7)
        nov_1 = datetime.datetime(year, 11, 1, 2)
        first_sunday_nov = nov_1 + datetime.timedelta(days=(6 - nov_1.weekday()) % 7)
        return second_sunday_march, first_sunday_nov

    def dst(self, dt):
        if dt is None:
            return datetime.timedelta(0)
        start, end = self._dst_bounds(dt.year)
        naive = dt.replace(tzinfo=None)
        return datetime.timedelta(hours=1) if start <= naive < end else datetime.timedelta(0)

    def utcoffset(self, dt):
        return datetime.timedelta(hours=-5) + self.dst(dt)

    def tzname(self, dt):
        return "EDT" if self.dst(dt) else "EST"


def get_new_york_tz():
    if ZoneInfo:
        try:
            return ZoneInfo("America/New_York")
        except Exception:
            pass
    return NewYorkFallback()


NY_TZ = get_new_york_tz()


def now_ny():
    return datetime.datetime.now(datetime.timezone.utc).astimezone(NY_TZ)


def fmt_dt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def parse_dt(value):
    if not value:
        return None
    try:
        return datetime.datetime.strptime(value[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=NY_TZ)
    except ValueError:
        return None


def trade_duration(trade):
    stored = trade.get("duration_seconds")
    if stored:
        return int(stored)
    opened = parse_dt(trade.get("timestamp_open"))
    closed = parse_dt(trade.get("timestamp_close"))
    if not opened or not closed:
        return None
    return max(0, int((closed - opened).total_seconds()))


def active_elapsed_seconds(trade):
    opened = parse_dt(trade.get("timestamp_open"))
    if not opened:
        return 0
    if trade.get("timestamp_close"):
        return trade_duration(trade) or 0
    return max(0, int((now_ny() - opened).total_seconds()))


def time_window(value):
    dt = parse_dt(value)
    if not dt:
        return "-"
    start = dt.replace(minute=0, second=0)
    end = start + datetime.timedelta(hours=1)
    fmt = "%I %p"
    return f"{start.strftime(fmt).lstrip('0')} - {end.strftime(fmt).lstrip('0')}"


def fmt_dur(seconds):
    if not seconds:
        return "-"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m:02d}m {s:02d}s" if h else f"{m}m {s:02d}s"


def fmt_clock(seconds):
    seconds = max(0, int(seconds or 0))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_FILE) as con:
        con.execute(
            """CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_open TEXT, timestamp_close TEXT, duration_seconds INTEGER,
            pair TEXT, direction TEXT, account_balance REAL, risk_amount REAL,
            stop_loss_pips REAL, take_profit_pips REAL, usdjpy_rate REAL,
            quantity INTEGER, margin_used REAL, risk_pct REAL, rr_ratio REAL,
            rationale TEXT, notes_before TEXT, notes_after TEXT,
            actual_result TEXT, actual_pnl_jpy REAL, status TEXT DEFAULT 'planned'
        )"""
        )
        con.execute(
            """CREATE TABLE IF NOT EXISTS media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER, phase TEXT, media_type TEXT, file_path TEXT, added_at TEXT
        )"""
        )
        con.execute(
            """CREATE TABLE IF NOT EXISTS journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT, title TEXT, details TEXT,
            media_type TEXT, file_path TEXT, added_at TEXT
        )"""
        )


def db_exec(sql, params=()):
    with sqlite3.connect(DB_FILE) as con:
        cur = con.execute(sql, params)
        return cur.lastrowid


def db_fetch(sql, params=()):
    con = sqlite3.connect(DB_FILE)
    con.row_factory = sqlite3.Row
    rows = con.execute(sql, params).fetchall()
    con.close()
    return [dict(row) for row in rows]


def get_open_trade():
    rows = db_fetch("SELECT * FROM trades WHERE status='open' ORDER BY id DESC LIMIT 1")
    return rows[0] if rows else None


def media_kind(filename):
    ext = Path(filename).suffix.lower()
    return "video" if ext in VIDEO_EXTS else "image"


def save_bytes(data: bytes, filename: str, prefix: str) -> str:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
    dest = UPLOAD_DIR / f"{prefix}_{safe}"
    dest.write_bytes(data)
    return str(dest)


def add_media_record(trade_id, phase, path):
    db_exec(
        "INSERT INTO media(trade_id,phase,media_type,file_path,added_at) VALUES(?,?,?,?,?)",
        (trade_id, phase, media_kind(path), path, fmt_dt(now_ny())),
    )


def resolve_media_path(path):
    if not path:
        return None
    p = Path(path)
    if p.is_file():
        return p
    candidate = UPLOAD_DIR / p.name
    return candidate if candidate.is_file() else None


def delete_journal_entry(entry_id):
    """Delete a journal row and its uploaded file (if stored on this server)."""
    rows = db_fetch("SELECT * FROM journal_entries WHERE id=?", (entry_id,))
    if not rows:
        return False
    entry = rows[0]
    resolved = resolve_media_path(entry.get("file_path"))
    if resolved:
        try:
            resolved.unlink(missing_ok=True)
        except OSError:
            pass
    db_exec("DELETE FROM journal_entries WHERE id=?", (entry_id,))
    return True


def fetch_fx():
    out = dict(FALLBACK_FX)
    out["_src"] = "Static fallback"
    if not requests:
        return out
    try:
        r = requests.get("https://api.frankfurter.app/latest?from=USD&to=JPY,EUR,GBP", timeout=6)
        r.raise_for_status()
        rates = r.json()["rates"]
        jpy, eur, gbp = float(rates["JPY"]), float(rates["EUR"]), float(rates["GBP"])
        dxy = 50.14348112 * (1 / eur) ** 0.576 * (jpy / 100) ** 0.136 * (1 / gbp) ** 0.119
        return {
            "EUR/USD": round(1 / eur, 5),
            "GBP/USD": round(1 / gbp, 5),
            "USD/JPY": round(jpy, 3),
            "DXY": round(dxy, 3),
            "_src": "frankfurter.app",
        }
    except Exception:
        return out


def fetch_nepse():
    out = dict(NEPSE_FALLBACK)
    if not requests:
        return out
    headers = {"User-Agent": "Mozilla/5.0"}
    for url in [
        "https://nepalstock.com.np/api/nots/nepse-data/index",
        "https://nepalstock.com.np/api/nots/market-open",
    ]:
        try:
            r = requests.get(url, headers=headers, timeout=8)
            r.raise_for_status()
            data = r.json()
            row = data[-1] if isinstance(data, list) and data else data.get("index", data)
            return {
                "index": float(row.get("currentValue", out["index"])),
                "change": float(row.get("absoluteChange", out["change"])),
                "change_pct": float(row.get("percentageChange", out["change_pct"])),
                "_src": "nepalstock.com.np",
            }
        except Exception:
            continue
    return out


def pip_size(pair):
    return 0.01 if pair == "USD/JPY" else 0.0001


def calc_pos(pair, balance, risk_jpy, sl, tp, rates):
    if min(balance, risk_jpy, sl, tp) <= 0:
        raise ValueError("Balance, risk, stop loss, and take profit must be greater than zero.")
    usdjpy = rates.get("USD/JPY", 155.0)
    pip_value_one = pip_size(pair) if pair == "USD/JPY" else pip_size(pair) * usdjpy
    qty = max(MIN_UNITS, math.floor(risk_jpy / (pip_value_one * sl) / MIN_UNITS) * MIN_UNITS)
    rate = rates.get(pair, usdjpy)
    notional = qty * rate if pair == "USD/JPY" else qty * rate * usdjpy
    return {
        "pair": pair,
        "quantity": qty,
        "margin_jpy": notional / LEVERAGE,
        "actual_risk_jpy": pip_value_one * qty * sl,
        "actual_profit_jpy": pip_value_one * qty * tp,
        "risk_pct": pip_value_one * qty * sl / balance * 100,
        "rr_ratio": tp / sl,
        "usdjpy": usdjpy,
        "current_rate": rate,
    }


def analytics(trades):
    closed = [t for t in trades if t.get("status") == "closed" and t.get("actual_pnl_jpy") is not None]
    if not closed:
        return {"n": 0}
    wins = [t for t in closed if float(t["actual_pnl_jpy"]) > 0]
    losses = [t for t in closed if float(t["actual_pnl_jpy"]) <= 0]
    gp = sum(float(t["actual_pnl_jpy"]) for t in wins)
    gl = abs(sum(float(t["actual_pnl_jpy"]) for t in losses))
    pnl = gp - gl
    wr = len(wins) / len(closed) * 100
    avg_w = gp / len(wins) if wins else 0
    avg_l = gl / len(losses) if losses else 0
    pf = gp / gl if gl else float("inf")
    equity, total, max_dd, peak = [], 0, 0, 0
    by_pair, by_time = {}, {}
    durations = [trade_duration(t) for t in closed if trade_duration(t) is not None]
    for trade in closed:
        pnl_one = float(trade["actual_pnl_jpy"])
        total += pnl_one
        equity.append(total)
        peak = max(peak, total)
        max_dd = max(max_dd, peak - total)
        pair = trade.get("pair") or "-"
        by_pair[pair] = by_pair.get(pair, 0) + pnl_one
        window = time_window(trade.get("timestamp_open"))
        by_time[window] = by_time.get(window, 0) + pnl_one
    best_window = max(by_time.items(), key=lambda item: item[1]) if by_time else ("-", 0)
    worst_window = min(by_time.items(), key=lambda item: item[1]) if by_time else ("-", 0)
    return {
        "n": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": wr,
        "profit_factor": pf,
        "total_pnl": pnl,
        "avg_win": avg_w,
        "avg_loss": avg_l,
        "expectancy": (wr / 100 * avg_w) - ((1 - wr / 100) * avg_l),
        "avg_rr": sum(float(t.get("rr_ratio") or 0) for t in closed) / len(closed),
        "equity": equity,
        "max_drawdown": max_dd,
        "by_pair": by_pair,
        "by_time": by_time,
        "avg_duration_s": sum(durations) / len(durations) if durations else 0,
        "best_window": best_window,
        "worst_window": worst_window,
    }


def group_trades(trades, mode):
    closed = [t for t in trades if t.get("status") == "closed"]
    groups = {}
    for index, trade in enumerate(closed):
        opened = parse_dt(trade.get("timestamp_open"))
        if mode == "per20":
            key = f"Block {index // 20 + 1}"
        elif not opened:
            key = "Unknown"
        elif mode == "weekly":
            iso = opened.isocalendar()
            key = f"{iso.year} W{iso.week:02d}"
        elif mode == "monthly":
            key = opened.strftime("%Y %b")
        elif mode == "yearly":
            key = str(opened.year)
        elif mode == "time":
            key = time_window(trade.get("timestamp_open"))
        else:
            key = "Overall"
        groups.setdefault(key, []).append(trade)
    return groups


def recommendations(data):
    if data["n"] == 0:
        return "Close at least one trade to begin analytics."
    pf = "infinite" if data["profit_factor"] == float("inf") else f"{data['profit_factor']:.2f}"
    return "\n".join(
        [
            f"- Win rate is {data['win_rate']:.1f}% across {data['n']} closed trades.",
            f"- Profit factor is {pf}.",
            f"- Average trade time is {fmt_dur(data['avg_duration_s'])}.",
            f"- Best NY window: {data['best_window'][0]} (¥{data['best_window'][1]:+,.0f}).",
            f"- Weakest NY window: {data['worst_window'][0]} (¥{data['worst_window'][1]:+,.0f}).",
            f"- Expectancy: ¥{data['expectancy']:+,.0f} per trade.",
            f"- Max drawdown: ¥{data['max_drawdown']:,.0f}.",
        ]
    )


def export_trades_xlsx(trades):
    if not openpyxl:
        raise RuntimeError("openpyxl is not installed.")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "All Trades"
    headers = list(trades[0].keys()) if trades else ["id", "timestamp_open", "pair", "direction", "actual_pnl_jpy", "status"]
    ws.append(headers)
    for trade in trades:
        ws.append([trade.get(h) for h in headers])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


def start_trade(calc, balance, risk, sl, tp, rationale, notes_before, pre_media_paths):
    now = fmt_dt(now_ny())
    tid = db_exec(
        """INSERT INTO trades
        (timestamp_open,pair,direction,account_balance,risk_amount,stop_loss_pips,take_profit_pips,
         usdjpy_rate,quantity,margin_used,risk_pct,rr_ratio,rationale,notes_before,status)
         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,'open')""",
        (
            now,
            calc["pair"],
            calc["direction"],
            balance,
            risk,
            sl,
            tp,
            calc["usdjpy"],
            calc["quantity"],
            calc["margin_jpy"],
            calc["risk_pct"],
            calc["rr_ratio"],
            rationale,
            notes_before or None,
        ),
    )
    for path in pre_media_paths:
        add_media_record(tid, "before_entry", path)
    return tid


def exit_trade(trade_id):
    trade = db_fetch("SELECT * FROM trades WHERE id=?", (trade_id,))[0]
    opened = parse_dt(trade["timestamp_open"])
    end = now_ny()
    duration = max(0, int((end - opened).total_seconds())) if opened else 0
    db_exec(
        "UPDATE trades SET timestamp_close=?, duration_seconds=? WHERE id=?",
        (fmt_dt(end), duration, trade_id),
    )


def close_trade(trade_id, result, raw_pnl, notes_after, post_media_paths):
    pnl = abs(raw_pnl) if result == "WIN" else -abs(raw_pnl) if result == "LOSS" else 0
    db_exec(
        "UPDATE trades SET actual_result=?, actual_pnl_jpy=?, notes_after=?, status='closed' WHERE id=?",
        (result, pnl, notes_after or None, trade_id),
    )
    for path in post_media_paths:
        add_media_record(trade_id, "after_exit", path)
    return pnl
