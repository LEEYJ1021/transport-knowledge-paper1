# -*- coding: utf-8 -*-
# s5_close.py: S5-7 체제 구간 기술 + S5-8 A등급 재추정. 읽기 전용(동결 판정 변경 없음). 미실행 코드.
import json, warnings
from pathlib import Path
import numpy as np, pandas as pd
from scipy.spatial.distance import jensenshannon
warnings.filterwarnings("ignore"); pd.set_option("display.width", 220)
ROOT = Path.home() / "Research/Minnesota_Transport"
S0, S3, S4, S5 = ROOT/"paper1/00_S0", ROOT/"paper1/03_S3", ROOT/"paper1/04_S4", ROOT/"paper1/05_S5"
Y0 = 2000
# 주 분석(c=1) 변화점. 값은 s5_detect 출력에서 옮긴 것이며 '새 구간의 첫 해'로 해석합니다(가정).
BREAKS = {"all": [2012, 2020], "fixed14": [2008, 2015, 2020], "within": [2009, 2015, 2020]}
END = 2025

cnt = np.load(S4/"yearly_venue_topic_counts.npy")            # (26, V, K)
venues = pd.read_csv(S4/"venues_order.csv").venue.astype(str).values
topics = pd.read_csv(S4/"topics_order.csv").topic.astype(int).values
V, K = cnt.shape[1], cnt.shape[2]
assert cnt.shape[0] == 26 and len(venues) == V and len(topics) == K

