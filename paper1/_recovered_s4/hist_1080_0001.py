# -*- coding: utf-8 -*-
# s4_6_rotation.py: 4.6 회전 지수 + S5 입력 시계열. OpenAlex 호출 없음. 분석 집합 76,984편.
import json, warnings
from pathlib import Path
import numpy as np, pandas as pd
from scipy.spatial.distance import jensenshannon
from scipy.stats import spearmanr
warnings.filterwarnings("ignore"); pd.set_option("display.width", 200)
ROOT = Path.home() / "Research/Minnesota_Transport"
DATA, S0, S3, S4 = ROOT / "analysis_data/final", ROOT / "paper1/00_S0", ROOT / "paper1/03_S3", ROOT / "paper1/04_S4"
tf = lambda s: s.astype(str).str.strip().str.lower().isin(["1", "1.0", "true", "t", "yes"])
spec = json.loads((S4 / "S4_0_PREREG.json").read_text(encoding="utf-8")); seed = int(spec["seed"]); rng = np.random.default_rng(seed)
W = pd.read_csv(DATA / "F1_papers.csv", low_memory=False); W["pid"] = W.pid.astype(str)
EXC = set(pd.read_csv(S0 / "EXCLUDE_PIDS_FROZEN.csv", dtype=str, encoding="utf-8-sig").pid)
W = W[~W.pid.isin(EXC) & tf(W.in_sample) & W.year.between(2000, 2025) & tf(W.has_topic) & W.topic150.notna()].copy()
assert len(W) == 76984, len(W)
W["topic"] = W.topic150.astype(int); W["fixed"] = tf(W.fixed_venue)
topics = np.array(sorted(pd.read_csv(S3 / "L7_topic_grade.csv").topic.astype(int))); K = len(topics); tix = {t: i for i, t in enumerate(topics)}
W["ti"] = W.topic.map(tix); years = np.arange(2000, 2026)
venues = np.array(sorted(W.venue_short.unique())); vix = {v: i for i, v in enumerate(venues)}; W["vi"] = W.venue_short.map(vix)

def vec(d): return np.bincount(d.ti.values, minlength=K).astype(float)
def norm(c): return c / c.sum() if c.sum() > 0 else c
js = lambda a, b: float(jensenshannon(a, b, base=2))
def noise_floor(d, R=50):
    x = d.ti.values; out = []
    for _ in range(R):
        p = rng.permutation(len(x)); h = len(x) // 2
        out.append(js(norm(np.bincount(x[p[:h]], minlength=K).astype(float)), norm(np.bincount(x[p[h:]], minlength=K).astype(float))))
    return float(np.median(out))

cnt = np.zeros((len(years), len(venues), K))
for (y, v), d in W.groupby(["year", "vi"]): cnt[y - 2000, v] = vec(d)
wbar = cnt.sum((0, 2)) / cnt.sum()
fixed_v = np.array([bool(W.loc[W.vi == i, "fixed"].mean() > 0.5) for i in range(len(venues))])
print(f"저널 {len(venues)}개 | 고정 저널로 판정된 수 {int(fixed_v.sum())} (14여야 함)")
D3 = set()
try:
    DS = pd.read_csv(S4 / "definition_sensitivity.csv"); D3 = set(DS[tf(DS.D3)].topic.astype(int))
except Exception as e: print("※ D3 생략:", e)
d3m = np.array([t in D3 for t in topics])

series = {}
for name in ["all", "fixed", "within"]:
    S = []
    for yi in range(len(years)):
        c = cnt[yi]
        if name == "all": v = norm(c.sum(0))
        elif name == "fixed": v = norm(c[fixed_v].sum(0))
        else:
            nj = c.sum(1); ok = nj > 0; sj = np.zeros_like(c); sj[ok] = c[ok] / nj[ok, None]
            ww = np.where(ok, wbar, 0); v = norm((ww[:, None] * sj).sum(0))
        S.append(v)
    series[name] = np.array(S)
