# -*- coding: utf-8 -*-
# PA-B2b: 2020 변화의 저널 구성·COVID 토픽 분리. 미실행 코드.
# MODE: "freeze" -> "tag" -> (git push --follow-tags) -> "run"(QUICK=True: 오류 점검 전용, 수치 미출력) -> "run"(QUICK=False)
# S0~S8 판정 불변. 모든 산출물 [Post-hoc].
import sys, json, hashlib, subprocess, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore"); pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40)
MODE = "run"
QUICK = False

ROOT = Path.home() / "Research/Minnesota_Transport"; P1 = ROOT/"paper1"; PA = P1/"09_PA"; S5 = P1/"05_S5"
now = lambda: pd.Timestamp.now().isoformat(timespec="seconds")
sha_b = lambda b: hashlib.sha256(b).hexdigest(); sha_f = lambda p: sha_b(Path(p).read_bytes())
git = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
class Halt(Exception): pass
spec_hash = lambda s: sha_b(json.dumps({k: v for k, v in s.items() if k not in ("sha256", "created", "refs")}, sort_keys=True, ensure_ascii=False).encode())
BP, B2P = PA/"PA_B2b_PLAN.json", PA/"PA_B2_PLAN.json"

PLAN = dict(
    version=1, seed=2026, parent="PA_B2_PLAN.json",
    status="사후 명세. PA-A1, PA-B2 결과(관측 기술 표 포함)를 본 뒤 작성. PA-B2b 결과는 미열람. S0~S8 판정 불변.",
    focus_year=2020, B=200, samples=["all", "fixed14", "within"],
    variants={
        "base": "제외 없음(관측 재현 점검용)",
        "drop_top1_venue": "2019->2020 논문 수 증가 1위 저널 제외",
        "drop_top3_venues": "증가 상위 3개 저널 제외",
        "drop_top5_venues": "증가 상위 5개 저널 제외",
        "drop_topic71": "COVID 토픽(topic 71) 제외 후 비중 재정규화",
        "drop_top5_venues_and_topic71": "상위 5개 저널과 토픽 71 동시 제외"},
    top_venue_rule="nv[2020]-nv[2019]가 큰 순서(전 저널 대상, 코드에서 결정적으로 계산)",
    detector="s5_lib.detect 그대로. 제외 후 저널·토픽 부분배열로 s5_lib.sample_P 재계산. pen = c_primary*phi_s*(Kv-1)*log(T), phi_s는 S5 값 고정(제외 후 비용/벌점 비율이 달라짐), Kv=남은 토픽 수",
    stats="(a) 관측 변화점과 R, (b) 2020 점프 J(PA-A1과 동일 3년 창 Hellinger, 가중치 4n), (c) 연도x저널 셀 다항 재표집(셀 카운트 기반 직접 구현, B회)에서 2020±1년 변화점 회수율",
    reading="변형별 표본별: 변화점 유지 = 관측 변화점 중 2020±1이 있고 AND 부트스트랩 회수율>=0.80. J 비율 = J(변형)/J(base, 같은 표본): >=0.80 '점프 유지', 0.50~0.80 '부분 감소', <0.50 '해당 성분이 점프의 주요 원천'. 변화점 유지와 J 비율을 따로 보고하고 하나의 결론으로 합치지 않음",
    caveat="제외는 저널 구성·토픽 정의를 바꾸므로 R은 변형 간 직접 비교 불가. N2 귀무는 재계산하지 않음. 토픽 71 외 COVID 관련 토픽은 카드를 읽기 전에는 지정하지 않음. 임베딩 보유율(측정 아티팩트)은 이 분석에 없음",
    forbidden="결과를 본 뒤 변형 정의·임계값 변경(변경 시 v2 계획으로 분리하고 사유 기록)")

