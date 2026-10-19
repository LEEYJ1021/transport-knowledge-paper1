# -*- coding: utf-8 -*-
# s6_run.py: S6 본 분석(4항 분해, 초과 진입분, 경로 분해, 순열, 부트스트랩, 따라감 비율, multiverse). 미실행 코드.
import sys, json, itertools
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from s6_lib import *
QUICK = False            # 먼저 True로 오류 확인 → False로 본 실행
spec = load_spec(); L = load_all(spec); K = L["K"]; rng = np.random.default_rng(spec["seed"])
B_perm, B_boot = (30, 30) if QUICK else (spec["B_perm"], spec["B_boot"]); sfx = "_QUICK" if QUICK else ""
PAIRS = pairs_of(spec); MAIN = spec["main"]; TERMS = ["adapt", "realloc", "entry_new", "entry_ret", "exit_final", "exit_gap"]
Dsets = {}
try:
    DS = pd.read_csv(S4 / "definition_sensitivity.csv")
    for d in spec["defs"]:
        if d in DS.columns: Dsets[d] = np.array([t in set(DS[tf(DS[d])].topic.astype(int)) for t in L["topics"]])
        else: print(f"※ {d} 열 없음: definition_sensitivity.csv 열 확인 {list(DS.columns)}")
except Exception as e: print("※ 신생 정의 로드 실패:", e)
def summarize(dec):
    tot = half(dec["total"]); row = dict(total_half=tot)
    ab = {t: half(dec[t]) for t in TERMS}; s = sum(ab.values())
    for t in TERMS: row["abs_" + t] = ab[t]; row["share_" + t] = ab[t] / s if s > 0 else np.nan
    return row

# ---------- 1. 4항 분해 (S6-2) + 저널 고정 변형 (6.5b) ----------
rows, exc_rows, path_rows = [], [], []
for p0, p1 in PAIRS:
    for sc in spec["schemes"]:
        if "m_" + sc not in L["R"].columns: continue
        P = make_pair(L, p0, p1, sc, "all", "all", "baseline"); d = P.decompose()
        rows.append(dict(pair=f"{p0}->{p1}", scheme=sc, variant="all_venues", n_P=int((P.role == "P").sum()),
                         n_E=int(np.isin(P.role, ["E_new", "E_ret"]).sum()), n_X=int(np.isin(P.role, ["X_final", "X_gap"]).sum()), **summarize(d)))
        ex, drop = P.excess(); exc_rows.append(dict(pair=f"{p0}->{p1}", scheme=sc, excess_half=half(ex), dropped_entrant_mass=drop,
                                                    **{f"excess_D{d_[1:]}": float(ex[m].sum()) for d_, m in Dsets.items()}))
        g = P.path_gap()
        if g: path_rows.append(dict(pair=f"{p0}->{p1}", scheme=sc, gap_half=half(g["gap"]), within_abs=half(g["within"]), between_abs=half(g["between"]),
                                    within_share=half(g["within"]) / (half(g["within"]) + half(g["between"]))))
    # 저널 고정 변형: 저널별로 같은 분해를 하고 저널 중점 질량으로 가중(역할은 저널 내 존재 기준)
    R = L["R"]; mc = "m_" + MAIN["scheme"]; acc = {t: np.zeros(K) for t in TERMS + ["total"]}
    m0 = R[R.period == p0].groupby("vi")[mc].sum(); m1 = R[R.period == p1].groupby("vi")[mc].sum()
    for j in range(L["V"]):
        if j not in m0.index or j not in m1.index: continue
        Rj = R[R.vi == j]; Pj = Pair(Rj, p0, p1, L, mc); dj = Pj.decompose(); vb = (m0[j] / m0.sum() + m1[j] / m1.sum()) / 2
        for t in acc: acc[t] += vb * dj[t]
    rows.append(dict(pair=f"{p0}->{p1}", scheme=MAIN["scheme"], variant="venue_fixed", **summarize({**acc})))
pd.DataFrame(rows).to_csv(S6 / f"renewal_decomposition{sfx}.csv", index=False, encoding="utf-8-sig")
pd.DataFrame(exc_rows).to_csv(S6 / f"entry_excess{sfx}.csv", index=False, encoding="utf-8-sig")
pd.DataFrame(path_rows).to_csv(S6 / f"journal_path_decomposition{sfx}.csv", index=False, encoding="utf-8-sig")
print("[4항 분해(주 가중치) 절대기여 몫]\n", pd.DataFrame(rows).query("variant=='all_venues'")[["pair", "scheme", "total_half"] + ["share_" + t for t in TERMS]].round(3).to_string(index=False))

