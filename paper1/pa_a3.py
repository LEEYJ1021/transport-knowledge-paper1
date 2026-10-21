# -*- coding: utf-8 -*-
# PA-A3: S7 선두 국가 서술 정밀화(미상 교정 rec 재집계, 균등 4구간, 중국 제외 HHI). 결정적 계산. 미실행 코드.
# MODE: "freeze" -> "tag" -> (git push --follow-tags) -> "run"(QUICK=True: 재현 점검만) -> "run"(QUICK=False)
# S0~S8 판정 불변. 모든 산출물 [Post-hoc].
import json, hashlib, subprocess, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore"); pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 200)
MODE = "run"
QUICK = False

ROOT = Path.home() / "Research/Minnesota_Transport"; P1 = ROOT/"paper1"; PA = P1/"09_PA"; S2, S7 = P1/"02_S2", P1/"07_S7"
now = lambda: pd.Timestamp.now().isoformat(timespec="seconds")
sha_b = lambda b: hashlib.sha256(b).hexdigest(); sha_f = lambda p: sha_b(Path(p).read_bytes())
git = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
class Halt(Exception): pass
spec_hash = lambda s: sha_b(json.dumps({k: v for k, v in s.items() if k not in ("sha256", "created", "refs")}, sort_keys=True, ensure_ascii=False).encode())
V2P, BP = PA/"PA_0_PLAN_v2.json", PA/"PA_A3_PLAN.json"

PLAN = dict(
    version=1, parent="PA_0_PLAN_v2.json",
    status="사후 명세. S7 결과, s7_period_stats.csv 주 설정 행, PA-C2 결과(원본 기간의 main 통계), country_mass_long의 열·variant 구성은 열람한 상태. PA-A3 결과 미열람. S0~S8 판정 불변.",
    setting="country_mass_long에서 scheme=inv_n_authors, variant in {main, rec}, year>=2007. UNK·ZZ_former는 미상, 알려진 국가 질량 기준 통계(S7 stats_of와 같은 정의). 소속 위치 기준이며 국적 아님",
    periods={"orig": {"P0709": [2007, 2009], "P1014": [2010, 2014], "P1519": [2015, 2019], "P2025": [2020, 2025]},
             "equal4": {"E0711": [2007, 2011], "E1216": [2012, 2016], "E1721": [2017, 2021], "E2225": [2022, 2025]}},
    stats="top5_incl, top5_known, hhi_known, cn_known, us_known, unk, 그리고 CN 제외(알려진 질량에서 CN을 빼고 재정규화): hhi_exCN, top5_exCN. 병기: n_active",
    A3_1="orig 기간에서 rec 대 main. 통계별 (마지막-첫) 변화의 부호가 같으면 '방향 일치'. 기간별 |rec-main|<=0.01은 '수준 일치'로 병기, 합치지 않음",
    A3_2="equal4 기간(마지막 4년, 2025 부분연도). 통계별 (마지막-첫) 부호가 orig main과 같으면 '방향 유지'. variant별로 따로 보고",
    A3_3="variant x 기간정의별로 hhi_known과 hhi_exCN 각각에서 (마지막 > 직전) 여부와 최솟값 기간을 보고. 포함만 반등: '반등은 중국 몫에 연동', 둘 다: '중국 제외에도 반등 유지', 둘 다 아님: '반등 없음'",
    reproduce_check="orig 기간·두 variant의 top5_incl, top5_known, hhi_known, cn_known, us_known, unk가 s7_period_stats.csv(scheme=inv_n_authors, sample=all, terr_merge=False, income=fixed)와 1e-9 이내, n_active 일치. 아니면 중단",
    caveat="결정적 재집계이며 추론 아님. equal4 마지막 구간은 4년·부분연도라 길이가 다름. rec와 main의 정의 차이는 S7 코드 기준이며 여기서 재검토하지 않음. 부호 판독은 변화가 0에 가까울 때 불안정함",
    forbidden="결과를 본 뒤 기간·기준(0.01)·판독 규칙 변경(변경 시 v2 계획으로 분리하고 사유 기록)")

