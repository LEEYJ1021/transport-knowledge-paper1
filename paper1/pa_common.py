# -*- coding: utf-8 -*-
# 사후분석 공통 모듈(동결·태그·실행 검증, S8/S4 입력 로더). 미실행 코드.
# 각 pa_*.py는 python3 pa_xxx.py freeze | tag | run [quick] 로 호출. 동결 후 이 파일과 스크립트 해시가 바뀌면 run이 중단됨.
import sys, json, re, hashlib, subprocess, warnings
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import rankdata
warnings.filterwarnings("ignore"); pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 400)

ROOT = Path.home()/"Research/Minnesota_Transport"; P1 = ROOT/"paper1"; PA = P1/"09_PA"; DATA = ROOT/"analysis_data/final"
S0, S1, S2, S3, S4, S5D, S6D, S8 = (P1/x for x in ["00_S0", "01_S1", "02_S2", "03_S3", "04_S4", "05_S5", "06_S6", "08_S8"])
now = lambda: pd.Timestamp.now().isoformat(timespec="seconds")
sha_b = lambda b: hashlib.sha256(b).hexdigest(); sha_f = lambda p: sha_b(Path(p).read_bytes())
tf = lambda s: s.astype(str).str.strip().str.lower().isin(["1", "1.0", "true", "t", "yes"]); bl = tf
git = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
class Halt(Exception): pass
spec_hash = lambda s: sha_b(json.dumps({k: v for k, v in s.items() if k not in ("sha256", "created", "refs")}, sort_keys=True, ensure_ascii=False).encode())
V2P = PA/"PA_0_PLAN_v2.json"; CL = PA/"PA_CHANGELOG.md"
INT = dict(road_deaths="death_rate", vehicles="veh_per1000", urban_pop="urban_share", transport_co2="co2_tr_pc")

def cl(line):
    t = CL.read_text(encoding="utf-8") if CL.exists() else ""
    with CL.open("a", encoding="utf-8") as f: f.write(("" if (not t or t.endswith("\n")) else "\n") + f"- {now()} | {line}\n")

def find_key(o, key):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == key: return v
            r = find_key(v, key)
            if r is not None: return r

def periods():
    """S4 동결 규칙 파일에서 main_contrast와 periods를 읽음(pa_b7a.py와 같은 방식)."""
    for f in sorted(P1.glob("0[0-4]_*/*PREREG*.json")):
        j = json.loads(f.read_text(encoding="utf-8")); mc, pr = find_key(j, "main_contrast"), find_key(j, "periods")
        if mc and pr and all(k in pr for k in mc): return mc[0], mc[1], {k: tuple(v) for k, v in pr.items()}
    raise Halt("main_contrast와 periods를 가진 S4 동결 규칙 파일을 찾지 못함")

def analysis_sets():
    """S4 분석 집합 F(76,984편)와 결측 집합 Mi(분석 저널 안). pa_b7a.py와 같은 정의."""
    W = pd.read_csv(DATA/"F1_papers.csv", low_memory=False); W["pid"] = W.pid.astype(str)
    EXC = set(pd.read_csv(S0/"EXCLUDE_PIDS_FROZEN.csv", dtype=str, encoding="utf-8-sig").pid)
    W = W[~W.pid.isin(EXC) & tf(W.in_sample) & W.year.between(2000, 2025)].copy(); W["ht"] = tf(W.has_topic) & W.topic150.notna()
    F, Mi = W[W.ht].copy(), W[~W.ht].copy()
    if len(F) != 76984: raise Halt(f"분석 집합 재현 실패: {len(F)} (76984여야 함)")
    F["topic"] = F.topic150.astype(int)
    topics = np.array(sorted(pd.read_csv(S3/"L7_topic_grade.csv").topic.astype(int))); venues = np.array(sorted(F.venue_short.unique()))
    return F, Mi[Mi.venue_short.isin(venues)], topics, venues

# ---------- S8 입력(pa_b8a.py와 같은 정의) ----------
def burden():
    Bt = pd.read_csv(S8/"burden_country_table.csv", keep_default_na=False, index_col=0); inc = Bt["income"].copy()
    Bt = Bt.drop(columns="income").apply(pd.to_numeric, errors="coerce"); Bt["income"] = inc; return Bt
def mass_raw():
    pm = S2/"country_mass_long.parquet"; M = pd.read_parquet(pm) if pm.exists() else pd.read_csv(S2/"country_mass_long.csv.gz", dtype={"pid": str})
    M["pid"] = M.pid.astype(str); M = M[(M.year >= 2007) & ~M.country.isin(["UNK", "ZZ_former"])]; return M[["pid", "year", "country", "w", "scheme", "variant"]]
