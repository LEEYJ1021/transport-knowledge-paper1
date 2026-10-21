# -*- coding: utf-8 -*-
# PA-B8a: precision 미달 4개 도메인에 S8 정렬(v2 규칙 그대로)을 부록용으로 적용. 사전·지표·임계값 변경 없음. 미실행 코드.
# 사용: python3 pa_b8a.py freeze | tag | run quick | run   (tag 뒤에 git push --follow-tags)
# S0~S8 판정 불변. 모든 산출물 [Post-hoc]. 출력은 09_PA/PA_B8a_*.csv만(S8 폴더 파일은 수정하지 않음).
import sys, json, re, hashlib, subprocess, warnings
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import rankdata
warnings.filterwarnings("ignore"); pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 200)
MODE = sys.argv[1] if len(sys.argv) > 1 else "freeze"; QUICK = "quick" in sys.argv[2:]

ROOT = Path.home()/"Research/Minnesota_Transport"; P1 = ROOT/"paper1"; PA = P1/"09_PA"
DATA, S0, S1, S2, S8 = ROOT/"analysis_data/final", P1/"00_S0", P1/"01_S1", P1/"02_S2", P1/"08_S8"
now = lambda: pd.Timestamp.now().isoformat(timespec="seconds")
sha_b = lambda b: hashlib.sha256(b).hexdigest(); sha_f = lambda p: sha_b(Path(p).read_bytes())
git = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
class Halt(Exception): pass
spec_hash = lambda s: sha_b(json.dumps({k: v for k, v in s.items() if k not in ("sha256", "created", "refs")}, sort_keys=True, ensure_ascii=False).encode())
V2P, BP = PA/"PA_0_PLAN_v2.json", PA/"PA_B8a_PLAN.json"
INT = dict(road_deaths="death_rate", vehicles="veh_per1000", urban_pop="urban_share", transport_co2="co2_tr_pc")   # S8 코드(INT)와 동일

PLAN = dict(
    version=1, parent="PA_0_PLAN_v2.json",
    status="사후 명세(PA-B8 중 B8-1만: 기존 사전으로 미달 4개 도메인에 정렬을 적용). S8 결과(통과 safety·transit의 정렬·지표 일관·편 순위상관), domain_precision_recall.csv(미달 4개 precision 0.76~0.84), align() 소스 열람한 상태. 미달 4개 도메인의 정렬 결과는 미계산·미열람. 사전 v3 재작성과 새 25편 이중 코딩(B8-2)은 별도(인력 필요). S0~S8 판정 불변.",
    scope="domains_passed.json의 failed 4개(electrification_env, freight, active_urban, infrastructure). S8_0_PREREG_v2.json(해시 9f59a75d7c63)의 domains, domain_indicators, periods, supply, sensitivity, direction, country_level, seed를 그대로 사용. S8 align()의 계산(렌즈 2종, 제외 민감도 3종, 지표 일관, 편 순위상관)을 복제하되 도메인 목록만 바꿈",
    outputs="09_PA/PA_B8a_alignment_gap_map.csv, PA_B8a_indicator_consistency.csv, PA_B8a_sensitivity_exclusion.csv, PA_B8a_country_partial_spearman.csv, PA_B8a_precision_note.csv. S8 폴더의 파일, S8_meta.json, CHANGELOG_S8.md는 수정하지 않음",
    reproduce_check="같은 복제 코드로 safety·transit을 계산해 S8 산출물(alignment_gap_map, indicator_consistency, country_partial_spearman)과 비교. 간극 지도·지표 일관·편 순위상관 점추정이 1e-9 이내로 일치하지 않으면 중단. 부트스트랩 구간(lo, hi)은 본 실행에서 비교하되 불일치 시 경고만(난수 순서 차이 가능)",
    reading="미달 4개 도메인은 사전 precision이 0.85 미만이라 본문 정렬 분석에서 제외한 도메인. 통과/실패 판정을 하지 않음. 보고: (1) 역량 렌즈 지표 일관 비율(도메인별, 참고로 0.75와 비교), (2) 마지막 기간 역량 렌즈에서 지표별 'HIC SBR>1 이면서 LIC·LMC SBR<1' 여부, (3) 편 순위상관(제외 없음)의 부호와 구간이 0을 배제하는지, (4) 제외 민감도 같은 쪽 비율. 통과 도메인(safety·transit)과 같은 방향인지 기술만 하고 본문 판정을 바꾸지 않음",
    caveat="미달 도메인은 사전 precision 0.76~0.84(n=25, Wilson 하한 0.57~0.65)라 공급 질량에 오분류가 섞여 있을 수 있음. 통과 도메인과 같은 선상의 증거가 아님. 모든 표에 precision을 병기. 국가 단위 상관은 생태학적 오류 가능, 인과 아님. 부트스트랩은 국가 단위",
    forbidden="결과를 본 뒤 사전·지표 대응·임계값·판독 문구 변경, 미달 도메인을 본문 통과 도메인으로 승격(변경 시 v2 계획으로 분리하고 사유 기록)")

