# -*- coding: utf-8 -*-
# s5_detect.py: S5 본 계산(동결 규칙 S5_0_PREREG.json 사용). 순서: 관측 탐지 -> 부트스트랩 -> 귀무 -> 반분 -> 강건성 -> 사건 대조 -> 유형 분류
# 사용: 먼저 QUICK=True로 오류 점검, 이후 QUICK=False. 결과를 보고 규칙을 바꾸지 않는다.
import sys, json, warnings
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from s5_lib import *
warnings.filterwarnings("ignore"); pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30)
QUICK = False

# ---------- 0. 동결 검증 ----------
spec = json.loads((S5 / "S5_0_PREREG.json").read_text(encoding="utf-8"))
core = {k: v for k, v in spec.items() if k not in ("created", "sha256", "reference_hashes_at_freeze")}
if sha_b(json.dumps(core, sort_keys=True, ensure_ascii=False).encode()) != spec["sha256"]: raise SystemExit("⛔ 동결 해시 불일치")
for f, h in spec["reference_hashes_at_freeze"].items():
    if sha_f(ROOT / f) != h: raise SystemExit(f"⛔ 참조 파일 {f} 해시가 동결 시점과 다름")
print("동결 검증 통과", spec["sha256"][:12])
rng = np.random.default_rng(spec["seed"])
cnt, venues, topics, fixed_v = load_counts(); wbar = cnt.sum((0, 2)) / cnt.sum()
T, K = len(YEARS), len(topics); SAM = spec["samples"]; D = spec["detection"]; PHI = {k: v["phi"] for k, v in D["phi"].items()}; CG, C0 = D["c_grid"], D["c_primary"]
KMAX, MINLEN, TOL = D["k_max"], D["min_len"], 1
B_BOOT, B_NULL, B_SPLIT, B_CIRC = (20, 20, 10, 200) if QUICK else (spec["bootstrap"]["B"], spec["nulls"]["B"], spec["split_half"]["B"], spec["events"]["circ_B"])
ALPHA = spec["nulls"]["alpha"]
pen = lambda s, c, k=K: c * PHI[s] * (k - 1) * np.log(T)

def run_P(P, n, s, c=C0, k=K, keep=None):
    d = detect(P, n, pen(s, c, k), KMAX, MINLEN, keep)
    yrs = YEARS if keep is None else YEARS[keep]
    d["years"] = [int(yrs[b]) for b in d["br"]]; return d
def run(c_arr, s, c=C0, tmask=None, keep=None, post=None):
    P, n = sample_P(c_arr, fixed_v, wbar, s, tmask)
    if post: P = post(P, n)
    return run_P(P, n, s, c, K if tmask is None else int(tmask.sum()), keep)

# ---------- 1. 관측 탐지 ----------
obs, rows = {}, []
for s in SAM:
    for c in CG:
        d = run(cnt, s, c); rows.append(dict(sample=s, c=c, k=d["k"], breaks=d["years"], R=round(d["R"], 4), jump=round(d["jump"], 4),
                                           curve=json.dumps({k: round(v, 1) for k, v in d["curve"].items()})))
        if c == C0: obs[s] = d
OBS = pd.DataFrame(rows); print("\n[관측 변화점]\n", OBS.drop(columns="curve").to_string(index=False))
Y = pd.read_csv(S4 / "yearly_series_for_S5.csv"); uni = []
for s in SAM:
    for col in ["eff_topics", "hhi", "d3_share"]:
        v = Y[(Y["sample"] == ("fixed" if s == "fixed14" else s))].sort_values("year")[col].values; assert len(v) == T, (s, len(v)); br = [int(YEARS[b]) for b in uni_bic(v, KMAX, MINLEN)]
        uni.append(dict(sample=s, series=col, breaks=br, matches_multivariate=[near(y, obs[s]["years"]) for y in br]))
