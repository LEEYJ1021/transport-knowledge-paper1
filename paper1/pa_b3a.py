# -*- coding: utf-8 -*-
# PA-B3a: 신생 토픽 정의 4종(D1~D4)의 핵심 집합(n_defs>=3) 대 정의 특이적(n_defs=1) 재요약. 결정적. 미실행 코드.
# MODE: "freeze" -> "tag" -> (git push --follow-tags) -> "run". S0~S8 판정 불변. 모든 산출물 [Post-hoc].
import json, hashlib, subprocess, itertools, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore"); pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40)
MODE = "tag"

ROOT = Path.home() / "Research/Minnesota_Transport"; P1 = ROOT/"paper1"; PA = P1/"09_PA"; S4 = P1/"04_S4"
now = lambda: pd.Timestamp.now().isoformat(timespec="seconds")
sha_b = lambda b: hashlib.sha256(b).hexdigest(); sha_f = lambda p: sha_b(Path(p).read_bytes())
bl = lambda s: s.astype(str).str.strip().str.lower().isin(["1", "1.0", "true", "t", "yes"])
git = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
class Halt(Exception): pass
spec_hash = lambda s: sha_b(json.dumps({k: v for k, v in s.items() if k not in ("sha256", "created", "refs")}, sort_keys=True, ensure_ascii=False).encode())
V2P, BP = PA/"PA_0_PLAN_v2.json", PA/"PA_B3a_PLAN.json"

PLAN = dict(
    version=1, parent="PA_0_PLAN_v2.json",
    status="사후 명세(PA-B3 중 핵심 집합 재요약 B3a). D1=F6.emerging(2005-09 대 2015-19, r>=3 and s1>=0.005), D2·D3=주 대비 상위 14(로그 비율·Δs), D4=민감도 대비 Δs 상위 14의 정의는 s4_main.py 열람으로 확인한 상태. definition_sensitivity.csv의 31개 토픽 행 수와 열 구조는 열람, 집합별 결과는 미열람. D1' 재구성(B3b)은 별도 계획. S0~S8 판정 불변.",
    sets="핵심 = n_defs>=3, 중간 = n_defs==2(보고만), 정의 특이적 = n_defs==1. definition_sensitivity.csv의 31개 토픽",
    join="topic_quadrants.csv(topic, between_share, delta, within, quadrant, quadrant_within, big, quality_high)와 topic으로 조인. grade는 definition_sensitivity.csv 값 사용",
    stats="집합별: 토픽 수, 등급(A/B/C) 수, big 비율, quality_high 비율, quadrant·quadrant_within 분포, between_share와 within/delta의 중앙값·사분위",
    reading="핵심 집합과 정의 특이적 집합의 between_share 중앙값 대소 방향만 보고. 임계값·유의성 판정 없음. 집합 간 차이를 효과로 해석하지 않음",
    reproduce_check="(a) 행 수 31, (b) 토픽이 모두 topic_quadrants.csv에 존재, (c) n_defs가 D1~D4 합과 일치, (d) D1~D4 쌍별 Jaccard의 최소·최대를 소수 둘째 자리로 반올림하면 0.04와 0.47(S4 요약 범위). 어긋나면 중단",
    caveat="집합이 작아 기술 통계이며 검정이 아님. D2~D4가 모두 상위 14 고정이고 D2·D3은 같은 대비라 n_defs>=3이 독립 정의 합의가 아님. D1은 구간과 규칙이 모두 달라 이질성의 원인을 분리하지 못함(B3b). between_share는 delta가 작으면 불안정. 신규 저자 진입 몫(지침서 B3-3)은 범위 밖",
    forbidden="결과를 본 뒤 집합 정의·판독 규칙 변경(변경 시 v2 계획으로 분리하고 사유 기록)")

def freeze():
    if not V2P.exists(): raise Halt("PA_0_PLAN_v2.json이 없습니다")
    h = spec_hash(PLAN); print("PA-B3a 계획 해시(예정)", h[:12])
    if BP.exists(): print("이미 동결:", "동일" if json.loads(BP.read_text(encoding="utf-8"))["sha256"] == h else "⛔ 다름"); return
    refs = {f.name: sha_f(f) for f in [V2P, S4/"definition_sensitivity.csv", S4/"topic_quadrants.csv", P1/"s4_main.py"] if f.exists()}
    BP.write_text(json.dumps(dict(PLAN, created=now(), sha256=h, refs=refs), ensure_ascii=False, indent=1), encoding="utf-8")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as f:
        f.write(f"\n- {now()} | PA-B3a 계획 동결(해시 {h[:12]}) | 사유: 신생 정의 4종의 핵심 집합 재요약. D1~D4 정의 열람, 집합별 결과 미열람. 지침서의 D1' 재구성은 D1이 이미 2005-09 대 2015-19라 전제가 어긋나 B3b로 대체 | 본 결과 변경 여부: 없음\n")
    print("저장: PA_B3a_PLAN.json")

