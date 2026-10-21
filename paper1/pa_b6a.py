# -*- coding: utf-8 -*-
# PA-B6a: F7의 OpenAlex ID에 ORCID를 붙여, 위험군 판정(F2_risk_names)의 독립 정답(서로 다른 ORCID 2개 이상=동명이인 확실)에 대한 정밀도·재현율. 미실행.
# python3 pa_b6a.py freeze | tag | fetch | run     (tag 뒤 git push --follow-tags)
import urllib.request, urllib.parse, time
from pa_common import *
from pa_extra import *
MAILTO = ""    # OpenAlex polite pool용 이메일(선택). 계획 해시에 넣지 않음
CACHE = PA/"PA_B6a_orcid_cache.csv"
PLAN = dict(
    version=1, parent="PA_0_PLAN_v2.json",
    status="사후 명세(지침서 B6-1). F7 구조(pid, rank, name_norm, oa_id; 2020-2025만), 분할 이름 3,749개, 위험군 1,431개 중 1,116개가 분할 이름이라는 점은 열람. ORCID 조회 결과 미열람. S0~S8 판정 불변.",
    fetch="F7의 고유 oa_id를 OpenAlex /authors?filter=openalex:ID1|ID2...(50개씩)로 조회해 orcid만 저장(select=id,orcid). 없으면 빈 값. 캐시 CSV는 재개 가능, 결과 해석 전에 해시를 changelog에 기록",
    population="F7에서 name_norm이 있고, 그 이름의 oa_id 중 ORCID가 하나 이상 있는 이름",
    truth="양성(동명이인 확실) = 이름에 서로 다른 ORCID가 2개 이상. 음성 = ORCID가 하나뿐이거나 모두 같은 ORCID. 한 이름에 ID가 둘 이상이어도 ORCID가 같으면 프로필 분할로 보고 음성",
    flag="F2_risk_names.csv의 name_norm = 위험군",
    stats="혼동표, 정밀도=P(양성|위험군), 재현율=P(위험군|양성), 각 Wilson 95%. 위험군 이름 중 F7 존재·모집단 포함 비율. 보조: ID가 둘 이상이고 ORCID 보유 ID가 둘 이상인 이름 중 서로 다른 ORCID 비율(분할 이름 중 실제 동명이인 비율)",
    reading="수치와 구간만 보고. 임계값·통과 판정 없음. 위험군 검증 순환성에 대한 독립 정답 1개로 기술",
    reproduce_check="F7 행 141,836, 분할 이름 3,749, 위험군 이름 수는 F2_risk_names 행 수와 일치(출력)",
    caveat="ORCID 보유자는 연구 활동이 활발한 저자에 치우침. F7은 2020+만 덮음. ORCID가 다른 두 프로필이 같은 사람일 가능성은 낮지만 0이 아님. 음성은 '동명이인 증거 없음'이지 '단일인 확인'이 아님",
    forbidden="결과를 본 뒤 정답 정의·모집단 변경(변경 시 v2 계획으로 분리)")