UNI = pd.DataFrame(uni); print("\n[단변량 교차 확인]\n", UNI.to_string(index=False))

# ---------- 2. 부트스트랩 ----------
BR = {s: [] for s in SAM}
for b in range(B_BOOT):
    cb = gen_boot(cnt, rng)
    for s in SAM: BR[s].append(run(cb, s)["years"])
brs = []
for s in SAM:
    for y in obs[s]["years"]:
        nr = [min([z for z in b if abs(z - y) <= 3], key=lambda z: abs(z - y)) for b in BR[s] if any(abs(z - y) <= 3 for z in b)]
        lo, hi = (np.percentile(nr, [5, 95]) if nr else (np.nan, np.nan))
        brs.append(dict(sample=s, break_year=y, hit_pm1=round(float(np.mean([near(y, b) for b in BR[s]])), 3), lo90=lo, hi90=hi,
                        k_dist=json.dumps(pd.Series([len(b) + 1 for b in BR[s]]).value_counts().sort_index().to_dict())))
BRS = pd.DataFrame(brs); print("\n[부트스트랩]\n", BRS.to_string(index=False))

# ---------- 3. 귀무 N0, N1, N2 ----------
P2 = trend_probs(cnt); GEN = {"N0": gen_N0, "N1": gen_N1, "N2": lambda c_, r_: gen_N2(c_, P2, r_)}; nr_ = []
for nm, g in GEN.items():
    for b in range(B_NULL):
        cc = g(cnt, rng)
        for s in SAM:
            d = run(cc, s); nr_.append(dict(null=nm, rep=b, sample=s, k=d["k"], R=d["R"], jump=d["jump"], years=d["years"]))
    print(f"{nm} 완료")
NL = pd.DataFrame(nr_); ps = []
for nm in GEN:
    for s in SAM:
        sub = NL[(NL["null"] == nm) & (NL["sample"] == s)]; r = dict(null=nm, sample=s, obs_k=obs[s]["k"], obs_R=round(obs[s]["R"], 4), obs_jump=round(obs[s]["jump"], 4))
        for st, ov in [("k", obs[s]["k"]), ("R", obs[s]["R"]), ("jump", obs[s]["jump"])]:
            r[f"null_med_{st}"] = round(float(sub[st].median()), 4); r[f"p_{st}"] = round((1 + float((sub[st] >= ov).sum())) / (1 + len(sub)), 4)
        ps.append(r)
PV = pd.DataFrame(ps); print("\n[귀무 대비]\n", PV.to_string(index=False))
PASS = {s: bool(PV[(PV["sample"] == s) & (PV["null"].isin(["N1", "N2"]))].p_R.max() < ALPHA) for s in SAM}
print("귀무 통과(N1·N2 모두 R p<%.2f):" % ALPHA, PASS)
n1hit = {(s, y): float(np.mean([near(y, r_) for r_ in NL[(NL["null"] == "N1") & (NL["sample"] == s)].years])) for s in SAM for y in obs[s]["years"]}

