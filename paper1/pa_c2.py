# -*- coding: utf-8 -*-
# PA-C2: S7 국가 몫을 임베딩 보유 논문(S6 분석 집합)만으로 재계산. 결정적 계산. 미실행 코드.
# MODE: "freeze" -> "tag" -> (git push --follow-tags) -> "run"(QUICK=True: 재현 점검과 논문 수만, 결과 수치 미출력) -> "run"(QUICK=False)
# S0~S8 판정 불변. 모든 산출물 [Post-hoc].
import json, hashlib, subprocess, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore"); pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40)
MODE = "tag"
QUICK = True

ROOT = Path.home() / "Research/Minnesota_Transport"; P1 = ROOT/"paper1"; PA = P1/"09_PA"
DATA, S0, S2, S7 = ROOT/"analysis_data/final", P1/"00_S0", P1/"02_S2", P1/"07_S7"
now = lambda: pd.Timestamp.now().isoformat(timespec="seconds")
sha_b = lambda b: hashlib.sha256(b).hexdigest(); sha_f = lambda p: sha_b(Path(p).read_bytes())
tf = lambda s: s.astype(str).str.strip().str.lower().isin(["1", "1.0", "true", "t", "yes"])
git = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
class Halt(Exception): pass
spec_hash = lambda s: sha_b(json.dumps({k: v for k, v in s.items() if k not in ("sha256", "created", "refs")}, sort_keys=True, ensure_ascii=False).encode())
V2P, BP = PA/"PA_0_PLAN_v2.json", PA/"PA_C2_PLAN.json"

PLAN = dict(
    version=1, parent="PA_0_PLAN_v2.json",
    status="사후 명세. S7 결과와 s7_run.py 일부 소스, s7_period_stats.csv 주 설정 행(P1519 cn 0.1373, P2025 cn 0.3476 등)은 열람한 상태. PA-C2 결과 미열람. S0~S8 판정 불변.",
    setting="S7 주 설정: scheme=inv_n_authors, variant=main, sample=all, terr_merge=False, income=fixed. country_mass_long에서 year>=2007, 기간은 S7_0_PREREG.json의 periods",
    subset="F1_papers.csv에서 EXCLUDE_PIDS_FROZEN.csv 제외(FREEZE_LOG 해시 검증), in_sample 참, 연도 2000~2025, has_topic 참, topic150 결측 아님. 이 pid 집합에 속한 country_mass_long 행만 유지. 재현 점검: 이 집합이 2000~2025에서 76,984편",
    stats="기간별 top5_known, hhi_known, cn_known, us_known, unk (S7 stats_of와 같은 정의: UNK·ZZ_former를 미상으로, 알려진 국가 질량 기준). 병기만: n_active(질량>=1 국가 수), top5_incl",
    reading="기간x통계별 |filtered - original| <= 0.01 이면 '일치', 아니면 '차이'. 기간별·통계별로 따로 보고하고 합치지 않음",
    diagnostics="기간별 원본·잔존 논문 수와 질량, 원본에서 걸러진 쪽과 남은 쪽의 unk 비율",
    reproduce_check="(a) 거르기 전 기간 통계가 s7_period_stats.csv 주 설정 행과 1e-9 이내(n_active는 일치), (b) S6 집합 76,984편, (c) 거른 뒤 논문당 질량 합 1",
    caveat="이 분석은 보유 논문 부분집합이 국가 몫을 바꾸는지만 본다. 소속은 국적이 아님. 국가 층 논문 중 F1에 없는 pid가 있으면 걸러진 쪽에 포함되어 보고됨",
    forbidden="결과를 본 뒤 설정·판독 기준(0.01) 변경(변경 시 v2 계획으로 분리하고 사유 기록)")

