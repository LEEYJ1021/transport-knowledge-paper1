# -*- coding: utf-8 -*-
# =====================================================================================
# 논문 1 사후 교정분석 (PA) 단일 셀. 미실행 코드: QUICK=True로 먼저 시험.
# MODE: "freeze"(PA_0_PLAN.json 동결, 결과 미열람) -> "tag"(커밋·태그) -> "check"(PA-0 재현성 점검, 읽기 전용) -> "a1"(PA-A1 검정력 곡선)
# 원칙: S0~S8 판정 불변. 모든 산출물·표 제목에 [Post-hoc]. 해석은 '함께 움직인다'까지.
# 주의: S5 탐지기(s5_lib)를 첨부에서 못 봤으므로, a1은 자체 대체 탐지기(Hellinger 좌표 + 동적계획 분할)를 씀.
#       S5와 정확히 같은 통계가 아님. USE_S5_LIB 훅에 s5_lib 함수를 연결하면 그쪽을 씀.
# =====================================================================================
import json, hashlib, subprocess, warnings
from pathlib import Path
import numpy as np, pandas as pd
from scipy.spatial.distance import jensenshannon
warnings.filterwarnings("ignore"); pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 200)

MODE = "tag"       # "freeze" | "tag" | "check" | "a1"
QUICK = True          # True: 귀무 B=200, 검정력 B=40 (파일명 _QUICK)

ROOT = Path.home() / "Research/Minnesota_Transport"
DATA, S0, S1, S3, PA = ROOT/"analysis_data/final", ROOT/"paper1/00_S0", ROOT/"paper1/01_S1", ROOT/"paper1/03_S3", ROOT/"paper1/09_PA"
now = lambda: pd.Timestamp.now().isoformat(timespec="seconds")
sha_b = lambda b: hashlib.sha256(b).hexdigest(); sha_f = lambda p: sha_b(Path(p).read_bytes())
tf = lambda s: s.astype(str).str.strip().str.lower().isin(["1", "1.0", "true", "t", "yes"])
git = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
class Halt(Exception): pass

# ------------------------------ PA_0_PLAN (실행 전 동결) ------------------------------
PLAN = dict(
    version=1, seed=2026,
    status="사후분석. S0~S8 결과 열람 후 설계. 탐색적, 다중성 보정 없음. 사전 명시 판정(통과/실패)은 변경하지 않음.",
    n_pa=14, core_claim_pa=["PA-A1", "PA-A2", "PA-B2"],
    core_note="지침서 0절은 A1·A2·B1(문구 작업)을, 우선순위 절은 A1·A2·B2를 권장해 불일치. 분석 3개는 A1·A2·B2로 둠(B1은 A1 결과로 정하는 문구).",
    items={
        "PA-A1": "N2 검정력 곡선 + 구간별 상수 대 선형 BIC", "PA-A2": "S6 진입 우세의 구성 방어(ID 대조, 진입 정의 2종, 부트스트랩 교정)",
        "PA-A3": "S7 국가 미상 교정, 균등 4구간, 중국 제외 HHI", "PA-B1": "체제 서사 철회 문구 확정(PA-A1 연동, 분석 아님)",
        "PA-B2": "2020 변화점 아티팩트 분리(하향 추출, 구성 토픽)", "PA-B3": "신생 핵심 집합(n_defs>=3)과 D1'", "PA-B4": "F1+F3 이분 등급 재추정",
        "PA-B5": "S4 안정성 Wilson 구간, 분위 컷 곡선, 방향 축만", "PA-B6": "위험군 독립 정답(ORCID, 수작업 50쌍)", "PA-B7": "결측 경계 분석, 분류기 대입, 저널x연도 IPW",
        "PA-B8": "미달 4도메인 부록 정렬, 사전 v2(새 25편)", "PA-B9": "소득군 내 상관, 더미 통제, 공급 정의 민감도", "PA-C1": "S6x S7 교차(중국 소속 신규 제외 분해)", "PA-C2": "S7 국가 몫을 임베딩 보유 논문만으로 재계산"},
    pa_a1=dict(window=[2007, 2025], samples=["all", "fixed14", "within"], delta_x=[0.5, 1, 2, 3], t_star=[2008, 2012, 2015, 2020],
               B_null=1000, B_power=200, null="N2 = 표본별 선형 추세 적합 + 다항 표본 잡음", alpha=0.05,
               baseline="선형 추세 적합 확률(점프 없음)에 점프를 삽입. 점프 크기 = delta x 관측 2020 점프(JS 거리, 전3년 대 후3년 평균 비중), 삽입 방향 = 관측 2020 이후 평균 - 이전 평균",
               statistic="R = 1 - cost(k*)/cost(1). Hellinger 좌표 제약 분할(min_len 3, k<=6), k* = argmin cost_k + lam(k-1), lam = pen_c*cost_1/T, pen_c=0.5(대체 탐지기 값)",
               reading="power(1x)>=0.8: 연속 변화 증거로 강화 / power(1x)<0.5: '체제 전환 여부 판정 불가'로 리프레이밍 / 사이: 둘 다 쓰지 않고 곡선으로만 보고",
               within_rule="저널 내: 전 연도 연도당 5편 이상인 저널만, 고정 저널 비중 고정(wbar)",
               bic_compare="Hellinger 좌표 상위 5 PC에서 구간별 상수 대 구간별 선형, 최소 구간 3, k<=6, BIC"),
    forbidden="PA 결과로 S0~S8 판정 변경, PA에서 유리한 정의만 본문 게재",
    report_marker="[Post-hoc]", changelog="PA_CHANGELOG.md")
