"""FXReplay-style analytics PDF for the live USDJPY basket (vol_box 0.25 / vol_gotobi 3.6 / m3 3.6, no fade).

Reads runs/basket/legs/*.parquet (R multiples net of costs), compounds risk % on the running balance
from $10,000, and writes reports/basket_analytics.pdf. Needs pandas, numpy, matplotlib, reportlab.

    python scripts/basket_report_pdf.py
"""
from __future__ import annotations

import io
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "basket_analytics.pdf"
START = 10_000.0
RISK = {"vol_box": 0.25, "vol_gotobi": 3.6, "m3": 3.6}   # % of balance per trade (mt5/AlphaBasketAssistant.mq5)
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
GREEN, RED, BLUE, GREY = "#1a9850", "#d73027", "#2b6cb0", "#6b7280"


def load() -> pd.DataFrame:
    t = pd.concat([pd.read_parquet(ROOT / "runs" / "basket" / "legs" / f"{k}.parquet") for k in RISK])
    t["entry_ts"] = pd.to_datetime(t["entry_ts"], utc=True)
    t["exit_ts"] = pd.to_datetime(t["exit_ts"], utc=True)
    t = t.sort_values("exit_ts").reset_index(drop=True)
    bal, pnl, before = START, [], []
    for r in t.itertuples():
        before.append(bal)
        p = bal * RISK[r.leg] / 100 * r.r_net
        pnl.append(p)
        bal += p
    t["pnl"], t["bal_before"], t["balance"] = pnl, before, START + np.cumsum(pnl)
    t["ret"] = t["pnl"] / t["bal_before"]
    return t


def streak(win: pd.Series, want: bool) -> int:
    best = cur = 0
    for w in win:
        cur = cur + 1 if w == want else 0
        best = max(best, cur)
    return best


def stats(t: pd.DataFrame) -> dict:
    days = t.set_index("exit_ts")["balance"].resample("D").last().ffill()
    days = pd.concat([pd.Series([START], index=[days.index[0] - pd.Timedelta(days=1)]), days])
    dret = days.pct_change().dropna()
    dd = days / days.cummax() - 1
    years = (days.index[-1] - days.index[0]).days / 365.25
    final = days.iloc[-1]
    win = t["pnl"] > 0
    gp, gl = t.loc[win, "pnl"].sum(), -t.loc[~win, "pnl"].sum()
    neg = dret[dret < 0]
    # longest drawdown (days from peak to recovery)
    peak_t, longest, cur_start = days.index[0], 0, days.index[0]
    peak = days.iloc[0]
    for ts, v in days.items():
        if v >= peak:
            longest = max(longest, (ts - cur_start).days)
            peak, cur_start = v, ts
    longest = max(longest, (days.index[-1] - cur_start).days)
    return {
        "Start balance": f"${START:,.0f}", "End balance": f"${final:,.0f}",
        "Net profit": f"${final - START:,.0f}", "Total return": f"{final / START - 1:.0%}",
        "CAGR": f"{(final / START) ** (1 / years) - 1:.1%}", "Period": f"{days.index[1].date()} to {days.index[-1].date()}",
        "Trades": f"{len(t):,}", "Win rate": f"{win.mean():.1%}",
        "Profit factor": f"{gp / gl:.2f}", "Expectancy / trade (R)": f"{t['r_net'].mean():.3f}",
        "Avg win / avg loss (R)": f"{t.loc[t.r_net > 0, 'r_net'].mean():.2f} / {t.loc[t.r_net <= 0, 'r_net'].mean():.2f}",
        "Best / worst trade (R)": f"{t['r_net'].max():.2f} / {t['r_net'].min():.2f}",
        "Max drawdown (daily close)": f"{dd.min():.1%}", "Longest drawdown": f"{longest} days",
        "Sharpe (daily, ann.)": f"{dret.mean() / dret.std() * np.sqrt(252):.2f}",
        "Sortino (daily, ann.)": f"{dret.mean() / np.sqrt((neg ** 2).mean()) * np.sqrt(252):.2f}",
        "Calmar": f"{((final / START) ** (1 / years) - 1) / -dd.min():.2f}",
        "Max win streak / loss streak": f"{streak(win, True)} / {streak(win, False)}",
        "Avg hold": f"{((t.exit_ts - t.entry_ts).dt.total_seconds() / 3600).mean():.1f} h",
    }, days, dd, dret