def freeze():
    if not V2P.exists(): raise Halt("PA_0_PLAN_v2.json이 없습니다")
    h = spec_hash(PLAN); print("PA-C2 계획 해시(예정)", h[:12])
    if BP.exists(): print("이미 동결:", "동일" if json.loads(BP.read_text(encoding="utf-8"))["sha256"] == h else "⛔ 다름"); return
    refs = {f.name: sha_f(f) for f in [V2P, S7/"S7_0_PREREG.json", S7/"s7_period_stats.csv", P1/"s7_run.py"] if f.exists()}
    BP.write_text(json.dumps(dict(PLAN, created=now(), sha256=h, refs=refs), ensure_ascii=False, indent=1), encoding="utf-8")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as f:
        f.write(f"\n- {now()} | PA-C2 계획 동결(해시 {h[:12]}) | 사유: S7 국가 몫(전체 논문)과 S6 저자 층(임베딩 보유 논문)의 모집단 불일치 점검. PA-C2 결과 미열람. QUICK은 수치 미출력 | 본 결과 변경 여부: 없음\n")
    print("저장: PA_C2_PLAN.json")

def tag():
    if not BP.exists(): raise Halt("먼저 freeze")
    t = f"PA-C2-plan-{pd.Timestamp.now().strftime('%Y-%m-%d')}"
    if git("tag", "-l", t).stdout.strip(): print("이미 있음:", t); return
    r = git("add", "--", "paper1/09_PA/PA_C2_PLAN.json", "paper1/09_PA/PA_CHANGELOG.md", "paper1/pa_c2.py"); print("add", r.returncode, r.stderr.strip())
    r = git("commit", "-m", "PA-C2 plan freeze (before execution)"); print("commit", r.returncode, (r.stdout + r.stderr)[:200])
    r = git("tag", "-a", t, "-m", "PA-C2 plan"); print("tag", r.returncode, r.stderr.strip()); print("※ 이어서 git push --follow-tags")

def st(vec, cols):
    unk = np.isin(cols, ["UNK", "ZZ_former"]); kn = np.where(unk, 0.0, vec); kt = kn.sum(); tot = vec.sum(); top = np.sort(kn)[::-1][:5].sum()
    return dict(top5_incl=top/tot, top5_known=top/kt, hhi_known=float(((kn/kt)**2).sum()), cn_known=float(kn[cols == "CN"].sum()/kt),
                us_known=float(kn[cols == "US"].sum()/kt), unk=float(1 - kt/tot), n_active=int((kn >= 1.0).sum()))
def period_stats(d, PER):
    G = d.pivot_table(index="year", columns="country", values="w", aggfunc="sum", fill_value=0); cols = np.array(G.columns)
    return {k: st(G.loc[a:b].sum(0).values, cols) for k, (a, b) in PER.items()}