def tag():
    if not BP.exists(): raise Halt("먼저 freeze")
    t = f"PA-B3a-plan-{pd.Timestamp.now().strftime('%Y-%m-%d')}"
    if git("tag", "-l", t).stdout.strip(): print("이미 있음:", t); return
    r = git("add", "--", "paper1/09_PA/PA_B3a_PLAN.json", "paper1/09_PA/PA_CHANGELOG.md", "paper1/pa_b3a.py"); print("add", r.returncode, r.stderr.strip())
    r = git("commit", "-m", "PA-B3a plan freeze (before execution)"); print("commit", r.returncode, (r.stdout + r.stderr)[:200])
    r = git("tag", "-a", t, "-m", "PA-B3a plan"); print("tag", r.returncode, r.stderr.strip()); print("※ 이어서 git push --follow-tags")

def run():
    if not BP.exists(): raise Halt("먼저 freeze")
    sp = json.loads(BP.read_text(encoding="utf-8"))
    if sp["sha256"] != spec_hash(sp) or sp["sha256"] != spec_hash(PLAN): raise Halt("동결 파일과 현재 계획이 다릅니다")
    if not git("tag", "-l", "PA-B3a-plan-*").stdout.strip(): raise Halt("tag 단계를 먼저 실행하세요")
    DS = pd.read_csv(S4/"definition_sensitivity.csv", encoding="utf-8-sig"); Q = pd.read_csv(S4/"topic_quadrants.csv", encoding="utf-8-sig")
    ks = ["D1", "D2", "D3", "D4"]
    if len(DS) != 31: raise Halt(f"행 수 {len(DS)} (31이어야 함)")
    if not set(DS.topic) <= set(Q.topic): raise Halt("definition_sensitivity 토픽이 topic_quadrants에 없음")
    for k in ks: DS[k] = bl(DS[k])
    if not (DS[ks].sum(axis=1).values == DS.n_defs.values).all(): raise Halt("n_defs가 D1~D4 합과 다름")
    S = {k: set(DS.topic[DS[k]]) for k in ks}; J = {f"{a}-{b}": len(S[a] & S[b])/len(S[a] | S[b]) for a, b in itertools.combinations(ks, 2)}
    if round(min(J.values()), 2) != 0.04 or round(max(J.values()), 2) != 0.47: raise Halt(f"Jaccard 범위 재현 실패: {min(J.values()):.3f}~{max(J.values()):.3f}")
    print("[재현 OK] 31개 토픽, n_defs 일치, 정의별 토픽 수", {k: len(v) for k, v in S.items()}, "| 쌍별 Jaccard", {a: round(b, 2) for a, b in J.items()})
    X = DS.merge(Q[["topic", "between_share", "delta", "within", "quadrant", "quadrant_within", "big", "quality_high"]], on="topic", how="left")
    X["within_ratio"] = X.within/X.delta; X["big"] = bl(X.big); X["quality_high"] = bl(X.quality_high)
    X["set"] = np.where(X.n_defs >= 3, "core(>=3)", np.where(X.n_defs == 2, "mid(2)", "specific(1)"))
    q = lambda s, p: float(s.quantile(p))
    rows = []
    for nm, g in X.groupby("set"):
        rows.append(dict(set=nm, n=len(g), nA=int((g.grade == "A").sum()), nB=int((g.grade == "B").sum()), nC=int((g.grade == "C").sum()), big_share=g.big.mean(), qhigh_share=g.quality_high.mean(),
                         bs_med=q(g.between_share, .5), bs_q25=q(g.between_share, .25), bs_q75=q(g.between_share, .75), wr_med=q(g.within_ratio, .5), wr_q25=q(g.within_ratio, .25), wr_q75=q(g.within_ratio, .75)))
    R = pd.DataFrame(rows); X.to_csv(PA/"PA_B3a_topics.csv", index=False, encoding="utf-8-sig"); R.to_csv(PA/"PA_B3a_summary.csv", index=False, encoding="utf-8-sig")
    print("\n[Post-hoc] PA-B3a 집합별 요약\n", R.round(3).to_string(index=False))
    print("\n[Post-hoc] 총변화 기준 4분면 분포\n", pd.crosstab(X["set"], X.quadrant).to_string()); print("\n[Post-hoc] 저널 내 성분 기준 4분면 분포\n", pd.crosstab(X["set"], X.quadrant_within).to_string())
    c, s = R.set_index("set").bs_med.get("core(>=3)", np.nan), R.set_index("set").bs_med.get("specific(1)", np.nan)
    print(f"\n[동결 판독] between_share 중앙값 핵심 {c:.3f} 대 특이적 {s:.3f} → 방향: " + ("핵심이 더 낮음(저널 내 성분 비중 큼)" if c < s else "핵심이 더 높음(저널 간 성분 비중 큼)" if c > s else "같음"))
    print("※ 31개 토픽 기술 통계이며 검정 아님. n_defs>=3은 비슷한 정의의 겹침일 수 있음. S0~S8 판정 불변.")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as fh:
        fh.write(f"- {now()} | PA-B3a 실행 | 정의: PA_B3a_PLAN {sp['sha256'][:12]} | 결과: PA_B3a_topics.csv, PA_B3a_summary.csv | 본 결과 변경 여부: 없음\n")

try: {"freeze": freeze, "tag": tag, "run": run}[MODE]()
except Halt as e: print(f"⛔ 중단: {e}")