# ---------- 2. 층화 순열 음성 대조 (S6-4) / 3. 곱셈 가중 부트스트랩 (S6-5) ----------
perm_rows, boot_rows = [], []
for p0, p1 in PAIRS:
    P = make_pair(L, p0, p1, MAIN["scheme"], MAIN["venue"], MAIN["topic"], MAIN["hom"]); obs, _ = P.excess(); o = half(obs)
    null = np.array([half(P.excess(isE=P.perm_isE(rng))[0]) for _ in range(B_perm)])
    perm_rows.append(dict(pair=f"{p0}->{p1}", obs_excess=o, null_min=null.min(), null_p05=np.percentile(null, 5), null_med=np.median(null),
                          null_p95=np.percentile(null, 95), null_max=null.max(), obs_percentile=float((null < o).mean() * 100)))
    nAuth, nPap = P.nA, int(max(P.pc0.max(), P.pc1.max())) + 1; bs = []
    for _ in range(B_boot):
        wa = rng.exponential(size=nAuth); wp = rng.exponential(size=nPap)
        m0, m1 = P.m0 * wa[P.a0] * wp[P.pc0], P.m1 * wa[P.a1] * wp[P.pc1]; d = P.decompose(m0, m1)
        bs.append({**{"abs_" + t: half(d[t]) for t in TERMS}, "total_half": half(d["total"]), "excess_half": half(P.excess(m1)[0])})
    bs = pd.DataFrame(bs); d0 = P.decompose(); ex0 = half(P.excess()[0])
    for c in bs.columns:
        ob = ex0 if c == "excess_half" else (half(d0["total"]) if c == "total_half" else half(d0[c[4:]]))
        boot_rows.append(dict(pair=f"{p0}->{p1}", stat=c, obs=ob, lo=np.percentile(bs[c], spec["ci"][0]), hi=np.percentile(bs[c], spec["ci"][1])))
pd.DataFrame(perm_rows).to_csv(S6 / f"renewal_permutation{sfx}.csv", index=False, encoding="utf-8-sig")
pd.DataFrame(boot_rows).to_csv(S6 / f"renewal_bootstrap{sfx}.csv", index=False, encoding="utf-8-sig")
print("\n[순열 음성 대조: 관측 초과분의 순열 분포 내 위치]\n", pd.DataFrame(perm_rows).round(4).to_string(index=False))

# ---------- 4. 지속 저자 따라감 비율 (4.7 / S6-8): 정의 D1~D4 범위로 보고 ----------
fr = []
for p0, p1 in PAIRS:
    P = make_pair(L, p0, p1, MAIN["scheme"], MAIN["venue"], MAIN["topic"], MAIN["hom"]); M0, M1 = P.mats(); Pm = P.role == "P"
    w0 = np.asarray(M0.sum(1)).ravel(); w1 = np.asarray(M1.sum(1)).ravel()
    for d, dm in Dsets.items():
        d0 = np.asarray(M0[:, dm].sum(1)).ravel() / np.where(w0 > 0, w0, 1); d1 = np.asarray(M1[:, dm].sum(1)).ravel() / np.where(w1 > 0, w1, 1)
        for sub, mk in [("all", Pm), (f"n0>={spec['follow_min_papers']}", Pm & (P.n0 >= spec["follow_min_papers"]))]:
            z = mk & (d0 == 0); wb = ((w0 + w1) / 2)[mk]
            # split-half 신뢰도: 지속 저자의 t1 논문 행을 반으로 나눠 D 몫의 상관
            rel = []
            for _ in range(spec["follow_splits"]):
                msk = mk[P.a1] & (P.n1[P.a1] >= 2); lab = rng.random(msk.sum()) < 0.5
                a_, h_ = P.a1[msk], lab.astype(int); dd = dm[P.t1[msk]].astype(float); mm = P.m1[msk]; key = a_ * 2 + h_
                num = np.bincount(key, mm * dd, 2 * P.nA); den = np.bincount(key, mm, 2 * P.nA); ok2 = (den[0::2] > 0) & (den[1::2] > 0)
                g = pd.DataFrame({"x": num[0::2][ok2] / den[0::2][ok2], "y": num[1::2][ok2] / den[1::2][ok2]})
                if len(g) > 30: rel.append(g.x.corr(g.y))
            fr.append(dict(pair=f"{p0}->{p1}", defn=d, subset=sub, n_persist=int(mk.sum()), n_zero_t0=int(z.sum()),
                           adopt_rate=float((d1[z] > 0).mean()) if z.sum() else np.nan,
                           mass_weighted_shift=float((wb * (d1 - d0)[mk]).sum() / wb.sum()) if wb.sum() else np.nan,
                           split_half_r=float(np.nanmean(rel)) if rel else np.nan))
