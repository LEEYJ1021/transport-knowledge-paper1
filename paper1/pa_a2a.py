# -*- coding: utf-8 -*-
# PA-A2a: 분할 이름(F7에서 oa_id>=2) 제외 민감도. ID 기반 재판별은 F7이 2020+만 덮어 불가 -> 진단으로 한정. 미실행 코드.
# MODE: "freeze" -> "tag" -> (git push --follow-tags) -> "run"(QUICK=True: 오류 점검 전용, 수치 미출력) -> "run"(QUICK=False)
# S0~S8 판정 불변. 모든 산출물 [Post-hoc]. 분해식·통계는 s6_lib.Pair, PA-A2c와 동일.
import sys, json, hashlib, subprocess, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore"); pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40)
MODE = "run"
QUICK = False

ROOT = Path.home() / "Research/Minnesota_Transport"; P1 = ROOT/"paper1"; PA = P1/"09_PA"; S6D = P1/"06_S6"; FD = ROOT/"analysis_data/final"
now = lambda: pd.Timestamp.now().isoformat(timespec="seconds")
sha_b = lambda b: hashlib.sha256(b).hexdigest(); sha_f = lambda p: sha_b(Path(p).read_bytes())
git = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
class Halt(Exception): pass
spec_hash = lambda s: sha_b(json.dumps({k: v for k, v in s.items() if k not in ("sha256", "created", "refs")}, sort_keys=True, ensure_ascii=False).encode())
V2P, BP = PA/"PA_0_PLAN_v2.json", PA/"PA_A2a_PLAN.json"

PLAN = dict(
    version=1, seed=2026, parent="PA_0_PLAN_v2.json",
    status="사후 명세(PA-A2의 1번 교정을 진단으로 축소). S6 결과, Pair·load_all 소스, PA-A2b·A2c 결과, F7 커버리지(2020-2025만)와 분할 이름 비중(2020+ F2 행의 9.0%), 위험군 겹침(1,116/3,749)은 열람한 상태. PA-A2a 결과는 미열람. S0~S8 판정 불변.",
    why_not_id="F7(OpenAlex ID)은 2020-2025 논문만 덮고 2015-19에는 ID가 없어 마지막 쌍의 지속 저자를 ID로 판정할 수 없음. 따라서 'ID 기반 결과와 일치'는 검증하지 않으며, '이름 기반 결과가 F7이 보여 주는 이름 분할에 얼마나 민감한가'만 본다",
    split_def="F7_oa_author_ids.csv에서 name_norm 결측 행 제외 후 name_norm별 고유 oa_id >= 2인 이름(재현 점검 3,749개). 분할 판정은 2020+ 논문에서만 관측됨. 분할은 실제 동명이인과 OpenAlex 프로필 분할을 구분하지 못함",
    scenarios={"orig": "S6 주 설정 spec['main'], s6_lib.make_pair 그대로", "excl_split": "orig의 저자-논문 행 R에서 aid(name_norm)가 분할 이름인 행을 모든 기간에서 제거한 뒤 같은 설정으로 Pair 구성(L['first'], L['last']는 원래 ai 기준 그대로)"},
    pairs="pairs_of(spec) 전부. 주 대상은 마지막 쌍 P1519->P2025",
    stats={"entry_share": "half(entry)/(half(adapt)+half(realloc)+half(entry)+half(exit)), entry=신규+복귀", "adapt_share": "half(adapt)/같은 분모", "entry_minus_adapt": "entry_share - adapt_share"},
    boot="저자 가중 wa~Exp(1)을 orig의 저자 전체에서 뽑고 excl_split의 같은 저자에게 같은 wa를 적용(대응 부트스트랩). B=spec['B_boot'], 역할은 재표집에서 고정. 변화량 delta=excl-orig의 부트스트랩 중앙값, 백분위 구간, basic 구간(2*delta_obs-q_hi, 2*delta_obs-q_lo)",
    diagnostics="쌍별·역할별(P, E_new, E_ret, X_final, X_gap) 분할 이름의 저자 수 비중과 질량 비중(P·E는 후기 질량, X는 전기 질량), 두 시나리오의 저자 수. 분할 이름 중 분석 집합에 남은 수와 위험군 겹침 수 출력",
    reading="마지막 쌍에서 entry_minus_adapt의 |delta_obs|<=0.03 이고 부호(orig 대비)가 유지되면 '분할 이름 제외에 둔감', 아니면 '민감'. 다른 쌍도 같은 규칙으로 쌍별 표기만 하고 하나의 결론으로 합치지 않음. 구간은 병기하며 판독에 쓰지 않음",
    reproduce_check="(a) 분할 이름 수 3,749, (b) orig의 total_half가 renewal_decomposition.csv(scheme=main, variant=all_venues)와 1e-6 이내, (c) orig의 entry_share가 PA_A2c_results.csv(mode=author, stat=entry_share)의 obs와 1e-6 이내, (d) excl_split의 저자 집합이 orig의 부분집합. 하나라도 어긋나면 중단",
    caveat="분할 이름은 다작·흔한 이름에 치우쳐 있을 가능성이 있어(미확인) 제외가 지속 저자(P)를 선택적으로 덜어낼 수 있음: 역할별 비중 진단으로 확인. 분할 판정이 2020+에서만 가능해 이전 기간 행은 '2020+에 나타난 이름'만 제외되는 비대칭이 있음. 이름 기반 식별 자체의 오류는 이 분석이 해결하지 않음. 위험군(F2에서 이미 제외)은 분할 이름과 겹침",
    forbidden="결과를 본 뒤 분할 정의·판독 기준(0.03)·B 변경(변경 시 v2 계획으로 분리하고 사유 기록)")

