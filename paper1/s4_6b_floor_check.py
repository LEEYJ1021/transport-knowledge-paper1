# 복구본: hist_1080_0006.py (+ 노트북 셀 교차 확인). 2026-10-19 복구. 최초 실행은 2026-10-16 (산출물 시각 이전 세션)
# 최종 실행본임을 증명하지는 못함: 산출물은 S4_MANIFEST.json 해시로 검증. 재실행하지 않음
# -*- coding: utf-8 -*-
# s4_6b_floor_check.py: 풀 재표집 바닥으로 연도 인접 JS 재점검. 읽기 전용 탐색(동결 파일 변경 없음).
import json, warnings
from pathlib import Path
import numpy as np, pandas as pd
from scipy.spatial.distance import jensenshannon
warnings.filterwarnings("ignore"); pd.set_option("display.width", 200)
R_ = 1000          # 귀무 재표집 횟수
ROOT = Path.home() / "Research/Minnesota_Transport"
DATA, S0, S3, S4 = ROOT / "analysis_data/final", ROOT / "paper1/00_S0", ROOT / "paper1/03_S3", ROOT / "paper1/04_S4"
tf = lambda s: s.astype(str).str.strip().str.lower().isin(["1", "1.0", "true", "t", "yes"])
rng = np.random.default_rng(2026)
PRE = json.loads((S0 / "PREREG.json").read_text(encoding="utf-8"))
def _find(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "fixed_venues": return v
            r = _find(v)
            if r is not None: return r
FIXED = set(_find(PRE)); assert len(FIXED) == 14, len(FIXED)

W = pd.read_csv(DATA / "F1_papers.csv", low_memory=False); W["pid"] = W.pid.astype(str)
EXC = set(pd.read_csv(S0 / "EXCLUDE_PIDS_FROZEN.csv", dtype=str, encoding="utf-8-sig").pid)
W = W[~W.pid.isin(EXC) & tf(W.in_sample) & W.year.between(2000, 2025) & tf(W.has_topic) & W.topic150.notna()].copy()
print(f"분석 집합 {len(W):,}편 (76,984여야 함)"); assert len(W) == 76984
topics = np.array(sorted(pd.read_csv(S3 / "L7_topic_grade.csv").topic.astype(int))); K = len(topics)
W["ti"] = W.topic150.astype(int).map({t: i for i, t in enumerate(topics)}).values
W["fixed"] = W.venue_short.isin(FIXED); W["vi"] = W.venue_short.astype("category").cat.codes
years = np.arange(2000, 2026)

def dist(x): c = np.bincount(x, minlength=K).astype(float); return c / c.sum()
js = lambda a, b: float(jensenshannon(a, b, base=2))

def pool_null(x0, x1):
    """x0, x1: 두 해의 토픽 인덱스. 풀에서 같은 크기로 재표집한 JS 분포."""
    pool = np.concatenate([x0, x1]); n0 = len(x0); out = np.empty(R_)
    for r in range(R_):
        p = rng.permutation(len(pool)); out[r] = js(dist(pool[p[:n0]]), dist(pool[p[n0:]]))
    return out

def within_null(d0, d1):
    """저널 구성은 유지하고 저널x연도 셀 안에서만 토픽을 섞는 귀무(풀은 두 해의 같은 저널 논문)."""
    out = np.empty(R_); j0, j1 = d0.vi.values, d1.vi.values; t0, t1 = d0.ti.values, d1.ti.values
    pooled = {v: np.concatenate([t0[j0 == v], t1[j1 == v]]) for v in np.union1d(j0, j1)}
    n0 = {v: int((j0 == v).sum()) for v in pooled}
    for r in range(R_):
        a, b = [], []
        for v, arr in pooled.items():
            p = rng.permutation(len(arr)); a.append(arr[p[:n0[v]]]); b.append(arr[p[n0[v]:]])
        out[r] = js(dist(np.concatenate(a)), dist(np.concatenate(b)))
    return out

rows = []
for name in ["all", "fixed", "within"]:
    base = W if name != "fixed" else W[W.fixed]
    for y in years[1:]:
        d0, d1 = base[base.year == y - 1], base[base.year == y]
        if len(d0) < 20 or len(d1) < 20: continue
        obs = js(dist(d0.ti.values), dist(d1.ti.values))
        null = within_null(d0, d1) if name == "within" else pool_null(d0.ti.values, d1.ti.values)
        rows.append(dict(sample=name, year=int(y), n0=len(d0), n1=len(d1), js_obs=obs, floor_med=float(np.median(null)),
                         floor_p95=float(np.percentile(null, 95)), corrected=obs - float(np.median(null)), p_emp=float((null >= obs).mean())))
    print(f"{name} 완료")
Y = pd.DataFrame(rows); Y.to_csv(S4 / "yearly_js_poolfloor_check.csv", index=False, encoding="utf-8-sig")
for name in ["all", "fixed", "within"]:
    s = Y[Y["sample"] == name]
    print(f"\n[{name}] 보정값>0 연도 {int((s.corrected > 0).sum())}/{len(s)} | p<0.05 연도 {int((s.p_emp < 0.05).sum())}")
    print(s.sort_values("corrected", ascending=False).head(6)[["year", "n0", "n1", "js_obs", "floor_med", "corrected", "p_emp"]].round(4).to_string(index=False))
print("\n[2006~2008, 2019~2021, 2024~2025 (all)]")
print(Y[(Y["sample"] == "all") & Y.year.isin([2006, 2007, 2008, 2019, 2020, 2021, 2024, 2025])][["year", "n0", "n1", "js_obs", "floor_med", "corrected", "p_emp"]].round(4).to_string(index=False))
with (S4 / "CHANGELOG_S4.md").open("a", encoding="utf-8") as f:
    f.write(f"- {pd.Timestamp.now().isoformat(timespec='seconds')} | 4.6b 바닥 재점검(탐색, 동결 판정 없음): 두 해 풀에서 같은 크기 재표집 {R_}회(within은 저널x연도 셀 내 토픽 섞기). 반분 바닥의 과대평가 점검 | S4 4.6 | S5 바닥 규칙\n")
print("\n저장: yearly_js_poolfloor_check.csv")