def freeze():
    if not B2P.exists(): raise Halt("PA_B2_PLAN.json이 없습니다")
    h = spec_hash(PLAN); print("PA-B2b 계획 해시(예정)", h[:12])
    if BP.exists(): print("이미 동결:", "동일" if json.loads(BP.read_text(encoding="utf-8"))["sha256"] == h else "⛔ 다름"); return
    refs = {f.name: sha_f(f) for f in [B2P, PA/"PA_0_PLAN_v2.json", S5/"S5_0_PREREG.json", P1/"s5_lib.py"] if f.exists()}
    BP.write_text(json.dumps(dict(PLAN, created=now(), sha256=h, refs=refs), ensure_ascii=False, indent=1), encoding="utf-8")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as f:
        f.write(f"\n- {now()} | PA-B2b 계획 동결(해시 {h[:12]}) | 사유: PA-B2 한계(저널 구성·내용 미분리) 보완. 결과 미열람. QUICK은 수치 미출력 | 본 결과 변경 여부: 없음\n")
    print("저장: PA_B2b_PLAN.json")

def tag():
    if not BP.exists(): raise Halt("먼저 freeze")
    t = f"PA-B2b-plan-{pd.Timestamp.now().strftime('%Y-%m-%d')}"
    if git("tag", "-l", t).stdout.strip(): print("이미 있음:", t); return
    r = git("add", "--", "paper1/09_PA/PA_B2b_PLAN.json", "paper1/09_PA/PA_CHANGELOG.md", "paper1/pa_b2b.py"); print("add", r.returncode, r.stderr.strip())
    r = git("commit", "-m", "PA-B2b plan freeze (before execution)"); print("commit", r.returncode, (r.stdout + r.stderr)[:200])
    r = git("tag", "-a", t, "-m", "PA-B2b plan"); print("tag", r.returncode, r.stderr.strip()); print("※ 이어서 git push --follow-tags")