def freeze():
    if not V2P.exists(): raise Halt("PA_0_PLAN_v2.json이 없습니다")
    h = spec_hash(PLAN); print("PA-A2a 계획 해시(예정)", h[:12])
    if BP.exists(): print("이미 동결:", "동일" if json.loads(BP.read_text(encoding="utf-8"))["sha256"] == h else "⛔ 다름"); return
    refs = {f.name: sha_f(f) for f in [V2P, S6D/"S6_0_PREREG.json", P1/"s6_lib.py", S6D/"renewal_decomposition.csv", PA/"PA_A2c_PLAN.json", PA/"PA_A2c_results.csv", FD/"F7_oa_author_ids.csv", FD/"F2_risk_names.csv"] if f.exists()}
    BP.write_text(json.dumps(dict(PLAN, created=now(), sha256=h, refs=refs), ensure_ascii=False, indent=1), encoding="utf-8")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as f:
        f.write(f"\n- {now()} | PA-A2a 계획 동결(해시 {h[:12]}) | 사유: F7이 2020+만 덮어 ID 재판별 불가 -> 분할 이름 제외 민감도 진단으로 축소. 설계 점검 수치(커버리지, 9.0%, 위험군 겹침)와 S6·A2b·A2c 결과 열람 상태, PA-A2a 결과 미열람. QUICK은 수치 미출력 | 본 결과 변경 여부: 없음\n")
    print("저장: PA_A2a_PLAN.json")

def tag():
    if not BP.exists(): raise Halt("먼저 freeze")
    t = f"PA-A2a-plan-{pd.Timestamp.now().strftime('%Y-%m-%d')}"
    if git("tag", "-l", t).stdout.strip(): print("이미 있음:", t); return
    r = git("add", "--", "paper1/09_PA/PA_A2a_PLAN.json", "paper1/09_PA/PA_CHANGELOG.md", "paper1/pa_a2a.py"); print("add", r.returncode, r.stderr.strip())
    r = git("commit", "-m", "PA-A2a plan freeze (before execution)"); print("commit", r.returncode, (r.stdout + r.stderr)[:200])
    r = git("tag", "-a", t, "-m", "PA-A2a plan"); print("tag", r.returncode, r.stderr.strip()); print("※ 이어서 git push --follow-tags")

