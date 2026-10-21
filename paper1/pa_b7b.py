# -*- coding: utf-8 -*-
# PA-B7b: 임베딩 결측 논문에 제목 분류기 예측 토픽을 대입했을 때 S4 big 토픽 부호가 유지되는가. 결정적 계산. 미실행 코드.
# 사용: python3 pa_b7b.py freeze | tag | run quick | run   (tag 뒤에 git push --follow-tags)
# S0~S8 판정 불변. 모든 산출물 [Post-hoc].
import sys, json, hashlib, subprocess, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore"); pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 200)
MODE = sys.argv[1] if len(sys.argv) > 1 else "freeze"
QUICK = "quick" in sys.argv[2:]

ROOT = Path.home() / "Research/Minnesota_Transport"; P1 = ROOT/"paper1"; PA = P1/"09_PA"; S0, S2, S3, S4 = P1/"00_S0", P1/"02_S2", P1/"03_S3", P1/"04_S4"; DATA = ROOT/"analysis_data/final"
now = lambda: pd.Timestamp.now().isoformat(timespec="seconds")
sha_b = lambda b: hashlib.sha256(b).hexdigest(); sha_f = lambda p: sha_b(Path(p).read_bytes())
tf = lambda s: s.astype(str).str.strip().str.lower().isin(["1", "1.0", "true", "t", "yes"])
git = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
class Halt(Exception): pass
spec_hash = lambda s: sha_b(json.dumps({k: v for k, v in s.items() if k not in ("sha256", "created", "refs")}, sort_keys=True, ensure_ascii=False).encode())
V2P, BP = PA/"PA_0_PLAN_v2.json", PA/"PA_B7b_PLAN.json"

PLAN = dict(
    version=1, parent="PA_0_PLAN_v2.json",
    status="사후 명세(PA-B7 중 분류기 대입 (b)만). S4 결과, pa_b7a.py, title_classifier_report.md(교차검증 정확도 0.508, tau 격자별 적용률·정확도), title_pred_missing_topic.csv의 기간별 적용률(0.348/0.374/0.369/0.408/0.450)과 pmax 중앙값은 열람한 상태. PA-B7b 결과 미열람. B7a(뒤집힘 배수), S4 IPW와 보완 관계. S0~S8 판정 불변.",
    data="B7a와 같은 분석 집합: F1_papers.csv에서 EXCLUDE_PIDS_FROZEN 제외, in_sample 참, 연도 2000~2025, has_topic 참 and topic150 있음(76,984편). 결측 집합 = 나머지 중 분석 저널 안. 대입 후보 = title_pred_missing_topic.csv(S2 분류기, 14,810편)와 pid가 겹치는 결측 논문. 연도·저널은 F1의 값 사용. 기간·대비는 S4 동결 규칙의 periods, main_contrast",
    imputation="선택된 결측 논문을 (저널, 기간, 예측 토픽) 카운트에 +1. 예측 토픽은 L7_topic_grade의 정렬된 토픽 목록 위치로 변환(배열 축은 149개, 토픽 ID는 0~149에서 18이 빠짐). 대입되지 않은 결측 논문은 분모에서 제외",
    share="share_full(t, 기간) = (관측 카운트 + 대입 카운트) / (관측 논문 수 + 대입 논문 수), 저널 합산. delta_full = share_full(후기) - share_full(전기). 관측 delta는 S4와 같은 저널 합산 몫의 차",
    scenarios={"s1": "title_pred_missing_topic.csv의 use_in_sensitivity 플래그(pmax>=0.5 and 토픽 F1>=0.3, S2 동결 외 사전 명시)", "s2": "pmax>=tau_s2(F1 하한 없음)", "s3": "pmax>=tau_s3(적용률 높음)", "s4": "pmax>=tau_s4(정확도 우선)"},
    tau={"s2": 0.5, "s3": 0.3, "s4": 0.7},
    scope="S4 big 토픽(topic_quadrants.csv의 big 참, 50개). 각 토픽의 delta_full 부호가 관측 delta 부호와 같은지. 대입 후 big 라벨·4분면 변화는 범위 밖(B7a와 동일)",
    stats="시나리오별 기간별 결측 대비 대입률(설계 정보), big 토픽 부호 유지 비율, 유지 실패 토픽 목록, |delta_full|/|delta| 중앙값(감쇠 정도)",
    reading="시나리오별 big 토픽 중 부호 유지 비율 >=0.90 '유지', 0.70~0.90 '부분', <0.70 '민감'. 시나리오를 합치지 않음. B7a와 같은 임계값이며 임의의 동결 사양",
    reproduce_check="(a) 분석 집합 76,984편, (b) 관측 delta가 topic_quadrants.csv와 1e-9 이내, (c) CSV pid의 99% 이상이 결측 집합(분석 저널 안)에 포함, (d) pred_topic이 모두 L7 토픽 목록 안. 하나라도 어긋나면 중단",
    caveat="교차검증 정확도는 결측 논문에 대한 정확도가 아님(분포가 다를 수 있음). 예측확률은 보정되지 않았고 pmax만 있어 부드러운 대입 불가. 확신 높은 예측만 대입하므로 F1 높은 토픽이 더 채워지고, 기간별 대입률이 다름(초기 낮음). 오분류가 몫을 흐리게 해 감쇠 쪽으로 작용할 수 있음. 인과 해석 아님",
    forbidden="결과를 본 뒤 시나리오·tau·판독 임계값 변경(변경 시 v2 계획으로 분리하고 사유 기록)")