def load_spec():
    SPEC = json.loads((S8/"S8_0_PREREG_v2.json").read_text(encoding="utf-8"))
    if str(SPEC.get("sha256", ""))[:12] != "9f59a75d7c63": raise Halt("S8_0_PREREG_v2.json 해시가 기록(9f59a75d7c63)과 다름")
    dp = json.loads((S8/"domains_passed.json").read_text(encoding="utf-8"))
    if dp["passed"] != ["safety", "transit"] or sorted(dp["failed"]) != sorted(["electrification_env", "freight", "active_urban", "infrastructure"]): raise Halt("domains_passed.json이 예상과 다름")
    return SPEC, dp

def freeze():
    if not V2P.exists(): raise Halt("PA_0_PLAN_v2.json이 없습니다")
    h = spec_hash(PLAN); print("PA-B8a 계획 해시(예정)", h[:12])
    if BP.exists(): print("이미 동결:", "동일" if json.loads(BP.read_text(encoding="utf-8"))["sha256"] == h else "⛔ 다름"); return
    refs = {f.name: sha_f(f) for f in [V2P, S8/"S8_0_PREREG_v2.json", S8/"domains_passed.json", S8/"domain_precision_recall.csv", S8/"alignment_gap_map.csv", S8/"indicator_consistency.csv", S8/"country_partial_spearman.csv", S8/"burden_country_table.csv", P1/"pa_b8a.py"] if f.exists()}
    BP.write_text(json.dumps(dict(PLAN, created=now(), sha256=h, refs=refs), ensure_ascii=False, indent=1), encoding="utf-8")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as f:
        f.write(f"\n- {now()} | PA-B8a 계획 동결(해시 {h[:12]}) | 사유: precision 미달 4개 도메인을 기존 사전으로 부록 정렬(B8-1). 통과 도메인 결과, 미달 precision, align() 소스 열람 상태, 미달 도메인 정렬 결과 미열람. QUICK은 재현 점검과 도메인별 표본·커버리지만. B8-2(사전 v3, 새 25편)는 별도 | 본 결과 변경 여부: 없음\n")
    print("저장: PA_B8a_PLAN.json")

def tag():
    if not BP.exists(): raise Halt("먼저 freeze")
    t = f"PA-B8a-plan-{pd.Timestamp.now().strftime('%Y-%m-%d')}"
    if git("tag", "-l", t).stdout.strip(): print("이미 있음:", t); return
    r = git("add", "--", "paper1/09_PA/PA_B8a_PLAN.json", "paper1/09_PA/PA_CHANGELOG.md", "paper1/pa_b8a.py"); print("add", r.returncode, r.stderr.strip())
    r = git("commit", "-m", "PA-B8a plan freeze (before execution)"); print("commit", r.returncode, (r.stdout + r.stderr)[:200])
    r = git("tag", "-a", t, "-m", "PA-B8a plan"); print("tag", r.returncode, r.stderr.strip()); print("※ 이어서 git push --follow-tags")

# ---------------- S8 정의 복제 ----------------
def partial_spearman(x, y, z):
    rx_, ry_, rz = rankdata(x), rankdata(y), rankdata(z); A = np.c_[np.ones(len(z)), rz]
    res = lambda v: v - A @ np.linalg.lstsq(A, v, rcond=None)[0]; a, b = res(rx_), res(ry_); return float(np.corrcoef(a, b)[0, 1])

