# -*- coding: utf-8 -*-
# PA-B3c(=지침서 B3-3): 신생 핵심 집합의 S6 분해 항별 기여. 미실행 코드. python3 pa_b3c.py freeze | tag | run [quick]
from pa_common import *
PLAN = dict(
    version=1, seed=2026, parent="PA_0_PLAN_v2.json",
    status="사후 명세(지침서 B3-3). B3a 결과(핵심 7·중간 10·특이적 14), S6 Pair 소스, PA-A2c(4항 분해, 진입=신규+복귀) 열람 상태. 결과 미열람. 이전에 생략 권고(미수행 목록 후보)했으나 연구자 요청으로 수행. S0~S8 판정 불변.",
    sets="definition_sensitivity.csv의 n_defs: core>=3, mid==2, specific==1, union31=전체 31개. 참조 집합 all_growth=쌍별 총변화>0인 전 토픽",
    setting="spec['main']과 s6_lib.make_pair 그대로, 쌍은 pairs_of(spec) 전부. 토픽 축은 Pair의 K(L['topics']). 집합 토픽이 L['topics']에 없으면 제외하고 수를 보고",
    stats="집합 안에서 쌍별 총변화>0인 토픽만. 합산 몫: entry_frac=sum(entry)/sum(total), entry_new_frac, adapt_frac, realloc_frac(진입=신규+복귀). 토픽별 entry/total의 중앙값, entry>adapt인 토픽 비율. 차이: core-all_growth, core-specific의 entry_frac",
    boot="저자 가중 wa~Exp(1)만(PA-A2c 저자 모드), B=spec['B_boot'], 역할 고정, 관측·백분위·basic 구간",
    reading="쌍별로 core의 entry_frac와 adapt_frac의 대소, core-all_growth entry_frac 차이의 부호와 구간이 0을 포함하는지를 기술. 임계값·판정 없음, 쌍을 합치지 않음. 마지막 쌍(P1519->P2025)을 주 대상으로 표기",
    reproduce_check="(a) 쌍별 total_half가 renewal_decomposition.csv(scheme=main, variant=all_venues)와 1e-6 이내, (b) 항 합=총변화(Pair 내부 assert), (c) definition_sensitivity 31행",
    caveat="D2~D4가 변화량 상위 14 기준이라 핵심 집합은 총변화가 큰 토픽에 치우침(구조적). 합산 몫은 큰 토픽이 지배. 토픽 단위 인과 아님. 신생 후보가 성장 토픽뿐이라 total>0 조건이 대부분 충족될 것(미확인)",
    forbidden="결과를 본 뒤 집합·통계·판독 변경(변경 시 v2 계획으로 분리하고 사유 기록)")

