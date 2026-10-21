# -*- coding: utf-8 -*-
# PA-A2c: S6 부트스트랩 보고 방식 교정(저자 단위 클러스터 부트스트랩 + 편향 보정). 미실행 코드.
# MODE: "freeze" -> "tag" -> (git push --follow-tags) -> "run"(QUICK=True: 오류 점검 전용, 수치 미출력) -> "run"(QUICK=False)
# S0~S8 판정 불변. 모든 산출물 [Post-hoc]. 신규·지속 판별과 분해식은 S6 코드(s6_lib.Pair) 그대로 사용.
import sys, json, hashlib, subprocess, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore"); pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40)
MODE = "tag"
QUICK = True

ROOT = Path.home() / "Research/Minnesota_Transport"; P1 = ROOT/"paper1"; PA = P1/"09_PA"; S6D = P1/"06_S6"
now = lambda: pd.Timestamp.now().isoformat(timespec="seconds")
sha_b = lambda b: hashlib.sha256(b).hexdigest(); sha_f = lambda p: sha_b(Path(p).read_bytes())
git = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
class Halt(Exception): pass
spec_hash = lambda s: sha_b(json.dumps({k: v for k, v in s.items() if k not in ("sha256", "created", "refs")}, sort_keys=True, ensure_ascii=False).encode())
V2P, BP = PA/"PA_0_PLAN_v2.json", PA/"PA_A2c_PLAN.json"

PLAN = dict(
    version=1, seed=2026, parent="PA_0_PLAN_v2.json",
    status="사후 명세(PA-A2의 3번 교정만). S6 결과는 열람한 상태. PA-A2c 결과는 미열람. ID 대조·진입 정의 민감도는 별도 계획(PA-A2a/b)으로 분리. S0~S8 판정 불변.",
    setting="S6 주 설정: spec['main'] (scheme, venue, topic, hom)과 s6_lib.make_pair 그대로. 쌍은 s6_lib.pairs_of(spec) 전부",
    B="spec['B_boot'] (S6와 같은 값, 실행 시 기록)", ci="spec['ci'] (S6와 같은 백분위)",
    boot_modes={"author": "저자 가중 wa~Exp(1)만 적용, 논문 가중 1 (저자 단위 클러스터 복원추출의 연속형 근사)",
                "mult": "S6 원본: 저자 wa x 논문 wp 곱셈 Exp(1) (민감도로 병기)"},
    stats={"entry_share": "half(entry)/sum(half(adapt,realloc,entry,exit))", "adapt_share": "half(adapt)/같은 분모",
           "entry_minus_adapt": "entry_share - adapt_share", "excess_half": "half(P.excess(m1)[0])"},
    report="통계별: 관측, 부트스트랩 중앙값, 편향 보정값(2*obs-median), 백분위 구간, basic 구간(2*obs-q_hi, 2*obs-q_lo)",
    reading="저자 모드에서 entry_minus_adapt의 basic 구간 하한>0인 쌍 수를 보고. 4쌍 모두 >0이면 '진입>적응 방향이 저자 단위 재표집에서 유지'. 일부면 쌍별로 표기. mult 모드는 병기만 하며 판독에 쓰지 않음",
    reproduce_check="관측 total_half가 renewal_decomposition.csv(scheme=main, variant=all_venues)와 1e-6 이내 일치하지 않으면 중단",
    caveat="저자 가중만 흔드는 방식은 공저로 묶인 저자들의 상관과 논문 단위 변동을 반영하지 않음. 지속/진입 역할은 재표집에서 고정(S6와 동일). 동명이인·이름 기반 식별 문제는 이 분석이 다루지 않음(PA-A2a)",
    forbidden="결과를 본 뒤 B·모드·판독 기준 변경(변경 시 v2 계획으로 분리하고 사유 기록)")

def freeze():
    if not V2P.exists(): raise Halt("PA_0_PLAN_v2.json이 없습니다")
    h = spec_hash(PLAN); print("PA-A2c 계획 해시(예정)", h[:12])
    if BP.exists(): print("이미 동결:", "동일" if json.loads(BP.read_text(encoding="utf-8"))["sha256"] == h else "⛔ 다름"); return
    refs = {f.name: sha_f(f) for f in [V2P, S6D/"S6_0_PREREG.json", P1/"s6_lib.py", P1/"s6_run.py", S6D/"renewal_decomposition.csv", S6D/"renewal_bootstrap.csv"] if f.exists()}
    BP.write_text(json.dumps(dict(PLAN, created=now(), sha256=h, refs=refs), ensure_ascii=False, indent=1), encoding="utf-8")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as f:
        f.write(f"\n- {now()} | PA-A2c 계획 동결(해시 {h[:12]}) | 사유: S6 부트스트랩 구간이 점추정을 포함하지 못한 문제의 보고 방식 교정. S6 결과·코드 열람 상태, PA-A2c 결과 미열람. QUICK은 수치 미출력 | 본 결과 변경 여부: 없음\n")
    print("저장: PA_A2c_PLAN.json")