def fig_png(fig) -> Image:
    b = io.BytesIO()
    fig.savefig(b, format="png", dpi=170, bbox_inches="tight")
    plt.close(fig)
    b.seek(0)
    return b


def img(buf, width_mm=180) -> Image:
    from PIL import Image as PI
    w, h = PI.open(buf).size
    buf.seek(0)
    return Image(buf, width=width_mm * mm, height=width_mm * mm * h / w)


def style_ax(ax):
    ax.grid(alpha=.25)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def charts(t, days, dd, dret, mon, yr):
    out = {}
    f, (a, b) = plt.subplots(2, 1, figsize=(10, 6), gridspec_kw={"height_ratios": [3, 1]}, sharex=True)
    a.plot(days.index, days.values, color=BLUE, lw=1.4); a.set_yscale("log"); a.set_ylabel("Balance ($, log)")
    a.set_title("Equity curve", loc="left", fontweight="bold"); style_ax(a)
    b.fill_between(dd.index, dd.values * 100, 0, color=RED, alpha=.45); b.set_ylabel("Drawdown %"); style_ax(b)
    out["equity"] = fig_png(f)

    f, ax = plt.subplots(figsize=(10, 3.4))
    ax.bar(yr.index.astype(str), yr["ret"] * 100, color=[GREEN if v >= 0 else RED for v in yr["ret"]])
    for i, v in enumerate(yr["ret"] * 100):
        ax.text(i, v + (1 if v >= 0 else -3), f"{v:.0f}%", ha="center", fontsize=8)
    ax.set_title("Yearly return %", loc="left", fontweight="bold"); style_ax(ax)
    out["yearly"] = fig_png(f)

    piv = mon.pivot(index="year", columns="month", values="ret").reindex(columns=range(1, 13)) * 100
    f, ax = plt.subplots(figsize=(10, 0.42 * len(piv) + 1.2))
    lim = np.nanpercentile(np.abs(piv.values), 95)
    ax.imshow(piv.values, cmap="RdYlGn", vmin=-lim, vmax=lim, aspect="auto")
    ax.set_xticks(range(12), MONTHS); ax.set_yticks(range(len(piv)), piv.index)
    for i in range(piv.shape[0]):
        for j in range(12):
            v = piv.values[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=7)
    ax.set_title("Monthly return heatmap (%)", loc="left", fontweight="bold")
    out["heat"] = fig_png(f)

    f, (a, b) = plt.subplots(1, 2, figsize=(10, 3.4))
    a.hist(t["r_net"], bins=50, color=BLUE); a.set_title("R distribution (net)", loc="left", fontweight="bold"); style_ax(a)
    mm_ = mon["ret"] * 100
    b.hist(mm_, bins=30, color=GREY); b.axvline(0, color="k", lw=.8)
    b.set_title("Monthly return distribution %", loc="left", fontweight="bold"); style_ax(b)
    out["dist"] = fig_png(f)

    roll = (1 + dret).rolling(252).apply(np.prod, raw=True) - 1
    f, ax = plt.subplots(figsize=(10, 3))
    ax.plot(roll.index, roll.values * 100, color=BLUE); ax.axhline(0, color="k", lw=.8)
    ax.set_title("Rolling 12-month return %", loc="left", fontweight="bold"); style_ax(ax)
    out["roll"] = fig_png(f)

    f, axs = plt.subplots(1, 3, figsize=(10, 3.2))
    t["dow"] = t.entry_ts.dt.dayofweek
    d = t.groupby("dow")["pnl"].sum()
    axs[0].bar(["Mon", "Tue", "Wed", "Thu", "Fri"], d.reindex(range(5)).fillna(0), color=BLUE); axs[0].set_title("P&L by weekday ($)", fontsize=9, fontweight="bold")
    h = t.groupby(t.entry_ts.dt.hour)["pnl"].sum()
    axs[1].bar(h.index, h.values, color=BLUE); axs[1].set_title("P&L by entry hour UTC ($)", fontsize=9, fontweight="bold")
    s = t.groupby("side")["pnl"].sum()
    axs[2].bar(s.index, s.values, color=[RED if x == "SELL" else GREEN for x in s.index]); axs[2].set_title("P&L by side ($)", fontsize=9, fontweight="bold")
    for a in axs: style_ax(a)
    f.tight_layout()
    out["slice"] = fig_png(f)
    return out