def freeze():
    if not V2P.exists(): raise Halt("PA_0_PLAN_v2.json이 없습니다")
    h = spec_hash(PLAN); print("PA-B7b 계획 해시(예정)", h[:12])
    if BP.exists(): print("이미 동결:", "동일" if json.loads(BP.read_text(encoding="utf-8"))["sha256"] == h else "⛔ 다름"); return
    refs = {f.name: sha_f(f) for f in [V2P, S4/"topic_quadrants.csv", P1/"pa_b7a.py", DATA/"F1_papers.csv", S2/"title_pred_missing_topic.csv", S2/"title_classifier_report.md"] if f.exists()}
    BP.write_text(json.dumps(dict(PLAN, created=now(), sha256=h, refs=refs), ensure_ascii=False, indent=1), encoding="utf-8")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as f:
        f.write(f"\n- {now()} | PA-B7b 계획 동결(해시 {h[:12]}) | 사유: 결측 경계를 제목 분류기 대입으로 점검(B7a 보완). 분류기 보고서(정확도·적용률)와 CSV의 기간별 적용률, pa_b7a.py 열람 상태, PA-B7b 결과 미열람. QUICK은 재현 점검과 기간별 대입 편수만 | 본 결과 변경 여부: 없음\n")
    print("저장: PA_B7b_PLAN.json")

def tag():
    if not BP.exists(): raise Halt("먼저 freeze")
    t = f"PA-B7b-plan-{pd.Timestamp.now().strftime('%Y-%m-%d')}"
    if git("tag", "-l", t).stdout.strip(): print("이미 있음:", t); return
    r = git("add", "--", "paper1/09_PA/PA_B7b_PLAN.json", "paper1/09_PA/PA_CHANGELOG.md", "paper1/pa_b7b.py"); print("add", r.returncode, r.stderr.strip())
    r = git("commit", "-m", "PA-B7b plan freeze (before execution)"); print("commit", r.returncode, (r.stdout + r.stderr)[:200])
    r = git("tag", "-a", t, "-m", "PA-B7b plan"); print("tag", r.returncode, r.stderr.strip()); print("※ 이어서 git push --follow-tags")

def find_key(o, key):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == key: return v
            r = find_key(v, key)
            if r is not None: return r

