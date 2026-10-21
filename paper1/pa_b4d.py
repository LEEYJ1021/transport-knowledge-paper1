# -*- coding: utf-8 -*-
# PA-B4d: L3_topic_metrics.csv의 jaccard_p10 하위 10% 토픽을 제외하고 S5·S6 재추정(B4와 같은 틀). 미실행.
# python3 pa_b4d.py freeze | tag | run [quick]
from pa_common import *
from pa_extra import *
PLAN = dict(
    version=1, seed=2026, parent="PA_0_PLAN_v2.json",
    status="사후 명세(지침서 B4-2의 Jaccard p10 부분). B4·B4b 결과(F1·F3 제외 4개뿐), S3 L3_topic_metrics.csv에 jaccard_p10 열 존재 확인 열람. 결과 미열람. S0~S8 판정 불변.",
    exclusion="L3_topic_metrics.csv의 jaccard_p10이 가장 낮은 ceil(0.10*토픽 수)개 토픽 제외(동률은 topic 번호 순). 제외 집합과 F1·F3 실패 4개, S3 등급의 겹침을 보고",
    reestimate="B4와 같은 절차. S5: 잔존 토픽만으로 s5_lib.detect(pen=c*phi*(K-1)*log T, K=잔존 수, phi는 S5 값 고정), N1·N2 귀무 B=500, 통과 규칙 N1·N2 모두 p<0.05. S6: R을 잔존 토픽 행으로 제한한 주 설정, 대응 저자 부트스트랩 B=spec['B_boot'], entry_minus_adapt 변화",
    reading="S5: 표본별 (a) 통과 여부가 S5와 같은지 (b) S5 관측 변화점이 +-1년 유지되는지. S6: 쌍별 |변화|<=0.03이고 부호 유지면 '둔감'(첫 쌍은 원값이 0 근처라 부호가 바뀌기 쉬움). 합치지 않음",
    reproduce_check="S5 관측 R이 regime_nulls.csv obs_R과 1e-3 이내, S6 total_half·A2c entry_share 재현, 부분 자료 저자 집합이 원본의 부분집합, 제외 토픽 수 15",
    caveat="jaccard_p10은 부트스트랩 군집 안정성이라 작은 토픽이 불리할 수 있음. 하위 10%는 임의 기준(동결). 등급 타당성은 검증하지 않음",
    forbidden="결과를 본 뒤 비율(10%)·판독 변경(변경 시 v2 계획으로 분리)")

def reestimate(ptop, quick, rng):
    import s5_lib as L5, s6_lib as S
    s5 = json.loads((S5D/"S5_0_PREREG.json").read_text(encoding="utf-8")); D = s5["detection"]; PHI = {k: v["phi"] for k, v in D["phi"].items()}
    C0, KMAX, MINLEN, ALPHA = D["c_primary"], D["k_max"], D["min_len"], s5["nulls"]["alpha"]; Bn = 20 if quick else 500
    cnt, venues, topics, fixed_v = L5.load_counts(); wbar = cnt.sum((0, 2))/cnt.sum(); T = len(L5.YEARS); YEARS = np.asarray(L5.YEARS); SAM = s5["samples"]
    tmask = np.isin(topics, list(ptop)); Ku = int(tmask.sum())
    det = lambda c, s, Kuse: (lambda Pn: L5.detect(Pn[0], Pn[1], C0*PHI[s]*(Kuse - 1)*np.log(T), KMAX, MINLEN))(L5.sample_P(c, fixed_v, wbar, s))
    ref = pd.read_csv(S5D/"regime_nulls.csv"); ref = ref[ref["null"] == "N2"].set_index("sample")
    for s in SAM:
        if abs(det(cnt, s, len(topics))["R"] - float(ref.loc[s, "obs_R"])) > 1e-3: raise Halt(f"S5 관측 R 재현 실패({s})")
    cs = cnt[:, :, tmask]; obs = {s: det(cs, s, Ku) for s in SAM}; P2 = L5.trend_probs(cs); NR = {"N1": {s: [] for s in SAM}, "N2": {s: [] for s in SAM}}
    for b in range(Bn):
        for nm, cc in (("N1", L5.gen_N1(cs, rng)), ("N2", L5.gen_N2(cs, P2, rng))):
            for s in SAM: NR[nm][s].append(det(cc, s, Ku)["R"])
    meta = json.loads((S5D/"S5_meta.json").read_text(encoding="utf-8")); rows5 = []
    for s in SAM:
        yrs = [int(YEARS[x]) for x in obs[s]["br"]]; pv = {nm: (1 + float((np.array(NR[nm][s]) >= obs[s]["R"]).sum()))/(1 + Bn) for nm in NR}
        kept = [L5.near(y, yrs, 1) for y in meta["obs_breaks"][s]]
        rows5.append(dict(sample=s, K=Ku, obs_R=obs[s]["R"], breaks=str(yrs), s5_breaks=str(meta["obs_breaks"][s]), p_N1=pv["N1"], p_N2=pv["N2"],
                          passed_new=max(pv.values()) < ALPHA, passed_s5=bool(meta["null_pass"][s]), all_breaks_kept=all(kept), B=Bn))
    spec = S.load_spec(); L = S.load_all(spec); M = spec["main"]; PAIRS = S.pairs_of(spec); half = S.half; R = L["R"]
    ok_ti = np.where(np.isin(L["topics"], list(ptop)))[0]; L2 = dict(L); L2["R"] = R[R.ti.isin(ok_ti)]
    ref6 = pd.read_csv(S6D/"renewal_decomposition.csv"); ref6 = ref6[(ref6.scheme == M["scheme"]) & (ref6.variant == "all_venues")].set_index("pair")
    a2c = pd.read_csv(PA/"PA_A2c_results.csv"); a2c = a2c[(a2c["mode"] == "author") & (a2c.stat == "entry_share")].set_index("pair")
    B6 = 20 if quick else int(spec["B_boot"]); lo_q, hi_q = spec["ci"]; STATS = ["entry_share", "adapt_share", "entry_minus_adapt"]
    def stats(d):
        h = {t: half(d[t]) for t in ["adapt", "realloc", "entry", "exit"]}; tot = sum(h.values())
        return dict(entry_share=h["entry"]/tot, adapt_share=h["adapt"]/tot, entry_minus_adapt=(h["entry"] - h["adapt"])/tot)
    rows6 = []
    for p0, p1 in PAIRS:
        name = f"{p0}->{p1}"; Pa = S.make_pair(L, p0, p1, M["scheme"], M["venue"], M["topic"], M["hom"]); Pb = S.make_pair(L2, p0, p1, M["scheme"], M["venue"], M["topic"], M["hom"])
        da, db = Pa.decompose(), Pb.decompose(); oa, ob = stats(da), stats(db)
        if abs(half(da["total"]) - float(ref6.loc[name, "total_half"])) > 1e-6 or abs(oa["entry_share"] - float(a2c.loc[name, "obs"])) > 1e-6: raise Halt(f"S6/A2c 재현 실패({name})")
        idx = np.searchsorted(Pa.aids, Pb.aids)
        if not (idx < len(Pa.aids)).all() or not (Pa.aids[idx] == Pb.aids).all(): raise Halt(f"부분 자료 저자 집합이 원본의 부분집합이 아님({name})")
        bs = []
        for _ in range(B6):
            wa = rng.exponential(size=Pa.nA); sa = stats(Pa.decompose(Pa.m0*wa[Pa.a0], Pa.m1*wa[Pa.a1])); wb = wa[idx]
            sb = stats(Pb.decompose(Pb.m0*wb[Pb.a0], Pb.m1*wb[Pb.a1])); bs.append({s: sb[s] - sa[s] for s in STATS})
        bs = pd.DataFrame(bs)
        for s in STATS:
            dl = ob[s] - oa[s]; ql, qh = np.percentile(bs[s], [lo_q, hi_q]); rows6.append(dict(pair=name, stat=s, obs_orig=oa[s], obs_sub=ob[s], delta=dl, pct_lo=ql, pct_hi=qh, B=B6))
    return pd.DataFrame(rows5), pd.DataFrame(rows6)

