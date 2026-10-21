# -*- coding: utf-8 -*-
# PA-B9a: S8 국가 수준 편 순위상관의 소득 수준 분리 진단(소득군 내 상관, 통제 변형). 미실행 코드.
# MODE: "freeze" -> "tag" -> (git push --follow-tags) -> "run"(QUICK=True: 재현 점검과 층별 n만) -> "run"(QUICK=False)
# 정의는 노트북 셀(def align / partial_spearman 포함)의 '# === freeze' 구분선 앞부분을 실행해 가져옴(해시 동결).
# S0~S8 판정 불변. 모든 산출물 [Post-hoc].
import json, hashlib, subprocess, warnings
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import rankdata
warnings.filterwarnings("ignore"); pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 200)
MODE = "tag"
QUICK = True

ROOT = Path.home() / "Research/Minnesota_Transport"; P1 = ROOT/"paper1"; PA = P1/"09_PA"; S8D = P1/"08_S8"
NB = P1/"S7. 지역 집중과 신규 유입, S8. 공급-부담 정렬.ipynb"; MARK = "# ============================== freeze"
now = lambda: pd.Timestamp.now().isoformat(timespec="seconds")
sha_b = lambda b: hashlib.sha256(b).hexdigest(); sha_f = lambda p: sha_b(Path(p).read_bytes())
git = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
class Halt(Exception): pass
spec_hash = lambda s: sha_b(json.dumps({k: v for k, v in s.items() if k not in ("sha256", "created", "refs")}, sort_keys=True, ensure_ascii=False).encode())
V2P, BP = PA/"PA_0_PLAN_v2.json", PA/"PA_B9a_PLAN.json"
G4 = ["HIC", "UMC", "LMC", "LIC"]

PLAN = dict(
    version=1, seed=2026, parent="PA_0_PLAN_v2.json",
    status="사후 명세(PA-B9 중 (1) 소득군 내 상관과 (2) 통제 변형). S8 결과, country_partial_spearman.csv 전체(none·제외 행), 소득군별 국가 수(필터 전 HIC 86, UMC 59, LMC 47, LIC 25), 노트북 셀의 align L206~282와 partial_spearman 정의는 열람한 상태. PA-B9a 결과 미열람. 공급 정의(논문 수 기준)와 min_country_mass 5/20은 PA-B9b로 분리. S0~S8 판정 불변.",
    scope="통과 도메인(domains_passed.json: safety, transit)의 기존 도메인-지표 쌍 4개(DOM_IND), 제외 없음(none) 설정, min_country_mass=10, 2007~2025 풀링 강도(S8 국가 수준과 동일)",
    definitions="공급 강도 s = 국가의 도메인 d 질량 / 국가 총 질량(load_mass, 제목 정규식 플래그 pid 조인, tot>=min_country_mass), 부담 강도 b = burden_country_table의 INT[지표], z = gdp_pc, pop = pop. 코드는 노트북 셀 상단을 그대로 실행해 사용(해시 동결). 기본 df = (s,b,z) 결측 제거",
    strata_controls={"ALL": ["none", "gdp", "income_dummy", "gdp_pop"], "HIC": ["none", "gdp"], "UMC": ["none", "gdp"], "LMC": ["none", "gdp"], "LIC": ["none", "gdp"]},
    control_defs={"none": "통제 없음(순위 상관)", "gdp": "rank(gdp_pc) 통제 편 순위상관(S8 정의, 재현 대상)", "income_dummy": "소득군 더미(HIC 기준 3개) 통제: s,b는 순위, 더미는 순위 변환 없이 OLS 잔차 상관. 소득군이 G4인 국가만",
                  "gdp_pop": "rank(gdp_pc)와 rank(pop) 이중 통제. pop 결측 국가 제외"},
    n_min=20, B=1000, ci=[2.5, 97.5], boot="국가 복원추출, 재표집마다 순위·잔차 재계산(S8과 같은 방식), 층별 통제별로 독립 추출(seed 고정, 실행 순서 고정)",
    reading="행(도메인x지표 x 층 x 통제)별로 보고. n<20이면 'NA'. 아니면 부호가 (ALL, gdp) 행의 부호와 같고 구간이 0을 배제하면 '관찰', 아니면 '비관찰'. 행·층·통제를 합쳐 하나의 결론으로 만들지 않음. 문구는 '소득 수준과 분리되지 않는 간극'이며 필요 충족 증거로 쓰지 않음",
    reproduce_check="(a) 노트북 앞부분 해시가 동결 시점과 일치, (b) (ALL, gdp) 행의 n, raw rho, partial rho가 country_partial_spearman.csv의 excl=none 행과 1e-6 이내(4쌍 모두), (c) 이 코드의 편 상관 함수가 노트북 partial_spearman과 1e-9 이내. 하나라도 어긋나면 중단",
    caveat="기존 편 rho에서 구간이 0을 배제하는 쌍은 safety-road_deaths 하나뿐이라 나머지 세 쌍의 '관찰' 여부는 해석하지 않음. 소득군 내는 n이 작아 구간이 넓고, 비관찰은 효과 없음이 아니라 검정력 한계일 수 있음. 소득군 더미와 gdp는 공선성이 큼. 48행, 다중성 보정 없음, 탐색적. 국가 단위 상관은 생태학적 오류 가능, 인과·필요 충족 증거 아님. 소득군 값은 wb_income_current 고정",
    forbidden="결과를 본 뒤 통제·층·n_min·판독 규칙 변경(변경 시 v2 계획으로 분리하고 사유 기록)")