def tag():
    if not BP.exists(): raise Halt("먼저 freeze")
    t = f"PA-A2c-plan-{pd.Timestamp.now().strftime('%Y-%m-%d')}"
    if git("tag", "-l", t).stdout.strip(): print("이미 있음:", t); return
    r = git("add", "--", "paper1/09_PA/PA_A2c_PLAN.json", "paper1/09_PA/PA_CHANGELOG.md", "paper1/pa_a2c.py"); print("add", r.returncode, r.stderr.strip())
    r = git("commit", "-m", "PA-A2c plan freeze (before execution)"); print("commit", r.returncode, (r.stdout + r.stderr)[:200])
    r = git("tag", "-a", t, "-m", "PA-A2c plan"); print("tag", r.returncode, r.stderr.strip()); print("※ 이어서 git push --follow-tags")

def run():
    if not BP.exists(): raise Halt("먼저 freeze")
    sp = json.loads(BP.read_text(encoding="utf-8"))
    if sp["sha256"] != spec_hash(sp) or sp["sha256"] != spec_hash(PLAN): raise Halt("동결 파일과 현재 계획이 다릅니다")
    if not git("tag", "-l", "PA-A2c-plan-*").stdout.strip(): raise Halt("tag 단계를 먼저 실행하세요")
    sys.path.insert(0, str(P1)); import s6_lib as S
    spec = S.load_spec(); L = S.load_all(spec); M = spec["main"]; PAIRS = S.pairs_of(spec); half = S.half
    sfx = "_QUICK" if QUICK else ""; B = 20 if QUICK else int(spec["B_boot"]); lo_q, hi_q = spec["ci"]; rng = np.random.default_rng(int(PLAN["seed"]))
    ref = pd.read_csv(S6D/"renewal_decomposition.csv"); ref = ref[(ref.scheme == M["scheme"]) & (ref.variant == "all_venues")].set_index("pair")
    def stats(d, ex):
        h = {t: half(d[t]) for t in ["adapt", "realloc", "entry", "exit"]}; tot = sum(h.values())
        return dict(entry_share=h["entry"]/tot, adapt_share=h["adapt"]/tot, entry_minus_adapt=(h["entry"]-h["adapt"])/tot, excess_half=half(ex))
    rows = []
    for p0, p1 in PAIRS:
        P = S.make_pair(L, p0, p1, M["scheme"], M["venue"], M["topic"], M["hom"]); d0 = P.decompose(); name = f"{p0}->{p1}"
        r0 = float(ref.loc[name, "total_half"])
        if abs(half(d0["total"]) - r0) > 1e-6: raise Halt(f"S6 관측 재현 실패({name}): {half(d0['total']):.8f} vs {r0:.8f}")
        obs = stats(d0, P.excess()[0]); nAuth, nPap = P.nA, int(max(P.pc0.max(), P.pc1.max())) + 1
        for mode in PLAN["boot_modes"]:
            bs = []
            for _ in range(B):
                wa = rng.exponential(size=nAuth); wp = rng.exponential(size=nPap) if mode == "mult" else np.ones(nPap)
                m0, m1 = P.m0 * wa[P.a0] * wp[P.pc0], P.m1 * wa[P.a1] * wp[P.pc1]
                bs.append(stats(P.decompose(m0, m1), P.excess(m1)[0]))
            bs = pd.DataFrame(bs)
            for c in bs.columns:
                med = float(bs[c].median()); ql, qh = np.percentile(bs[c], [lo_q, hi_q]); o = obs[c]
                rows.append(dict(pair=name, mode=mode, stat=c, obs=o, boot_median=med, bias_corrected=2*o - med, pct_lo=ql, pct_hi=qh, basic_lo=2*o - qh, basic_hi=2*o - ql, B=B))
        print(f"  {name} 완료")
    RS = pd.DataFrame(rows); RS.to_csv(PA/f"PA_A2c_results{sfx}.csv", index=False, encoding="utf-8-sig")
    if QUICK: print("\n[QUICK] 오류 없이 완료. 수치는 출력하지 않음(_QUICK 파일을 열어 해석하지 마세요)."); return
    print("\n[Post-hoc] PA-A2c 결과(저자 모드)\n", RS[RS["mode"] == "author"].round(4).to_string(index=False))
    print("\n[Post-hoc] PA-A2c 결과(곱셈 모드, 병기)\n", RS[RS["mode"] == "mult"].round(4).to_string(index=False))
    k = RS[(RS["mode"] == "author") & (RS.stat == "entry_minus_adapt")].set_index("pair"); kept = (k.basic_lo > 0)
    print("\n[동결 판독] entry_minus_adapt basic 하한>0:", kept.to_dict(), "→", "4쌍 모두 유지" if kept.all() else ("일부 유지" if kept.any() else "유지 안 됨"))
    print("※ 저자 가중만 흔든 근사이며 공저 연결성분·동명이인은 다루지 않음. S0~S8 판정 불변.")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as fh:
        fh.write(f"- {now()} | PA-A2c 실행 | 정의: PA_A2c_PLAN {sp['sha256'][:12]} | 결과: PA_A2c_results.csv | 본 결과 변경 여부: 없음\n")

try: {"freeze": freeze, "tag": tag, "run": run}[MODE]()
except Halt as e: print(f"⛔ 중단: {e}")