def run():
    if not BP.exists(): raise Halt("먼저 freeze")
    sp = json.loads(BP.read_text(encoding="utf-8"))
    if sp["sha256"] != spec_hash(sp) or sp["sha256"] != spec_hash(PLAN): raise Halt("동결 파일과 현재 계획이 다릅니다")
    if not git("tag", "-l", "PA-B2b-plan-*").stdout.strip(): raise Halt("tag 단계를 먼저 실행하세요")
    sys.path.insert(0, str(P1)); import s5_lib as L
    sfx = "_QUICK" if QUICK else ""; B = 10 if QUICK else PLAN["B"]; rng = np.random.default_rng(int(PLAN["seed"]))
    s5 = json.loads((S5/"S5_0_PREREG.json").read_text(encoding="utf-8")); D = s5["detection"]; PHI = {k: v["phi"] for k, v in D["phi"].items()}
    C0, KMAX, MINLEN = D["c_primary"], D["k_max"], D["min_len"]
    cnt, venues, topics, fixed_v = L.load_counts(); T = len(L.YEARS); YEARS = np.asarray(L.YEARS); SAM = PLAN["samples"]; f = PLAN["focus_year"]
    i20 = int(np.where(YEARS == f)[0][0]); i19 = i20 - 1
    nv = cnt.sum(2); order = np.argsort(-(nv[i20] - nv[i19])); top = [str(venues[i]) for i in order[:5]]
    VARS = {"base": (set(), set()), "drop_top1_venue": (set(top[:1]), set()), "drop_top3_venues": (set(top[:3]), set()), "drop_top5_venues": (set(top[:5]), set()),
            "drop_topic71": (set(), {71}), "drop_top5_venues_and_topic71": (set(top[:5]), {71})}
    assert set(VARS) == set(PLAN["variants"]), "변형 목록이 계획과 다름"
    def J(P, n, it):
        X, w = np.sqrt(P), 4.0*n; a, b = slice(max(0, it-3), it), slice(it, it+3)
        m = lambda sl: np.average(X[sl], axis=0, weights=w[sl]) if w[sl].sum() > 0 else X[sl].mean(0)
        return float(np.linalg.norm(m(b) - m(a))/np.sqrt(2))
    def ctx(dv, dt):
        kv = np.array([str(v) not in dv for v in venues]); kt = np.array([int(t) not in dt for t in topics])
        c = cnt[:, kv, :][:, :, kt]; return c, fixed_v[kv], c.sum((0, 2))/c.sum(), int(kt.sum())
    def boot_cells(c):   # 연도x저널 셀 내 다항 재표집(S5 부트스트랩과 같은 정의, 부분 배열 지원)
        out = np.zeros(c.shape, dtype=np.int64); n = c.sum(2)
        for y, v in zip(*np.nonzero(n)):
            p = c[y, v]/c[y, v].sum(); out[y, v] = rng.multinomial(int(n[y, v]), p)
        return out
    def det(c, fv, wb, Kv, s):
        P, n = L.sample_P(c, fv, wb, s); d = L.detect(P, n, C0*PHI[s]*(Kv-1)*np.log(T), KMAX, MINLEN)
        return d, J(P, n, i20), [int(YEARS[b]) for b in d["br"]]
    ref = pd.read_csv(S5/"regime_nulls.csv"); rows = []
    for name, (dv, dt) in VARS.items():
        c, fv, wb, Kv = ctx(dv, dt); obs = {}
        for s in SAM:
            d, j, yrs = det(c, fv, wb, Kv, s); obs[s] = (d["R"], j, yrs)
            if name == "base":
                r0 = float(ref[(ref["null"] == "N2") & (ref["sample"] == s)].obs_R.iloc[0])
                if abs(d["R"] - r0) > 1e-3: raise Halt(f"S5 관측 R 재현 실패({s}): {d['R']:.4f} vs {r0:.4f}")
        hit = {s: [] for s in SAM}
        for _ in range(B):
            cb = boot_cells(c)
            for s in SAM: hit[s].append(any(abs(y - f) <= 1 for y in det(cb, fv, wb, Kv, s)[2]))
        for s in SAM:
            R, j, yrs = obs[s]; rows.append(dict(variant=name, sample=s, n_venues=int(c.shape[1]), K=Kv, obs_R=R, obs_k=len(yrs)+1, obs_breaks=str(yrs), obs_break_at_2020pm1=any(abs(y-f) <= 1 for y in yrs), J=j, boot_hit_2020pm1=float(np.mean(hit[s])), B=B))
        print(f"  {name} 완료")
    RS = pd.DataFrame(rows); jb = RS[RS.variant == "base"].set_index("sample").J; RS["J_ratio_vs_base"] = RS.apply(lambda r: r.J/jb[r["sample"]], axis=1)
    RS["break_kept"] = RS.obs_break_at_2020pm1 & (RS.boot_hit_2020pm1 >= 0.80)
    RS["J_class"] = pd.cut(RS.J_ratio_vs_base, [-np.inf, .5, .8, np.inf], right=False, labels=["주요 원천", "부분 감소", "점프 유지"])
    RS.to_csv(PA/f"PA_B2b_results{sfx}.csv", index=False, encoding="utf-8-sig"); pd.DataFrame(dict(rank=range(1, 6), venue=top)).to_csv(PA/f"PA_B2b_top_venues{sfx}.csv", index=False, encoding="utf-8-sig")
    if QUICK: print("\n[QUICK] 오류 없이 완료. 수치는 출력하지 않음(_QUICK 파일을 열어 해석하지 마세요)."); return
    print("\n제외 대상 상위 5개 저널:", top)
    print("\n[Post-hoc] PA-B2b 결과\n", RS[["variant", "sample", "n_venues", "K", "obs_R", "obs_breaks", "J", "J_ratio_vs_base", "J_class", "boot_hit_2020pm1", "break_kept"]].round(3).to_string(index=False))
    print("\n※ 동결 판독은 변화점 유지와 J 비율을 따로 읽음. 변형 간 R은 직접 비교 불가. S0~S8 판정 불변.")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as fh:
        fh.write(f"- {now()} | PA-B2b 실행 | 정의: PA_B2b_PLAN {sp['sha256'][:12]} | 결과: PA_B2b_*.csv | 본 결과 변경 여부: 없음\n")

try: {"freeze": freeze, "tag": tag, "run": run}[MODE]()
except Halt as e: print(f"⛔ 중단: {e}")