def freeze():
    if not V2P.exists(): raise Halt("PA_0_PLAN_v2.json이 없습니다")
    h = spec_hash(PLAN); print("PA-A3 계획 해시(예정)", h[:12])
    if BP.exists(): print("이미 동결:", "동일" if json.loads(BP.read_text(encoding="utf-8"))["sha256"] == h else "⛔ 다름"); return
    refs = {f.name: sha_f(f) for f in [V2P, S7/"S7_0_PREREG.json", S7/"s7_period_stats.csv", P1/"s7_run.py", PA/"PA_C2_results.csv"] if f.exists()}
    BP.write_text(json.dumps(dict(PLAN, created=now(), sha256=h, refs=refs), ensure_ascii=False, indent=1), encoding="utf-8")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as f:
        f.write(f"\n- {now()} | PA-A3 계획 동결(해시 {h[:12]}) | 사유: S7 선두 국가 서술 정밀화(rec 재집계, 균등 4구간, 중국 제외 HHI). PA-A3 결과 미열람. QUICK은 재현 점검만 | 본 결과 변경 여부: 없음\n")
    print("저장: PA_A3_PLAN.json")

def tag():
    if not BP.exists(): raise Halt("먼저 freeze")
    t = f"PA-A3-plan-{pd.Timestamp.now().strftime('%Y-%m-%d')}"
    if git("tag", "-l", t).stdout.strip(): print("이미 있음:", t); return
    r = git("add", "--", "paper1/09_PA/PA_A3_PLAN.json", "paper1/09_PA/PA_CHANGELOG.md", "paper1/pa_a3.py"); print("add", r.returncode, r.stderr.strip())
    r = git("commit", "-m", "PA-A3 plan freeze (before execution)"); print("commit", r.returncode, (r.stdout + r.stderr)[:200])
    r = git("tag", "-a", t, "-m", "PA-A3 plan"); print("tag", r.returncode, r.stderr.strip()); print("※ 이어서 git push --follow-tags")

def st(vec, cols):
    unk = np.isin(cols, ["UNK", "ZZ_former"]); kn = np.where(unk, 0.0, vec); kt = kn.sum(); tot = vec.sum(); top = np.sort(kn)[::-1][:5].sum()
    ex = np.where(cols == "CN", 0.0, kn); et = ex.sum()
    return dict(top5_incl=top/tot, top5_known=top/kt, hhi_known=float(((kn/kt)**2).sum()), cn_known=float(kn[cols == "CN"].sum()/kt), us_known=float(kn[cols == "US"].sum()/kt),
                unk=float(1 - kt/tot), hhi_exCN=float(((ex/et)**2).sum()), top5_exCN=float(np.sort(ex)[::-1][:5].sum()/et), n_active=int((kn >= 1.0).sum()))
def pstats(d, PER):
    G = d.pivot_table(index="year", columns="country", values="w", aggfunc="sum", fill_value=0); cols = np.array(G.columns)
    return {k: st(G.loc[a:b].sum(0).values, cols) for k, (a, b) in PER.items()}

