# -*- coding: utf-8 -*-
# s6_lib.py (v2): S6 공용 함수. 직접 실행하지 않음. F2/F4/S2 실제 열 구성에 맞춤.
import json, hashlib, warnings
from pathlib import Path
import numpy as np, pandas as pd
import scipy.sparse as sp
warnings.filterwarnings("ignore")
ROOT = Path.home() / "Research/Minnesota_Transport"
DATA, S0, S2, S3, S4 = ROOT/"analysis_data/final", ROOT/"paper1/00_S0", ROOT/"paper1/02_S2", ROOT/"paper1/03_S3", ROOT/"paper1/04_S4"
S6 = ROOT/"paper1/06_S6"; S6.mkdir(parents=True, exist_ok=True)
tf = lambda s: s.astype(str).str.strip().str.lower().isin(["1", "1.0", "true", "t", "yes"])
def pick(df, cands, what):
    for c in cands:
        if c in df.columns: return c
    raise KeyError(f"[{what}] 후보 열 {cands} 중 없음. 실제 열: {list(df.columns)[:40]}")
def _find(o, key):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == key: return v
            r = _find(v, key)
            if r is not None: return r
def load_spec():
    p = S6 / "S6_0_PREREG.json"
    assert p.exists(), "S6_0_PREREG.json 없음: s6_0_freeze.py를 FREEZE=True로 먼저 실행"
    return json.loads(p.read_text(encoding="utf-8"))

# ---------- 결측 보정 가중치: S2 산출물 paper_ipw.csv.gz 사용 (S4와 같은 모델이어야 함) ----------
def ipw_weights(W, spec):
    I = pd.read_csv(S2 / spec["files"]["ipw"], low_memory=False); I["pid"] = I.pid.astype(str)
    print("IPW 모델별 행 수:", I.model.value_counts().to_dict(), "| 사용:", spec["ipw_model"])
    I = I[I.model == spec["ipw_model"]].drop_duplicates("pid").set_index("pid")
    w = W.pid.map(I.w_ipw); ht = tf(W.has_topic)
    print(f"IPW 범위(주제 논문) {w[ht].min():.3f}~{w[ht].max():.3f} (S4는 0.86~1.94) | 결측 {int(w[ht].isna().sum())}편은 1로 대체")
    return w.fillna(1.0)

# ---------- 데이터 구축 ----------
def load_all(spec):
    F = spec["files"]; per = spec["periods"]; c = spec["cols"]
    W = pd.read_csv(DATA / F["papers"], low_memory=False); W["pid"] = W.pid.astype(str)
    EXC = set(pd.read_csv(S0 / "EXCLUDE_PIDS_FROZEN.csv", dtype=str, encoding="utf-8-sig").pid)
    W = W[~W.pid.isin(EXC) & tf(W.in_sample) & W.year.between(2000, spec["data_end"])].copy()
    W["period"] = W.year.map(lambda y: next((k for k, (a, b) in per.items() if a <= y <= b), None))
    W["ipw"] = ipw_weights(W, spec)
    T = W[tf(W.has_topic) & W.topic150.notna()].copy()
    assert len(T) == spec["n_analysis"], (len(T), spec["n_analysis"])
    G = pd.read_csv(S3 / "L7_topic_grade.csv"); topics = np.array(sorted(G.topic.astype(int))); K = len(topics)
    gcol = [x for x in G.columns if "grade" in x.lower()][0]
    A_set = set(G[G[gcol].astype(str).str.strip().str.upper() == "A"].topic.astype(int))
    T["ti"] = T.topic150.astype(int).map({t: i for i, t in enumerate(topics)}).astype(int)
    venues = np.array(sorted(T.venue_short.unique())); T["vi"] = T.venue_short.map({v: i for i, v in enumerate(venues)}).astype(int)
    FIXED = set(_find(json.loads((S0 / "PREREG.json").read_text(encoding="utf-8")), "fixed_venues")); assert len(FIXED) == 14
    T["fixed"] = T.venue_short.isin(FIXED); T["isA"] = T.topic150.astype(int).isin(A_set)
    T["cell"] = T.year * 1000 + T.vi
    # 저자-논문 행 (F2: 위험군 이름 이미 제외, w = 남은 저자 수로 재정규화한 equal)
    AP = pd.read_csv(DATA / F["author_paper"], encoding="utf-8-sig", low_memory=False)
    AP["pid"] = AP[pick(AP, c["pid"], "pid")].astype(str); AP["aid"] = AP[pick(AP, c["aid"], "저자 식별자")].astype(str)
    AP["ai"], uniq = pd.factorize(AP.aid); nA = len(uniq)
    n = pd.to_numeric(AP[pick(AP, c["n_authors"], "n_authors")], errors="coerce"); pos = pd.to_numeric(AP[pick(AP, c["position"], "author_pos")], errors="coerce")
    # 첫/마지막 출판 연도: F4(주제 없는 논문 포함 기준) 우선, 없으면 F2 최소/최대
    F4 = pd.read_csv(DATA / F["authors"], encoding="utf-8-sig").drop_duplicates("name_norm").set_index("name_norm")
    f2min = AP.groupby("ai").year.min().reindex(range(nA)).values.astype(float); f2max = AP.groupby("ai").year.max().reindex(range(nA)).values.astype(float)
    f4min = pd.Series(uniq).map(F4.first_year).values.astype(float); f4max = pd.Series(uniq).map(F4.last_year).values.astype(float)
    fy = np.nanmin(np.vstack([f4min, f2min]), axis=0).astype(int); ly = np.nanmax(np.vstack([f4max, f2max]), axis=0).astype(int)
    print(f"F4에 없는 저자 {int(np.isnan(f4min).sum())}명 | F4 첫해 > F2 첫해인 저자 {int((f4min > f2min).sum())}명(0이어야 정상) | F4 마지막해 < F2 마지막해 {int((f4max < f2max).sum())}명")
    # 가중치 4종
    al = pd.read_csv(S2 / F["alpha"], low_memory=False); al["pid"] = al.pid.astype(str); isal = AP.pid.isin(set(al.loc[tf(al.is_alpha), "pid"])).values
    fl = np.where(n == 1, 1.0, np.where((pos == 1) | (pos == n), 0.5, 0.0))
    allw = {"equal": AP.w.values, "inv_n_authors": (1.0 / n).values, "first_last": np.where(isal, AP.w.values, fl), "full_count": np.ones(len(AP))}
    wcols = {s: allw[s] for s in spec["schemes"]}
    for s, v in wcols.items(): AP["w_" + s] = v
    R = AP[["pid", "aid", "ai"] + ["w_" + s for s in wcols]].merge(T[["pid", "year", "ti", "vi", "cell", "period", "ipw", "fixed", "isA"]], on="pid", how="inner")
    R["pc"] = pd.factorize(R.pid)[0]
    for s in wcols: R["m_" + s] = R["w_" + s] * R.ipw
    R = R[R.period.notna()].dropna(subset=["m_" + s for s in wcols])
    risk = {"baseline": np.zeros(nA, bool)}                                           # 위험군은 F2에서 이미 제외됨: 변형은 baseline뿐
    print(f"분석 논문 {len(T):,} | 저자-논문 행 {len(R):,} | 저자 {R.ai.nunique():,} | 가중치 {list(wcols)} | 위험군 변형 {list(risk)} (F2는 위험군 제외 상태)")
    return dict(R=R, first=fy, last=ly, risk=risk, K=K, V=len(venues), topics=topics, venues=venues, spec=spec, A=np.array([t in A_set for t in topics]))

