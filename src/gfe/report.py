"""Write outputs/report.html: one page to read a model run.

Self-contained (inline SVG, no scripts), opens in any browser.
"""
from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

CSS = """
:root{--paper:#f4f1ea;--ink:#16130f;--muted:#6f685d;--rule:#d8d2c5;--pos:#2f6b4f;--neg:#a8392b;--blue:#2c5d8f}
@media (prefers-color-scheme:dark){:root{--paper:#14130f;--ink:#ece7dc;--muted:#9a9284;--rule:#2e2b25;--pos:#6fb38e;--neg:#e07a68;--blue:#7fb0e0}}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 Georgia,"Times New Roman",serif}
.wrap{max-width:1040px;margin:0 auto;padding:32px 20px 80px}
.k{font:500 11px/1 ui-monospace,Menlo,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
h1{font-size:40px;line-height:1.05;margin:10px 0 6px;font-weight:600}h2{font-size:21px;margin:38px 0 4px}
.sub{color:var(--muted);font-size:14px;margin:0 0 14px}header{border-bottom:2px solid var(--ink);padding-bottom:14px}
.facts{display:grid;grid-template-columns:repeat(4,1fr);border-bottom:1px solid var(--rule)}
.facts div{padding:14px 12px 12px 0;border-right:1px solid var(--rule)}.facts div+div{padding-left:12px}.facts div:last-child{border-right:0}
.facts b{display:block;font-size:26px;font-weight:400}.facts span{font:500 10.5px ui-monospace,Menlo,monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
table{width:100%;border-collapse:collapse;font-size:14px}th{font:500 10.5px ui-monospace,Menlo,monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);text-align:left;padding:8px 6px;border-bottom:1px solid var(--ink)}
td{padding:7px 6px;border-bottom:1px solid var(--rule)}td.n{text-align:right;font:13px ui-monospace,Menlo,monospace}
tr.best td{background:color-mix(in srgb,var(--pos) 10%,transparent)}.pos{color:var(--pos)}.neg{color:var(--neg)}
svg text{font:10px ui-monospace,Menlo,monospace;fill:var(--muted)}.note{border-left:3px solid var(--ink);padding:4px 0 4px 14px;margin:18px 0;color:var(--ink)}
.terms{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px 24px;font-size:13.5px}.terms b{font:500 11px ui-monospace,Menlo,monospace;display:block;color:var(--muted)}
@media(max-width:700px){.facts{grid-template-columns:1fr 1fr}.facts div:nth-child(2){border-right:0}.facts div:nth-child(3){padding-left:0}}
"""