def run(quick, sp):
    sys.path.insert(0, str(P1)); rng = np.random.default_rng(int(PLAN["seed"]))
    M3 = pd.read_csv(S3/"L3_topic_metrics.csv", encoding="utf-8-sig")
    if not {"topic", "jaccard_p10"} <= set(M3.columns): raise Halt(f"L3_topic_metrics.csv 열 확인 필요: {list(M3.columns)}")
    M3 = M3.dropna(subset=["jaccard_p10"]).sort_values(["jaccard_p10", "topic"]); k = int(np.ceil(0.10*len(M3))); ex = set(M3.topic.head(k).astype(int))
    if k != 15: raise Halt(f"제외 토픽 수 {k} (15여야 함)")
    G = pd.read_csv(S3/"L7_topic_grade.csv", encoding="utf-8-sig").set_index("topic"); f13 = set(G.index[bl(G.F1) | bl(G.F3)].astype(int)); allt = set(G.index.astype(int))
    print(f"[재현 설계] 제외 {k}개 | F1·F3 실패와 겹침 {len(ex & f13)} | 등급 분포 {G.loc[sorted(ex), 'grade'].value_counts().to_dict()}")
    R5, R6 = reestimate(allt - ex, quick, rng)
    if quick: print("[QUICK] 오류 점검만. 수치 출력 안 함."); return
    pd.DataFrame(dict(topic=sorted(ex), jaccard_p10=M3.set_index("topic").loc[sorted(ex), "jaccard_p10"].values, grade=G.loc[sorted(ex), "grade"].values, f1f3_fail=[t in f13 for t in sorted(ex)])).to_csv(PA/"PA_B4d_excluded.csv", index=False, encoding="utf-8-sig")
    R5.to_csv(PA/"PA_B4d_s5.csv", index=False, encoding="utf-8-sig"); R6.to_csv(PA/"PA_B4d_s6.csv", index=False, encoding="utf-8-sig")
    kk = R6[R6.stat == "entry_minus_adapt"].copy(); kk["insensitive"] = (np.sign(kk.obs_sub) == np.sign(kk.obs_orig)) & (kk.delta.abs() <= 0.03)
    print("\n[Post-hoc] PA-B4d S5\n", R5.round(4).to_string(index=False)); print("\n[Post-hoc] PA-B4d S6 entry_minus_adapt\n", kk.round(4).to_string(index=False))
    print("[동결 판독] S5:", R5.assign(same=R5.passed_new == R5.passed_s5)[["sample", "same", "all_breaks_kept"]].to_dict("records"))
    print("※ 제외 집합 15개의 부분집합 재추정. S0~S8 판정 불변.")

run_pa("B4d", PLAN, run, [S3/"L3_topic_metrics.csv", S3/"L7_topic_grade.csv", S5D/"S5_0_PREREG.json", PA/"PA_B4_PLAN.json", P1/"pa_extra.py"], "jaccard_p10 하위 10% 제외 재추정(지침서 B4-2)")