rows = []
for name, S in series.items():
    for yi, y in enumerate(years):
        s = S[yi]; p = s[s > 0]; H = -(p * np.log(p)).sum()
        npap = int(cnt[yi].sum() if name != "fixed" else cnt[yi][fixed_v].sum())
        r = dict(sample=name, year=int(y), n_papers=npap, eff_topics=float(np.exp(H)), hhi=float((s ** 2).sum()), d3_share=float(s[d3m].sum()))
        if yi > 0:
            r["js_adj"] = js(S[yi - 1], s)
            if name != "within":
                sub = W[W.year == y] if name != "fixed" else W[(W.year == y) & W.fixed]
                sub0 = W[W.year == y - 1] if name != "fixed" else W[(W.year == y - 1) & W.fixed]
                r["noise_floor"] = float(np.mean([noise_floor(sub), noise_floor(sub0)])); r["js_adj_corrected"] = r["js_adj"] - r["noise_floor"]
            else: r["noise_floor"] = np.nan; r["js_adj_corrected"] = np.nan
        rows.append(r)
Y = pd.DataFrame(rows); Y.to_csv(S4 / "yearly_series_for_S5.csv", index=False, encoding="utf-8-sig")
for nm in ["all", "fixed", "within"]: np.save(S4 / f"yearly_topic_shares_{nm}.npy", series[nm])
np.save(S4 / "yearly_venue_topic_counts.npy", cnt)
pd.Series(venues).to_csv(S4 / "venues_order.csv", index=False, header=["venue"]); pd.Series(topics).to_csv(S4 / "topics_order.csv", index=False, header=["topic"])

print("[연도 인접 JS: 보정값 상위 5, 표본별]")
for name in ["all", "fixed"]:
    print(name); print(Y[Y["sample"] == name].dropna(subset=["js_adj_corrected"]).sort_values("js_adj_corrected", ascending=False).head(5)[["year", "n_papers", "js_adj", "noise_floor", "js_adj_corrected"]].round(4).to_string(index=False))
print("within 인접 JS 상위 5:\n", Y[Y["sample"] == "within"].dropna(subset=["js_adj"]).sort_values("js_adj", ascending=False).head(5)[["year", "js_adj"]].round(4).to_string(index=False))
print("2006~2008, 2020, 2024~2025 (all):\n", Y[(Y["sample"] == "all") & Y.year.isin([2006, 2007, 2008, 2020, 2024, 2025])][["year", "n_papers", "js_adj", "noise_floor", "js_adj_corrected", "eff_topics", "hhi"]].round(4).to_string(index=False))

per = {"P0004": (2000, 2004), "P0509": (2005, 2009), "P1014": (2010, 2014), "P1519": (2015, 2019), "P2025": (2020, 2025)}
pv = {k: norm(sum(cnt[y - 2000].sum(0) for y in range(a, b + 1))) for k, (a, b) in per.items()}; ks = list(per); rr = []
for a, b in zip(ks[:-1], ks[1:]):
    t0, t1 = set(np.argsort(-pv[a])[:20]), set(np.argsort(-pv[b])[:20])
    rr.append(dict(pair=f"{a}->{b}", js=js(pv[a], pv[b]), spearman=float(spearmanr(pv[a], pv[b])[0]), top20_entry=len(t1 - t0), top20_exit=len(t0 - t1)))
R = pd.DataFrame(rr); R.to_csv(S4 / "rotation_index_periods.csv", index=False, encoding="utf-8-sig"); print("\n[기간 회전 지수]\n", R.round(4).to_string(index=False))
H = []
for k, (a, b) in per.items():
    c = sum(cnt[y - 2000] for y in range(a, b + 1))
    for vi, v in enumerate(venues):
        for ti_, t in enumerate(topics):
            if c[vi, ti_] > 0: H.append((k, v, int(t), int(c[vi, ti_]), c[vi, ti_] / c[vi].sum()))
pd.DataFrame(H, columns=["period", "venue", "topic", "n", "share_in_venue"]).to_csv(S4 / "heatmap_topic_venue_period.csv", index=False, encoding="utf-8-sig")
with (S4 / "CHANGELOG_S4.md").open("a", encoding="utf-8") as f:
    f.write(f"- {pd.Timestamp.now().isoformat(timespec='seconds')} | 4.6 실행(이월 항목): 연도 인접 JS(잡음 바닥=같은 해 반분 중앙값 50회), 세 표본(all/fixed/within), 기간 회전 지수, 토픽x저널x기간 표. S5 입력 시계열 저장 | S4 4.6 | S5\n")
print("저장 완료")