# 고정 저널 14개
PRE = json.loads((S0/"PREREG.json").read_text(encoding="utf-8"))
def _find(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "fixed_venues": return v
            r = _find(v)
            if r is not None: return r
FIXED = set(_find(PRE)); fixed_v = np.array([v in FIXED for v in venues]); assert fixed_v.sum() == 14, fixed_v.sum()

# A등급 토픽
G = pd.read_csv(S3/"L7_topic_grade.csv")
gcol = [c for c in G.columns if "grade" in c.lower()][0]
A_set = set(G[G[gcol].astype(str).str.strip().str.upper() == "A"].topic.astype(int))
a_mask = np.array([t in A_set for t in topics]); print(f"A등급 토픽 {a_mask.sum()}개 (112여야 함)")

# D3 신생 토픽
d3m = np.zeros(K, bool)
try:
    DS = pd.read_csv(S4/"definition_sensitivity.csv")
    d3 = set(DS[DS.D3.astype(str).str.strip().str.lower().isin(["1","1.0","true","t","yes"])].topic.astype(int))
    d3m = np.array([t in d3 for t in topics])
except Exception as e: print("※ D3 생략:", e)

# 토픽 이름(S3 카드, 열 이름을 추정하므로 실패하면 번호만 씀)
names = {}
try:
    C = pd.read_csv(S3/"topic_evidence_cards.csv")
    ncol = [c for c in C.columns if c.lower() in ("name","label","topic_name","top_terms","top10","keywords")]
    if ncol: names = dict(zip(C.topic.astype(int), C[ncol[0]].astype(str).str.slice(0, 60)))
except Exception as e: print("※ 카드 이름 생략:", e)

wbar_all = cnt.sum((0, 2)) / cnt.sum()
def segments(brk): 
    e = [Y0] + list(brk) + [END + 1]; return [(e[i], e[i+1]-1) for i in range(len(e)-1)]
def seg_counts(a, b, sample):
    c = cnt[a-Y0:b-Y0+1].sum(0)                              # (V, K)
    if sample == "fixed14": c = c * fixed_v[:, None]
    return c
def share_vec(c, sample, mask=None):
    if mask is not None: c = c[:, mask]
    if sample == "within":
        nj = c.sum(1); ok = nj > 0; sj = np.zeros_like(c, float); sj[ok] = c[ok]/nj[ok, None]
        v = (np.where(ok, wbar_all, 0)[:, None] * sj).sum(0)
    else: v = c.sum(0).astype(float)
    return v / v.sum()
js = lambda a, b: float(jensenshannon(a, b, base=2))

def decompose(c0, c1):
    """Griliches-Regev 중점 분해. 반환: (내, 간, 총) 토픽별 벡터."""
    n0, n1 = c0.sum(1), c1.sum(1); w0, w1 = n0/n0.sum(), n1/n1.sum()
    s0 = np.divide(c0, n0[:, None], out=np.zeros_like(c0, float), where=n0[:, None] > 0)
    s1 = np.divide(c1, n1[:, None], out=np.zeros_like(c1, float), where=n1[:, None] > 0)
    within = (((w0+w1)/2)[:, None] * (s1-s0)).sum(0); between = (((s0+s1)/2) * (w1-w0)[:, None]).sum(0)
    tot = (w1[:, None]*s1).sum(0) - (w0[:, None]*s0).sum(0)
    assert np.allclose(within+between, tot, atol=1e-9), "불변식 실패(내+간≠총)"
    return within, between, tot

desc, trans, topr, ag = [], [], [], []
for sample, brk in BREAKS.items():
    segs = segments(brk); sv, svA, cs = [], [], []
    for (a, b) in segs:
        c = seg_counts(a, b, sample); cs.append(c)
        v = share_vec(c, sample); vA = share_vec(c, sample, a_mask); sv.append(v); svA.append(vA)
        p = v[v > 0]
        desc.append(dict(sample=sample, seg=f"{a}-{b}", n_years=b-a+1, n_papers=int(c.sum()),
                         eff_topics=float(np.exp(-(p*np.log(p)).sum())), hhi=float((v**2).sum()), d3_share=float(v[d3m].sum())))
        for r, i in enumerate(np.argsort(-v)[:10], 1):
            topr.append(dict(sample=sample, seg=f"{a}-{b}", kind="top_share", rank=r, topic=int(topics[i]), share=float(v[i]), name=names.get(int(topics[i]), "")))
    for s in range(len(segs)-1):
        lab = f"{segs[s][0]}-{segs[s][1]} -> {segs[s+1][0]}-{segs[s+1][1]}"
        row = dict(sample=sample, transition=lab, js_all=js(sv[s], sv[s+1]), js_Aonly=js(svA[s], svA[s+1]))
        row["js_ratio_A_vs_all"] = row["js_Aonly"]/row["js_all"]; row["A_within_30pct"] = bool(abs(row["js_ratio_A_vs_all"]-1) <= 0.30)
        if sample != "within":
            wi, bt, tot = decompose(cs[s], cs[s+1])
            row["between_share_abs"] = float(np.abs(bt).sum()/(np.abs(wi).sum()+np.abs(bt).sum()))
            for r, i in enumerate(np.argsort(-np.abs(tot))[:10], 1):
                topr.append(dict(sample=sample, seg=lab, kind="top_change", rank=r, topic=int(topics[i]), share=float(tot[i]),
                                 between=float(bt[i]), within=float(wi[i]), grade_A=bool(a_mask[i]), name=names.get(int(topics[i]), "")))
        else: row["between_share_abs"] = np.nan
        trans.append(row)
# S5-8: 변화점 위치 A등급 재탐지와의 비교는 강건성 표(A_grade_only)를 그대로 인용합니다.
ag = [dict(sample="all", obs=[2012, 2020], A_only=[2014, 2020], same_within_1y=False),
      dict(sample="fixed14", obs=[2008, 2015, 2020], A_only=[2012, 2020], same_within_1y=False),
      dict(sample="within", obs=[2009, 2015, 2020], A_only=[2009, 2015, 2020], same_within_1y=True)]
D, T, R, A = pd.DataFrame(desc), pd.DataFrame(trans), pd.DataFrame(topr), pd.DataFrame(ag)
D.to_csv(S5/"segment_description.csv", index=False, encoding="utf-8-sig"); T.to_csv(S5/"segment_transitions_Agrade.csv", index=False, encoding="utf-8-sig")
R.to_csv(S5/"segment_top_topics.csv", index=False, encoding="utf-8-sig"); A.to_csv(S5/"Agrade_break_positions.csv", index=False, encoding="utf-8-sig")
print("\n[구간 기술]\n", D.round(4).to_string(index=False))
print("\n[구간 간 JS: 전체 vs A등급, ±30% 기준]\n", T.round(4).to_string(index=False))
print("\n[변화점 위치 A등급 비교(강건성 표 인용)]\n", A.to_string(index=False))
print("\n저장: segment_description.csv, segment_transitions_Agrade.csv, segment_top_topics.csv, Agrade_break_positions.csv")
print("※ 이 출력은 기술용입니다. 귀무 미통과(연속 변화 서술) 판정은 바뀌지 않습니다.")