def nb_prefix():
    cells = json.loads(NB.read_text(encoding="utf-8"))["cells"]; cand = []
    for i, c in enumerate(cells):
        s = "".join(c.get("source", []))
        if c.get("cell_type") == "code" and "def align():" in s and "def partial_spearman" in s and MARK in s: cand.append((i, s))
    if not cand: raise Halt("노트북에서 def align / partial_spearman / freeze 구분선을 가진 셀을 찾지 못함")
    i, s = cand[-1]; return i, s.split(MARK)[0], len(cand)

def freeze():
    if not V2P.exists(): raise Halt("PA_0_PLAN_v2.json이 없습니다")
    i, pre, nc = nb_prefix(); h = spec_hash(PLAN); print("PA-B9a 계획 해시(예정)", h[:12], f"| 노트북 셀 {i}(후보 {nc}개) 앞부분 {len(pre):,}자")
    if BP.exists(): print("이미 동결:", "동일" if json.loads(BP.read_text(encoding="utf-8"))["sha256"] == h else "⛔ 다름"); return
    refs = {f.name: sha_f(f) for f in [V2P, S8D/"S8_0_PREREG_v2.json", S8D/"country_partial_spearman.csv", S8D/"burden_country_table.csv", S8D/"domains_passed.json", NB] if f.exists()}
    refs["s8_prefix_sha256"] = sha_b(pre.encode("utf-8")); refs["s8_prefix_cell_index"] = i
    BP.write_text(json.dumps(dict(PLAN, created=now(), sha256=h, refs=refs), ensure_ascii=False, indent=1), encoding="utf-8")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as f:
        f.write(f"\n- {now()} | PA-B9a 계획 동결(해시 {h[:12]}) | 사유: S8 편 순위상관의 소득 수준 분리 진단(소득군 내, 통제 변형). 노트북 셀 {i} 앞부분 해시 동결. PA-B9a 결과 미열람. QUICK은 재현 점검과 층별 n만 | 본 결과 변경 여부: 없음\n")
    print("저장: PA_B9a_PLAN.json")

def tag():
    if not BP.exists(): raise Halt("먼저 freeze")
    t = f"PA-B9a-plan-{pd.Timestamp.now().strftime('%Y-%m-%d')}"
    if git("tag", "-l", t).stdout.strip(): print("이미 있음:", t); return
    r = git("add", "--", "paper1/09_PA/PA_B9a_PLAN.json", "paper1/09_PA/PA_CHANGELOG.md", "paper1/pa_b9a.py"); print("add", r.returncode, r.stderr.strip())
    r = git("commit", "-m", "PA-B9a plan freeze (before execution)"); print("commit", r.returncode, (r.stdout + r.stderr)[:200])
    r = git("tag", "-a", t, "-m", "PA-B9a plan"); print("tag", r.returncode, r.stderr.strip()); print("※ 이어서 git push --follow-tags")