def tbl(rows, widths, header=True, zebra=True, font=8):
    tb = Table(rows, colWidths=[w * mm for w in widths], repeatRows=1 if header else 0)
    st = [("FONTSIZE", (0, 0), (-1, -1), font), ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
          ("GRID", (0, 0), (-1, -1), .25, colors.HexColor("#d1d5db")), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
    if header:
        st += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
    if zebra:
        st += [("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")])]
    tb.setStyle(TableStyle(st))
    return tb


def main():
    t = load()
    s, days, dd, dret = stats(t)
    me = t.set_index("exit_ts")["balance"].resample("ME").last()
    me = pd.concat([pd.Series([START], index=[me.index[0] - pd.offsets.MonthEnd(1)]), me])
    mon = pd.DataFrame({"ret": me.pct_change().dropna()})
    mon["year"], mon["month"] = mon.index.year, mon.index.month
    ye = me.resample("YE").last()
    yr = pd.DataFrame({"ret": ye.pct_change().dropna()}); yr.index = yr.index.year
    yr["yoy_change"] = yr["ret"].diff()
    ch = charts(t, days, dd, dret, mon, yr)

    ss = getSampleStyleSheet()
    H1 = ParagraphStyle("h1", parent=ss["Title"], fontSize=20, alignment=0, spaceAfter=2)
    H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=13, spaceBefore=6, spaceAfter=4)
    P = ParagraphStyle("p", parent=ss["BodyText"], fontSize=8.5, leading=11, textColor=colors.HexColor("#374151"))
    el = [Paragraph("USDJPY Basket - Performance Analytics", H1),
          Paragraph(f"Legs: Tokyo box breakout 0.25% | Gotobi fix short 3.6% | Month-end USD bid 3.6% (risk per trade, compounding on balance). "
                    f"Backtest on Dukascopy minute data, costs and 0.2 pip slippage included, fade leg excluded. Start ${START:,.0f}.", P), Spacer(1, 4)]
    keys = list(s)
    half = (len(keys) + 1) // 2
    rows = [[keys[i], s[keys[i]], keys[i + half] if i + half < len(keys) else "", s[keys[i + half]] if i + half < len(keys) else ""] for i in range(half)]
    el += [Paragraph("Summary", H2), tbl(rows, [48, 40, 48, 40], header=False, font=8)]
    el += [Spacer(1, 4), img(ch["equity"]), img(ch["yearly"], 175)]
    el.append(PageBreak())

    # yearly table with YoY
    g = t.groupby(t.exit_ts.dt.year)
    yrows = [["Year", "Return", "YoY change", "Net $", "Trades", "Win %", "PF", "Max DD", "Best mo", "Worst mo"]]
    ddy = dd.groupby(dd.index.year).min()
    for y, r in yr.iterrows():
        gg = g.get_group(y); w = gg.pnl > 0
        pf = gg.loc[w, "pnl"].sum() / max(-gg.loc[~w, "pnl"].sum(), 1e-9)
        mm_ = mon[mon.year == y]["ret"]
        yrows.append([str(y), f"{r.ret:.1%}", "" if np.isnan(r.yoy_change) else f"{r.yoy_change * 100:+.1f} pp", f"{gg.pnl.sum():,.0f}",
                      str(len(gg)), f"{w.mean():.0%}", f"{pf:.2f}", f"{ddy.get(y, 0):.1%}", f"{mm_.max():.1%}", f"{mm_.min():.1%}"])
    el += [Paragraph("Year-over-year", H2), tbl(yrows, [14, 18, 22, 20, 14, 14, 14, 18, 20, 20])]

    # month-over-month stats
    mrows = [["Month", "Avg", "Median", "Win months", "Best", "Worst"]]
    for m in range(1, 13):
        x = mon[mon.month == m]["ret"]
        mrows.append([MONTHS[m - 1], f"{x.mean():.2%}", f"{x.median():.2%}", f"{(x > 0).mean():.0%}", f"{x.max():.1%}", f"{x.min():.1%}"])
    mo = mon["ret"]
    el += [Paragraph("Month-over-month (seasonality)", H2), tbl(mrows, [24, 26, 26, 28, 26, 26]), Spacer(1, 3),
           Paragraph(f"{len(mo)} months: {(mo > 0).mean():.0%} positive, average {mo.mean():.2%}, median {mo.median():.2%}, "
                     f"std {mo.std():.2%}, best {mo.max():.1%}, worst {mo.min():.1%}. "
                     f"Longest run of positive months {streak(mo > 0, True)}, of negative months {streak(mo > 0, False)}.", P)]
    el.append(PageBreak())
    el += [img(ch["heat"], 165), img(ch["roll"], 150), img(ch["dist"], 150)]
    el.append(PageBreak())

    lrows = [["Leg", "Risk %", "Trades", "Win %", "Avg R", "PF", "Net $", "Share of profit"]]
    tot = t.pnl.sum()
    for k in RISK:
        x = t[t.leg == k]; w = x.pnl > 0
        lrows.append([k, f"{RISK[k]}", f"{len(x)}", f"{w.mean():.0%}", f"{x.r_net.mean():.3f}",
                      f"{x.loc[w, 'pnl'].sum() / max(-x.loc[~w, 'pnl'].sum(), 1e-9):.2f}", f"{x.pnl.sum():,.0f}", f"{x.pnl.sum() / tot:.0%}"])
    ex = t.reason.value_counts()
    el += [Paragraph("By strategy leg", H2), tbl(lrows, [30, 16, 18, 16, 18, 14, 24, 28]), Spacer(1, 4), img(ch["slice"], 180), Spacer(1, 3),
           Paragraph("Exit reasons: " + ", ".join(f"{k} {v}" for k, v in ex.items()) + ".", P)]
    top = t.nlargest(5, "pnl")[["leg", "entry_ts", "r_net", "pnl"]]; bot = t.nsmallest(5, "pnl")[["leg", "entry_ts", "r_net", "pnl"]]
    fr = lambda d: [[r.leg, str(r.entry_ts.date()), f"{r.r_net:.2f}", f"{r.pnl:,.0f}"] for r in d.itertuples()]
    el += [Paragraph("Best and worst trades", H2), tbl([["Leg", "Date", "R", "P&L $"]] + fr(top), [30, 30, 20, 26]),
           Spacer(1, 4), tbl([["Leg", "Date", "R", "P&L $"]] + fr(bot), [30, 30, 20, 26]), Spacer(1, 8),
           Paragraph("Backtest, not live results. Compounded risk % assumes each trade is sized on the closed balance at entry; "
                     "overlapping trades and the prop-firm daily-loss rule are not modelled here (see runs/basket/sizing_report.md).", P)]

    OUT.parent.mkdir(exist_ok=True)
    def foot(c, d):
        c.setFont("Helvetica", 7); c.setFillColor(colors.grey)
        c.drawString(15 * mm, 8 * mm, "USDJPY basket analytics"); c.drawRightString(195 * mm, 8 * mm, f"Page {d.page}")
    SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=12 * mm, bottomMargin=14 * mm,
                      title="USDJPY Basket Analytics").build(el, onFirstPage=foot, onLaterPages=foot)
    print(OUT)
    print(s)


if __name__ == "__main__":
    main()
