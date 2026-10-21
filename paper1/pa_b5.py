# -*- coding: utf-8 -*-
# PA-B5: S4 안정성 민감도(컷 곡선, 탈락/부호반전 분해, 방향 일치). 결정적 계산, QUICK 없음.
# MODE: "freeze" -> "tag" -> (git push --follow-tags) -> "run". S0~S8 판정 불변. 모든 산출물 [Post-hoc].
import json, hashlib, subprocess, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore"); pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40)
MODE = "run"

ROOT = Path.home() / "Research/Minnesota_Transport"; P1 = ROOT/"paper1"; PA = P1/"09_PA"; S4 = P1/"04_S4"
now = lambda: pd.Timestamp.now().isoformat(timespec="seconds")
sha_b = lambda b: hashlib.sha256(b).hexdigest(); sha_f = lambda p: sha_b(Path(p).read_bytes())
git = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
class Halt(Exception): pass
spec_hash = lambda s: sha_b(json.dumps({k: v for k, v in s.items() if k not in ("sha256", "created", "refs")}, sort_keys=True, ensure_ascii=False).encode())
V2P, BP = PA/"PA_0_PLAN_v2.json", PA/"PA_B5_PLAN.json"

PLAN = dict(
    version=1, parent="PA_0_PLAN_v2.json",
    status="사후 명세. S4 결과·s4_main.py 라벨 규칙 열람 상태. PA-B5 결과 미열람. S0~S8 판정 불변.",
    input="04_S4/topic_quadrants.csv (열: delta, within, quality_high, grade, quadrant, quadrant_within, big, big_within)",
    label_rule="s4_main.label: cut=|col|.quantile(q), big=|col|>=cut, 라벨=small_change | (growth/decline)+(_highQ/_notHighQ). quality_high는 delta용·within용 라벨에서 같은 열",
    cut_grid=[0.60, 0.6667, 0.70, 0.75], q_original=0.6667,
    stats={"n_big": "big(delta) 수", "stab_full": "big(delta) 중 라벨(delta)==라벨(within) 비율(S4 안정성 정의)", "stab_A": "같은 정의, grade==A만(컷은 전체 토픽에서 계산)",
           "lost_big": "big(delta) 중 big(within) 아닌 수", "sign_flip": "big(delta)이고 big(within)인데 부호가 다른 수",
           "sign_agree": "big(delta) 중 sign(within)==sign(delta) 비율", "dir_stab": "방향 라벨(small/growth/decline, 품질 무시) 일치 비율은 stab_full과 같은 경로이므로 sign_agree와 lost_big 분해로 대체"},
    reproduce_check="q=0.6667에서 stab_full=0.700, stab_A=0.69(S4_meta.json, 소수 3자리), 저장된 quadrant·big 열과 재계산 라벨이 전 토픽 일치. 아니면 중단",
    wilson="q 원본의 stab_full에 대한 Wilson 95% 구간을 '토픽을 표본으로 볼 경우의 참고치'로만 병기",
    reading="판독 규칙 없음(기술 분석). 컷별 값을 표로 보고하고 범위만 서술. 탈락/부호반전 분해로 불일치의 원천을 보고",
    caveat="안정성은 재표집이 아니라 150개 토픽에 대한 결정적 비율. 불일치는 within 기준 상위 1/3 재선정에 따른 탈락이며 품질 축 효과가 아님(quality_high 공유). 복구 코드(s4_main.py) 기준",
    forbidden="결과를 본 뒤 컷 격자·정의 변경(변경 시 v2 계획으로 분리하고 사유 기록)")

def freeze():
    if not V2P.exists(): raise Halt("PA_0_PLAN_v2.json이 없습니다")
    h = spec_hash(PLAN); print("PA-B5 계획 해시(예정)", h[:12])
    if BP.exists(): print("이미 동결:", "동일" if json.loads(BP.read_text(encoding="utf-8"))["sha256"] == h else "⛔ 다름"); return
    refs = {f.name: sha_f(f) for f in [V2P, S4/"topic_quadrants.csv", S4/"S4_meta.json", P1/"s4_main.py"] if f.exists()}
    BP.write_text(json.dumps(dict(PLAN, created=now(), sha256=h, refs=refs), ensure_ascii=False, indent=1), encoding="utf-8")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as f:
        f.write(f"\n- {now()} | PA-B5 계획 동결(해시 {h[:12]}) | 사유: S4 안정성 0.700의 민감도·불일치 원천 분해. 라벨 규칙 열람, 결과 미열람. 결정적 계산이라 QUICK 없음 | 본 결과 변경 여부: 없음\n")
    print("저장: PA_B5_PLAN.json")