spec_hash = lambda s: sha_b(json.dumps({k: v for k, v in s.items() if k not in ("sha256", "created", "refs")}, sort_keys=True, ensure_ascii=False).encode())
PP = PA/"PA_0_PLAN.json"

def freeze():
    PA.mkdir(parents=True, exist_ok=True); h = spec_hash(PLAN); print("PA-0 해시(예정)", h[:12])
    if PP.exists(): old = json.loads(PP.read_text(encoding="utf-8")); print("이미 동결:", "동일" if old["sha256"] == h else "⛔ 다름(새 버전으로 분리하고 CHANGELOG에 사유)"); return
    refs = {f.name: sha_f(f) for f in [S0/"PREREG.json", S3/"L7_topic_grade.csv", ROOT/"paper1/07_S7/S7_0_PREREG.json", ROOT/"paper1/08_S8/S8_0_PREREG_v2.json"] if f.exists()}
    PP.write_text(json.dumps(dict(PLAN, created=now(), sha256=h, refs=refs), ensure_ascii=False, indent=1), encoding="utf-8")
    (PA/"PA_CHANGELOG.md").write_text(f"# PA_CHANGELOG\n\n- {now()} | PA-0 계획 동결(해시 {h[:12]}) | 목적: 사후분석 14개 항목·A1 정의·판독 규칙을 실행 전에 고정 | 본 결과 변경 여부: 없음\n", encoding="utf-8")
    print("저장: PA_0_PLAN.json, PA_CHANGELOG.md | refs", list(refs))

def tag():
    if not PP.exists(): raise Halt("먼저 freeze")
    t = f"PA-0-plan-{pd.Timestamp.now().strftime('%Y-%m-%d')}"
    if git("tag", "-l", t).stdout.strip(): print("이미 있음:", t); return
    r = git("add", "--", "paper1/09_PA"); print("add", r.returncode, r.stderr.strip())
    r = git("commit", "-m", "PA-0 plan freeze (post-hoc, before execution)"); print("commit", r.returncode, (r.stdout + r.stderr)[:200])
    r = git("tag", "-a", t, "-m", "PA-0 plan"); print("tag", r.returncode, r.stderr.strip())