def run():
    if not BP.exists(): raise Halt("먼저 freeze")
    sp = json.loads(BP.read_text(encoding="utf-8"))
    if sp["sha256"] != spec_hash(sp) or sp["sha256"] != spec_hash(PLAN): raise Halt("동결 파일과 현재 계획이 다릅니다")
    if not git("tag", "-l", "PA-A2a-plan-*").stdout.strip(): raise Halt("tag 단계를 먼저 실행하세요")
    sys.path.insert(0, str(P1)); import s6_lib as S
    spec = S.load_spec(); L = S.load_all(spec); M = spec["main"]; PAIRS = S.pairs_of(spec); half = S.half; R = L["R"]
    sfx = "_QUICK" if QUICK else ""; B = 20 if QUICK else int(spec["B_boot"]); lo_q, hi_q = spec["ci"]; rng = np.random.default_rng(int(PLAN["seed"]))
    # 분할 이름
    f7 = pd.read_csv(FD/"F7_oa_author_ids.csv", encoding="utf-8-sig", low_memory=False)
    g = f7.dropna(subset=["name_norm"]).groupby("name_norm").oa_id.nunique(); split = set(g[g >= 2].index)
    if len(split) != 3749: raise Halt(f"분할 이름 수 재현 실패: {len(split)} (3749여야 함)")
    rk = set(pd.read_csv(FD/"F2_risk_names.csv", encoding="utf-8-sig").name_norm.astype(str)); in_R = set(R.aid.unique()) & split
    print(f"분할 이름 {len(split):,} | 분석 집합(R)에 존재 {len(in_R):,} | 위험군과 겹침 {len(split & rk):,} | R에 존재하는 위험군 이름 {len(set(R.aid.unique()) & rk):,}")
    L2 = dict(L); L2["R"] = R[~R.aid.isin(split)]
    aid_of = R.drop_duplicates("ai").set_index("ai").aid
    ref = pd.read_csv(S6D/"renewal_decomposition.csv"); ref = ref[(ref.scheme == M["scheme"]) & (ref.variant == "all_venues")].set_index("pair")
    a2c = pd.read_csv(PA/"PA_A2c_results.csv"); a2c = a2c[(a2c["mode"] == "author") & (a2c.stat == "entry_share")].set_index("pair")
    STATS = ["entry_share", "adapt_share", "entry_minus_adapt"]
    def stats(d):
        h = {t: half(d[t]) for t in ["adapt", "realloc", "entry", "exit"]}; tot = sum(h.values())
        return dict(entry_share=h["entry"]/tot, adapt_share=h["adapt"]/tot, entry_minus_adapt=(h["entry"] - h["adapt"])/tot)
    rows, roles = [], []
    for p0, p1 in PAIRS:
        name = f"{p0}->{p1}"
        Pa = S.make_pair(L, p0, p1, M["scheme"], M["venue"], M["topic"], M["hom"]); Pb = S.make_pair(L2, p0, p1, M["scheme"], M["venue"], M["topic"], M["hom"])
        da, db = Pa.decompose(), Pb.decompose(); oa, ob = stats(da), stats(db)
        if abs(half(da["total"]) - float(ref.loc[name, "total_half"])) > 1e-6: raise Halt(f"S6 관측 재현 실패({name})")
        if abs(oa["entry_share"] - float(a2c.loc[name, "obs"])) > 1e-6: raise Halt(f"PA-A2c entry_share 재현 실패({name})")
        idx = np.searchsorted(Pa.aids, Pb.aids)
        if not (idx < len(Pa.aids)).all() or not (Pa.aids[idx] == Pb.aids).all(): raise Halt(f"excl_split 저자 집합이 orig의 부분집합이 아님({name})")
        # 역할별 진단
        flag = pd.Series(aid_of.loc[Pa.aids].values).isin(split).values
        mass0 = np.bincount(Pa.a0, Pa.m0, Pa.nA)/Pa.m0.sum(); mass1 = np.bincount(Pa.a1, Pa.m1, Pa.nA)/Pa.m1.sum()
        for r in ["P", "E_new", "E_ret", "X_final", "X_gap"]:
            m = Pa.role == r; ms = mass0 if r.startswith("X") else mass1
            roles.append(dict(pair=name, role=r, n_authors=int(m.sum()), split_author_share=float(flag[m].mean()) if m.any() else np.nan,
                              mass=float(ms[m].sum()), split_mass_share=float(ms[m & flag].sum()/ms[m].sum()) if ms[m].sum() > 0 else np.nan))
        roles.append(dict(pair=name, role="ALL_period0", n_authors=int(Pa.nA), split_author_share=float(flag.mean()), mass=1.0, split_mass_share=float(mass0[flag].sum())))
        roles.append(dict(pair=name, role="ALL_period1", n_authors=int(Pb.nA), split_author_share=float(flag.mean()), mass=1.0, split_mass_share=float(mass1[flag].sum())))
        # 대응 부트스트랩
        bs = []
        for _ in range(B):
            wa = rng.exponential(size=Pa.nA); sa = stats(Pa.decompose(Pa.m0*wa[Pa.a0], Pa.m1*wa[Pa.a1]))
            wb = wa[idx]; sb = stats(Pb.decompose(Pb.m0*wb[Pb.a0], Pb.m1*wb[Pb.a1]))
            bs.append({s: sb[s] - sa[s] for s in STATS})
        bs = pd.DataFrame(bs)
        for s in STATS:
            dl = ob[s] - oa[s]; ql, qh = np.percentile(bs[s], [lo_q, hi_q])
            rows.append(dict(pair=name, stat=s, obs_orig=oa[s], obs_excl=ob[s], delta=dl, boot_median=float(bs[s].median()), pct_lo=ql, pct_hi=qh, basic_lo=2*dl - qh, basic_hi=2*dl - ql,
                             n_authors_orig=int(Pa.nA), n_authors_excl=int(Pb.nA), B=B))
        print(f"  {name} 완료")
    RS, RO = pd.DataFrame(rows), pd.DataFrame(roles)
    RS.to_csv(PA/f"PA_A2a_results{sfx}.csv", index=False, encoding="utf-8-sig"); RO.to_csv(PA/f"PA_A2a_roles{sfx}.csv", index=False, encoding="utf-8-sig")
    if QUICK: print("\n[QUICK] 오류 없이 완료. 수치는 출력하지 않음(_QUICK 파일을 열어 해석하지 마세요)."); return
    print("\n[Post-hoc] PA-A2a 결과(분할 이름 제외 대 원본)\n", RS.round(4).to_string(index=False))
    print("\n[Post-hoc] 역할별 분할 이름 비중\n", RO.round(4).to_string(index=False))
    k = RS[RS.stat == "entry_minus_adapt"].copy(); k["sign_kept"] = np.sign(k.obs_excl) == np.sign(k.obs_orig); k["within_003"] = k.delta.abs() <= 0.03; k["insensitive"] = k.sign_kept & k.within_003
    print("\n[동결 판독] entry_minus_adapt\n", k[["pair", "obs_orig", "obs_excl", "delta", "pct_lo", "pct_hi", "sign_kept", "within_003", "insensitive"]].round(4).to_string(index=False))
    last = k[k.pair == f"{PAIRS[-1][0]}->{PAIRS[-1][1]}"].iloc[0]; print("→ 마지막 쌍:", "분할 이름 제외에 둔감" if last.insensitive else "분할 이름 제외에 민감")
    print("※ ID 기반 재판별이 아니라 분할 이름 제외 민감도임. 분할 판정은 2020+에서만 관측. 쌍별로 따로 읽고 합치지 않음. S0~S8 판정 불변.")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as fh:
        fh.write(f"- {now()} | PA-A2a 실행 | 정의: PA_A2a_PLAN {sp['sha256'][:12]} | 결과: PA_A2a_results.csv, PA_A2a_roles.csv | 본 결과 변경 여부: 없음\n")

try: {"freeze": freeze, "tag": tag, "run": run}[MODE]()
except Halt as e: print(f"⛔ 중단: {e}")