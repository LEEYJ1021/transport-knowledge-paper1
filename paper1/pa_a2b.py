# -*- coding: utf-8 -*-
# PA-A2b: 신규 진입 정의 민감도(s6 원본 / 첫 출판 후 2년 이내 / 이전 5년 코퍼스 부재). 미실행 코드.
# MODE: "freeze" -> "tag" -> (git push --follow-tags) -> "run"(QUICK=True: 오류 점검 전용, 수치 미출력) -> "run"(QUICK=False)
# S0~S8 판정 불변. 모든 산출물 [Post-hoc]. 분해식은 s6_lib.Pair 그대로, 신규 분할만 마스크로 재계산.
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
V2P, BP = PA/"PA_0_PLAN_v2.json", PA/"PA_A2b_PLAN.json"

PLAN = dict(
    version=1, seed=2026, parent="PA_0_PLAN_v2.json",
    status="사후 명세(PA-A2의 2번 교정). S6 결과·Pair 소스·PA-A2c 결과 열람 상태. PA-A2b 결과 미열람. S0~S8 판정 불변.",
    setting="S6 주 설정 spec['main']과 s6_lib.make_pair 그대로, 쌍은 pairs_of(spec) 전부. 적응·재배분·진입 총량·퇴출은 Pair.decompose 그대로(정의와 무관)",
    definitions={"s6": "E이고 첫 출판 연도 >= t1 시작 (S6 원본, 재현 점검)",
                 "y2": "E이고 첫 출판 연도 in [t1 시작, t1 시작+1]",
                 "y5": "E이고 t1 시작 전 5년(t1시작-5 ~ t1시작-1)의 분석 코퍼스 행(L['R'])에 없던 저자. 첫 쌍은 2000년 이전 자료가 없어 전원 해당"},
    stats={"new_share": "half(entry_def)/(half(adapt)+half(realloc)+half(entry_total)+half(exit))", "adapt_share": "half(adapt)/같은 분모",
           "new_minus_adapt": "new_share - adapt_share", "rest_entry_share": "(entry_total - entry_def의 half)/같은 분모는 쓰지 않고 half(entry_total - entry_def)/같은 분모"},
    boot="저자 가중 wa~Exp(1)만 적용(PA-A2c 저자 모드와 동일), B=spec['B_boot'], 역할·마스크는 재표집에서 고정",
    report="정의x쌍별: 관측, 부트스트랩 중앙값, 백분위 구간, basic 구간(2*obs-q_hi, 2*obs-q_lo)",
    reading="정의별로 new_minus_adapt의 관측>0이고 basic 하한>0인 쌍 수를 보고. 정의 간 평균하거나 하나의 결론으로 합치지 않음. 첫 쌍은 s6 원본에서도 통과하지 못했을 가능성이 있으며 그 경우 그대로 보고",
    reproduce_check="(a) s6 정의의 entry_def가 decompose의 entry_new와 1e-9 이내, (b) total_half가 renewal_decomposition.csv와 1e-6 이내. 아니면 중단",
    caveat="진입 총량은 정의와 무관하므로 이 분석은 신규/복귀 분할 민감도만 본다. y5는 분석 코퍼스(주제 있는 논문)의 행을 기준으로 해 F4 첫 출판 연도(주제 없는 논문 포함)와 기준이 다르다. 이름 기반 식별 문제는 다루지 않음(PA-A2a)",
    forbidden="결과를 본 뒤 정의·B·판독 기준 변경(변경 시 v2 계획으로 분리하고 사유 기록)")

def freeze():
    if not V2P.exists(): raise Halt("PA_0_PLAN_v2.json이 없습니다")
    h = spec_hash(PLAN); print("PA-A2b 계획 해시(예정)", h[:12])
    if BP.exists(): print("이미 동결:", "동일" if json.loads(BP.read_text(encoding="utf-8"))["sha256"] == h else "⛔ 다름"); return
    refs = {f.name: sha_f(f) for f in [V2P, S6D/"S6_0_PREREG.json", P1/"s6_lib.py", S6D/"renewal_decomposition.csv", PA/"PA_A2c_PLAN.json"] if f.exists()}
    BP.write_text(json.dumps(dict(PLAN, created=now(), sha256=h, refs=refs), ensure_ascii=False, indent=1), encoding="utf-8")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as f:
        f.write(f"\n- {now()} | PA-A2b 계획 동결(해시 {h[:12]}) | 사유: S6 신규 정의 민감도(신규/복귀 분할). S6·Pair·PA-A2c 결과 열람 상태, PA-A2b 결과 미열람. QUICK은 수치 미출력 | 본 결과 변경 여부: 없음\n")
    print("저장: PA_A2b_PLAN.json")

def tag():
    if not BP.exists(): raise Halt("먼저 freeze")
    t = f"PA-A2b-plan-{pd.Timestamp.now().strftime('%Y-%m-%d')}"
    if git("tag", "-l", t).stdout.strip(): print("이미 있음:", t); return
    r = git("add", "--", "paper1/09_PA/PA_A2b_PLAN.json", "paper1/09_PA/PA_CHANGELOG.md", "paper1/pa_a2b.py"); print("add", r.returncode, r.stderr.strip())
    r = git("commit", "-m", "PA-A2b plan freeze (before execution)"); print("commit", r.returncode, (r.stdout + r.stderr)[:200])
    r = git("tag", "-a", t, "-m", "PA-A2b plan"); print("tag", r.returncode, r.stderr.strip()); print("※ 이어서 git push --follow-tags")