def load_all(SPEC):
    PER = {k: tuple(v) for k, v in SPEC["periods"].items()}; YP = {y: k for k, (a, b) in PER.items() for y in range(a, b + 1)}
    RX = {k: re.compile(v, re.I) for k, v in SPEC["domains"].items()}
    F1 = pd.read_csv(DATA/"F1_papers.csv", low_memory=False); F1["pid"] = F1.pid.astype(str)
    exf = S0/"EXCLUDE_PIDS_FROZEN.csv"; log = pd.read_csv(S0/"FREEZE_LOG.csv"); last = log[log.file == exf.name].iloc[-1]
    if sha_f(exf) != last.sha256: raise Halt("EXCLUDE_PIDS_FROZEN.csv 해시 불일치")
    F = F1[~F1.pid.isin(set(pd.read_csv(exf, dtype=str, encoding="utf-8-sig").pid))].copy(); F = F[F.year >= 2007].copy(); F = F[F.title.notna()]
    flall = pd.DataFrame({d: F.title.fillna("").str.contains(rx).values for d, rx in RX.items()}, index=F.index); flall["pid"] = F.pid.values
    pm = S2/"country_mass_long.parquet"; Mall = pd.read_parquet(pm) if pm.exists() else pd.read_csv(S2/"country_mass_long.csv.gz", dtype={"pid": str}); Mall["pid"] = Mall.pid.astype(str)
    sp_ = SPEC["supply"]; Mall = Mall[(Mall.scheme == sp_["scheme"]) & (Mall.variant == sp_["variant"]) & (Mall.year >= 2007)]; Mall = Mall[~Mall.country.isin(["UNK", "ZZ_former"])]
    Bt = pd.read_csv(S8/"burden_country_table.csv", keep_default_na=False, index_col=0); inc = Bt["income"].copy(); Bt = Bt.drop(columns="income").apply(pd.to_numeric, errors="coerce"); Bt["income"] = inc
    TP0 = pd.read_csv(S1/"title_places.csv", dtype={"pid": str}, keep_default_na=False); TP0 = TP0[TP0.target_countries != ""].copy(); TP0["tc"] = TP0.target_countries.str.split("|"); TP0 = TP0.explode("tc")
    TP0["w"] = 1.0/TP0.groupby("pid").pid.transform("size"); TP0 = TP0.rename(columns={"tc": "country"})[["pid", "country", "w", "year"]]
    TP0["per"] = TP0.year.astype(int).map(YP); TP0 = TP0.dropna(subset=["per"])
    return dict(PER=PER, YP=YP, flall=flall, Mall=Mall, Bt=Bt, TP0=TP0)