def fetch(sp):
    f7 = pd.read_csv(DATA/"F7_oa_author_ids.csv", encoding="utf-8-sig", low_memory=False)
    ids = sorted(set(f7.oa_id.dropna().astype(str).str.replace("https://openalex.org/", "", regex=False))); done = set(pd.read_csv(CACHE).oa_id) if CACHE.exists() else set()
    todo = [i for i in ids if i not in done]; print(f"고유 ID {len(ids):,} | 캐시 {len(done):,} | 남음 {len(todo):,}")
    for k in range(0, len(todo), 50):
        b = todo[k:k+50]; q = {"filter": "openalex:" + "|".join(b), "select": "id,orcid", "per-page": 50}
        if MAILTO: q["mailto"] = MAILTO
        url = "https://api.openalex.org/authors?" + urllib.parse.urlencode(q); res = None
        for att in range(4):
            try: res = json.load(urllib.request.urlopen(url, timeout=60)); break
            except Exception as e: print("재시도", att, str(e)[:60]); time.sleep(3*(att + 1))
        if res is None: raise Halt("API 호출 실패(캐시는 보존됨, 다시 fetch하면 이어서 진행)")
        got = {r["id"].replace("https://openalex.org/", ""): (r.get("orcid") or "") for r in res.get("results", [])}
        pd.DataFrame([dict(oa_id=i, orcid=got.get(i, ""), found=i in got) for i in b]).to_csv(CACHE, mode="a", header=not CACHE.exists(), index=False, encoding="utf-8-sig")
        if (k//50) % 20 == 0: print(f"  {k + len(b):,}/{len(todo):,}"); time.sleep(0.2)
    c = pd.read_csv(CACHE); cl(f"PA-B6a fetch 완료 | 캐시 {len(c):,}행, ORCID 보유 {int((c.orcid.fillna('') != '').sum()):,}, 해시 {sha_f(CACHE)[:12]} | 본 결과 변경: 없음")

def run(quick, sp):
    if not CACHE.exists(): raise Halt("먼저 fetch")
    f7 = pd.read_csv(DATA/"F7_oa_author_ids.csv", encoding="utf-8-sig", low_memory=False)
    if len(f7) != 141836: raise Halt(f"F7 행 수 {len(f7)} (141836이어야 함)")
    c = pd.read_csv(CACHE).drop_duplicates("oa_id"); c["orcid"] = c.orcid.fillna("").astype(str)
    f7["oa"] = f7.oa_id.astype(str).str.replace("https://openalex.org/", "", regex=False); f7 = f7.dropna(subset=["name_norm"]).merge(c[["oa_id", "orcid"]].rename(columns={"oa_id": "oa"}), on="oa", how="left"); f7["orcid"] = f7.orcid.fillna("")
    g = f7.groupby("name_norm").apply(lambda d: pd.Series(dict(n_ids=d.oa.nunique(), n_orcid_ids=d[d.orcid != ""].oa.nunique(), n_orcids=d[d.orcid != ""].orcid.nunique()))).reset_index()
    split = set(g.name_norm[g.n_ids >= 2])
    if len(split) != 3749: raise Halt(f"분할 이름 수 {len(split)} (3749여야 함)")
    risk = set(pd.read_csv(DATA/"F2_risk_names.csv", encoding="utf-8-sig").name_norm.astype(str))
    pop = g[g.n_orcid_ids >= 1].copy(); pop["truth"] = pop.n_orcids >= 2; pop["risk"] = pop.name_norm.isin(risk)
    tp = int((pop.truth & pop.risk).sum()); fp = int((~pop.truth & pop.risk).sum()); fn = int((pop.truth & ~pop.risk).sum()); tn = int((~pop.truth & ~pop.risk).sum())
    pl, ph = wilson(tp, tp + fp); rl, rh = wilson(tp, tp + fn)
    cov = dict(risk_names=len(risk), risk_in_F7=int(len(risk & set(g.name_norm))), risk_in_population=int(pop.risk.sum()), population=len(pop), n_truth=int(pop.truth.sum()))
    out = pd.DataFrame([dict(tp=tp, fp=fp, fn=fn, tn=tn, precision=tp/(tp + fp) if tp + fp else np.nan, p_lo=pl, p_hi=ph, recall=tp/(tp + fn) if tp + fn else np.nan, r_lo=rl, r_hi=rh, **cov)])
    sp2 = g[(g.n_ids >= 2) & (g.n_orcid_ids >= 2)]; k2 = int((sp2.n_orcids >= 2).sum()); l2, h2 = wilson(k2, len(sp2))
    aux = pd.DataFrame([dict(n_split_names_with_2plus_orcid_ids=len(sp2), n_distinct_orcids=k2, share_distinct=k2/len(sp2) if len(sp2) else np.nan, lo=l2, hi=h2)])
    out.to_csv(PA/"PA_B6a_results.csv", index=False, encoding="utf-8-sig"); aux.to_csv(PA/"PA_B6a_split_names_orcid.csv", index=False, encoding="utf-8-sig"); pop.to_csv(PA/"PA_B6a_population.csv", index=False, encoding="utf-8-sig")
    print("\n[Post-hoc] PA-B6a 위험군 판정의 독립 정답 대비\n", out.round(4).T.to_string(header=False)); print("\n[보조] 분할 이름 중 서로 다른 ORCID 비율\n", aux.round(4).T.to_string(header=False))
    print("※ ORCID 보유자 편향, 2020+ 한정. 음성은 '증거 없음'. 판정 없이 수치만 보고. S0~S8 판정 불변.")

if not special("B6a", PLAN, {"fetch": fetch}):
    run_pa("B6a", PLAN, run, [DATA/"F7_oa_author_ids.csv", DATA/"F2_risk_names.csv", P1/"pa_extra.py"], "위험군 판정의 독립 정답(ORCID) 확보(지침서 B6-1)")