def check():   # PA-0 재현성 (읽기 전용: 삭제·수정 없음)
    print("[S4 코드]", {f: (ROOT/"paper1"/f).exists() for f in ["s4_main.py", "s4_6_rotation.py", "s4_6b_floor_check.py"]})
    for t in ["S4-main-2026-10-16", "S4-final-2026-10-16"]:
        print(f"\n[git show --stat {t}]\n", git("show", "--stat", "--format=%h %s (%ad)", t).stdout[:600])
    print("[git status paper1/]\n", git("status", "--short", "--", "paper1/").stdout[:1500] or "(깨끗함)")
    print("[원격 태그 미푸시 점검: 로컬 태그]", git("tag", "--sort=-creatordate").stdout.split()[:12])
    print("[origin 태그]", git("ls-remote", "--tags", "origin").stdout[:800] or "(원격 태그 없음 또는 origin 미설정)")
    print("[oa_raw 백업 존재]", [str(p) for p in (ROOT/"archive").glob("oa_raw_*.tar.gz")] if (ROOT/"archive").exists() else "archive/ 없음")
    print("※ 태그 정정은 직접: 가리키는 커밋 확인 -> git tag -d <이름> -> CHANGELOG에 정정 기록 -> 재태그 -> git push --follow-tags")

# ------------------------------ PA-A1 ------------------------------
USE_S5_LIB = None   # 예: from s5_lib import detect_R; USE_S5_LIB = detect_R  (시그니처 f(shares[T,K], years) -> float)
def load_F1X():
    F1 = pd.read_csv(DATA/"F1_papers.csv", low_memory=False); F1["pid"] = F1.pid.astype(str)
    exf = S0/"EXCLUDE_PIDS_FROZEN.csv"; log = pd.read_csv(S0/"FREEZE_LOG.csv"); last = log[log.file == exf.name].iloc[-1]
    if sha_f(exf) != last.sha256: raise Halt("EXCLUDE_PIDS_FROZEN.csv 해시 불일치")
    return F1[~F1.pid.isin(set(pd.read_csv(exf, dtype=str, encoding="utf-8-sig").pid))].copy()

def seg_costs(X, minlen=3, kmax=6):
    T = len(X); cs = np.vstack([np.zeros(X.shape[1]), np.cumsum(X, 0)]); sq = np.r_[0, np.cumsum((X**2).sum(1))]
    S = cs[None, :, :] - cs[:, None, :]; a = np.arange(T+1); L = (a[None, :] - a[:, None]).astype(float)
    C = (sq[None, :] - sq[:, None]) - (S**2).sum(2)/np.where(L > 0, L, 1); C[L < minlen] = np.inf
    best = np.full((kmax+1, T+1), np.inf); best[0, 0] = 0
    for k in range(1, kmax+1): best[k] = np.min(best[k-1][:, None] + C, axis=0)
    return best[:, T]
def detect_R(shares, years, pen_c=0.5, kmax=6):
    if USE_S5_LIB: return USE_S5_LIB(shares, years)
    c = seg_costs(np.sqrt(shares), 3, kmax); ks = np.arange(1, kmax+1); ok = np.isfinite(c[1:]); lam = pen_c*c[1]/len(shares)
    crit = np.where(ok, c[1:] + lam*(ks-1), np.inf); k = int(ks[np.argmin(crit)]); return 1 - c[k]/c[1]

def make_panel(sample, tops):
    tix = {t: i for i, t in enumerate(tops)}; K = len(tops); yrs = np.arange(2007, 2026)
    F = load_F1X(); F = F[F.year.between(2007, 2025) & tf(F.has_topic) & F.topic150.notna()]; F = F.assign(k=F.topic150.astype(int).map(tix)).dropna(subset=["k"])
    if sample == "fixed14":
        FIXED = set(json.loads((S0/"PREREG.json").read_text(encoding="utf-8"))["event"]["fixed_venues"]); F = F[F.venue_short.isin(FIXED)]
    if sample == "within":
        n = F.groupby(["venue_short", "year"]).size().unstack(fill_value=0).reindex(columns=yrs, fill_value=0); vs = list(n.index[(n >= 5).all(1)]); F = F[F.venue_short.isin(vs)]
    else: vs = ["ALL"]; F = F.assign(venue_short="ALL")
    C = np.zeros((len(yrs), len(vs), K)); np.add.at(C, (F.year.values-2007, F.venue_short.map({v: i for i, v in enumerate(vs)}).values, F.k.astype(int).values), 1)
    n = C.sum(2); W = (n/n.sum(1, keepdims=True)).mean(0); W = W/W.sum()    # 고정 저널 비중(within) 또는 [1]
    return yrs, C, n.astype(int), W, len(F)
