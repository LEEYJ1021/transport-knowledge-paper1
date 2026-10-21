# -*- coding: utf-8 -*-
# PA-B4b: S4 4분면 라벨을 F1+F3 통과 145개 토픽의 big 컷으로 재계산(delta·within·quality_high는 기존 값). 결정적. 미실행 코드.
# MODE: "freeze" -> "tag" -> (git push --follow-tags) -> "run"(QUICK=True: 재현 점검만) -> "run"(QUICK=False)
# S0~S8 판정 불변. 모든 산출물 [Post-hoc].
import json, hashlib, subprocess, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore"); pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 200)
MODE = "run"
QUICK = False

ROOT = Path.home() / "Research/Minnesota_Transport"; P1 = ROOT/"paper1"; PA = P1/"09_PA"; S3, S4 = P1/"03_S3", P1/"04_S4"
now = lambda: pd.Timestamp.now().isoformat(timespec="seconds")
sha_b = lambda b: hashlib.sha256(b).hexdigest(); sha_f = lambda p: sha_b(Path(p).read_bytes())
bl = lambda s: s.astype(str).str.strip().str.lower().isin(["1", "1.0", "true", "t", "yes"])
git = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
class Halt(Exception): pass
spec_hash = lambda s: sha_b(json.dumps({k: v for k, v in s.items() if k not in ("sha256", "created", "refs")}, sort_keys=True, ensure_ascii=False).encode())
V2P, BP = PA/"PA_0_PLAN_v2.json", PA/"PA_B4b_PLAN.json"

PLAN = dict(
    version=1, parent="PA_0_PLAN_v2.json",
    status="사후 명세(PA-B4의 S4 부분). s4_main.py 80~100행(big=|x|의 2/3 분위 이상, quality_high=q_mean>0.5 and q_lo>0.5), S4 요약(안정성 0.70/0.69), PA-B5·B4 결과는 열람한 상태. PA-B4b 결과 미열람. S0~S8 판정 불변.",
    grade_def="L7_topic_grade.csv의 F1, F3 열(True=실패). 통과 = 둘 다 False. 재현 점검: 정확히 145개",
    option="(b): delta, within, quality_high는 topic_quadrants.csv 값 그대로(149개 토픽 기준 몫). big 컷만 통과 145개 토픽의 |delta|(또는 |within|)의 2/3 분위(pandas quantile, 선형 보간)로 재계산. 질 지표는 재추정하지 않음",
    labels="s4_main.py label()과 동일: small_change 또는 (growth|decline)+(_highQ|_notHighQ). 총변화 기준 quadrant, 저널 내 성분 기준 quadrant_within",
    stats="(1) 통과 토픽 중 원본 big의 새 컷 big 유지율과 같은 4분면 라벨 유지율, 새 컷에서 새로 big이 된 토픽 수, (2) 안정성 = big 토픽 중 quadrant==quadrant_within 비율을 전체와 A등급 각각, 원본(같은 145개 부분집합 기준) 대비, (3) 제외 4개 토픽의 원본 big 여부와 라벨",
    reading="판독1: 원본 big 통과 토픽의 같은 라벨 유지율 >=0.95 이면 '둔감', 아니면 '민감'. 판독2: 안정성(전체)·안정성(A) 변화 모두 |.|<=0.03이면 '둔감', 아니면 '민감'. 두 판독을 합치지 않음. 임계값은 임의의 동결 사양",
    reproduce_check="(a) 통과 토픽 145개, (b) 149개 전체에서 재계산한 big, quadrant, quadrant_within이 topic_quadrants.csv와 전부 일치, (c) 전체 안정성 round 2자리 0.70, A등급 0.69. 하나라도 어긋나면 중단",
    caveat="제외 토픽이 4개뿐이라 약한 시험. 몫을 재정규화하지 않아 145개 기준 몫이 아님. 질 라벨은 149개 기준 인용 백분위 구간 그대로. 등급의 타당성은 검증하지 않음",
    forbidden="결과를 본 뒤 통과 정의·임계값(0.95, 0.03) 변경(변경 시 v2 계획으로 분리하고 사유 기록)")