def compute(SPEC, L, dom_ok, Bn):
    PER, YP, Bt, Mall = L["PER"], L["YP"], L["Bt"], L["Mall"]; DOM_IND = SPEC["domain_indicators"]
    INC = Bt["income"].to_dict(); G4 = ["HIC", "UMC", "LMC", "LIC"]; EXC = [("none", [])] + [("excl_" + "_".join(s), s) for s in SPEC["sensitivity"]["exclude_country_sets"]]
    fl = L["flall"][["pid"] + dom_ok]; M = Mall.copy(); M["per"] = M.year.map(YP); M = M.merge(fl, on="pid", how="inner"); TP = L["TP0"].merge(fl, on="pid", how="inner")
    rows = []
    for lens, D0 in [("capability", M), ("target", TP)]:
        for exn, ex in EXC:
            D = D0[D0.country.isin(Bt.index) & ~D0.country.isin(ex)]
            for d in dom_ok:
                for ind in sorted(set(DOM_IND[d])):
                    sup_c = Bt.index[Bt[ind].notna() & ~Bt.index.isin(ex) & Bt["income"].isin(G4)]
                    Bi = Bt.loc[sup_c, ind].groupby(Bt.loc[sup_c, "income"]).sum().reindex(G4).fillna(0); bsh = Bi/Bi.sum()
                    for per in PER:
                        x = D[(D.per == per) & D[d] & D.country.isin(sup_c)]; Sg = x.groupby(x.country.map(INC)).w.sum().reindex(G4).fillna(0)
                        if Sg.sum() <= 0: continue
                        for g in G4: rows.append(dict(lens=lens, excl=exn, domain=d, indicator=ind, period=per, group=g, supply_share=Sg[g]/Sg.sum(), burden_share=bsh[g], sbr=(Sg[g]/Sg.sum())/bsh[g] if bsh[g] > 0 else np.nan, supply_mass=Sg.sum()))
    R = pd.DataFrame(rows); Rm = R[R.excl == "none"]
    cons = []
    for (lens, d, per, g), x in Rm.groupby(["lens", "domain", "period", "group"]):
        x = x[x.indicator.isin(DOM_IND[d])].dropna(subset=["sbr"])
        if len(x) == 2: cons.append(dict(lens=lens, domain=d, period=per, group=g, same_side=bool((x.sbr > 1).nunique() == 1)))
    C = pd.DataFrame(cons)
    key = ["lens", "domain", "indicator", "period", "group"]; mm = Rm[key + ["sbr"]].rename(columns={"sbr": "sbr_main"}); sens = []
    for exn, _ in EXC[1:]:
        x = R[R.excl == exn][key + ["sbr"]].merge(mm, on=key).dropna(); x["same"] = (x.sbr > 1) == (x.sbr_main > 1)
        for (lens, d), g in x.groupby(["lens", "domain"]): sens.append(dict(excl=exn, lens=lens, domain=d, n=len(g), same_side_as_main=g.same.mean()))
        sens.append(dict(excl=exn, lens="ALL", domain="ALL", n=len(x), same_side_as_main=x.same.mean()))
    SN = pd.DataFrame(sens)
    cl = SPEC["country_level"]; rng = np.random.default_rng(SPEC["seed"]); pc = []
    for exn, ex in EXC:
        tot = Mall[~Mall.country.isin(ex)].groupby("country").w.sum(); tot = tot[tot >= cl["min_country_mass"]]
        for d in dom_ok:
            dm = M[M[d] & ~M.country.isin(ex)].groupby("country").w.sum().reindex(tot.index).fillna(0); sup = dm/tot
            for ind in DOM_IND[d]:
                df = pd.DataFrame({"s": sup, "b": Bt[INT[ind]].reindex(tot.index), "z": Bt["gdp_pc"].reindex(tot.index)}).dropna()
                if len(df) < 20: pc.append(dict(excl=exn, domain=d, indicator=ind, n=len(df))); continue
                r = partial_spearman(df.s.values, df.b.values, df.z.values); bs = []
                for _ in range(Bn):
                    i = rng.integers(0, len(df), len(df)); bs.append(partial_spearman(df.s.values[i], df.b.values[i], df.z.values[i]))
                pc.append(dict(excl=exn, domain=d, indicator=ind, n=len(df), raw_rho=float(np.corrcoef(rankdata(df.s), rankdata(df.b))[0, 1]), partial_rho=r, lo=np.nanpercentile(bs, 2.5) if Bn else np.nan, hi=np.nanpercentile(bs, 97.5) if Bn else np.nan))
    return R, C, SN, pd.DataFrame(pc)

def same(a, b, keys, cols, tol=1e-9):
    m = a.merge(b, on=keys, suffixes=("_a", "_b"), how="outer", indicator=True)
    if (m._merge != "both").any(): return False, f"행 불일치 {int((m._merge != 'both').sum())}"
    bad = [c for c in cols if c in a.columns and not np.allclose(m[c + "_a"].astype(float), m[c + "_b"].astype(float), atol=tol, equal_nan=True)]
    return (not bad), (f"불일치 열 {bad}" if bad else "일치")