def _line_chart(x: list[str], series: dict[str, np.ndarray], colors: dict[str, str], W=1000, H=300) -> str:
    P = dict(l=48, r=12, t=14, b=28)
    allv = np.concatenate([v[~np.isnan(v)] for v in series.values()])
    lo, hi = float(allv.min()), float(allv.max())
    pad = (hi - lo) * 0.06 or 1
    lo, hi = lo - pad, hi + pad
    n = len(x)
    X = lambda i: P["l"] + i * (W - P["l"] - P["r"]) / max(n - 1, 1)  # noqa: E731
    Y = lambda v: P["t"] + (1 - (v - lo) / (hi - lo)) * (H - P["t"] - P["b"])  # noqa: E731
    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img">']
    for f in np.linspace(0, 1, 5):
        v = lo + f * (hi - lo)
        out.append(f'<line x1="{P["l"]}" x2="{W-P["r"]}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="var(--rule)"/>'
                   f'<text x="{P["l"]-6}" y="{Y(v)+3:.1f}" text-anchor="end">{v:.0f}</text>')
    step = max(1, n // 8)
    for i in range(0, n, step):
        out.append(f'<text x="{X(i):.1f}" y="{H-8}" text-anchor="middle">{x[i][5:]}</text>')
    for name, v in series.items():
        pts = " ".join(f"{X(i):.1f},{Y(val):.1f}" for i, val in enumerate(v) if not np.isnan(val))
        w = 2.2 if name == "actual" else 1.4
        dash = ' stroke-dasharray="4 3"' if name == "persistence" else ""
        out.append(f'<polyline points="{pts}" fill="none" stroke="{colors[name]}" stroke-width="{w}"{dash}/>')
    out.append("</svg>")
    legend = " ".join(f'<span style="color:{colors[k]}">━</span> {html.escape(k)}' for k in series)
    return "".join(out) + f'<p class="sub" style="margin-top:6px">{legend}</p>'


def _bars(res: pd.DataFrame, W=1000) -> str:
    rows = res[res["model"] != "persistence"]
    H = 26 * len(rows) + 20
    m = max(1.0, float(rows["mae_vs_persistence_pct"].abs().max()))
    left, right = 340, W - 80          # bars live here; value labels sit in the right margin
    mid = (left + right) / 2
    sc = (right - left) / 2 / m
    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img"><line x1="{mid}" x2="{mid}" y1="0" y2="{H}" stroke="var(--ink)"/>']
    for i, (_, r) in enumerate(rows.iterrows()):
        y = 8 + i * 26
        v = float(r["mae_vs_persistence_pct"])
        color = "var(--pos)" if v < 0 else "var(--neg)"
        x0, w = (mid + v * sc, -v * sc) if v < 0 else (mid, v * sc)
        out.append(f'<text x="320" y="{y+13}" text-anchor="end" style="font-size:12px;fill:var(--ink)">{html.escape(r["model"])}</text>'
                   f'<rect x="{x0:.1f}" y="{y}" width="{max(w,1):.1f}" height="18" fill="{color}"/>'
                   f'<text x="{W - 4}" y="{y+13}" text-anchor="end">{v:+.2f}%</text>')
    out.append("</svg>")
    return "".join(out)


def write_report(res: pd.DataFrame, dev: pd.DataFrame, test: pd.DataFrame, groups: dict, text_info: dict,
                 out_path: Path, title: str = "AAPL next-session close", data_note: str = "") -> Path:
    preds = res.attrs.get("predictions")
    best = res.loc[res["model"] != "persistence"].sort_values("mae_usd").iloc[0]
    base = res.loc[res["model"] == "persistence"].iloc[0]
    beat = best["mae_usd"] < base["mae_usd"]

    table = ["<table><thead><tr><th>Model</th><th style='text-align:right'>Features</th><th style='text-align:right'>MAE ($)</th><th style='text-align:right'>vs. persistence</th><th style='text-align:right'>Direction hit</th></tr></thead><tbody>"]
    for _, r in res.iterrows():
        v = r["mae_vs_persistence_pct"]
        cls = "best" if r["model"] == best["model"] else ""
        dcls = "pos" if v < 0 else "neg" if v > 0 else ""
        nf = "" if pd.isna(r.get("n_features")) else int(r["n_features"])
        da = "" if pd.isna(r["dir_acc"]) else f'{r["dir_acc"]:.0%}'
        table.append(f'<tr class="{cls}"><td>{html.escape(r["model"])}</td><td class="n">{nf}</td><td class="n">{r["mae_usd"]:.3f}</td>'
                     f'<td class="n {dcls}">{v:+.2f}%</td><td class="n">{da}</td></tr>')
    table.append("</tbody></table>")

    chart = ""
    if preds is not None and len(preds):
        last = min(len(preds), 60)            # last 60 sessions; a full year is too dense to read
        x = [d.strftime("%Y-%m-%d") for d in pd.DatetimeIndex(test["target_session"])][-last:]
        series = {"actual": preds["actual"].values[-last:], "persistence": preds["persistence"].values[-last:],
                  best["model"]: preds[best["model"]].values[-last:]}
        colors = {"actual": "var(--ink)", "persistence": "var(--muted)", best["model"]: "var(--blue)"}
        chart = _line_chart(x, series, colors)

    terms = ""
    if text_info and text_info.get("top_terms"):
        terms = '<div class="terms">' + "".join(
            f"<div><b>{k}</b>{html.escape(', '.join(v[:6]))}</div>" for k, v in text_info["top_terms"].items()) + "</div>"

    verdict = (f"The best model, <b>{html.escape(best['model'])}</b>, cut test MAE by {-best['mae_vs_persistence_pct']:.2f}% versus "
               f"'tomorrow = today'." if beat else
               "No model beat the persistence baseline ('tomorrow = today') on the test period. That is the normal "
               "outcome for daily stock prices and the bar every feature has to clear.")
    groups_html = "".join(f"<tr><td>{html.escape(g)}</td><td class='n'>{len(c)}</td><td style='font-size:12.5px;color:var(--muted)'>"
                          f"{html.escape(', '.join(c[:8]))}{' …' if len(c) > 8 else ''}</td></tr>" for g, c in groups.items())

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Grid run report</title><style>{CSS}</style></head><body><div class="wrap">
<header><div class="k">Grid Feature Engineering · run report · {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC</div>
<h1>{html.escape(title)}</h1><p class="sub">Target: next exchange session's close. Train on the earliest 80% of sessions, score on the latest 20%, never shuffled.</p></header>
<div class="facts"><div><b>{len(dev)}</b><span>Train sessions</span></div><div><b>{len(test)}</b><span>Test sessions</span></div>
<div><b>${base['mae_usd']:.2f}</b><span>Persistence MAE</span></div><div><b class="{'pos' if beat else ''}">${best['mae_usd']:.2f}</b><span>Best model MAE</span></div></div>
<p class="note">{verdict} {html.escape(data_note)}</p>
<h2>Test period: actual vs. forecast</h2><p class="sub">Last {min(len(test), 60)} test sessions, ending {test['target_session'].max():%Y-%m-%d}. Dashed line is the baseline.</p>{chart}
<h2>Each feature family, added one at a time</h2><p class="sub">Green bars lower the error versus persistence; red bars raise it.</p>{_bars(res)}
<h2>Scores</h2>{''.join(table)}
<h2>Feature families</h2><table><thead><tr><th>Group</th><th>Columns</th><th>Examples</th></tr></thead><tbody>{groups_html}</tbody></table>
{'<h2>What the text dimensions mean</h2><p class="sub">Top words behind each latent news variable, fitted on training-period news only.</p>' + terms if terms else ''}
<p class="sub" style="margin-top:40px">Research output, not investment advice. Dev {dev.index[0]:%Y-%m-%d}–{dev.index[-1]:%Y-%m-%d} · Test {test.index[0]:%Y-%m-%d}–{test.index[-1]:%Y-%m-%d}</p>
</div></body></html>"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page)
    return out_path