def flags(SPEC):
    RX = {k: re.compile(v, re.I) for k, v in SPEC["domains"].items()}
    F1 = pd.read_csv(DATA/"F1_papers.csv", low_memory=False); F1["pid"] = F1.pid.astype(str)
    exf = S0/"EXCLUDE_PIDS_FROZEN.csv"; log = pd.read_csv(S0/"FREEZE_LOG.csv"); last = log[log.file == exf.name].iloc[-1]
    if sha_f(exf) != last.sha256: raise Halt("EXCLUDE_PIDS_FROZEN.csv 해시 불일치")
    F = F1[~F1.pid.isin(set(pd.read_csv(exf, dtype=str, encoding="utf-8-sig").pid))].copy(); F = F[F.year >= 2007].copy(); F = F[F.title.notna()]
    fl = pd.DataFrame({d: F.title.fillna("").str.contains(rx).values for d, rx in RX.items()}, index=F.index); fl["pid"] = F.pid.values; return fl

def pr(x, y, cols=(), rk=()):
    a, b = rankdata(x), rankdata(y)
    if not len(cols): return float(np.corrcoef(a, b)[0, 1])
    A = np.column_stack([np.ones(len(a))] + [rankdata(c) if r else np.asarray(c, float) for c, r in zip(cols, rk)])
    res = lambda v: v - A @ np.linalg.lstsq(A, v, rcond=None)[0]; return float(np.corrcoef(res(a), res(b))[0, 1])

def label(df, col, qh):
    cut = df[col].abs().quantile(2/3); big = df[col].abs() >= cut
    lab = ["small_change" if not b else ("growth" if d > 0 else "decline") + ("_highQ" if q else "_notHighQ") for b, d, q in zip(big, df[col], qh)]
    return pd.Series(lab, index=df.index), big, float(cut)

def run_pa(name, PLAN, run_fn, ref_files, why):
    BP = PA/f"PA_{name}_PLAN.json"; script = f"pa_{name.lower()}.py"
    mode = sys.argv[1] if len(sys.argv) > 1 else "freeze"; quick = "quick" in sys.argv[2:]
    try:
        if mode == "freeze":
            if not V2P.exists(): raise Halt("PA_0_PLAN_v2.json이 없습니다")
            h = spec_hash(PLAN); print(f"PA-{name} 계획 해시(예정)", h[:12])
            if BP.exists(): print("이미 동결:", "동일" if json.loads(BP.read_text(encoding="utf-8"))["sha256"] == h else "⛔ 다름"); return
            refs = {f.name: sha_f(f) for f in [V2P, P1/"pa_common.py", P1/script] + [Path(x) for x in ref_files] if Path(f).exists()}
            BP.write_text(json.dumps(dict(PLAN, created=now(), sha256=h, refs=refs), ensure_ascii=False, indent=1), encoding="utf-8")
            cl(f"PA-{name} 계획 동결(해시 {h[:12]}) | 사유: {why} | 이전에 생략을 권했던 항목은 연구자 요청으로 재개(침묵을 동의로 본 처리를 정정). 결과 미열람. QUICK은 재현 점검과 설계 정보만 | 본 결과 변경 여부: 없음")
            print("저장:", BP.name)
        elif mode == "tag":
            if not BP.exists(): raise Halt("먼저 freeze")
            t = f"PA-{name}-plan-{pd.Timestamp.now().strftime('%Y-%m-%d')}"
            if git("tag", "-l", t).stdout.strip(): print("이미 있음:", t); return
            r = git("add", "--", f"paper1/09_PA/PA_{name}_PLAN.json", "paper1/09_PA/PA_CHANGELOG.md", f"paper1/{script}", "paper1/pa_common.py"); print("add", r.returncode, r.stderr.strip())
            r = git("commit", "-m", f"PA-{name} plan freeze (before execution)"); print("commit", r.returncode, (r.stdout + r.stderr)[:200])
            r = git("tag", "-a", t, "-m", f"PA-{name} plan"); print("tag", r.returncode, r.stderr.strip()); print("※ 이어서 git push --follow-tags")
        elif mode == "run":
            if not BP.exists(): raise Halt("먼저 freeze")
            sp = json.loads(BP.read_text(encoding="utf-8"))
            if sp["sha256"] != spec_hash(sp) or sp["sha256"] != spec_hash(PLAN): raise Halt("동결 파일과 현재 계획이 다릅니다")
            if not git("tag", "-l", f"PA-{name}-plan-*").stdout.strip(): raise Halt("tag 단계를 먼저 실행하세요")
            for fn in ["pa_common.py", script]:
                if sp["refs"].get(fn) != sha_f(P1/fn): raise Halt(f"{fn}이 동결 시점과 다름(수정됐다면 v2 계획으로 분리하고 사유 기록)")
            run_fn(quick, sp)
            if not quick: cl(f"PA-{name} 실행 | 정의: PA_{name}_PLAN {sp['sha256'][:12]} | 결과: PA_{name}_*.csv | 본 결과 변경 여부: 없음")
        else: raise Halt("모드는 freeze | tag | run [quick]")
    except Halt as e: print(f"⛔ 중단: {e}")