def run(quick, sp):
    sys.path.insert(0, str(P1)); import s6_lib as S
    spec = S.load_spec(); L = S.load_all(spec); M = spec["main"]; PAIRS = S.pairs_of(spec); half = S.half
    DS = pd.read_csv(S4/"definition_sensitivity.csv", encoding="utf-8-sig")
    if len(DS) != 31: raise Halt(f"definition_sensitivity 행 수 {len(DS)} (31이어야 함)")
    sets = {"core": set(DS.topic[DS.n_defs >= 3].astype(int)), "mid": set(DS.topic[DS.n_defs == 2].astype(int)), "specific": set(DS.topic[DS.n_defs == 1].astype(int)), "union31": set(DS.topic.astype(int))}
    pos = {int(t): i for i, t in enumerate(L["topics"])}; K = len(L["topics"]); G = {nm: [pos[t] for t in ids if t in pos] for nm, ids in sets.items()}; G["all_growth"] = list(range(K))
    ref = pd.read_csv(S6D/"renewal_decomposition.csv"); ref = ref[(ref.scheme == M["scheme"]) & (ref.variant == "all_venues")].set_index("pair")
    B = 20 if quick else int(spec["B_boot"]); lo_q, hi_q = spec["ci"]; rng = np.random.default_rng(int(PLAN["seed"]))
    print("[설계 정보] 집합 크기(정의/S6 토픽 축에 존재):", {nm: (len(sets[nm]), len(G[nm])) for nm in sets})
    def stats(d):
        tot = d["total"]; out = {}
        for nm, ix in G.items():
            ix = np.array([i for i in ix if tot[i] > 0], int)
            if not len(ix): out[nm] = None; continue
            T_ = tot[ix].sum(); out[nm] = dict(n=len(ix), entry_frac=d["entry"][ix].sum()/T_, entry_new_frac=d["entry_new"][ix].sum()/T_, adapt_frac=d["adapt"][ix].sum()/T_, realloc_frac=d["realloc"][ix].sum()/T_,
                                               med_entry_frac=float(np.median(d["entry"][ix]/tot[ix])), share_entry_gt_adapt=float((d["entry"][ix] > d["adapt"][ix]).mean()))
        return out
    def flat(st):
        r = {}
        for nm, v in st.items():
            for k, x in (v or {}).items(): r[(nm, k)] = x
        g = lambda a, b: (st[a]["entry_frac"] - st[b]["entry_frac"]) if st.get(a) and st.get(b) else np.nan
        r[("core_minus_all_growth", "entry_frac")] = g("core", "all_growth"); r[("core_minus_specific", "entry_frac")] = g("core", "specific"); return r
    rows = []
    for p0, p1 in PAIRS:
        name = f"{p0}->{p1}"; P = S.make_pair(L, p0, p1, M["scheme"], M["venue"], M["topic"], M["hom"]); d0 = P.decompose()
        if abs(half(d0["total"]) - float(ref.loc[name, "total_half"])) > 1e-6: raise Halt(f"S6 관측 재현 실패({name})")
        obs = flat(stats(d0)); bs = []
        for _ in range(B):
            wa = rng.exponential(size=P.nA); bs.append(flat(stats(P.decompose(P.m0*wa[P.a0], P.m1*wa[P.a1]))))
        for k, o in obs.items():
            if k[1] == "n": rows.append(dict(pair=name, set=k[0], stat="n_topics", obs=o)); continue
            v = np.array([b.get(k, np.nan) for b in bs], float); ql, qh = np.nanpercentile(v, [lo_q, hi_q]) if np.isfinite(v).any() else (np.nan, np.nan)
            rows.append(dict(pair=name, set=k[0], stat=k[1], obs=o, pct_lo=ql, pct_hi=qh, basic_lo=2*o - qh, basic_hi=2*o - ql, B=B))
        print(f"  {name} 완료")
    R = pd.DataFrame(rows)
    if quick: print("\n[QUICK] 재현 점검과 설계 정보만. 결과 통계는 출력하지 않음(_QUICK 파일 열람 금지)."); R.to_csv(PA/"PA_B3c_results_QUICK.csv", index=False, encoding="utf-8-sig"); return
    R.to_csv(PA/"PA_B3c_results.csv", index=False, encoding="utf-8-sig")
    print("\n[Post-hoc] PA-B3c 집합별 합산 몫(쌍별)\n", R[R.stat.isin(["n_topics", "entry_frac", "adapt_frac", "realloc_frac", "entry_new_frac"])].pivot_table(index=["pair", "set"], columns="stat", values="obs").round(4).to_string())
    print("\n[Post-hoc] 차이와 구간\n", R[R.set.str.startswith("core_minus")].round(4).to_string(index=False))
    print("\n[Post-hoc] 토픽별 지표\n", R[R.stat.isin(["med_entry_frac", "share_entry_gt_adapt"])].round(4).to_string(index=False))
    print("※ 쌍별로 따로 읽고 합치지 않음. 핵심 집합은 변화량 상위 정의의 부산물일 수 있음. S0~S8 판정 불변.")

run_pa("B3c", PLAN, run, [S4/"definition_sensitivity.csv", P1/"s6_lib.py", S6D/"renewal_decomposition.csv", PA/"PA_B3a_PLAN.json"], "지침서 B3-3: 신생 핵심 집합의 신규 진입 연계(S6 항별 기여)")