def run():
    if not BP.exists(): raise Halt("먼저 freeze")
    sp = json.loads(BP.read_text(encoding="utf-8"))
    if sp["sha256"] != spec_hash(sp) or sp["sha256"] != spec_hash(PLAN): raise Halt("동결 파일과 현재 계획이 다릅니다")
    if not git("tag", "-l", "PA-B7b-plan-*").stdout.strip(): raise Halt("tag 단계를 먼저 실행하세요")
    spec = None
    for f in sorted(P1.glob("0[0-4]_*/*PREREG*.json")):
        j = json.loads(f.read_text(encoding="utf-8")); mc, pr = find_key(j, "main_contrast"), find_key(j, "periods")
        if mc and pr and all(k in pr for k in mc): spec = (f.name, mc, pr); break
    if spec is None: raise Halt("main_contrast와 periods를 가진 S4 동결 규칙 파일을 찾지 못함")
    fname, (c0, c1), PR = spec; P = {k: tuple(v) for k, v in PR.items()}; print(f"[규칙 파일] {fname} | main_contrast {c0}->{c1} | {P[c0]}, {P[c1]}")
    W = pd.read_csv(DATA/"F1_papers.csv", low_memory=False); W["pid"] = W.pid.astype(str)
    EXC = set(pd.read_csv(S0/"EXCLUDE_PIDS_FROZEN.csv", dtype=str, encoding="utf-8-sig").pid)
    W = W[~W.pid.isin(EXC) & tf(W.in_sample) & W.year.between(2000, 2025)].copy(); W["ht"] = tf(W.has_topic) & W.topic150.notna()
    F, Mi = W[W.ht].copy(), W[~W.ht].copy()
    if len(F) != 76984: raise Halt(f"분석 집합 재현 실패: {len(F)} (76984여야 함)")
    F["topic"] = F.topic150.astype(int)
    topics = np.array(sorted(pd.read_csv(S3/"L7_topic_grade.csv").topic.astype(int))); venues = np.array(sorted(F.venue_short.unique()))
    Mi = Mi[Mi.venue_short.isin(venues)]; pos = {int(t): i for i, t in enumerate(topics)}
    tp = pd.read_csv(S2/"title_pred_missing_topic.csv"); tp["pid"] = tp.pid.astype(str)
    if not tp.pred_topic.isin(topics).all(): raise Halt("pred_topic이 L7 토픽 목록 밖에 있음")
    M2 = Mi[["pid", "year", "venue_short"]].merge(tp[["pid", "pred_topic", "pmax", "use_in_sensitivity"]], on="pid", how="inner")
    cov = len(M2)/len(tp)
    if cov < 0.99: raise Halt(f"CSV pid 중 결측 집합에 포함된 비율 {cov:.3f} < 0.99")
    M2["tpos"] = M2.pred_topic.map(pos).astype(int); M2["flag"] = tf(M2.use_in_sensitivity)
    tau = PLAN["tau"]; SC = {"s1": M2.flag, "s2": M2.pmax >= tau["s2"], "s3": M2.pmax >= tau["s3"], "s4": M2.pmax >= tau["s4"]}
    def base(lo, hi):
        d = F[F.year.between(lo, hi)]; C = pd.crosstab(d.venue_short, d.topic).reindex(index=venues, columns=topics, fill_value=0).values.astype(float)
        return C.sum(0), float(C.sum())
    def imp(mask, lo, hi):
        d = M2[mask & M2.year.between(lo, hi)]; return np.bincount(d.tpos.values, minlength=len(topics)).astype(float), float(len(d))
    (a0, n0), (a1, n1) = base(*P[c0]), base(*P[c1])
    Q = pd.read_csv(S4/"topic_quadrants.csv").set_index("topic"); delta_obs = a1/n1 - a0/n0
    if np.abs(delta_obs - Q.loc[topics, "delta"].values).max() > 1e-9: raise Halt("관측 delta가 topic_quadrants.csv와 다름")
    rows = []
    for nm, mk in SC.items():
        for c in (c0, c1):
            b, m = imp(mk, *P[c]); nmiss = int(Mi.year.between(*P[c]).sum()); rows.append(dict(scenario=nm, period=c, n_missing=nmiss, n_with_pred=int(M2.year.between(*P[c]).sum()), n_imputed=int(m), rate_of_missing=m/nmiss if nmiss else np.nan))
    IM = pd.DataFrame(rows)
    print(f"[재현 OK] 분석 집합 76,984, 관측 delta, CSV pid 포함 비율 {cov:.4f} | 위치 매핑(L7 정렬 목록) 사용")
    print("[기간별 대입 편수(설계 정보)]\n", IM.round(3).to_string(index=False))
    if QUICK: print("\n[QUICK] 재현 점검과 기간별 대입 편수만 출력. 결과 통계는 계산·출력하지 않음."); return
    D = {}
    for nm, mk in SC.items():
        b0, m0 = imp(mk, *P[c0]); b1, m1 = imp(mk, *P[c1]); D[nm] = (a1 + b1)/(n1 + m1) - (a0 + b0)/(n0 + m0)
    big = Q.loc[topics, "big"].values.astype(bool); sgn = np.sign(delta_obs)
    R = pd.DataFrame(dict(topic=topics, grade=Q.loc[topics, "grade"].values, quadrant=Q.loc[topics, "quadrant"].values, big=big, delta=delta_obs))
    for nm in SC: R[f"delta_full_{nm}"] = D[nm]; R[f"kept_{nm}"] = np.sign(D[nm]) == sgn
    R.to_csv(PA/"PA_B7b_results.csv", index=False, encoding="utf-8-sig"); IM.to_csv(PA/"PA_B7b_imputed_by_period.csv", index=False, encoding="utf-8-sig")
    B = R[R.big]; out = []
    for nm in SC:
        share = float(B[f"kept_{nm}"].mean()); v = "유지" if share >= 0.90 else ("부분" if share >= 0.70 else "민감")
        out.append(dict(scenario=nm, kept_share=share, n_not_kept=int((~B[f"kept_{nm}"]).sum()), atten_median=float((B[f"delta_full_{nm}"].abs()/B.delta.abs()).median()), 판독=v))
    O = pd.DataFrame(out); print(f"\n[Post-hoc] PA-B7b big 토픽 {len(B)}개\n[동결 판독]\n", O.round(3).to_string(index=False)); O.to_csv(PA/"PA_B7b_summary.csv", index=False, encoding="utf-8-sig")
    for nm in SC:
        X = B[~B[f"kept_{nm}"]]
        if len(X): print(f"\n[부호 유지 실패 big 토픽 {nm}]\n", X[["topic", "grade", "quadrant", "delta", f"delta_full_{nm}"]].round(4).to_string(index=False))
    print("※ 분류기 대입 민감도이며 경계가 아님. 시나리오를 합치지 않음. S0~S8 판정 불변.")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as fh:
        fh.write(f"- {now()} | PA-B7b 실행 | 정의: PA_B7b_PLAN {sp['sha256'][:12]} | 결과: PA_B7b_*.csv | 본 결과 변경 여부: 없음\n")

try: {"freeze": freeze, "tag": tag, "run": run}[MODE]()
except Halt as e: print(f"⛔ 중단: {e}")
