# -*- coding: utf-8 -*-
# PA-B9b: S8 국가 수준 편 순위상관(통과 도메인)의 공급 정의·질량 하한 민감도. 미실행. 소득군별 n을 먼저 보고.
from pa_common import *
G4 = ["HIC", "UMC", "LMC", "LIC"]; SCH = ["inv_n_authors", "full_count", "equal"]; VAR = ["main", "rec"]; FLOORS = [5, 10, 20]
PLAN = dict(
    version=1, seed=2026, parent="PA_0_PLAN_v2.json",
    status="사후 명세(지침서 B9-3). B9a 결과, B9b 설계 점검(LIC는 하한 5에서도 1개국이라 자료상 불가, LMC n 12~13, UMC n 20~22), country_mass_long의 스킴 구조 열람 상태. 결과 미열람. 이전에 생략 권고했으나 연구자 요청으로 수행. S0~S8 판정 불변.",
    grid=dict(scheme=SCH, variant=VAR, floor=FLOORS, strata=["ALL"] + G4, control="rank(gdp_pc) 통제 편 순위상관(B9a의 gdp와 동일)"),
    definitions="공급 강도 s = 해당 스킴·변형의 (도메인 논문 질량/국가 총 질량). 국가 포함 기준 = 같은 변형의 inv_n_authors 총질량 >= floor. 도메인·지표쌍은 S8_0_PREREG_v2.json의 domain_indicators 중 통과 도메인(domains_passed.json). 부담 지표·gdp_pc·소득군은 burden_country_table(wb_income_current 고정). full_count는 논문당 w 합이 국가 수라 총질량 분모도 같은 스킴",
    n_min=20, B=1000, ci=[2.5, 97.5], boot="국가 복원추출, 재표집마다 순위·잔차 재계산, 단일 rng(seed 고정) 순차",
    reading="소득군별 n 표를 먼저 보고. 행(스킴x변형x하한x쌍x층)별로 n<20이면 NA, 아니면 부호가 기준행((ALL, inv_n_authors, main, floor 10)의 같은 쌍)과 같고 구간이 0을 배제하면 '관찰', 아니면 '비관찰'. 행을 합치지 않음. 기준 구간이 0을 배제하는 쌍은 B9a에서 safety-road_deaths 하나뿐이므로 나머지 쌍의 관찰 여부는 해석하지 않음",
    reproduce_check="기준행((ALL, inv_n_authors, main, floor 10))의 n과 편 rho가 country_partial_spearman.csv(excl=none)와 1e-6 이내. 불일치 시 중단",
    caveat="LIC는 하한과 무관하게 n<20(자료상 불가), LMC도 대부분 n<20이므로 소득군 내 추정이 가능한 칸은 HIC와 하한 5의 UMC 정도. 하한 5는 질량이 작은 국가(공급 강도 잡음 큼)를 포함. 변형 rec가 모든 스킴에 존재하지 않으면 해당 칸은 NA로 기록. 다중성 보정 없음, 탐색적. 국가 단위 상관은 생태학적 오류 가능, 인과·필요 충족 증거 아님",
    forbidden="결과를 본 뒤 격자·n_min·판독 변경(변경 시 v2 계획으로 분리하고 사유 기록)")