def tag():
    if not BP.exists(): raise Halt("먼저 freeze")
    t = f"PA-B5-plan-{pd.Timestamp.now().strftime('%Y-%m-%d')}"
    if git("tag", "-l", t).stdout.strip(): print("이미 있음:", t); return
    r = git("add", "--", "paper1/09_PA/PA_B5_PLAN.json", "paper1/09_PA/PA_CHANGELOG.md", "paper1/pa_b5.py"); print("add", r.returncode, r.stderr.strip())
    r = git("commit", "-m", "PA-B5 plan freeze (before execution)"); print("commit", r.returncode, (r.stdout + r.stderr)[:200])
    r = git("tag", "-a", t, "-m", "PA-B5 plan"); print("tag", r.returncode, r.stderr.strip()); print("※ 이어서 git push --follow-tags")

def wilson(k, n, z=1.96):
    p = k/n; d = 1 + z*z/n; c = (p + z*z/(2*n))/d; h = z*np.sqrt(p*(1-p)/n + z*z/(4*n*n))/d; return c-h, c+h

def run():
    if not BP.exists(): raise Halt("먼저 freeze")
    sp = json.loads(BP.read_text(encoding="utf-8"))
    if sp["sha256"] != spec_hash(sp) or sp["sha256"] != spec_hash(PLAN): raise Halt("동결 파일과 현재 계획이 다릅니다")
    if not git("tag", "-l", "PA-B5-plan-*").stdout.strip(): raise Halt("tag 단계를 먼저 실행하세요")
    d = pd.read_csv(S4/"topic_quadrants.csv", encoding="utf-8-sig"); qh = d.quality_high.astype(str).str.lower().isin(["true", "1"]).values
    meta = json.load(open(S4/"S4_meta.json", encoding="utf-8")); isA = (d.grade.astype(str).str.upper() == "A").values
    def label(col, q):
        a = d[col].abs(); big = (a >= a.quantile(q)).values
        lab = np.array(["small_change" if not b else ("growth" if x > 0 else "decline") + ("_highQ" if h else "_notHighQ") for b, x, h in zip(big, d[col].values, qh)])
        return lab, big
    rows, mm = [], None
    for q in PLAN["cut_grid"]:
        ld, bd = label("delta", q); lw, bw = label("within", q); s = bd
        stab = float((ld[s] == lw[s]).mean()); sA = float((ld[s & isA] == lw[s & isA]).mean()) if (s & isA).any() else np.nan
        lost = s & ~bw; flip = s & bw & (np.sign(d.delta.values) != np.sign(d.within.values))
        rows.append(dict(q=q, n_big=int(s.sum()), n_big_A=int((s & isA).sum()), stab_full=stab, stab_A=sA, lost_big=int(lost.sum()), sign_flip=int(flip.sum()),
                         kept=int((ld[s] == lw[s]).sum()), sign_agree=float((np.sign(d.within.values[s]) == np.sign(d.delta.values[s])).mean()), lost_but_sign_same=int((lost & (np.sign(d.within.values) == np.sign(d.delta.values))).sum())))
        if q == PLAN["q_original"]:
            if abs(stab - meta["stability_all"]) > 1e-3 or abs(sA - meta["stability_A"]) > 1e-3: raise Halt(f"S4 안정성 재현 실패: {stab:.3f}/{sA:.3f} vs {meta['stability_all']}/{meta['stability_A']}")
            if not (ld == d.quadrant.values).all() or not (lw == d.quadrant_within.values).all(): raise Halt("저장된 quadrant 열과 재계산 라벨이 다름")
            mm = d.assign(lab_delta=ld, lab_within=lw, lost_big=lost, sign_flip=flip)[lost | flip][["topic", "grade", "delta", "within", "lab_delta", "lab_within", "lost_big", "sign_flip"]]
    R = pd.DataFrame(rows); R.to_csv(PA/"PA_B5_results.csv", index=False, encoding="utf-8-sig"); mm.to_csv(PA/"PA_B5_mismatch_q0.6667.csv", index=False, encoding="utf-8-sig")
    k0 = int(R[R.q == PLAN["q_original"]].kept.iloc[0]); n0 = int(R[R.q == PLAN["q_original"]].n_big.iloc[0]); lo, hi = wilson(k0, n0)
    print("[재현 OK] 원본 컷에서 S4 안정성·라벨 일치\n"); print("[Post-hoc] PA-B5 컷 민감도\n", R.round(3).to_string(index=False))
    print(f"\n[참고] 원본 {k0}/{n0}의 Wilson 95%: [{lo:.3f}, {hi:.3f}] (토픽을 표본으로 볼 경우의 참고치, 결정적 비율임)")
    print("\n[Post-hoc] 원본 컷 불일치 토픽\n", mm.round(4).to_string(index=False))
    print("\n※ 불일치 원천은 within 기준 상위 1/3 재선정에 따른 탈락. quality_high 공유라 품질 축 효과 아님. S0~S8 판정 불변.")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as fh:
        fh.write(f"- {now()} | PA-B5 실행 | 정의: PA_B5_PLAN {sp['sha256'][:12]} | 결과: PA_B5_*.csv | 본 결과 변경 여부: 없음\n")

try: {"freeze": freeze, "tag": tag, "run": run}[MODE]()
except Halt as e: print(f"⛔ 중단: {e}")