def run():
    if not BP.exists(): raise Halt("먼저 freeze")
    sp = json.loads(BP.read_text(encoding="utf-8"))
    if sp["sha256"] != spec_hash(sp) or sp["sha256"] != spec_hash(PLAN): raise Halt("동결 파일과 현재 계획이 다릅니다")
    if not git("tag", "-l", "PA-B8a-plan-*").stdout.strip(): raise Halt("tag 단계를 먼저 실행하세요")
    SPEC, dp = load_spec(); L = load_all(SPEC); fails = dp["failed"]; Bn = SPEC["country_level"]["bootstrap_B"]
    # --- 재현 점검: 통과 도메인을 같은 코드로 계산해 S8 산출물과 비교 ---
    Bn_rep = 2 if QUICK else Bn
    R0, C0, SN0, PC0 = compute(SPEC, L, dp["passed"], Bn_rep)
    ok1, m1 = same(R0, pd.read_csv(S8/"alignment_gap_map.csv"), ["lens", "excl", "domain", "indicator", "period", "group"], ["supply_share", "burden_share", "sbr", "supply_mass"])
    ok2, m2 = same(C0.assign(same_side=C0.same_side.astype(int)), pd.read_csv(S8/"indicator_consistency.csv").assign(same_side=lambda d: d.same_side.astype(int)), ["lens", "domain", "period", "group"], ["same_side"])
    pcs = pd.read_csv(S8/"country_partial_spearman.csv"); ok3, m3 = same(PC0, pcs, ["excl", "domain", "indicator"], ["n", "raw_rho", "partial_rho"])
    print(f"[재현 점검] 간극 지도 {m1} | 지표 일관 {m2} | 편 순위상관 점추정 {m3}")
    if not (ok1 and ok2 and ok3): raise Halt("재현 점검 실패: 복제 코드가 S8 산출물과 다름")
    if not QUICK:
        ok4, m4 = same(PC0, pcs, ["excl", "domain", "indicator"], ["lo", "hi"]); print(f"[재현 점검] 부트스트랩 구간 {m4}" + ("" if ok4 else "  ※ 경고만(난수 순서 차이 가능)"))
    pr = pd.read_csv(S8/"domain_precision_recall.csv"); pr = pr[pr.domain.isin(fails)][["domain", "n_prec", "precision", "p_lo", "p_hi", "recall"]]
    if QUICK:
        fl = L["flall"]; print("\n[QUICK 설계 정보: 미달 도메인 규칙 양성 논문 수, 부담 지표 가용 국가 수]")
        print({d: int(fl[d].sum()) for d in fails}); print({ind: int(L["Bt"][ind].notna().sum()) for ind in INT})
        print("미달 도메인 precision:\n", pr.round(3).to_string(index=False)); print("\n[QUICK] 재현 점검과 설계 정보만 출력. 미달 도메인 정렬 결과는 계산·출력하지 않음."); return
    R, C, SN, PC = compute(SPEC, L, fails, Bn)
    R.to_csv(PA/"PA_B8a_alignment_gap_map.csv", index=False, encoding="utf-8-sig"); C.to_csv(PA/"PA_B8a_indicator_consistency.csv", index=False, encoding="utf-8-sig")
    SN.to_csv(PA/"PA_B8a_sensitivity_exclusion.csv", index=False, encoding="utf-8-sig"); PC.to_csv(PA/"PA_B8a_country_partial_spearman.csv", index=False, encoding="utf-8-sig"); pr.to_csv(PA/"PA_B8a_precision_note.csv", index=False, encoding="utf-8-sig")
    print("\n[Post-hoc] PA-B8a 미달 4개 도메인(사전 precision 기준 미달, 참고용)\n[도메인 precision]\n", pr.round(3).to_string(index=False))
    last = sorted(L["PER"])[-1]; Rm = R[R.excl == "none"]
    print(f"\n[정렬 간극 지도: 역량 렌즈, {last}, 제외 없음]\n", Rm[(Rm.lens == "capability") & (Rm.period == last)].pivot_table(index=["domain", "indicator"], columns="group", values="sbr").round(2).to_string())
    pv = Rm[(Rm.lens == "capability") & (Rm.period == last)].pivot_table(index=["domain", "indicator"], columns="group", values="sbr")
    if {"HIC", "LIC", "LMC"} <= set(pv.columns): print("\n[HIC 과잉·LIC/LMC 과소 패턴(SBR HIC>1, LIC<1, LMC<1)]\n", ((pv.HIC > 1) & (pv.LIC < 1) & (pv.LMC < 1)).to_string())
    cs = C.groupby(["lens", "domain"]).same_side.mean().unstack(0).round(3); cs["ref_>=0.75(capability)"] = cs["capability"] >= SPEC["direction"]["min_share"]; print("\n[도메인별 지표 일관 비율(참고, 판정 아님)]\n", cs.to_string())
    print("\n[제외 민감도: 주 결과와 같은 쪽인 셀 비율]\n", SN.round(3).to_string(index=False))
    print("\n[국가 수준 편 순위상관(전 기간 풀링, 제외 없음)]\n", PC[PC.excl == "none"].round(3).to_string(index=False))
    print("※ 사전 precision 미달 도메인의 참고용 결과. 통과 도메인과 같은 선상의 증거가 아니며 본문 판정(2/6 통과)을 바꾸지 않음. 국가 단위 상관은 생태학적 오류 가능, 인과 아님.")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as fh:
        fh.write(f"- {now()} | PA-B8a 실행 | 정의: PA_B8a_PLAN {sp['sha256'][:12]} | 결과: PA_B8a_*.csv | 본 결과 변경 여부: 없음\n")

try: {"freeze": freeze, "tag": tag, "run": run}[MODE]()
except Halt as e: print(f"⛔ 중단: {e}")