def run():
    if not BP.exists(): raise Halt("먼저 freeze")
    sp = json.loads(BP.read_text(encoding="utf-8"))
    if sp["sha256"] != spec_hash(sp) or sp["sha256"] != spec_hash(PLAN): raise Halt("동결 파일과 현재 계획이 다릅니다")
    if not git("tag", "-l", "PA-C2-plan-*").stdout.strip(): raise Halt("tag 단계를 먼저 실행하세요")
    sfx = "_QUICK" if QUICK else ""
    PER = {k: tuple(v) for k, v in json.loads((S7/"S7_0_PREREG.json").read_text(encoding="utf-8"))["periods"].items()}
    pm = S2/"country_mass_long.parquet"
    M = pd.read_parquet(pm) if pm.exists() else pd.read_csv(S2/"country_mass_long.csv.gz", dtype={"pid": str})
    M["pid"] = M.pid.astype(str); M = M[(M.year >= 2007) & (M.scheme == "inv_n_authors") & (M.variant == "main")][["pid", "year", "country", "w"]]
    # S6 분석 집합
    F1 = pd.read_csv(DATA/"F1_papers.csv", low_memory=False); F1["pid"] = F1.pid.astype(str)
    exf = S0/"EXCLUDE_PIDS_FROZEN.csv"; log = pd.read_csv(S0/"FREEZE_LOG.csv"); last = log[log.file == exf.name].iloc[-1]
    if sha_f(exf) != last.sha256: raise Halt("EXCLUDE_PIDS_FROZEN.csv 해시 불일치")
    F1 = F1[~F1.pid.isin(set(pd.read_csv(exf, dtype=str, encoding="utf-8-sig").pid))]
    keep = F1[tf(F1.in_sample) & F1.year.between(2000, 2025) & tf(F1.has_topic) & F1.topic150.notna()]
    if len(keep) != 76984: raise Halt(f"S6 분석 집합 재현 실패: {len(keep)} (76984여야 함)")
    kp = set(keep.pid)
    # (a) 재현
    ref = pd.read_csv(S7/"s7_period_stats.csv"); ref = ref[(ref.scheme == "inv_n_authors") & (ref.variant == "main") & (ref["sample"] == "all") & (ref.terr_merge == False) & (ref.income == "fixed")].set_index("period")
    ST0 = period_stats(M.groupby(["year", "country"], as_index=False).w.sum(), PER)
    for k in PER:
        for s in ["top5_known", "hhi_known", "cn_known", "us_known", "unk"]:
            if abs(ST0[k][s] - float(ref.loc[k, s])) > 1e-9: raise Halt(f"S7 재현 실패({k}, {s})")
        if ST0[k]["n_active"] != int(ref.loc[k, "n_active"]): raise Halt(f"S7 n_active 재현 실패({k})")
    Mk = M[M.pid.isin(kp)]
    chk = Mk.groupby("pid").w.sum()
    if not np.allclose(chk, 1.0): raise Halt("거른 뒤 논문당 질량 합이 1이 아님")
    print("[재현 OK] S7 주 설정 기간 통계, S6 집합 76,984편, 질량 보존")
    diag = []
    for k, (a, b) in PER.items():
        o, f = M[M.year.between(a, b)], Mk[Mk.year.between(a, b)]; dr = o[~o.pid.isin(kp)]
        un = lambda x: float(x.w[x.country.isin(["UNK", "ZZ_former"])].sum()/x.w.sum()) if len(x) else np.nan
        diag.append(dict(period=k, papers_orig=int(o.pid.nunique()), papers_kept=int(f.pid.nunique()), kept_share=float(f.pid.nunique()/o.pid.nunique()), unk_orig=un(o), unk_kept=un(f), unk_dropped=un(dr)))
    DG = pd.DataFrame(diag)
    if QUICK:
        print("논문 수(진단)\n", DG[["period", "papers_orig", "papers_kept", "kept_share"]].round(4).to_string(index=False))
        print("\n[QUICK] 재현 점검과 논문 수만 출력. 결과 통계는 계산·출력하지 않음."); return
    ST1 = period_stats(Mk.groupby(["year", "country"], as_index=False).w.sum(), PER); rows = []
    for k in PER:
        for s in ["top5_known", "hhi_known", "cn_known", "us_known", "unk", "n_active", "top5_incl"]:
            d = ST1[k][s] - ST0[k][s]; core = s in ["top5_known", "hhi_known", "cn_known", "us_known", "unk"]
            rows.append(dict(period=k, stat=s, orig=ST0[k][s], kept=ST1[k][s], delta=d, core=core, verdict=("일치" if abs(d) <= 0.01 else "차이") if core else "병기"))
    RS = pd.DataFrame(rows); RS.to_csv(PA/"PA_C2_results.csv", index=False, encoding="utf-8-sig"); DG.to_csv(PA/"PA_C2_diagnostics.csv", index=False, encoding="utf-8-sig")
    print("\n[Post-hoc] PA-C2 결과(보유 논문만 대 전체)\n", RS.round(4).to_string(index=False))
    print("\n[Post-hoc] 진단\n", DG.round(4).to_string(index=False))
    print("※ 기간·통계별로 따로 읽고 합치지 않음. 소속은 국적 아님. S0~S8 판정 불변.")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as fh:
        fh.write(f"- {now()} | PA-C2 실행 | 정의: PA_C2_PLAN {sp['sha256'][:12]} | 결과: PA_C2_results.csv, PA_C2_diagnostics.csv | 본 결과 변경 여부: 없음\n")

try: {"freeze": freeze, "tag": tag, "run": run}[MODE]()
except Halt as e: print(f"⛔ 중단: {e}")