def freeze():
    if not V2P.exists(): raise Halt("PA_0_PLAN_v2.json이 없습니다")
    h = spec_hash(PLAN); print("PA-B4b 계획 해시(예정)", h[:12])
    if BP.exists(): print("이미 동결:", "동일" if json.loads(BP.read_text(encoding="utf-8"))["sha256"] == h else "⛔ 다름"); return
    refs = {f.name: sha_f(f) for f in [V2P, S3/"L7_topic_grade.csv", S4/"topic_quadrants.csv", P1/"s4_main.py", PA/"PA_B4_PLAN.json"] if f.exists()}
    BP.write_text(json.dumps(dict(PLAN, created=now(), sha256=h, refs=refs), ensure_ascii=False, indent=1), encoding="utf-8")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as f:
        f.write(f"\n- {now()} | PA-B4b 계획 동결(해시 {h[:12]}) | 사유: S4 라벨을 F1+F3 통과 145개 big 컷으로 재계산(옵션 b). 제외 4개뿐인 약한 시험. 결과 미열람. QUICK은 재현 점검만 | 본 결과 변경 여부: 없음\n")
    print("저장: PA_B4b_PLAN.json")

def tag():
    if not BP.exists(): raise Halt("먼저 freeze")
    t = f"PA-B4b-plan-{pd.Timestamp.now().strftime('%Y-%m-%d')}"
    if git("tag", "-l", t).stdout.strip(): print("이미 있음:", t); return
    r = git("add", "--", "paper1/09_PA/PA_B4b_PLAN.json", "paper1/09_PA/PA_CHANGELOG.md", "paper1/pa_b4b.py"); print("add", r.returncode, r.stderr.strip())
    r = git("commit", "-m", "PA-B4b plan freeze (before execution)"); print("commit", r.returncode, (r.stdout + r.stderr)[:200])
    r = git("tag", "-a", t, "-m", "PA-B4b plan"); print("tag", r.returncode, r.stderr.strip()); print("※ 이어서 git push --follow-tags")

def label(df, col, qh, subset=None):
    base = df if subset is None else df[subset]
    cut = base[col].abs().quantile(2/3); big = df[col].abs() >= cut
    lab = ["small_change" if not b else ("growth" if d > 0 else "decline") + ("_highQ" if q else "_notHighQ") for b, d, q in zip(big, df[col], qh)]
    return pd.Series(lab, index=df.index), big, float(cut)
def stab(d, big, q1, q2):
    return float((d.loc[big, q1] == d.loc[big, q2]).mean()) if big.any() else np.nan