def run(quick, sp):
    SPEC = json.loads((S8/"S8_0_PREREG_v2.json").read_text(encoding="utf-8")); DOM_IND = SPEC["domain_indicators"]
    dp = json.loads((S8/"domains_passed.json").read_text(encoding="utf-8"))["passed"]
    Bt = burden(); fl = flags(SPEC)[["pid"] + dp]; Mr = mass_raw(); cache = {}
    def prep(sc, vr):
        if (sc, vr) not in cache:
            A = Mr[(Mr.scheme == sc) & (Mr.variant == vr)]
            cache[(sc, vr)] = None if A.empty else (A.groupby("country").w.sum(), A.merge(fl, on="pid", how="inner"))
        return cache[(sc, vr)]
    def build(sc, vr, floor):
        a, b = prep(sc, vr), prep("inv_n_authors", vr)
        if a is None or b is None: return None
        tot = a[0].reindex(b[0][b[0] >= floor].index).dropna(); tot = tot[tot > 0]; out = {}
        for d in dp:
            sup = a[1][a[1][d]].groupby("country").w.sum().reindex(tot.index).fillna(0)/tot
            for ind in DOM_IND[d]:
                out[(d, ind)] = pd.DataFrame({"s": sup, "b": Bt[INT[ind]].reindex(tot.index), "z": Bt["gdp_pc"].reindex(tot.index), "inc": Bt["income"].reindex(tot.index)}).dropna(subset=["s", "b", "z"])
        return out
    ref = pd.read_csv(S8/"country_partial_spearman.csv", encoding="utf-8-sig"); ref = ref[ref.excl == "none"].set_index(["domain", "indicator"])
    base = build("inv_n_authors", "main", 10); base_rho = {}
    for k, df in base.items():
        r = pr(df.s.values, df.b.values, [df.z.values], [True]); r0 = ref.loc[k]; base_rho[k] = r
        if len(df) != int(r0.n) or abs(r - float(r0.partial_rho)) > 1e-6: raise Halt(f"기준행 재현 실패{k}: n {len(df)} vs {int(r0.n)}, rho {r:.6f} vs {r0.partial_rho:.6f}")
    print(f"[재현 OK] 기준행 {len(base)}쌍이 country_partial_spearman.csv(none)와 일치")
    B = 0 if quick else int(PLAN["B"]); rng = np.random.default_rng(int(PLAN["seed"])); rows = []
    for sc in SCH:
        for vr in VAR:
            for fl_ in FLOORS:
                bd = build(sc, vr, fl_)
                for k in base:
                    for st in ["ALL"] + G4:
                        row = dict(scheme=sc, variant=vr, floor=fl_, domain=k[0], indicator=k[1], stratum=st, B=B)
                        if bd is None: rows.append(dict(row, n=0, rho=np.nan, lo=np.nan, hi=np.nan, note="스킴·변형 없음")); continue
                        df = bd[k]; sub = df if st == "ALL" else df[df.inc == st]; n = len(sub)
                        if n < PLAN["n_min"] or quick: rows.append(dict(row, n=n, rho=np.nan, lo=np.nan, hi=np.nan, note="")); continue
                        x, y, z = sub.s.values, sub.b.values, sub.z.values; r = pr(x, y, [z], [True]); bs = []
                        for _ in range(B):
                            i = rng.integers(0, n, n); bs.append(pr(x[i], y[i], [z[i]], [True]))
                        rows.append(dict(row, n=n, rho=r, lo=float(np.nanpercentile(bs, 2.5)), hi=float(np.nanpercentile(bs, 97.5)), note=""))
    R = pd.DataFrame(rows); sfx = "_QUICK" if quick else ""; NT = R.pivot_table(index=["scheme", "variant", "floor", "domain", "indicator"], columns="stratum", values="n", aggfunc="first")[["ALL"] + G4]
    NT.to_csv(PA/f"PA_B9b_n_table{sfx}.csv", encoding="utf-8-sig"); print("\n[층별 n(설계 정보)]\n", NT.astype(int).to_string())
    if quick: print("\n[QUICK] 재현 점검과 n 표만. rho는 계산하지 않음."); return
    R["base_sign"] = [np.sign(base_rho[(a, b)]) for a, b in zip(R.domain, R.indicator)]; R["verdict"] = np.where(R.rho.isna(), "NA", np.where((np.sign(R.rho) == R.base_sign) & ((R.lo > 0) | (R.hi < 0)), "관찰", "비관찰"))
    R.to_csv(PA/"PA_B9b_results.csv", index=False, encoding="utf-8-sig")
    for st in ["ALL", "HIC", "UMC"]:
        print(f"\n[Post-hoc] PA-B9b {st} (rho / 구간 / verdict)\n", R[(R.stratum == st) & R.rho.notna()].round(3)[["scheme", "variant", "floor", "domain", "indicator", "n", "rho", "lo", "hi", "verdict"]].to_string(index=False))
    print("\n[동결 판독] verdict 집계\n", R.groupby(["stratum", "verdict"]).size().unstack(fill_value=0).to_string())
    print("※ LIC·LMC는 대부분 NA(자료상 불가). 기준 구간이 0을 배제하는 쌍(safety-road_deaths)만 해석. 48행 이상 탐색적. S0~S8 판정 불변.")

run_pa("B9b", PLAN, run, [S8/"S8_0_PREREG_v2.json", S8/"domains_passed.json", S8/"country_partial_spearman.csv", S8/"burden_country_table.csv", PA/"PA_B9a_PLAN.json"], "공급 정의(스킴)·변형·질량 하한 민감도(지침서 B9-3)")