# ---------- 기간 쌍 ----------
class Pair:
    def __init__(s, R, p0, p1, L, mcol):
        spec = L["spec"]; a, b = spec["periods"][p0], spec["periods"][p1]; s.K, s.nV = L["K"], L["V"]; s.p0, s.p1 = p0, p1
        R = R[R[mcol] > 0]                                                              # 가중치 0인 행(예: first_last의 중간 저자)은 '존재'로 세지 않음
        r0, r1 = R[R.period == p0], R[R.period == p1]
        s.aids = np.union1d(r0.ai.values, r1.ai.values); s.nA = len(s.aids); ix = lambda x: np.searchsorted(s.aids, x)
        s.a0, s.t0, s.m0 = ix(r0.ai.values), r0.ti.values, r0[mcol].values.astype(float)
        s.a1, s.t1, s.m1 = ix(r1.ai.values), r1.ti.values, r1[mcol].values.astype(float)
        s.c1, s.v1 = pd.factorize(r1.cell.values)[0], r1.vi.values; s.nC = s.c1.max() + 1
        s.pc0, s.pc1 = r0.pc.values, r1.pc.values
        in0 = np.zeros(s.nA, bool); in0[s.a0] = True; in1 = np.zeros(s.nA, bool); in1[s.a1] = True
        fy, ly = L["first"][s.aids], L["last"][s.aids]; role = np.full(s.nA, "", dtype=object)
        role[in0 & in1] = "P"; role[~in0 & in1 & (fy >= b[0])] = "E_new"; role[~in0 & in1 & (fy < b[0])] = "E_ret"
        role[in0 & ~in1 & (ly <= a[1])] = "X_final"; role[in0 & ~in1 & (ly > a[1])] = "X_gap"
        s.role = role; s.isE0 = np.isin(role[s.a1], ["E_new", "E_ret"]); s.exit_censored = b[1] >= spec["data_end"]
        s.n0 = np.bincount(s.a0, minlength=s.nA); s.n1 = np.bincount(s.a1, minlength=s.nA)
    def mats(s, m0=None, m1=None):
        m0 = s.m0 if m0 is None else m0; m1 = s.m1 if m1 is None else m1
        mk = lambda a, t, m: sp.coo_matrix((m / m.sum(), (a, t)), shape=(s.nA, s.K)).tocsr()
        return mk(s.a0, s.t0, m0), mk(s.a1, s.t1, m1)
    def decompose(s, m0=None, m1=None):
        M0, M1 = s.mats(m0, m1); w0 = np.asarray(M0.sum(1)).ravel(); w1 = np.asarray(M1.sum(1)).ravel()
        S0 = np.asarray(M0.sum(0)).ravel(); S1 = np.asarray(M1.sum(0)).ravel(); Sb = (S0 + S1) / 2
        assert abs(S0.sum() - 1) < 1e-9 and abs(S1.sum() - 1) < 1e-9, "질량 보존 실패"
        inv = lambda w: np.where(w > 0, 1 / np.where(w > 0, w, 1), 0.0)
        s0 = sp.diags(inv(w0)) @ M0; s1 = sp.diags(inv(w1)) @ M1; P = s.role == "P"; out = {}
        sv = lambda X: np.asarray(X.sum(0)).ravel()
        out["adapt"] = sv(sp.diags(((w0 + w1) / 2)[P]) @ (s1[P] - s0[P]))
        out["realloc"] = sv(sp.diags((w1 - w0)[P]) @ ((s0[P] + s1[P]) / 2)) - Sb * (w1 - w0)[P].sum()
        for r in ["E_new", "E_ret"]: m = s.role == r; out["entry_" + r[2:]] = sv(M1[m]) - Sb * w1[m].sum()
        for r in ["X_final", "X_gap"]: m = s.role == r; out["exit_" + r[2:]] = -(sv(M0[m]) - Sb * w0[m].sum())
        out["total"] = S1 - S0
        assert np.allclose(sum(v for k, v in out.items() if k != "total"), out["total"], atol=1e-9), "불변식 실패(항 합≠총변화): 이 실행 수치 폐기"
        out["entry"] = out["entry_new"] + out["entry_ret"]; out["exit"] = out["exit_final"] + out["exit_gap"]; return out
    def excess(s, m1=None, isE=None):
        """초과 진입분 = 진입 저자 토픽 질량 − 같은 저널×연도 셀 지속 저자 분포로 대체한 기대치(셀에 지속 질량이 없으면 제외)."""
        m1 = s.m1 if m1 is None else m1; isE = s.isE0 if isE is None else isE; m = m1 / m1.sum(); K = s.K
        Pm = np.bincount(s.c1[~isE] * K + s.t1[~isE], m[~isE], s.nC * K).reshape(s.nC, K); Pc = Pm.sum(1)
        Em = np.bincount(s.c1[isE], m[isE], s.nC); ok = Pc > 0; sel = isE & ok[s.c1]
        obs = np.bincount(s.t1[sel], m[sel], K); exp = ((Em[ok] / Pc[ok])[:, None] * Pm[ok]).sum(0)
        return obs - exp, float(Em[~ok].sum() / max(Em.sum(), 1e-300))
    def perm_isE(s, rng):
        n = len(s.c1); order = np.lexsort((rng.random(n), s.c1)); cs = s.c1[order]
        start = np.r_[0, np.flatnonzero(np.diff(cs)) + 1]; cnt = np.diff(np.r_[start, n]); rank = np.arange(n) - np.repeat(start, cnt)
        nE = np.bincount(s.c1[s.isE0], minlength=s.nC); lab = np.empty(n, bool); lab[order] = rank < nE[cs]; return lab
    def path_gap(s, m1=None):
        """신규-지속 토픽 분포 차이 E_k−P_k의 저널 내/간 분해(중점 가중). 불변식: 내+간=E−P."""
        m1 = s.m1 if m1 is None else m1; V, K = s.nV, s.K
        def dist(sel):
            Mj = np.bincount(s.v1[sel] * K + s.t1[sel], m1[sel], V * K).reshape(V, K); j = Mj.sum(1)
            if j.sum() <= 0: return None
            return j / j.sum(), np.divide(Mj, j[:, None], out=np.zeros_like(Mj), where=j[:, None] > 0), Mj.sum(0) / Mj.sum()
        E, Pp = dist(s.isE0), dist(~s.isE0)
        if E is None or Pp is None: return None
        e, Ejk, Ek = E; p, Pjk, Pk = Pp
        within = (((e + p) / 2)[:, None] * (Ejk - Pjk)).sum(0); between = (((Ejk + Pjk) / 2) * (e - p)[:, None]).sum(0)
        assert np.allclose(within + between, Ek - Pk, atol=1e-9), "경로 분해 불변식 실패"
        return dict(within=within, between=between, gap=Ek - Pk)

half = lambda v: float(0.5 * np.abs(v).sum())
def make_pair(L, p0, p1, scheme="equal", venue="all", topic="all", hom="baseline"):
    R = L["R"]; mk = R.period.isin([p0, p1])
    if venue == "fixed14": mk &= R.fixed
    if topic == "A": mk &= R.isA
    if hom != "baseline": mk &= ~L["risk"][hom][R.ai.values]
    return Pair(R[mk], p0, p1, L, "m_" + scheme)
def pairs_of(spec): ks = list(spec["periods"]); return list(zip(ks[:-1], ks[1:]))