def agg(P, W): return np.tensordot(P, W, axes=([1], [0])) if False else (P*W[None, :, None]).sum(1)
def draw(P, n, W, rng):
    S = np.zeros((P.shape[0], P.shape[2]))
    for y in range(P.shape[0]):
        for j in range(P.shape[1]):
            if n[y, j] > 0: S[y] += W[j]*rng.multinomial(n[y, j], P[y, j]/P[y, j].sum())/n[y, j]
    return S/W.sum()
def jump(S, i): pre, post = S[max(0, i-3):i].mean(0), S[i:i+3].mean(0); return float(jensenshannon(pre, post))

def a1():
    if not PP.exists(): raise Halt("먼저 freeze")
    sp = json.loads(PP.read_text(encoding="utf-8"))
    if sp["sha256"] != spec_hash(sp) or sp["sha256"] != spec_hash(PLAN): raise Halt("동결 파일과 현재 PLAN이 다릅니다(사후 변경 금지)")
    cfg = PLAN["pa_a1"]; sfx = "_QUICK" if QUICK else ""; Bn = 200 if QUICK else cfg["B_null"]; Bp = 40 if QUICK else cfg["B_power"]
    rng = np.random.default_rng(PLAN["seed"]); tops = np.array(sorted(pd.read_csv(S3/"L7_topic_grade.csv").topic.astype(int))); rows, info, bic_rows = [], [], []
    for sample in cfg["samples"]:
        yrs, C, n, W, npap = make_panel(sample, tops); T, J, K = C.shape; Pobs = np.divide(C, n[:, :, None], out=np.full(C.shape, 1.0/K), where=n[:, :, None] > 0)
        coef = np.polyfit(yrs, Pobs.reshape(T, -1), 1); Ptr = np.clip((coef[0]*yrs[:, None] + coef[1]).reshape(Pobs.shape), 1e-9, None); Ptr /= Ptr.sum(2, keepdims=True)
        Sobs, Str = agg(Pobs, W), agg(Ptr, W); i20 = list(yrs).index(2020); Jobs = jump(Sobs, i20); d = Sobs[i20:].mean(0) - Sobs[:i20].mean(0)
        Robs = detect_R(Sobs, yrs); Rnull = np.array([detect_R(draw(Ptr, n, W, rng), yrs) for _ in range(Bn)]); q95 = float(np.quantile(Rnull, 1-cfg["alpha"])); pobs = float((Rnull >= Robs).mean())
        info.append(dict(sample=sample, n_papers=npap, n_venues=J, J_obs_2020=Jobs, R_obs=Robs, null_q95=q95, p_N2_this_detector=pobs)); print(f"\n[{sample}] 논문 {npap:,}, 저널 {J}, 관측 2020 점프(JS) {Jobs:.4f}, R_obs {Robs:.3f}, 귀무 95% {q95:.3f}, p(이 탐지기) {pobs:.3f}")
        for ts in cfg["t_star"]:
            it = list(yrs).index(ts); base_j = jump(Str, it)
            for dx in cfg["delta_x"]:
                target = base_j + dx*Jobs; lo, hi = 0.0, 2.0/np.abs(d).max()
                def inj(a):
                    P = Ptr.copy(); P[it:] = np.clip(P[it:] + a*d[None, None, :], 1e-9, None); return P/P.sum(2, keepdims=True)
                if jump(agg(inj(hi), W), it) < target: rows.append(dict(sample=sample, t_star=ts, delta_x=dx, power=np.nan, note="목표 점프 도달 불가")); continue
                for _ in range(40):
                    mid = (lo+hi)/2; lo, hi = (mid, hi) if jump(agg(inj(mid), W), it) < target else (lo, mid)
                Pi = inj(hi); Rs = np.array([detect_R(draw(Pi, n, W, rng), yrs) for _ in range(Bp)])
                rows.append(dict(sample=sample, t_star=ts, delta_x=dx, power=float((Rs > q95).mean()), R_mean=float(Rs.mean()), jump_target=target, jump_base=base_j, note=""))
        # 구간별 상수 대 선형 BIC (상위 5 PC)
        Z = np.sqrt(Sobs); Z = Z - Z.mean(0); U, s, Vt = np.linalg.svd(Z, full_matrices=False); Y = (U*s)[:, :5]; N = Y.size
        def seg_rss(lin):
            R = np.full((T+1, T+1), np.inf)
            for a_ in range(T+1):
                for b_ in range(a_+3, T+1):
                    y = Y[a_:b_]; x = np.arange(b_-a_); A = np.c_[np.ones_like(x), x] if lin else np.ones((len(x), 1)); R[a_, b_] = ((y - A @ np.linalg.lstsq(A, y, rcond=None)[0])**2).sum()
            best = np.full((7, T+1), np.inf); best[0, 0] = 0
            for k in range(1, 7): best[k] = np.min(best[k-1][:, None] + R, axis=0)
            return best[:, T]
        for name, lin in [("constant", False), ("linear", True)]:
            rs = seg_rss(lin)
            for k in range(1, 7):
                if np.isfinite(rs[k]): bic_rows.append(dict(sample=sample, model=name, k=k, rss=rs[k], bic=N*np.log(rs[k]/N + 1e-12) + (k*5*(2 if lin else 1) + (k-1))*np.log(N)))
    PW, IN, BC = pd.DataFrame(rows), pd.DataFrame(info), pd.DataFrame(bic_rows)
    PW.to_csv(PA/f"PA_A1_power_curve{sfx}.csv", index=False, encoding="utf-8-sig"); IN.to_csv(PA/f"PA_A1_observed{sfx}.csv", index=False, encoding="utf-8-sig"); BC.to_csv(PA/f"PA_A1_bic{sfx}.csv", index=False, encoding="utf-8-sig")
    print("\n[Post-hoc] PA-A1 검정력(행: 표본 x t*, 열: delta x 관측 점프)\n", PW.pivot_table(index=["sample", "t_star"], columns="delta_x", values="power").round(2).to_string())
    one = PW[PW.delta_x == 1].groupby("sample").power.agg(["min", "median", "max"]).round(2); print("\n[1배 점프 검정력 요약]\n", one.to_string())
    for sname, r in one.iterrows():
        v = "강화(연속 변화 증거)" if r["min"] >= 0.8 else ("리프레이밍(판정 불가)" if r["median"] < 0.5 else "곡선으로만 보고(0.5~0.8 구간 또는 t*별 혼재)"); print(f"  {sname}: 사전 판독 규칙 → {v}")
    print("\n[Post-hoc] BIC 최솟값(표본별 상수 대 선형)\n", BC.loc[BC.groupby(["sample", "model"]).bic.idxmin()].round(1).to_string(index=False))
    print("\n※ 대체 탐지기·5 PC·within 정의는 S5와 같지 않음. 규칙 판독(min/median)은 PLAN의 reading을 코드로 옮긴 것이며, 경계 사례는 사람이 곡선을 보고 판단. S0~S8 판정은 바꾸지 않음.")
    if not QUICK:
        with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as f: f.write(f"- {now()} | PA-A1 | 목적: N2 검정력 곡선 | 정의: PA_0_PLAN {sp['sha256'][:12]} | 결과: PA_A1_*.csv | 본 결과 변경 여부: 없음\n")

try: {"freeze": freeze, "tag": tag, "check": check, "a1": a1}[MODE]()
except Halt as e: print(f"⛔ 중단: {e}")