# ---------- 4. 주제 반분 재현 + 교차 적합 ----------
sh = []
for s in spec["split_half"]["samples"]:
    rep, rec, xf = [], {y: [] for y in obs[s]["years"]}, []
    for b in range(B_SPLIT):
        idx = rng.permutation(K); A = np.zeros(K, bool); A[idx[:K // 2]] = True
        dA, dB = run(cnt, s, tmask=A), run(cnt, s, tmask=~A); a, bb = dA["years"], dB["years"]
        if a or bb:
            fa = np.mean([near(y, bb) for y in a]) if a else 0.0; fb = np.mean([near(y, a) for y in bb]) if bb else 0.0; rep.append((fa + fb) / 2)
        for y in obs[s]["years"]: rec[y].append(near(y, a) and near(y, bb))
        PB, nB = sample_P(cnt, fixed_v, wbar, s, ~A); XB, wB = np.sqrt(PB), 4.0 * nB
        c1 = cost_given(XB, wB, []); xf.append(1 - cost_given(XB, wB, dA["br"]) / c1 if c1 > 0 else np.nan)
    sh.append(dict(sample=s, repro_mean=round(float(np.mean(rep)), 3) if rep else np.nan, n_reps_with_breaks=len(rep), pass_ge_0_50=bool(rep and np.mean(rep) >= spec["split_half"]["pass_min"]),
                   per_break_joint=json.dumps({y: round(float(np.mean(v)), 3) for y, v in rec.items()}), crossfit_R_B_median=round(float(np.nanmedian(xf)), 4)))
SH = pd.DataFrame(sh); print("\n[반분 재현]\n", SH.to_string(index=False))

# ---------- 5. 강건성: 추세 제거, 연도·셀 제외, A등급, IPW ----------
G = pd.read_csv(S3 / "L7_topic_grade.csv"); gm = dict(zip(G.topic.astype(int), G.grade)); tA = np.array([gm[t] == "A" for t in topics])
variants = []   # (이름, 표본, 탐지결과)
for s in SAM:
    variants.append(("detrended", s, run(cnt, s, post=detrend_P)))
    for yx in spec["robust"]["exclude_years"]:
        variants.append((f"drop_{yx}", s, run(cnt, s, keep=(YEARS != yx))))
    c2 = cnt.copy(); vi = {v: i for i, v in enumerate(venues)}
    for v, y in spec["robust"]["exclude_cells"]:
        if v in vi: c2[y - 2000, vi[v]] = 0
        else: print("※ 셀 제외 저널 없음:", v)
    variants.append(("drop_cells", s, run(c2, s)))
    variants.append(("A_grade_only", s, run(cnt, s, tmask=tA)))
ipw = S4 / "yearly_venue_topic_counts_ipw.npy"
if ipw.exists():
    ci = np.load(ipw)
    for s in SAM: variants.append(("ipw", s, run(ci, s)))
rb = []
for nm, s, d in variants:
    rb.append(dict(variant=nm, sample=s, k=d["k"], breaks=d["years"], obs_breaks=obs[s]["years"], obs_recovered=[near(y, d["years"]) for y in obs[s]["years"]],
                   new_breaks=[y for y in d["years"] if not near(y, obs[s]["years"])], R=round(d["R"], 4),
                   jump_ratio_vs_obs=round(d["jump"] / obs[s]["jump"], 3) if obs[s]["jump"] > 0 else np.nan))
RB = pd.DataFrame(rb); print("\n[강건성 재탐지]\n", RB.to_string(index=False))
ART = [2007, 2020, 2025]; art_flag = {(s, y): any(near(y, [a], 1) for a in ART) for s in SAM for y in obs[s]["years"]}

# ---------- 6. 사건 대조 (두 사건 집합: big=주, entry=보조) ----------
EVD = spec["events"]; ea = []
EV = pd.read_csv(S0 / EVD["file"], encoding="utf-8-sig")
n_pend = int(tf(EV[EVD["pending_col"]]).sum()); EV = EV[~tf(EV[EVD["pending_col"]])].copy()   # 미결(pending) 저널은 사건 집합에서 제외
def evset(nm):
    d = EVD["sets"][nm]
    if d.get("top_frac"):
        x = EV[tf(EV[d["elig_col"]])].copy(); x = x[x[d["size_col"]] >= x[d["size_col"]].quantile(1 - d["top_frac"])].copy()
    else: x = EV[tf(EV[d["flag_col"]])].copy()
    x["yr"] = pd.to_numeric(x[d["year_col"]], errors="coerce")
    return x[x.yr.between(2000, 2025)]
SETS = {nm: evset(nm) for nm in EVD["sets"]}
LO, HI = 2000 + MINLEN, 2000 + T - MINLEN          # 최소 구간 3년 때문에 변화점이 놓일 수 있는 연도 범위
print(f"\npending 제외 {n_pend}개 | 변화점이 놓일 수 있는 연도 {LO}~{HI}")
def evstat(brs_, ev_):
    a = np.mean([near(b, ev_) for b in brs_]) if brs_ else np.nan; b_ = np.mean([near(e, brs_) for e in ev_]) if len(ev_) else np.nan; return a, b_
ev_match = {}
for nm, X_ in SETS.items():
    ey = X_.yr.astype(int).values
    cover = float(np.mean([near(y, ey) for y in range(LO, HI + 1)])) if len(ey) else np.nan
    print(f"[{nm}] 창 안 사건 {len(ey)}개 | 변화점 가능 범위 밖 {int(((ey < LO) | (ey > HI)).sum())}개 | 우연 일치 기준 커버리지 {cover:.2f}(높을수록 검정력 낮음)")
    for s in SAM:
        brs_ = obs[s]["years"]; a, b_ = evstat(brs_, ey); sims = []
        for _ in range(B_CIRC):
            sh_ = int(rng.integers(1, T)); sims.append(evstat(brs_, 2000 + (ey - 2000 + sh_) % T))
        sims = np.array(sims, float); ok = bool(brs_) and len(ey) > 0
        pa = (1 + np.nansum(sims[:, 0] >= a)) / (1 + B_CIRC) if ok else np.nan; pb = (1 + np.nansum(sims[:, 1] >= b_)) / (1 + B_CIRC) if ok else np.nan
        ea.append(dict(set=nm, sample=s, test="breaks_near_event(i)", n_events=len(ey), coverage=cover, obs=a, null_mean=np.nanmean(sims[:, 0]) if ok else np.nan, p=pa))
        ea.append(dict(set=nm, sample=s, test="events_followed_by_break(ii)", n_events=len(ey), coverage=cover, obs=b_, null_mean=np.nanmean(sims[:, 1]) if ok else np.nan, p=pb))
        for y in brs_: ev_match[(nm, s, y)] = near(y, ey)
EA = pd.DataFrame(ea); print("\n[사건 대조: 순환이동 귀무]\n", EA.round(4).to_string(index=False))

# 내용 일치: 변화점 분해(저널 간 성분)와 사건 저널 초기 3년 벡터의 코사인
bs, cs = {}, []
e_all = [0] + obs["all"]["br"] + [T]; vi = {v: i for i, v in enumerate(venues)}
for j, y in enumerate(obs["all"]["years"]):
    w_, b_, t_ = decomp_break(cnt, e_all[j], e_all[j + 1], e_all[j + 2])
    bs[y] = float(np.abs(b_).sum() / (np.abs(w_).sum() + np.abs(b_).sum()))
    left = cnt[e_all[j]:e_all[j + 1]].sum((0, 1)).astype(float); left /= left.sum(); right = cnt[e_all[j + 1]:e_all[j + 2]].sum((0, 1)).astype(float); right /= right.sum(); ch = right - left
    for nm, X_ in SETS.items():
        for _, r in X_.iterrows():
            v = r[EVD["venue_col"]]; e = int(r.yr)
            if v not in vi or abs(e - y) > TOL or e + 3 > 2026: continue
            def cosv(u):
                x = cnt[e - 2000:e - 2000 + 3, u].sum(0).astype(float)
                return np.nan if x.sum() < 30 else float(((x / x.sum() - left) @ ch) / (np.linalg.norm(x / x.sum() - left) * np.linalg.norm(ch) + 1e-12))
            o = cosv(vi[v]); nl = np.array([cosv(u) for u in range(len(venues)) if u != vi[v]], float); nl = nl[~np.isnan(nl)]
            cs.append(dict(set=nm, break_year=y, venue=v, event_year=e, cosine=round(o, 3), null_pct=round(float((nl < o).mean()), 3) if len(nl) and not np.isnan(o) else np.nan, n_null=len(nl)))
CS = pd.DataFrame(cs); print("\n[저널 간 성분 비중(all 변화점)]", {k: round(v, 2) for k, v in bs.items()}); print("[사건 저널 코사인]\n", CS.to_string(index=False) if len(CS) else "(해당 없음)")

# ---------- 7. 유형 분류 ----------
types = []
for y in obs["all"]["years"]:
    in_w, in_f = near(y, obs["within"]["years"]), near(y, obs["fixed14"]["years"]); evm = ev_match[("big", "all", y)]; evm_e = ev_match[("entry", "all", y)]
    if not (PASS["all"]): t = "탐지 없음(귀무 미통과): 연속 변화로 서술"
    elif in_w: t = "내재(사건일치)" if evm else "미설명 전환"
    elif bs[y] >= 0.5: t = "구성"
    else: t = "혼합·미분류"
    types.append(dict(break_year=y, in_fixed14=in_f, in_within=in_w, event_match=evm, entry_match=evm_e, between_share=round(bs[y], 3), n1_hit_rate=round(n1hit[("all", y)], 3),
                      artifact_candidate=art_flag[("all", y)], boot_hit=float(BRS[(BRS["sample"] == "all") & (BRS.break_year == y)].hit_pm1.iloc[0]), type=t))
for y in obs["within"]["years"]:
    if not near(y, obs["all"]["years"]):
        types.append(dict(break_year=y, in_fixed14=near(y, obs["fixed14"]["years"]), in_within=True, event_match=ev_match[("big", "within", y)], entry_match=ev_match[("entry", "within", y)], between_share=np.nan,
                          n1_hit_rate=round(n1hit[("within", y)], 3), artifact_candidate=art_flag[("within", y)], boot_hit=np.nan, type="내재(within에서만 탐지)" if PASS["within"] else "탐지 없음(귀무 미통과)"))
TY = pd.DataFrame(types); print("\n[유형 분류]\n", TY.to_string(index=False))

# ---------- 8. 저장 ----------
S5.mkdir(parents=True, exist_ok=True); sv = lambda d, f: d.to_csv(S5 / f, index=False, encoding="utf-8-sig")
tag_ = "_QUICK" if QUICK else ""
sv(OBS.merge(BRS.groupby("sample").size().rename("n_boot_rows").reset_index(), on="sample", how="left"), f"regime_breaks{tag_}.csv"); sv(BRS, f"regime_break_bootstrap{tag_}.csv"); sv(UNI.astype(str), f"regime_univariate{tag_}.csv")
sv(PV, f"regime_nulls{tag_}.csv"); sv(NL.astype({"years": str}), f"regime_nulls_reps{tag_}.csv"); sv(SH, f"split_half{tag_}.csv"); sv(RB.astype(str), f"artifact_exclusion_redetect{tag_}.csv")
sv(pd.concat([EA, CS], ignore_index=True), f"event_alignment{tag_}.csv"); sv(TY, f"regime_types{tag_}.csv")
meta = dict(spec_sha256=spec["sha256"], at=now(), quick=QUICK, B=dict(boot=B_BOOT, null=B_NULL, split=B_SPLIT, circ=B_CIRC), null_pass=PASS, obs_breaks={s: obs[s]["years"] for s in SAM})
(S5 / f"S5_meta{tag_}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
if not QUICK:
    with (S5 / "CHANGELOG_S5.md").open("a", encoding="utf-8") as f:
        f.write(f"- {now()} | S5 본 계산 실행(규칙 해시 {spec['sha256'][:12]}): 관측 변화점 { {s: obs[s]['years'] for s in SAM} }, 귀무 통과 {PASS}. 임계값·규칙 변경 없음 | S5 | 체제 식별\n")
print("\n저장 완료(", "QUICK 파일은 _QUICK 접미사" if QUICK else "본 실행", ")")