def pr(x, y, cols=(), rk=()):
    a, b = rankdata(x), rankdata(y)
    if not len(cols): return float(np.corrcoef(a, b)[0, 1])
    A = np.column_stack([np.ones(len(a))] + [rankdata(c) if r else np.asarray(c, float) for c, r in zip(cols, rk)])
    res = lambda v: v - A @ np.linalg.lstsq(A, v, rcond=None)[0]
    return float(np.corrcoef(res(a), res(b))[0, 1])

def cols_of(sub, ctrl):
    if ctrl == "none": return [], []
    if ctrl == "gdp": return [sub.z.values], [True]
    if ctrl == "gdp_pop": return [sub.z.values, sub["pop"].values], [True, True]
    if ctrl == "income_dummy": return [(sub.inc.values == g).astype(float) for g in G4[1:]], [False]*3
    raise Halt(f"알 수 없는 통제 {ctrl}")

def subset(base, stratum, ctrl):
    if stratum == "ALL":
        if ctrl == "income_dummy": return base[base.inc.isin(G4)]
        if ctrl == "gdp_pop": return base.dropna(subset=["pop"])
        return base
    return base[base.inc == stratum]

def run():
    if not BP.exists(): raise Halt("먼저 freeze")
    sp = json.loads(BP.read_text(encoding="utf-8"))
    if sp["sha256"] != spec_hash(sp) or sp["sha256"] != spec_hash(PLAN): raise Halt("동결 파일과 현재 계획이 다릅니다")
    if not git("tag", "-l", "PA-B9a-plan-*").stdout.strip(): raise Halt("tag 단계를 먼저 실행하세요")
    sfx = "_QUICK" if QUICK else ""
    i, pre, _ = nb_prefix()
    if sha_b(pre.encode("utf-8")) != sp["refs"]["s8_prefix_sha256"]: raise Halt("노트북 앞부분이 동결 시점과 다름(노트북이 수정됨)")
    ns = {"__name__": "s8_prefix"}; exec(compile(pre, "s8_prefix", "exec"), ns)
    for k in ["SPEC", "YP", "DOM_IND", "INT", "load_F1X", "flag_domains", "load_mass", "partial_spearman", "check_spec"]:
        if k not in ns: raise Halt(f"노트북 앞부분에 {k}가 없음")
    ns["check_spec"]()
    SPEC = ns["SPEC"]; cl = SPEC["country_level"]; INT, DOM_IND = ns["INT"], ns["DOM_IND"]
    dom_ok = json.loads((S8D/"domains_passed.json").read_text(encoding="utf-8"))["passed"]
    Bt = pd.read_csv(S8D/"burden_country_table.csv", keep_default_na=False, index_col=0); inc = Bt["income"].copy(); Bt = Bt.drop(columns="income").apply(pd.to_numeric, errors="coerce"); Bt["income"] = inc
    F = ns["load_F1X"](); F = F[F.title.notna()]; fl = ns["flag_domains"](F.title); fl["pid"] = F.pid.values; fl = fl[["pid"] + dom_ok]
    Mall = ns["load_mass"](); M = Mall.copy(); M["per"] = M.year.map(ns["YP"]); M = M.merge(fl, on="pid", how="inner")
    tot = Mall.groupby("country").w.sum(); tot = tot[tot >= cl["min_country_mass"]]
    ref = pd.read_csv(S8D/"country_partial_spearman.csv", encoding="utf-8-sig"); ref = ref[ref.excl == "none"].set_index(["domain", "indicator"])
    base_of = {}
    for d in dom_ok:
        dm = M[M[d]].groupby("country").w.sum().reindex(tot.index).fillna(0); sup = dm/tot
        for ind in DOM_IND[d]:
            base_of[(d, ind)] = pd.DataFrame({"s": sup, "b": Bt[INT[ind]].reindex(tot.index), "z": Bt["gdp_pc"].reindex(tot.index), "pop": Bt["pop"].reindex(tot.index), "inc": Bt["income"].reindex(tot.index)}).dropna(subset=["s", "b", "z"])
    # 재현 점검
    for (d, ind), df in base_of.items():
        r0 = ref.loc[(d, ind)]; ph = pr(df.s.values, df.b.values, [df.z.values], [True]); pn = ns["partial_spearman"](df.s.values, df.b.values, df.z.values); rw = pr(df.s.values, df.b.values)
        if abs(ph - pn) > 1e-9: raise Halt(f"편 상관 함수가 노트북과 다름({d},{ind})")
        if len(df) != int(r0.n) or abs(rw - float(r0.raw_rho)) > 1e-6 or abs(ph - float(r0.partial_rho)) > 1e-6: raise Halt(f"S8 재현 실패({d},{ind}): n {len(df)} vs {int(r0.n)}, raw {rw:.6f} vs {r0.raw_rho:.6f}, partial {ph:.6f} vs {r0.partial_rho:.6f}")
    print(f"[재현 OK] {len(base_of)}쌍의 n, raw rho, 편 rho가 country_partial_spearman.csv(none)와 일치 | 노트북 셀 {i} 앞부분 해시 일치")
    plan_rows = [(st, c) for st, cs in PLAN["strata_controls"].items() for c in cs]
    NT = pd.DataFrame([dict(domain=d, indicator=ind, stratum=st, control=c, n=len(subset(df, st, c))) for (d, ind), df in base_of.items() for st, c in plan_rows])
    NT.to_csv(PA/f"PA_B9a_n_by_stratum{sfx}.csv", index=False, encoding="utf-8-sig")
    print("\n[층별 n(설계 정보)]\n", NT.pivot_table(index=["domain", "indicator"], columns=["stratum", "control"], values="n").astype(int).to_string())
    B = 20 if QUICK else int(PLAN["B"]); rng = np.random.default_rng(int(PLAN["seed"])); rows = []
    for (d, ind), df in base_of.items():
        for st, c in plan_rows:
            sub = subset(df, st, c); n = len(sub); row = dict(domain=d, indicator=ind, stratum=st, control=c, n=n, B=B)
            if n < PLAN["n_min"]: rows.append(dict(row, rho=np.nan, lo=np.nan, hi=np.nan)); continue
            cols, rk = cols_of(sub, c); x, y = sub.s.values, sub.b.values; r = pr(x, y, cols, rk); bs = []
            for _ in range(B):
                k = rng.integers(0, n, n); bs.append(pr(x[k], y[k], [cc[k] for cc in cols], rk))
            rows.append(dict(row, rho=r, lo=float(np.nanpercentile(bs, PLAN["ci"][0])), hi=float(np.nanpercentile(bs, PLAN["ci"][1]))))
    R = pd.DataFrame(rows); main = R[(R.stratum == "ALL") & (R.control == "gdp")].set_index(["domain", "indicator"]).rho
    R["main_sign"] = [np.sign(main.loc[(a, b)]) for a, b in zip(R.domain, R.indicator)]; R["sign_same"] = np.sign(R.rho) == R.main_sign; R["excludes0"] = (R.lo > 0) | (R.hi < 0)
    R["verdict"] = np.where(R.rho.isna(), "NA", np.where(R.sign_same & R.excludes0, "관찰", "비관찰"))
    R.to_csv(PA/f"PA_B9a_results{sfx}.csv", index=False, encoding="utf-8-sig")
    if QUICK: print("\n[QUICK] 오류 없이 완료. 결과 통계는 출력하지 않음(_QUICK 파일을 열어 해석하지 마세요)."); return
    print("\n[Post-hoc] PA-B9a 편·순위상관(전체 표본 통제 변형)\n", R[R.stratum == "ALL"].round(4).drop(columns=["B", "main_sign"]).to_string(index=False))
    print("\n[Post-hoc] PA-B9a 소득군 내\n", R[R.stratum != "ALL"].round(4).drop(columns=["B", "main_sign"]).to_string(index=False))
    print("\n[동결 판독] 행별 verdict(합치지 않음)\n", R.pivot_table(index=["domain", "indicator", "stratum"], columns="control", values="verdict", aggfunc="first").to_string())
    print("※ 비관찰은 효과 없음이 아니라 검정력 한계일 수 있음. 기준 부호가 불확실한 세 쌍은 해석하지 않음. 48행 탐색적, 소득군은 wb_income_current 고정. S0~S8 판정 불변.")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as fh:
        fh.write(f"- {now()} | PA-B9a 실행 | 정의: PA_B9a_PLAN {sp['sha256'][:12]} | 결과: PA_B9a_results.csv, PA_B9a_n_by_stratum.csv | 본 결과 변경 여부: 없음\n")

try: {"freeze": freeze, "tag": tag, "run": run}[MODE]()
except Halt as e: print(f"⛔ 중단: {e}")