FR = pd.DataFrame(fr); FR.to_csv(S6 / f"follow_rate_by_definition{sfx}.csv", index=False, encoding="utf-8-sig")
print("\n[따라감 비율: 정의별 범위(채택률)]\n", FR[FR.subset == "all"].groupby("pair").adopt_rate.agg(["min", "max"]).round(3).to_string())

# ---------- 5. Multiverse (S6-9) + 동명이인 범위 (S6-7) ----------
grid = []
axes = list(itertools.product(PAIRS, [s for s in spec["schemes"] if "m_" + s in L["R"].columns], spec["venue_sets"], list(L["risk"]), spec["topic_sets"]))
if QUICK: axes = axes[::max(1, len(axes) // 40)]
for (p0, p1), sc, vs, hom, ts in axes:
    try:
        P = make_pair(L, p0, p1, sc, vs, ts, hom); d = P.decompose(); ex, _ = P.excess(); g = P.path_gap()
    except AssertionError as e: print("불변식 실패, 수치 폐기:", (p0, p1, sc, vs, hom, ts), e); continue
    tm = L["A"] if ts == "A" else np.ones(K, bool)
    for dn, dm in Dsets.items():
        grid.append(dict(pair=f"{p0}->{p1}", scheme=sc, venue=vs, hom=hom, topic=ts, defn=dn, circular=bool({p0, p1} & set(spec["circular"][dn])),
                         K1=int(np.sign(ex[dm & tm].sum())), K2=(int(half(g["within"]) > half(g["between"])) if g else np.nan),
                         K3=int(half(d["adapt"]) > half(d["entry"])), excess_half=half(ex), within_share=(half(g["within"]) / (half(g["within"]) + half(g["between"])) if g else np.nan),
                         entry_share=half(d["entry"]) / max(sum(half(d[t]) for t in ["adapt", "realloc", "entry", "exit"]), 1e-300)))
G = pd.DataFrame(grid); G.to_csv(S6 / f"multiverse_grid{sfx}.csv", index=False, encoding="utf-8-sig")
G.groupby(["pair", "hom"])[["excess_half", "within_share", "entry_share"]].agg(["min", "max"]).to_csv(S6 / f"homonym_range{sfx}.csv", encoding="utf-8-sig")
res = []
for pr, g in G.groupby("pair"):
    mrow = g[(g.scheme == MAIN["scheme"]) & (g.venue == MAIN["venue"]) & (g.hom == MAIN["hom"]) & (g.topic == MAIN["topic"]) & (g.defn == MAIN["defn"])]
    if mrow.empty: print("※ 주 설정 칸이 없음(QUICK 표본 때문일 수 있음):", pr); continue
    for k in ["K1", "K2", "K3"]:
        for lab, gg in ([("전체", g), ("순환 칸 제외", g[~g.circular])] if k == "K1" else [("전체", g)]):   # K2·K3는 D와 무관하므로 순환 제외는 K1에만
            res.append(dict(pair=pr, var=k, subset=lab, n=len(gg), main=mrow[k].iloc[0], frac_diff=float((gg[k] != mrow[k].iloc[0]).mean())))
RS = pd.DataFrame(res); RS["pass_le_0.25"] = (RS.frac_diff <= spec["pass_criteria"]["direction_split_max"]).where(RS.n > 0, other=np.nan); print("\n[Multiverse: 주 설정과 방향이 다른 비율]\n", RS.round(3).to_string(index=False))
RS.to_csv(S6 / f"multiverse_direction_split{sfx}.csv", index=False, encoding="utf-8-sig")
json.dump(dict(spec_hash=spec["hash"], seed=spec["seed"], quick=QUICK, B_perm=B_perm, B_boot=B_boot, n_grid=len(G), note="불변식 실패 설정은 제외됨"), open(S6 / f"S6_meta{sfx}.json", "w"), indent=1)
print("저장 완료. ※ 해석은 '함께 움직인다'까지, '구간'이라고 쓰고 '체제'라고 쓰지 않음.")