def run():
    if not BP.exists(): raise Halt("먼저 freeze")
    sp = json.loads(BP.read_text(encoding="utf-8"))
    if sp["sha256"] != spec_hash(sp) or sp["sha256"] != spec_hash(PLAN): raise Halt("동결 파일과 현재 계획이 다릅니다")
    if not git("tag", "-l", "PA-B4b-plan-*").stdout.strip(): raise Halt("tag 단계를 먼저 실행하세요")
    sfx = "_QUICK" if QUICK else ""
    G = pd.read_csv(S3/"L7_topic_grade.csv", encoding="utf-8-sig"); ptop = set(G[~bl(G.F1) & ~bl(G.F3)].topic.astype(int))
    if len(ptop) != 145: raise Halt(f"통과 토픽 수 재현 실패: {len(ptop)} (145여야 함)")
    M = pd.read_csv(S4/"topic_quadrants.csv", encoding="utf-8-sig"); M["topic"] = M.topic.astype(int); M["qh"] = bl(M.quality_high)
    # 재현: 149개 전체
    q0, b0, _ = label(M, "delta", M.qh); qw0, bw0, _ = label(M, "within", M.qh)
    if not ((q0 == M.quadrant).all() and (b0 == bl(M.big)).all() and (qw0 == M.quadrant_within).all()): raise Halt("전체 토픽 재계산 라벨이 topic_quadrants.csv와 다름")
    M["quadrant_rc"], M["big_rc"], M["qw_rc"] = q0, b0, qw0
    sA, sAA = stab(M, M.big_rc, "quadrant_rc", "qw_rc"), stab(M[M.grade == "A"], M[M.grade == "A"].big_rc, "quadrant_rc", "qw_rc")
    if round(sA, 2) != 0.70 or round(sAA, 2) != 0.69: raise Halt(f"안정성 재현 실패: {sA:.3f}/{sAA:.3f}")
    print(f"[재현 OK] 통과 토픽 145개, 전체 149개 라벨 일치, 안정성 {sA:.3f}/{sAA:.3f}")
    if QUICK: print("[QUICK] 재현 점검만 수행. 결과 통계는 출력하지 않음."); return
    P = M[M.topic.isin(ptop)].copy().reset_index(drop=True)
    P["quad145"], P["big145"], cut_t = label(P, "delta", P.qh); P["qw145"], P["bigw145"], cut_w = label(P, "within", P.qh)
    P["orig_big"] = bl(P.big); P["same_label"] = P.quad145 == P.quadrant
    # 원본 기준(같은 145개 부분집합): 원본 big/라벨 그대로의 안정성
    s_orig_all = stab(P, P.orig_big, "quadrant", "quadrant_within"); A = P.grade == "A"; s_orig_A = stab(P[A], P[A].orig_big, "quadrant", "quadrant_within")
    s_new_all = stab(P, P.big145, "quad145", "qw145"); s_new_A = stab(P[A], P[A].big145, "quad145", "qw145")
    ob = P[P.orig_big]; keep_big = float(ob.big145.mean()); keep_label = float(ob.same_label.mean()); new_big = int((P.big145 & ~P.orig_big).sum())
    out = pd.DataFrame([dict(cut_total_orig=float(M.delta.abs().quantile(2/3)), cut_total_145=cut_t, cut_within_145=cut_w, n_big_orig=int(P.orig_big.sum()), n_big_145=int(P.big145.sum()), orig_big_still_big=keep_big,
                             orig_big_same_label=keep_label, n_newly_big=new_big, stab_all_orig=s_orig_all, stab_all_145=s_new_all, stab_A_orig=s_orig_A, stab_A_145=s_new_A)])
    ex = M[~M.topic.isin(ptop)][["topic", "grade", "delta", "within", "big", "quadrant", "quadrant_within"]]
    P.to_csv(PA/"PA_B4b_results.csv", index=False, encoding="utf-8-sig"); out.to_csv(PA/"PA_B4b_summary.csv", index=False, encoding="utf-8-sig"); ex.to_csv(PA/"PA_B4b_excluded4.csv", index=False, encoding="utf-8-sig")
    print("\n[Post-hoc] PA-B4b 요약(145개, 컷만 재계산)\n", out.round(4).T.to_string(header=False)); print("\n[제외 4개 토픽]\n", ex.round(4).to_string(index=False))
    chg = P[P.orig_big & ~P.same_label][["topic", "grade", "delta", "quadrant", "quad145"]]; nb = P[P.big145 & ~P.orig_big][["topic", "grade", "delta", "quadrant", "quad145"]]
    print("\n[원본 big인데 라벨이 바뀐 토픽]\n", chg.round(4).to_string(index=False) if len(chg) else "없음"); print("\n[새로 big이 된 토픽]\n", nb.round(4).to_string(index=False) if len(nb) else "없음")
    r1 = "둔감" if keep_label >= 0.95 else "민감"; r2 = "둔감" if (abs(s_new_all - s_orig_all) <= 0.03 and abs(s_new_A - s_orig_A) <= 0.03) else "민감"
    print(f"\n[동결 판독] 1) 같은 라벨 유지율 {keep_label:.3f} → {r1} | 2) 안정성 변화 전체 {s_new_all - s_orig_all:+.3f}, A {s_new_A - s_orig_A:+.3f} → {r2}")
    print("※ 제외 4개뿐인 약한 시험. 몫은 149개 기준. 판독을 합치지 않음. S0~S8 판정 불변.")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as fh:
        fh.write(f"- {now()} | PA-B4b 실행 | 정의: PA_B4b_PLAN {sp['sha256'][:12]} | 결과: PA_B4b_*.csv | 본 결과 변경 여부: 없음\n")

try: {"freeze": freeze, "tag": tag, "run": run}[MODE]()
except Halt as e: print(f"⛔ 중단: {e}")