def run():
    if not BP.exists(): raise Halt("먼저 freeze")
    sp = json.loads(BP.read_text(encoding="utf-8"))
    if sp["sha256"] != spec_hash(sp) or sp["sha256"] != spec_hash(PLAN): raise Halt("동결 파일과 현재 계획이 다릅니다")
    if not git("tag", "-l", "PA-A2b-plan-*").stdout.strip(): raise Halt("tag 단계를 먼저 실행하세요")
    sys.path.insert(0, str(P1)); import s6_lib as S
    spec = S.load_spec(); L = S.load_all(spec); M = spec["main"]; PAIRS = S.pairs_of(spec); half = S.half; R = L["R"]
    sfx = "_QUICK" if QUICK else ""; B = 20 if QUICK else int(spec["B_boot"]); lo_q, hi_q = spec["ci"]; rng = np.random.default_rng(int(PLAN["seed"]))
    ref = pd.read_csv(S6D/"renewal_decomposition.csv"); ref = ref[(ref.scheme == M["scheme"]) & (ref.variant == "all_venues")].set_index("pair")
    DEFS = list(PLAN["definitions"]); rows = []
    def compute(P, masks, m0=None, m1=None):
        d = P.decompose(m0, m1); M0, M1 = P.mats(m0, m1); Sb = (np.asarray(M0.sum(0)).ravel() + np.asarray(M1.sum(0)).ravel())/2
        w1 = np.asarray(M1.sum(1)).ravel(); tot = sum(half(d[t]) for t in ["adapt", "realloc", "entry", "exit"]); out = {}
        for k, mk in masks.items():
            ent = np.asarray(M1[mk].sum(0)).ravel() - Sb*w1[mk].sum() if mk.any() else np.zeros(P.K)
            out[k] = dict(new_share=half(ent)/tot, adapt_share=half(d["adapt"])/tot, new_minus_adapt=(half(ent) - half(d["adapt"]))/tot, rest_entry_share=half(d["entry"] - ent)/tot, ent=ent)
        return out, d
    for p0, p1 in PAIRS:
        P = S.make_pair(L, p0, p1, M["scheme"], M["venue"], M["topic"], M["hom"]); name = f"{p0}->{p1}"; b0 = spec["periods"][p1][0]
        E = np.isin(P.role, ["E_new", "E_ret"]); fy = L["first"][P.aids]
        prev = np.unique(R.ai.values[R.year.between(b0 - 5, b0 - 1).values]); present = np.isin(P.aids, prev)
        masks = {"s6": E & (fy >= b0), "y2": E & (fy >= b0) & (fy <= b0 + 1), "y5": E & ~present}
        obs, d0 = compute(P, masks)
        r0 = float(ref.loc[name, "total_half"])
        if abs(half(d0["total"]) - r0) > 1e-6: raise Halt(f"S6 관측 재현 실패({name})")
        if np.abs(obs["s6"]["ent"] - d0["entry_new"]).max() > 1e-9: raise Halt(f"s6 정의가 decompose의 entry_new와 다름({name})")
        bs = {k: [] for k in DEFS}
        for _ in range(B):
            wa = rng.exponential(size=P.nA); b_, _d = compute(P, masks, P.m0*wa[P.a0], P.m1*wa[P.a1])
            for k in DEFS: bs[k].append(b_[k])
        for k in DEFS:
            B_ = pd.DataFrame([{c: v[c] for c in ["new_share", "adapt_share", "new_minus_adapt", "rest_entry_share"]} for v in bs[k]])
            for c in B_.columns:
                o = obs[k][c]; ql, qh = np.percentile(B_[c], [lo_q, hi_q])
                rows.append(dict(pair=name, definition=k, stat=c, n_entrants=int(masks[k].sum()), obs=o, boot_median=float(B_[c].median()), pct_lo=ql, pct_hi=qh, basic_lo=2*o - qh, basic_hi=2*o - ql, B=B))
        print(f"  {name} 완료")
    RS = pd.DataFrame(rows); RS.to_csv(PA/f"PA_A2b_results{sfx}.csv", index=False, encoding="utf-8-sig")
    if QUICK: print("\n[QUICK] 오류 없이 완료. 수치는 출력하지 않음(_QUICK 파일을 열어 해석하지 마세요)."); return
    print("\n[Post-hoc] PA-A2b 결과\n", RS.round(4).to_string(index=False))
    k = RS[RS.stat == "new_minus_adapt"].copy(); k["kept"] = (k.obs > 0) & (k.basic_lo > 0)
    print("\n[동결 판독] 정의별 new_minus_adapt(관측>0 and basic 하한>0)인 쌍 수:", k.groupby("definition").kept.sum().to_dict(), "/ 쌍 수", len(PAIRS))
    print("※ 정의별로 따로 읽고 하나의 결론으로 합치지 않음. 진입 총량은 정의와 무관. S0~S8 판정 불변.")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as fh:
        fh.write(f"- {now()} | PA-A2b 실행 | 정의: PA_A2b_PLAN {sp['sha256'][:12]} | 결과: PA_A2b_results.csv | 본 결과 변경 여부: 없음\n")

try: {"freeze": freeze, "tag": tag, "run": run}[MODE]()
except Halt as e: print(f"⛔ 중단: {e}")