CORE = ["top5_incl", "top5_known", "hhi_known", "cn_known", "us_known", "unk"]
def run():
    if not BP.exists(): raise Halt("먼저 freeze")
    sp = json.loads(BP.read_text(encoding="utf-8"))
    if sp["sha256"] != spec_hash(sp) or sp["sha256"] != spec_hash(PLAN): raise Halt("동결 파일과 현재 계획이 다릅니다")
    if not git("tag", "-l", "PA-A3-plan-*").stdout.strip(): raise Halt("tag 단계를 먼저 실행하세요")
    sfx = "_QUICK" if QUICK else ""
    pm = S2/"country_mass_long.parquet"
    M = pd.read_parquet(pm) if pm.exists() else pd.read_csv(S2/"country_mass_long.csv.gz", dtype={"pid": str})
    M = M[(M.year >= 2007) & (M.scheme == "inv_n_authors")][["year", "country", "w", "variant"]]
    PO = {k: tuple(v) for k, v in PLAN["periods"]["orig"].items()}; PE = {k: tuple(v) for k, v in PLAN["periods"]["equal4"].items()}
    ref = pd.read_csv(S7/"s7_period_stats.csv"); ref = ref[(ref.scheme == "inv_n_authors") & (ref["sample"] == "all") & (ref.terr_merge == False) & (ref.income == "fixed")]
    ST = {}
    for v in ["main", "rec"]:
        d = M[M.variant == v].groupby(["year", "country"], as_index=False).w.sum()
        ST[(v, "orig")] = pstats(d, PO); ST[(v, "equal4")] = pstats(d, PE)
        r = ref[ref.variant == v].set_index("period")
        for k in PO:
            for s in CORE:
                if abs(ST[(v, "orig")][k][s] - float(r.loc[k, s])) > 1e-9: raise Halt(f"S7 재현 실패({v}, {k}, {s})")
            if ST[(v, "orig")][k]["n_active"] != int(r.loc[k, "n_active"]): raise Halt(f"n_active 재현 실패({v}, {k})")
    print("[재현 OK] S7 orig 기간 통계(main·rec)")
    if QUICK: print("[QUICK] 재현 점검만 수행. 결과 통계는 출력하지 않음."); return
    rows = []
    for (v, ps), D in ST.items():
        for k, dd in D.items():
            for s in CORE + ["hhi_exCN", "top5_exCN", "n_active"]: rows.append(dict(variant=v, periodset=ps, period=k, stat=s, value=dd[s]))
    RS = pd.DataFrame(rows); RS.to_csv(PA/"PA_A3_results.csv", index=False, encoding="utf-8-sig")
    print("\n[Post-hoc] PA-A3 기간별 통계\n", RS.pivot_table(index=["variant", "periodset", "stat"], columns="period", values="value", sort=False).round(4).to_string())
    def dlt(v, ps, s):
        ks = list(ST[(v, ps)]); return ST[(v, ps)][ks[-1]][s] - ST[(v, ps)][ks[0]][s]
    # A3-1
    a1 = []
    for s in CORE:
        gap = max(abs(ST[("rec", "orig")][k][s] - ST[("main", "orig")][k][s]) for k in PO)
        a1.append(dict(stat=s, d_main=dlt("main", "orig", s), d_rec=dlt("rec", "orig", s), 방향=("일치" if np.sign(dlt("main", "orig", s)) == np.sign(dlt("rec", "orig", s)) else "불일치"), max_level_gap=gap, 수준=("일치" if gap <= 0.01 else "차이")))
    A1 = pd.DataFrame(a1); print("\n[동결 판독 A3-1] rec 대 main(orig 기간)\n", A1.round(4).to_string(index=False))
    # A3-2
    a2 = []
    for v in ["main", "rec"]:
        for s in CORE:
            a2.append(dict(variant=v, stat=s, d_orig_main=dlt("main", "orig", s), d_equal4=dlt(v, "equal4", s), 판독=("방향 유지" if np.sign(dlt("main", "orig", s)) == np.sign(dlt(v, "equal4", s)) else "방향 다름")))
    A2 = pd.DataFrame(a2); print("\n[동결 판독 A3-2] 균등 4구간\n", A2.round(4).to_string(index=False))
    # A3-3
    a3 = []
    for (v, ps), D in ST.items():
        ks = list(D); rb = lambda s: D[ks[-1]][s] > D[ks[-2]][s]; amin = lambda s: min(ks, key=lambda k: D[k][s])
        w, x = rb("hhi_known"), rb("hhi_exCN")
        a3.append(dict(variant=v, periodset=ps, hhi_known_min=amin("hhi_known"), hhi_exCN_min=amin("hhi_exCN"), rebound_known=w, rebound_exCN=x,
                       판독=("중국 제외에도 반등 유지" if w and x else ("반등은 중국 몫에 연동" if w and not x else ("반등 없음" if not w and not x else "중국 제외에서만 반등")))))
    A3 = pd.DataFrame(a3); print("\n[동결 판독 A3-3] 중국 제외 HHI\n", A3.to_string(index=False))
    A1.to_csv(PA/"PA_A3_A1_rec_vs_main.csv", index=False, encoding="utf-8-sig"); A2.to_csv(PA/"PA_A3_A2_equal4.csv", index=False, encoding="utf-8-sig"); A3.to_csv(PA/"PA_A3_A3_exCN.csv", index=False, encoding="utf-8-sig")
    print("※ 결정적 재집계. 항목별·variant별로 따로 읽고 합치지 않음. 소속은 국적 아님. S0~S8 판정 불변.")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as fh:
        fh.write(f"- {now()} | PA-A3 실행 | 정의: PA_A3_PLAN {sp['sha256'][:12]} | 결과: PA_A3_*.csv | 본 결과 변경 여부: 없음\n")

try: {"freeze": freeze, "tag": tag, "run": run}[MODE]()
except Halt as e: print(f"⛔ 중단: {e}")