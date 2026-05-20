"""Data Track — production Streamlit web app (feature parity with desktop professional edition)."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

import app_core as core

# ── Page & theme ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title=core.APP_NAME,
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="auto",
)

MOBILE_CSS = """
<style>
  .block-container { padding-top: 1rem; padding-bottom: 2rem; max-width: 1200px; }
  .ticker-row { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.75rem; }
  .ticker-pill {
    background: #111827; border: 1px solid #29364F; border-radius: 8px;
    padding: 0.35rem 0.65rem; font-size: 0.8rem; color: #A8B4CB;
  }
  .ticker-pill b { color: #22D3EE; }
  .risk-warn { color: #EF4444 !important; }
  @media (max-width: 768px) {
    .block-container { padding-left: 0.75rem; padding-right: 0.75rem; }
    [data-testid="stMetric"] { min-width: 0 !important; }
    [data-testid="column"] { width: 100% !important; flex: 1 1 100% !important; min-width: 100% !important; }
    div[data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; gap: 0.25rem; }
    .ticker-pill { flex: 1 1 45%; font-size: 0.72rem; }
  }
</style>
"""
st.markdown(MOBILE_CSS, unsafe_allow_html=True)


# ── Auth (optional, set APP_PASSWORD on Render) ───────────────────────────────

def _load_secrets_file():
    """Read secrets.toml if present — avoids Streamlit's st.secrets (errors when file missing)."""
    for path in (
        Path(__file__).resolve().parent / ".streamlit" / "secrets.toml",
        Path.home() / ".streamlit" / "secrets.toml",
    ):
        if path.is_file():
            with open(path, "rb") as f:
                return tomllib.load(f)
    return {}


def _app_password():
    """Password from env (Render) or optional secrets.toml. No secrets file required locally."""
    pwd = (os.environ.get("APP_PASSWORD") or "").strip()
    if pwd:
        return pwd
    return str(_load_secrets_file().get("APP_PASSWORD", "")).strip()


def require_auth():
    password = _app_password()
    if not password:
        return
    if st.session_state.get("authenticated"):
        return
    st.title(core.APP_NAME)
    st.caption("Enter the app password to continue.")
    entered = st.text_input("Password", type="password")
    if st.button("Sign in", type="primary"):
        if entered == password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Invalid password.")
    st.stop()


# ── Charts (matplotlib — avoids Altair / Python 3.13 issues) ─────────────────

def line_chart(values, title, ylabel):
    if not values:
        st.caption("No data yet.")
        return
    fig, ax = plt.subplots(figsize=(10, 3.2))
    fig.patch.set_facecolor("#0A0E17")
    ax.set_facecolor("#111827")
    ax.plot(range(1, len(values) + 1), values, color="#10B981", linewidth=2, marker="o", markersize=4)
    ax.set_title(title, color="#F5A623", fontsize=11)
    ax.set_xlabel("Trade #", color="#70809F")
    ax.set_ylabel(ylabel, color="#70809F")
    ax.tick_params(colors="#70809F")
    ax.grid(True, alpha=0.25)
    for spine in ax.spines.values():
        spine.set_color("#29364F")
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def bar_chart(labels, values, title, ylabel):
    if not values:
        st.caption("No data yet.")
        return
    fig, ax = plt.subplots(figsize=(10, 3.2))
    fig.patch.set_facecolor("#0A0E17")
    ax.set_facecolor("#111827")
    colors = ["#10B981" if v >= 0 else "#EF4444" for v in values]
    ax.bar(labels, values, color=colors)
    ax.set_title(title, color="#F5A623", fontsize=11)
    ax.set_ylabel(ylabel, color="#70809F")
    ax.tick_params(colors="#70809F", axis="x", rotation=25)
    ax.axhline(0, color="#666", linewidth=0.8)
    ax.grid(True, axis="y", alpha=0.25)
    for spine in ax.spines.values():
        spine.set_color("#29364F")
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def pie_chart(wins, losses):
    fig, ax = plt.subplots(figsize=(4, 3.2))
    fig.patch.set_facecolor("#0A0E17")
    if wins + losses == 0:
        st.caption("No data yet.")
        return
    ax.pie([wins, losses], labels=["Wins", "Losses"], colors=["#10B981", "#EF4444"], autopct="%1.0f%%")
    ax.set_title("Win / Loss", color="#F5A623", fontsize=11)
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def metrics_row(items, per_row=4):
    """Responsive metric rows — fewer columns on small screens via wrapping."""
    for i in range(0, len(items), per_row):
        cols = st.columns(min(per_row, len(items) - i))
        for col, (label, value) in zip(cols, items[i : i + per_row]):
            col.metric(label, value)


def show_media(path, media_type):
    resolved = core.resolve_media_path(path)
    if not resolved:
        st.warning(f"File not on server: `{path}`")
        return
    if media_type == "image":
        st.image(str(resolved), use_container_width=True)
    else:
        st.video(str(resolved))


# ── Market ticker ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def load_markets():
    return core.fetch_fx(), core.fetch_nepse()


def render_ticker():
    fx, nepse = load_markets()
    pills = "".join(
        f'<span class="ticker-pill">{pair} <b>{fx.get(pair, "—")}</b></span>'
        for pair in core.ASSETS
    )
    chg = nepse.get("change", 0)
    color = "#10B981" if chg >= 0 else "#EF4444"
    nepse_html = (
        f'<span class="ticker-pill">NEPSE <b>{nepse.get("index", 0):,.2f}</b> '
        f'<span style="color:{color}">{chg:+.2f} ({nepse.get("change_pct", 0):+.2f}%)</span></span>'
    )
    st.markdown(
        f'<motion-div class="ticker-row">{pills}{nepse_html}</motion-div>'
        f'<p style="color:#70809F;font-size:0.75rem;margin:0;">'
        f'FX: {fx.get("_src", "?")} · NY {core.now_ny().strftime("%H:%M:%S %Z")}</p>',
        unsafe_allow_html=True,
    )
    if st.button("Refresh markets", key="refresh_markets"):
        load_markets.clear()
        st.rerun()
    return fx


# ── Pages ─────────────────────────────────────────────────────────────────────

def page_dashboard(trades):
    stats = core.analytics(trades)
    if stats["n"] == 0:
        st.info("No closed trades yet. Use **Calculator** to open a trade, or log one from **Trade Log**.")
        return
    metrics_row(
        [
            ("Net P&L", f"¥{stats['total_pnl']:+,.0f}"),
            ("Win rate", f"{stats['win_rate']:.1f}%"),
            ("Trades", str(stats["n"])),
            ("Profit factor", "∞" if stats["profit_factor"] == float("inf") else f"{stats['profit_factor']:.2f}"),
            ("Avg win", f"¥{stats['avg_win']:,.0f}"),
            ("Avg loss", f"¥{stats['avg_loss']:,.0f}"),
            ("Expectancy", f"¥{stats['expectancy']:+,.0f}"),
            ("Max DD", f"¥{stats['max_drawdown']:,.0f}"),
        ],
        per_row=4,
    )
    line_chart(stats["equity"], "Equity curve", "Cumulative P&L (JPY)")


def page_calculator(fx):
    st.subheader("Position size calculator")
    if "calc_result" not in st.session_state:
        st.session_state.calc_result = None
    if "pre_media_paths" not in st.session_state:
        st.session_state.pre_media_paths = []

    with st.form("calc_form"):
        c1, c2 = st.columns(2)
        pair = c1.selectbox("Pair", core.ASSETS)
        direction = c2.selectbox("Direction", core.DIRECTIONS)
        c3, c4 = st.columns(2)
        balance = c3.number_input("Account balance (JPY)", min_value=1.0, value=100000.0, step=1000.0)
        risk = c4.number_input("Risk per trade (JPY)", min_value=1.0, value=5000.0, step=100.0)
        c5, c6 = st.columns(2)
        sl = c5.number_input("Stop loss (pips)", min_value=0.1, value=20.0)
        tp = c6.number_input("Take profit (pips)", min_value=0.1, value=40.0)
        calc_btn = st.form_submit_button("Calculate", type="primary")

    if calc_btn:
        try:
            result = core.calc_pos(pair, balance, risk, sl, tp, fx)
            result["direction"] = direction
            st.session_state.calc_result = result
        except ValueError as exc:
            st.error(str(exc))

    r = st.session_state.calc_result
    if r:
        risk_cls = "risk-warn" if r["risk_pct"] > core.RISK_WARN else ""
        st.markdown(
            f"""
| | |
|---|---|
| **Quantity** | {r['quantity']:,} units |
| **Margin** | ¥{r['margin_jpy']:,.0f} |
| **Actual risk** | ¥{r['actual_risk_jpy']:,.0f} |
| **Profit target** | ¥{r['actual_profit_jpy']:,.0f} |
| **Risk %** | <span class="{risk_cls}">{r['risk_pct']:.2f}%</span> |
| **R:R** | 1 : {r['rr_ratio']:.2f} |
| **Rate** | {r['current_rate']:.5f} |
""",
            unsafe_allow_html=True,
        )

    rationale = st.text_area("Trade rationale (required)", key="calc_rationale")
    notes_before = st.text_area("Notes before trade", key="calc_notes_before")
    uploads = st.file_uploader("Pre-entry media", accept_multiple_files=True, key="calc_pre_upload")
    if uploads:
        st.session_state.pre_media_paths = []
        for f in uploads:
            path = core.save_bytes(f.getvalue(), f.name, "pre")
            st.session_state.pre_media_paths.append(path)
        st.caption(f"{len(uploads)} file(s) ready to attach.")

    open_trade = core.get_open_trade()
    if st.button("Go with this trade", type="primary", disabled=not r or bool(open_trade)):
        if not rationale.strip():
            st.warning("Rationale is required.")
        elif open_trade:
            st.warning(f"Trade #{open_trade['id']} is still open. Close it first.")
        else:
            tid = core.start_trade(
                r, balance, risk, sl, tp, rationale.strip(), notes_before.strip(),
                st.session_state.pre_media_paths,
            )
            st.session_state.calc_result = None
            st.session_state.pre_media_paths = []
            st.success(f"Trade #{tid} opened.")
            st.rerun()

    if st.button("Clear calculator"):
        st.session_state.calc_result = None
        st.session_state.pre_media_paths = []
        st.rerun()


@st.fragment(run_every=1)
def active_timer_block(trade):
    elapsed = core.active_elapsed_seconds(trade)
    st.metric("Elapsed (NY)", core.fmt_clock(elapsed))


def page_active_trade():
    trade = core.get_open_trade()
    if not trade:
        st.info("No active trade. Use **Calculator → Go with this trade** to start.")
        return

    tid = trade["id"]
    closed = bool(trade.get("timestamp_close"))
    st.success(f"**Trade #{tid}** · {trade.get('pair')} {trade.get('direction')} · Qty {trade.get('quantity', 0):,}")

    if not closed:
        active_timer_block(trade)
        if st.button("Exit / close trade", type="primary"):
            core.exit_trade(tid)
            st.rerun()
        st.caption("Timer uses New York time. After exit, enter outcome below.")
        st.stop()

    st.warning("Trade exited — enter outcome and save.")
    active_timer_block(trade)

    c1, c2 = st.columns(2)
    result = c1.selectbox("Result", core.RESULTS)
    raw_pnl = c2.number_input("P&L amount (JPY, positive number)", min_value=0.0, value=0.0, step=50.0)
    notes_after = st.text_area("Notes after trade")
    post_files = st.file_uploader("Post-exit media", accept_multiple_files=True, key="post_media")
    post_paths = []
    if post_files:
        for f in post_files:
            post_paths.append(core.save_bytes(f.getvalue(), f.name, f"post{tid}"))

    if st.button("Save closed trade", type="primary"):
        pnl = core.close_trade(tid, result, raw_pnl, notes_after.strip(), post_paths)
        st.success(f"Trade #{tid} saved. P&L: ¥{pnl:+,.0f}")
        st.rerun()

    st.divider()
    st.markdown("**Attach media to an older trade**")
    patch_id = st.number_input("Trade ID", min_value=1, step=1, key="patch_id")
    patch_notes = st.text_area("Notes to add", key="patch_notes")
    patch_files = st.file_uploader("Media for patch", accept_multiple_files=True, key="patch_upload")
    if st.button("Update trade"):
        rows = core.db_fetch("SELECT id FROM trades WHERE id=?", (int(patch_id),))
        if not rows:
            st.error("Trade not found.")
        else:
            if patch_notes.strip():
                core.db_exec("UPDATE trades SET notes_after=? WHERE id=?", (patch_notes.strip(), int(patch_id)))
            for f in patch_files or []:
                path = core.save_bytes(f.getvalue(), f.name, f"patch{patch_id}")
                core.add_media_record(int(patch_id), "after_exit_patch", path)
            st.success(f"Trade #{patch_id} updated.")


def page_trade_log(trades):
    if not trades:
        st.info("No trades yet.")
        return
    st.caption(f"{len(trades)} trades recorded")
    rows = []
    for t in trades:
        pnl = t.get("actual_pnl_jpy")
        rows.append(
            {
                "ID": t["id"],
                "Opened": (t.get("timestamp_open") or "")[:16],
                "Window": core.time_window(t.get("timestamp_open")),
                "Closed": (t.get("timestamp_close") or "-")[:16],
                "Duration": core.fmt_dur(t.get("duration_seconds") or core.trade_duration(t)),
                "Pair": t.get("pair"),
                "Dir": t.get("direction"),
                "Qty": t.get("quantity"),
                "R:R": f"1:{(t.get('rr_ratio') or 0):.2f}",
                "Risk %": f"{(t.get('risk_pct') or 0):.2f}%",
                "P&L": f"¥{pnl:+,.0f}" if pnl is not None else "-",
                "Result": t.get("actual_result") or "-",
                "Status": (t.get("status") or "").upper(),
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    tid = st.selectbox("Trade detail", [t["id"] for t in trades], format_func=lambda x: f"#{x}")
    trade = next(t for t in trades if t["id"] == tid)
    with st.expander(f"Trade #{tid}", expanded=True):
        st.json({k: v for k, v in trade.items() if v is not None})
        for item in core.db_fetch("SELECT * FROM media WHERE trade_id=? ORDER BY id", (tid,)):
            st.caption(f"{item['phase']} · {item['media_type']}")
            show_media(item["file_path"], item["media_type"])


def page_analytics(trades):
    stats = core.analytics(trades)
    if stats["n"] == 0:
        st.info("No closed trades for analytics.")
        return

    metrics_row(
        [
            ("Trades", str(stats["n"])),
            ("Win rate", f"{stats['win_rate']:.1f}%"),
            ("Net P&L", f"¥{stats['total_pnl']:+,.0f}"),
            ("Profit factor", "∞" if stats["profit_factor"] == float("inf") else f"{stats['profit_factor']:.2f}"),
            ("Expectancy", f"¥{stats['expectancy']:+,.0f}"),
            ("Avg R:R", f"1:{stats['avg_rr']:.2f}"),
            ("Avg duration", core.fmt_dur(stats["avg_duration_s"])),
            ("Max DD", f"¥{stats['max_drawdown']:,.0f}"),
        ],
        per_row=4,
    )

    c1, c2 = st.columns(2)
    with c1:
        line_chart(stats["equity"], "Equity curve", "JPY")
        bar_chart(
            list(stats["by_pair"].keys()),
            list(stats["by_pair"].values()),
            "P&L by pair",
            "JPY",
        )
    with c2:
        pie_chart(stats["wins"], stats["losses"])
        if stats["by_time"]:
            bar_chart(
                list(stats["by_time"].keys())[:12],
                list(stats["by_time"].values())[:12],
                "P&L by NY window",
                "JPY",
            )

    st.markdown("#### Recommendations")
    st.markdown(core.recommendations(stats).replace("\n", "\n\n"))

    mode = st.selectbox("Group by", list(core.GROUP_MODES.keys()), format_func=lambda k: core.GROUP_MODES[k])
    groups = {"Overall": [t for t in trades if t.get("status") == "closed"]} if mode == "overall" else core.group_trades(trades, mode)
    group_rows = []
    for period, group in groups.items():
        row = core.analytics(group)
        if row["n"] == 0:
            continue
        pf = "∞" if row["profit_factor"] == float("inf") else f"{row['profit_factor']:.2f}"
        group_rows.append(
            {
                "Period": period,
                "Trades": row["n"],
                "Win %": f"{row['win_rate']:.1f}",
                "P&L": f"¥{row['total_pnl']:+,.0f}",
                "PF": pf,
                "Expectancy": f"¥{row['expectancy']:+,.0f}",
            }
        )
    if group_rows:
        st.dataframe(pd.DataFrame(group_rows), use_container_width=True, hide_index=True)


def page_journal(category: str):
    st.subheader(f"{category.title()} journal")

    toast_key = f"journal_toast_{category}"
    if toast_key in st.session_state:
        st.toast(st.session_state.pop(toast_key), icon="✅")

    form_ver_key = f"journal_form_ver_{category}"
    st.session_state.setdefault(form_ver_key, 0)
    form_id = st.session_state[form_ver_key]

    with st.expander("Add entry", expanded=False):
        with st.form(f"journal_{category}_{form_id}", clear_on_submit=False):
            title = st.text_input("Title", key=f"j_title_{category}_{form_id}")
            details = st.text_area("Details", key=f"j_details_{category}_{form_id}")
            media = st.file_uploader("Picture or video", key=f"j_media_{category}_{form_id}")
            if st.form_submit_button("Save", type="primary"):
                if not details.strip() and not media:
                    st.warning("Add details or media before saving.")
                else:
                    path, mtype = None, None
                    if media:
                        mtype = "video" if media.type and media.type.startswith("video") else "image"
                        path = core.save_bytes(media.getvalue(), media.name, f"j_{category}")
                    core.db_exec(
                        "INSERT INTO journal_entries(category,title,details,media_type,file_path,added_at) VALUES(?,?,?,?,?,?)",
                        (category, title.strip() or f"{category.title()} entry", details.strip(), mtype, path, core.fmt_dt(core.now_ny())),
                    )
                    label = "Daily" if category == "daily" else category.title()
                    st.session_state[toast_key] = f"{label} journal data is saved."
                    st.session_state[form_ver_key] += 1
                    st.rerun()

    entries = core.db_fetch(
        "SELECT * FROM journal_entries WHERE category=? ORDER BY id DESC", (category,)
    )
    if not entries:
        st.info("No entries yet.")
        return
    for entry in entries:
        eid = entry["id"]
        confirm_key = f"confirm_delete_journal_{category}_{eid}"
        with st.expander(f"#{eid} · {entry.get('title', '')}"):
            st.write(entry.get("details") or "")
            st.caption(entry.get("added_at") or "")
            if entry.get("file_path"):
                show_media(entry["file_path"], entry.get("media_type") or "image")

            if st.button("Delete entry", key=f"del_journal_{category}_{eid}", type="secondary"):
                st.session_state[confirm_key] = True

            if st.session_state.get(confirm_key):
                st.warning("Delete this journal entry permanently?")
                yes, no = st.columns(2)
                if yes.button("Yes, delete", key=f"yes_del_{category}_{eid}", type="primary"):
                    if core.delete_journal_entry(eid):
                        label = "Daily" if category == "daily" else category.title()
                        st.session_state[toast_key] = f"{label} journal entry deleted."
                    else:
                        st.session_state[toast_key] = "Entry not found."
                    st.session_state.pop(confirm_key, None)
                    st.rerun()
                if no.button("Cancel", key=f"no_del_{category}_{eid}"):
                    st.session_state.pop(confirm_key, None)
                    st.rerun()


def sidebar_panel(trades):
    st.sidebar.markdown(f"### {core.APP_NAME}")
    st.sidebar.caption(f"{core.APP_CREDIT} · NY time")
    st.sidebar.markdown(f"**Clock:** {core.now_ny().strftime('%Y-%m-%d %H:%M:%S %Z')}")
    st.sidebar.markdown(f"**Trades:** {len(trades)}")

    if msg := st.session_state.pop("data_folder_msg", None):
        if st.session_state.pop("data_folder_ok", True):
            st.sidebar.success(msg)
        else:
            st.sidebar.warning(msg)

    def _open_data_folder():
        ok, text = core.open_data_folder()
        st.session_state["data_folder_ok"] = ok
        st.session_state["data_folder_msg"] = text

    st.sidebar.button(
        "Open data folder",
        help="Opens the folder with data_track.db and uploads/ in File Explorer",
        on_click=_open_data_folder,
        use_container_width=True,
    )

    if core.DB_FILE.exists():
        st.sidebar.download_button(
            "Download database",
            data=core.DB_FILE.read_bytes(),
            file_name="data_track.db",
            mime="application/octet-stream",
            use_container_width=True,
        )
    try:
        xlsx = core.export_trades_xlsx(trades)
        st.sidebar.download_button(
            "Export Excel",
            data=xlsx,
            file_name=f"DataTrack_{core.now_ny().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    except RuntimeError as exc:
        st.sidebar.caption(str(exc))


def main():
    require_auth()
    core.init_db()

    st.title(core.APP_NAME)
    st.caption(f"{core.APP_CREDIT} · Professional trading journal · New York time")

    fx = render_ticker()
    trades = core.db_fetch("SELECT * FROM trades ORDER BY id DESC")
    sidebar_panel(trades)

    tabs = st.tabs(
        [
            "Dashboard",
            "Calculator",
            "Active Trade",
            "Trade Log",
            "Analytics",
            "Weekly Journal",
            "Daily Journal",
        ]
    )
    with tabs[0]:
        page_dashboard(trades)
    with tabs[1]:
        page_calculator(fx)
    with tabs[2]:
        page_active_trade()
    with tabs[3]:
        page_trade_log(trades)
    with tabs[4]:
        page_analytics(trades)
    with tabs[5]:
        page_journal("weekly")
    with tabs[6]:
        page_journal("daily")


if __name__ == "__main__":
    main()
