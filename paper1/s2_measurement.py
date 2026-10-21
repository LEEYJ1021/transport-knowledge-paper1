# -*- coding: utf-8 -*-
# =====================================================================================
# 논문 1 / S2 측정 교정 (OpenAlex 호출 없음, 크레딧 소모 없음)
# 실행 순서 (STEPS만 바꿔 여러 번 실행)  [v2: schema 결과 반영, f2_check 추가]
#   0) ["f2_check"]                    F2 가중치 정의·F1 열(in_sample, fixed_venue) 점검. prereg 전에 실행, 출력 붙여 주세요
#   1) ["schema"]                       F1~F7·토픽 파일의 열 구조와 변수 사전 골격 생성 -> 출력을 붙여 주세요
#   2) ["prereg"]                       S2 사전등록 부록(핵심 목록, 정의, 임계값)을 동결. CORE_CONFIRMED=True 필요
#   3) ["clean_flags","country_rec","weights_country","unk_resid"]   지금 가진 자료만으로 실행 가능
#   4) ["missing"]                      토픽 파일이 확인된 뒤 (TOPIC_FILE/TOPIC_COL 지정 또는 자동 탐색)
#   5) ["risk","risk_selection"]        위험군 플래그 재현율 / 위험군 제외의 국가 선택 효과
#   6) ["commit"]                       산출물 해시 기록 + 커밋 + 태그
# 이 파일이 하지 않는 것: 포트폴리오 지표(2.4), 잡음 대응(2.5), 제목 분류기(2.7), K 민감도(2.9), 저자 단위 가중 결과.
#   F2/F4와 임베딩·토픽 구조를 본 뒤 다음 단계로 만듭니다.
# 모든 임계값은 prereg 단계에서 결과를 보기 전에 동결됩니다. 실행 후 바꾸면 사후 변경이므로 CHANGELOG_S2에 기록하세요.
# =====================================================================================
import re, json, hashlib, subprocess, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 120)

# ---------------- 설정 (여기만 수정) ----------------
STEPS = ["schema"]
ROOT = Path.home() / "Research/Minnesota_Transport"
CORE_CONFIRMED = False       # 핵심 목록(아래 CORE_LIST)을 연구자가 확인·수정했으면 True
WINDOW = 2007                # 국가 층 창(S1 확정)
TOPIC_START = 2000           # 주제 분석 본분석 시작
SEED = 2026
TOPIC_FILE = "F1_papers.csv"  # schema 결과: 토픽은 F1의 topic150(결측 21%)
TOPIC_COL = "topic150"
TOPIC_PID_COL = "pid"
TOPIC_MISSING_VALUES = [-1]  # 토픽 없음으로 볼 값(NaN은 항상 결측). schema 출력의 값 분포를 보고 확정
F7_FILE = "F7_oa_author_ids.csv"; RISK_FILE = "F2_risk_names.csv"   # schema 결과
COMMIT = False               # commit 단계에서만 사용
TAG_NAME = None

CORE_LIST = [  # 결과를 보기 전에 연구자가 확정할 것(3.2 제안안)
    dict(id="C1", stat="주제 유효수·HHI 시간 추세 부호", source="S5.1(a)", status="주제 층 필요: 이 파일에서는 계산 안 함"),
    dict(id="C2", stat="연속 노출 Spearman(Δexposure, d_all-d_fixed) 부호", source="S5 주 분석", status="이 파일에서는 계산 안 함"),
    dict(id="C3", stat="갱신 4항 분해의 진입·재배분 몫 방향", source="S6", status="저자 층 필요: 이 파일에서는 계산 안 함"),
    dict(id="C4", stat="상위 5개국 몫(top5_incl, top5_known)과 HHI(hhi_known)의 연도 추세 부호", source="S7", status="weights_country 단계에서 계산(19개 연도)"),
    dict(id="C5", stat="신규 저자 지역 구성 변화 방향", source="S7.2", status="저자 층 필요: 이 파일에서는 계산 안 함"),
]
# ----------------------------------------------------

S0, S1, S2 = ROOT / "paper1/00_S0", ROOT / "paper1/01_S1", ROOT / "paper1/02_S2"
DATA = ROOT / "analysis_data/final"; SC = S1 / "scimago"
hdr = lambda t: print("\n" + "=" * 90 + f"\n{t}\n" + "=" * 90)
now = lambda: pd.Timestamp.now().isoformat(timespec="seconds")
sha_b = lambda b: hashlib.sha256(b).hexdigest()
sha_f = lambda p: sha_b(Path(p).read_bytes())
class Halt(Exception): pass

# ---------------- 공통 ----------------
def nd(s):
    if not isinstance(s, str) or not s.strip(): return None
    s = s.strip().lower(); s = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", s); return s or None

def load_any(p, nrows=None):
    p = Path(p)
    if p.suffix == ".parquet": return pd.read_parquet(p)
    return pd.read_csv(p, low_memory=False, nrows=nrows)

def read_tbl(name):
    p = S1 / f"{name}.parquet"
    return pd.read_parquet(p) if p.exists() else pd.read_csv(S1 / f"{name}.csv.gz")

def changelog(line):
    cl = S2 / "CHANGELOG_S2.md"; S2.mkdir(parents=True, exist_ok=True)
    if not cl.exists(): cl.write_text("# CHANGELOG S2 (날짜 | 변경 | 사유 | 영향)\n\n", encoding="utf-8")
    if line in cl.read_text(encoding="utf-8"): return
    with cl.open("a", encoding="utf-8") as f: f.write(line + "\n")

def git(*a, check=False):
    r = subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
    if check and r.returncode: raise Halt(f"git {' '.join(a)} 실패: {r.stderr.strip()}")
    return r

def load_F1X():
    F1 = pd.read_csv(DATA / "F1_papers.csv", low_memory=False); F1["pid"] = F1.pid.astype(str)
    exf = S0 / "EXCLUDE_PIDS_FROZEN.csv"; log = pd.read_csv(S0 / "FREEZE_LOG.csv"); last = log[log.file == exf.name].iloc[-1]
    if sha_f(exf) != last.sha256: raise Halt("EXCLUDE_PIDS_FROZEN.csv 해시가 동결 기록과 다릅니다")
    EXC = set(pd.read_csv(exf, dtype=str, encoding="utf-8-sig").pid)
    return F1[~F1.pid.isin(EXC)].copy()

def spec_hash(spec): return sha_b(json.dumps({k: v for k, v in spec.items() if k not in ("sha256", "created")}, sort_keys=True, ensure_ascii=False).encode())

# ============================================================
# S2 사전등록 부록 (모든 임계값과 정의의 단일 출처)
# ============================================================
def make_spec():
    return dict(version=1, created=now(), seed=SEED, window=WINDOW, topic_start=TOPIC_START, core_list=CORE_LIST,
        weights=dict(
            equal="F2.w 방식: 위험군 이름을 뺀 뒤 남은 저자 수로 1/n_retained(논문 질량 1). f2_check로 F2 논문 100%가 이 정의임을 확인",
            inv_n_authors="1/n_authors(F1의 원래 저자 수). 위험군으로 빠진 저자의 질량은 '손실 질량'으로 보고",
            first_last="원래 저자 순서·수 기준: 단독 1.0 / 2인 0.5씩 / 3인 이상 제1·마지막 각 0.3, 중간 0.4/(n-2). 위험군 제외 시 남은 저자 몫을 논문 질량 1로 재정규화(가정)",
            full_count="저자-논문 쌍마다 1(논문 질량 = 남은 저자 수). 국가 층에서는 소속 국가마다 1(분할 없음)",
            country_layer_note="국가 층은 저자 신원이 필요 없어 위험군 제외를 적용하지 않음 -> 국가 층에서 equal = inv_n_authors(동일 값). 구분되는 가중치는 3종이며 equal과 inv_n의 차이는 저자 층에서만 생김",
            fixed_venues_note="분석의 고정 저널은 PREREG.json event.fixed_venues(14개)를 쓴다. F1.fixed_venue 열은 JPT에서 PREREG와 달라 사용하지 않는다"),
        country_variants=dict(main="OpenAlex 국가(S1 주 분석)", rec="국가 미상을 동결된 복구 규칙(RECOVERY d4a87d357217)으로 보충(민감도)",
                              terr_merge="HK·MO를 CN과 합산한 민감도(주 분석은 영토 별도)"),
        clean_rules=dict(bib_section=r"bibliographic section", vt_mobile_radio=dict(venue="VT Mag", regex=r"\[\s*mobile radio\s*\]"),
                         repeat_title_min=5, dup_title="같은 저널·연도·정규화 제목 중복: 첫 건 제외 나머지 표시", topic_excluded=[18],
                         note="표시만 하고 제거는 하지 않음. 제거 전후 비교는 별도 단계"),
        propensity=dict(clip_pct=[1, 99], positivity_floor=0.05, model="logistic(main effects, C=10)", cv_folds=5,
                        outcome="has_topic = 토픽 열이 결측이 아니고 TOPIC_MISSING_VALUES에 없음",
                        covariates_A="year, venue_short, n_authors 구간, is_solo (2000~2025)",
                        covariates_B="A + 논문 주 국가군(상위 8 + other + UNK) (2007~2025)"),
        portfolio=dict(shrink_k=5, min_topic_papers=3),
        stats=dict(top5="연도별 상위 5개국 몫 합(UNK 제외 국가 중). top5_incl=전체 질량 분모, top5_known=국가 아는 질량 분모",
                   hhi_known="국가 아는 질량 기준 국가 몫 제곱합", trend="연도와의 Spearman 부호(보조: OLS 기울기)"),
        pass_rule="핵심 통계의 부호가 가중치 4종에서 모두 같음(변형·표본·영토 조합마다)")

def check_prereg():
    p = S2 / "S2_PREREG_ADDENDUM.json"
    if not p.exists(): raise Halt("먼저 prereg 단계를 실행해 S2 부록을 동결하세요")
    spec = json.loads(p.read_text(encoding="utf-8"))
    if spec_hash(spec) != spec["sha256"]: raise Halt("S2_PREREG_ADDENDUM.json이 동결 후 변경되었습니다")
    return spec

def st_prereg():
    hdr("[prereg] S2 사전등록 부록 동결")
    S2.mkdir(parents=True, exist_ok=True); p = S2 / "S2_PREREG_ADDENDUM.json"
    spec = make_spec(); spec["sha256"] = spec_hash(spec)
    if p.exists():
        old = json.loads(p.read_text(encoding="utf-8"))
        if old["sha256"] != spec["sha256"]: raise Halt(f"이미 동결된 부록({old['sha256'][:12]})과 현재 설정({spec['sha256'][:12]})이 다릅니다. 사후 변경이면 새 파일로 분리하고 CHANGELOG_S2에 사유를 쓰세요")
        print("이미 동결됨, 동일:", old["sha256"][:12]); return
    if not CORE_CONFIRMED: raise Halt("CORE_LIST를 확인·수정한 뒤 CORE_CONFIRMED=True로 바꾸세요(핵심 목록은 결과를 보기 전에 확정해야 함)")
    try:
        pr = json.loads((S0 / "PREREG.json").read_text(encoding="utf-8")); print("S0 PREREG의 weights 항목:", pr.get("weights"), "| 위 weights 정의와 대조하세요")
    except Exception: pass
    p.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    changelog(f"- {now()} | S2 사전등록 부록 동결(sha256 {spec['sha256'][:12]}): 핵심 목록, 가중치 4종 정의, 정리 규칙, 성향 모형 설정, 영토 합산 민감도 | S2 시작 전, 결과 열람 전 | 이후 모든 S2 단계가 이 해시를 확인함")
    print("동결:", p.name, spec["sha256"][:12])

# ============================================================
# [schema] 열 구조와 변수 사전 골격
# ============================================================
def st_schema():
    hdr("[schema] 파일 구조 점검")
    S2.mkdir(parents=True, exist_ok=True); rows = []
    files = sorted(p for p in DATA.iterdir() if p.is_file() and (p.suffix in (".csv", ".parquet") or p.name.endswith(".csv.gz")))
    print("DATA 폴더 파일:", [p.name for p in files])
    for p in files:
        try:
            big = p.stat().st_size > 300e6; df = load_any(p, nrows=500000 if big else None)
        except Exception as e: print(f"  {p.name}: 읽기 실패 {e}"); continue
        print(f"\n[{p.name}] {len(df):,}행{' (대용량: 앞 50만 행만)' if big else ''}, {df.shape[1]}열")
        for c in df.columns:
            s = df[c]; ex = s.dropna().iloc[0] if s.notna().any() else ""
            rows.append(dict(file=p.name, column=c, dtype=str(s.dtype), null_rate=round(float(s.isna().mean()), 4), n_unique=int(s.nunique()) if s.dtype == object or s.nunique() < 1000 else -1,
                             example=str(ex)[:60], definition="", base_sample="", derived_from="", topic_papers_only=""))
        sm = pd.DataFrame(rows[-df.shape[1]:])[["column", "dtype", "null_rate", "example"]]; print(sm.head(60).to_string(index=False))
    pd.DataFrame(rows).to_csv(S2 / "variable_dictionary_skeleton.csv", index=False, encoding="utf-8-sig")
    print("\n저장: variable_dictionary_skeleton.csv (definition, base_sample, derived_from, topic_papers_only 열은 직접 채움)")
    others = [str(p.relative_to(ROOT)) for p in (ROOT / "analysis_data").rglob("*") if p.is_file() and re.search(r"topic|embed|specter|cluster", p.name, re.I)]
    print("토픽·임베딩 관련 파일 후보:", others[:30] or "없음")
    tf = find_topic(quiet=True)
    if tf: print(f"토픽 열 후보: {tf[0]} / {tf[1]}")

def find_topic(quiet=False):
    if TOPIC_FILE:
        p = DATA / TOPIC_FILE if (DATA / TOPIC_FILE).exists() else ROOT / TOPIC_FILE
        if not TOPIC_COL: raise Halt("TOPIC_FILE을 지정했으면 TOPIC_COL도 지정하세요")
        return p, TOPIC_COL
    cands = []
    for p in sorted(DATA.iterdir()):
        if not p.is_file(): continue
        try:
            if p.suffix == ".parquet":
                import pyarrow.parquet as pq; cols = pq.ParquetFile(p).schema.names
            elif p.suffix == ".csv" or p.name.endswith(".csv.gz"): cols = list(pd.read_csv(p, nrows=3).columns)
            else: continue
        except Exception: continue
        if TOPIC_PID_COL in cols: cands += [(p, c) for c in cols if re.search(r"topic", c, re.I)]
    if len(cands) == 1: return cands[0]
    if quiet: print("토픽 열 후보(여러 개 또는 없음):", [(p.name, c) for p, c in cands]); return None
    raise Halt(f"토픽 열을 하나로 정하지 못했습니다. 후보 {[(p.name, c) for p, c in cands]}. TOPIC_FILE/TOPIC_COL을 지정하세요")

def load_has_topic(F):
    p, col = find_topic(); T = load_any(p, None); T[TOPIC_PID_COL] = T[TOPIC_PID_COL].astype(str)
    print(f"토픽 파일 {p.name}, 열 {col}: 값 분포 상위", T[col].value_counts(dropna=False).head(8).to_dict())
    ok = T[col].notna() & ~T[col].isin(TOPIC_MISSING_VALUES)
    m = dict(zip(T.loc[ok, TOPIC_PID_COL], T.loc[ok, col]))
    F = F.copy(); F["topic"] = F.pid.map(m); F["has_topic"] = F.topic.notna().astype(int)
    print(f"F1X {len(F):,}편 중 토픽 보유 {F.has_topic.mean():.1%} (계획서 EDA: 결측 약 21%와 대조)")
    return F

# ============================================================
# [clean_flags] 정리 규칙 2.8 (표시만, 제거하지 않음)
# ============================================================
def normt(s): return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()

def st_clean_flags():
    hdr("[clean_flags] 비연구 항목 규칙 표시"); spec = check_prereg(); cr = spec["clean_rules"]
    F = load_F1X(); F["t"] = F.title.fillna("").map(normt)
    F["f_bib"] = F.title.fillna("").str.contains(cr["bib_section"], case=False, regex=True)
    F["f_vtmr"] = (F.venue_short == cr["vt_mobile_radio"]["venue"]) & F.title.fillna("").str.contains(cr["vt_mobile_radio"]["regex"], case=False, regex=True)
    cnt = F[F.t != ""].groupby(["venue_short", "t"]).pid.transform("size"); F["f_repeat"] = False; F.loc[cnt.index, "f_repeat"] = cnt >= cr["repeat_title_min"]
    F["f_dup"] = False; d = F[F.t != ""].duplicated(["venue_short", "year", "t"], keep="first"); F.loc[d[d].index, "f_dup"] = True
    flags = ["f_bib", "f_vtmr", "f_repeat", "f_dup"]; F["any_flag"] = F[flags].any(axis=1)
    try:
        tp, tc = find_topic(quiet=True) or (None, None)
        if tp is not None:
            G = load_has_topic(F); F["f_topic18"] = G.topic.isin(cr["topic_excluded"]).values; flags.append("f_topic18"); F["any_flag"] |= F.f_topic18
    except Exception as e: print("※ 주제 18번 규칙은 토픽 파일 확인 후 적용:", e)
    print("규칙별 표시 건수:", {f: int(F[f].sum()) for f in flags}, "| 하나라도:", int(F.any_flag.sum()), f"({F.any_flag.mean():.2%})")
    print("(참고: 계획서의 '중복 제목 459행'과 f_dup 건수를 대조. 다르면 정의가 다른 것이니 이유를 확인)")
    F[["pid", "year", "venue_short"] + flags + ["any_flag"]].to_csv(S2 / "clean_flags.csv", index=False)
    rng = np.random.default_rng(SEED); S = []
    for f in flags:
        g = F[F[f]]; S.append(g.sample(min(30, len(g)), random_state=SEED)[["pid", "venue_short", "year", "title"]].assign(rule=f, correct=""))
    pd.concat(S).to_csv(S2 / "clean_review_samples.csv", index=False, encoding="utf-8-sig"); print("규칙별 30건 표본 저장: clean_review_samples.csv (correct 열에 1/0 수작업 확인)")
    rp = F[F.f_repeat].groupby(["venue_short", "t"]).size().sort_values(ascending=False).head(30).reset_index(name="n"); rp.to_csv(S2 / "top_repeated_titles.csv", index=False, encoding="utf-8-sig")
    print("반복 제목 상위:\n", rp.head(10).to_string(index=False))
    vy = F.groupby(["venue_short", "year"]).agg(n=("pid", "size"), **{f: (f, "sum") for f in flags}, any_flag=("any_flag", "sum")).reset_index(); vy["any_share"] = vy.any_flag / vy.n
    sp = next(iter(SC.glob("**/scimago_journal_year.csv")), None)
    if sp is not None:
        S_ = pd.read_csv(sp)
        if {"venue_short", "year", "d_noncitable_share_3y"} <= set(S_.columns):
            vy = vy.merge(S_[["venue_short", "year", "d_noncitable_share_3y"]], on=["venue_short", "year"], how="left")
            x = vy.dropna(subset=["d_noncitable_share_3y"]); x = x[x.n >= 20]
            print(f"[참고] 표시 비중과 Scimago 비인용 문서 비중의 Spearman {x.any_share.corr(x.d_noncitable_share_3y, method='spearman'):.2f} (n={len(x)} 칸, 정의가 달라 목표가 아니라 그럴듯함 점검)")
    else: print("※ scimago_journal_year.csv를 찾지 못해 Scimago 병기 생략")
    vy.to_csv(S2 / "clean_summary_venue_year.csv", index=False, encoding="utf-8-sig")
    changelog(f"- {now()} | clean_flags 실행: 정리 규칙 표시만(제거 안 함), 건수 {{{', '.join(f'{f}:{int(F[f].sum())}' for f in flags)}}} | S2.8 | 제거 전후 비교는 별도")

# ============================================================
# 가중치 4종과 복구판 국가 질량
# ============================================================
SCHEMES = ["equal", "inv_n_authors", "first_last", "full_count"]

def author_w(A, scheme):
    n = A["n"].values.astype(float); r = A["rank"].values
    if scheme == "full_count": return np.ones(len(A))
    if scheme in ("equal", "inv_n_authors"): return 1.0 / n   # 국가 층에서는 두 정의가 같은 값(위험군 제외 없음)
    if scheme == "first_last":
        return np.where(n == 1, 1.0, np.where(n == 2, 0.5, np.where((r == 0) | (r == n - 1), 0.3, 0.4 / np.maximum(n - 2, 1))))
    raise ValueError(scheme)

def country_mass(A, col, scheme):
    """A: pid, rank, n, <col>(국가 '|' 구분, 빈 문자열=미상). 반환: pid, country, w"""
    w = author_w(A, scheme); cs = A[col].where(A[col] != "", "UNK").str.split("|"); k = cs.str.len().values
    B = pd.DataFrame({"pid": A.pid.values, "country": cs.values, "w": w if scheme == "full_count" else w / k})
    return B.explode("country").groupby(["pid", "country"], as_index=False).w.sum()

def extra_unk(D, scheme):
    n = D.n_authors.fillna(1).astype(float).values
    return pd.DataFrame({"pid": D.pid.values, "country": "UNK", "w": n if scheme == "full_count" else 1.0})

def build_authorship(F):
    A = read_tbl("authorship_level"); A["pid"] = A.pid.astype(str); A["countries"] = A.countries.fillna("")
    Rr = pd.read_csv(S1 / "authorship_level_recovered.csv.gz", dtype={"pid": str}); Rr["countries_rec"] = Rr.countries_rec.fillna("")
    A = A.merge(Rr[["pid", "rank", "countries_rec"]], on=["pid", "rank"], how="left"); A["countries_rec"] = A.countries_rec.fillna("")
    A["cs_main"] = A.countries; A["cs_rec"] = np.where((A.countries == "") & (A.countries_rec != ""), A.countries_rec, A.countries)
    A["n"] = A.groupby("pid")["rank"].transform("size")
    return A

def st_country_rec():
    hdr("[country_rec] 가중치(국가 층은 equal=inv_n이라 실질 3종) x (주, 복구) 국가 질량 + 불변식"); check_prereg()
    F = load_F1X(); D = F[F.year >= WINDOW]; A = build_authorship(F); ok = True; L = []
    ex = D[~D.pid.isin(A.pid)]; print(f"창 안 논문 {len(D):,} | authorship 있는 논문 {A.pid.nunique():,} | 없는 논문(국가 미상 처리) {len(ex):,}")
    for var, col in [("main", "cs_main"), ("rec", "cs_rec")]:
        for sc in SCHEMES:
            M = pd.concat([country_mass(A, col, sc), extra_unk(ex, sc)]); M["scheme"] = sc; M["variant"] = var; L.append(M)
            ps = M.groupby("pid").w.sum(); nn = A.groupby("pid").n.first().reindex(ps.index).fillna(F.set_index("pid").n_authors.reindex(ps.index))
            if sc in ("equal", "inv_n_authors", "first_last"): t = np.allclose(ps, 1.0)
            else: t = bool((ps.values >= nn.fillna(1).values - 1e-9).all())
            print(f"  불변식 질량 [{var}/{sc}] 논문당 합: {'PASS' if t else 'FAIL'}"); ok &= bool(t)
    L = pd.concat(L).merge(F[["pid", "year", "venue_short"]], on="pid")
    P = read_tbl("country_authorship"); P["pid"] = P.pid.astype(str)
    Mo = L[(L.variant == "main") & (L.scheme == "inv_n_authors")][["pid", "country", "w"]].merge(P[["pid", "country", "w"]], on=["pid", "country"], how="outer", suffixes=("_new", "_old")).fillna(0)
    dmax = float((Mo.w_new - Mo.w_old).abs().max()); t = dmax < 1e-9; ok &= t; print(f"  재현 점검: 재구축(main, inv_n)이 S1 country_authorship과 일치, 최대 차이 {dmax:.2e}: {'PASS' if t else 'FAIL'}")
    u = L[L.scheme == "inv_n_authors"].assign(unk=lambda d: d.country == "UNK").groupby(["variant", "year"]).apply(lambda d: d.w[d.unk].sum() / d.w.sum()).unstack(0).round(3)
    print("연도별 미상 질량 몫(inv_n, 논문 단위):\n", u.T.to_string())
    L.to_parquet(S2 / "country_mass_long.parquet", index=False) if _has_pa() else L.to_csv(S2 / "country_mass_long.csv.gz", index=False, compression="gzip")
    if not ok: raise Halt("불변식 FAIL: 이후 단계를 진행하지 마세요")
    changelog(f"- {now()} | country_rec: 4종 가중치 x (주, 복구) 국가 질량 생성, 불변식 PASS, S1 재현 최대 차이 {dmax:.1e} | S2.1, S7 민감도")

def _has_pa():
    try: import pyarrow; return True
    except Exception: return False

def load_mass():
    p = S2 / "country_mass_long.parquet"
    return pd.read_parquet(p) if p.exists() else pd.read_csv(S2 / "country_mass_long.csv.gz", dtype={"pid": str})

# ============================================================
# [weights_country] 핵심 C4 부호표: 4종 가중치 x 변형 x 표본 x 영토
# ============================================================
def yearly_stats(L, fixed, sample, terr):
    d = L if sample == "all" else L[L.venue_short.isin(fixed)]
    if terr: d = d.assign(country=d.country.replace({"HK": "CN", "MO": "CN"}))
    g = d.groupby(["year", "country"]).w.sum().unstack(fill_value=0); tot = g.sum(axis=1)
    kn = g.drop(columns=[c for c in ["UNK", "ZZ_former"] if c in g.columns]); kt = kn.sum(axis=1)
    top5 = kn.apply(lambda r: r.nlargest(5).sum(), axis=1)
    return pd.DataFrame(dict(top5_incl=top5 / tot, top5_known=top5 / kt, hhi_known=((kn.div(kt, axis=0)) ** 2).sum(axis=1),
                             cn_known=kn.get("CN", 0) / kt, us_known=kn.get("US", 0) / kt, unk=g.get("UNK", 0) / tot))

def st_weights_country():
    hdr("[weights_country] C4 부호표"); spec = check_prereg(); fixed = json.loads((S0 / "PREREG.json").read_text(encoding="utf-8"))["event"]["fixed_venues"]
    L = load_mass(); R = []; Y = []
    for (sc, var), d in L.groupby(["scheme", "variant"]):
        for sample in ["all", "fixed"]:
            for terr in [False, True]:
                S = yearly_stats(d, fixed, sample, terr); yrs = S.index.values.astype(float)
                for st in S.columns:
                    y = S[st]; R.append(dict(scheme=sc, variant=var, sample=sample, terr_merge=terr, stat=st, spearman=y.corr(pd.Series(y.index, index=y.index), method="spearman"), slope=np.polyfit(yrs, y.values, 1)[0], n_years=len(y)))
                Y.append(S.assign(scheme=sc, variant=var, sample=sample, terr_merge=terr).reset_index())
    R = pd.DataFrame(R); R["sign"] = np.sign(R.spearman).astype(int); pd.concat(Y).to_csv(S2 / "country_year_stats.csv", index=False)
    R.to_csv(S2 / "weights_signs_long.csv", index=False)
    key = ["variant", "sample", "terr_merge", "stat"]; A = R.groupby(key).agg(signs=("sign", lambda s: "".join("+" if v > 0 else "-" if v < 0 else "0" for v in s)), agree=("sign", lambda s: s.nunique() == 1),
                                                                         rho_min=("spearman", "min"), rho_max=("spearman", "max")).reset_index()
    A.to_csv(S2 / "weights_signs_summary.csv", index=False)
    core = A[A.stat.isin(["top5_incl", "top5_known", "hhi_known"])]
    print("핵심 C4(top5_incl, top5_known, hhi_known): 조합 중 4종 가중치 부호 일치 비율", f"{core.agree.mean():.2%}", f"({int(core.agree.sum())}/{len(core)})")
    print(core.pivot_table(index=["variant", "sample", "terr_merge"], columns="stat", values="signs", aggfunc="first").to_string())
    print("\n(scheme 순서는 equal, first_last, full_count, inv_n_authors의 알파벳 정렬 순서)")
    print("부호가 갈린 조합:\n", A[~A.agree][key + ["signs", "rho_min", "rho_max"]].round(2).to_string(index=False) if (~A.agree).any() else "없음")
    print("※ 연도 19개 Spearman이라 |rho|가 작으면 부호는 불안정합니다. rho_min/rho_max를 같이 보세요. 판정은 prereg의 pass_rule(부호 일치)이며 크기 기준은 없음")
    changelog(f"- {now()} | weights_country 실행: C4 부호 일치 {int(core.agree.sum())}/{len(core)} 조합 | S2.1 판정(핵심 목록 C4만)")

# ============================================================
# [unk_resid] 2024~2025 잔여 미상 표본
# ============================================================
def st_unk_resid():
    hdr("[unk_resid] 복구 후 잔여 미상(2024~2025) 표본"); check_prereg()
    F = load_F1X(); A = build_authorship(F).merge(F[["pid", "year", "venue_short"]], on="pid")
    U = A[(A.cs_rec == "") & (A.raw_aff.fillna("") != "") & A.year.isin([2024, 2025])]
    print(f"2024~2025 소속 문자열은 있으나 복구 후에도 미상: {len(U):,}건"); n = A[A.year.isin([2024, 2025])]; print(f"  전체 authorship 대비 {len(U) / len(n):.2%}")
    S = U.sample(min(30, len(U)), random_state=SEED)[["pid", "rank", "year", "venue_short", "raw_aff"]].assign(note=""); S.to_csv(S2 / "unk_resid_2024_25_sample.csv", index=False, encoding="utf-8-sig")
    print("저장: unk_resid_2024_25_sample.csv (30건을 읽고 note에 원인 유형 기입: 형식 문제, 기관명만, 빈 문자열 등)")
    V = A[(A.cs_rec == "") & A.year.isin([2024, 2025])]; print("소속 문자열 자체가 빈 비중(복구 후 미상 중):", f"{(V.raw_aff.fillna('') == '').mean():.1%}")

# ============================================================
# [missing] 토픽 결측 2.6
# ============================================================
def st_missing():
    hdr("[missing] 토픽 결측 분해 + 성향 가중"); check_prereg(); pp = check_prereg()["propensity"]
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_predict, StratifiedKFold
    from sklearn.metrics import roc_auc_score
    F = load_has_topic(load_F1X()); F = F[F.year >= TOPIC_START].copy()
    F["nb"] = pd.cut(F.n_authors.fillna(1), [0, 1, 2, 3, 4, 5, 10, 1e9], labels=["1", "2", "3", "4", "5", "6-10", "11+"]).astype(str); F["solo"] = (F.n_authors == 1).astype(int)
    L = load_mass(); L = L[(L.scheme == "inv_n_authors") & (L.variant == "main")]; K = L[L.country != "UNK"].sort_values("w", ascending=False).drop_duplicates("pid").set_index("pid").country
    top = K.value_counts().head(8).index; F["cg"] = F.pid.map(K).map(lambda c: c if c in top else "other" if isinstance(c, str) else "UNK"); F.loc[F.year < WINDOW, "cg"] = "pre_window"
    T = []
    for dim, col in [("year", "year"), ("venue", "venue_short"), ("n_authors", "nb"), ("solo", "solo"), ("country_group", "cg")]:
        g = F.groupby(col).has_topic.agg(["size", "mean"]).reset_index().rename(columns={col: "level", "size": "n", "mean": "has_topic_rate"}); g["dim"] = dim; T.append(g)
    T = pd.concat(T); T.to_csv(S2 / "missingness_tables.csv", index=False, encoding="utf-8-sig")
    print("연도별 토픽 보유율:", F.groupby("year").has_topic.mean().round(3).to_dict()); print("저널별(하위 8):\n", T[T.dim == "venue"].sort_values("has_topic_rate").head(8).to_string(index=False))
    sp = SC / "coverage_vs_scopus.csv"
    if sp.exists():
        C = pd.read_csv(sp); cell = F.groupby(["venue_short", "year"]).has_topic.agg(["size", "mean"]).reset_index().rename(columns={"mean": "topic_rate"}); X = cell.merge(C[["venue_short", "year", "ratio", "flag"]], on=["venue_short", "year"], how="inner"); X = X[X["size"] >= 20]
        print(f"[Scopus 분모] 칸 {len(X)}개: 코퍼스/Scopus 비와 토픽 보유율의 Spearman {X.ratio.corr(X.topic_rate, method='spearman'):.2f}"); print(X.groupby("flag").topic_rate.agg(["size", "mean"]).round(3).to_string())
        X.to_csv(S2 / "missingness_vs_scopus.csv", index=False)
    out = []; W = {}
    for name, sub, cats in [("A", F, ["year", "venue_short", "nb"]), ("B", F[F.year >= WINDOW], ["year", "venue_short", "nb", "cg"])]:
        X = pd.get_dummies(sub[cats].astype(str), drop_first=True).astype(float); X["solo"] = sub.solo.values; y = sub.has_topic.values
        m = LogisticRegression(C=10, max_iter=2000); m.fit(X, y); p = m.predict_proba(X)[:, 1]
        pcv = cross_val_predict(LogisticRegression(C=10, max_iter=2000), X, y, cv=StratifiedKFold(pp["cv_folds"], shuffle=True, random_state=SEED), method="predict_proba")[:, 1]
        auc, aucv = roc_auc_score(y, p), roc_auc_score(y, pcv); pbar = y.mean(); w = np.where(y == 1, pbar / np.clip(p, 1e-6, 1), np.nan)
        lo, hi = np.nanpercentile(w, pp["clip_pct"]); wc = np.clip(w, lo, hi); ess = np.nansum(wc) ** 2 / np.nansum(wc ** 2); nt = int(y.sum()); low = p < pp["positivity_floor"]
        print(f"[모형 {name}] n={len(sub):,}, 토픽 보유 {nt:,} | AUC {auc:.3f} (CV {aucv:.3f}) | 유효 표본 {ess:,.0f} ({ess / nt:.1%}) | 절단 [{lo:.2f}, {hi:.2f}] | 양수성: 성향<{pp['positivity_floor']} 논문 {low.mean():.2%}")
        if low.any(): print("   양수성 위반 상위 저널:", sub[low].venue_short.value_counts().head(5).to_dict(), "→ 분리 보고와 경계(최악·최선 대입) 분석 대상")
        out.append(pd.DataFrame(dict(pid=sub.pid.values, model=name, p=p, w_ipw=wc, has_topic=y, low_p=low))); W[name] = dict(auc=auc, auc_cv=aucv, ess=ess, n_topic=nt, low_share=float(low.mean()))
    pd.concat(out).to_csv(S2 / "paper_ipw.csv.gz", index=False, compression="gzip"); json.dump(W, open(S2 / "propensity_diag.json", "w"), indent=1)
    print("※ 코호트(저자 층)와 경계 분석(최악·최선 대입)은 F4 구조 확인 후 추가. 가중치는 주제 논문 대상 분석에만 쓰고, 국가·연도 공급 몫은 토픽 유무와 무관하게 전체 논문으로 계산(2.6d)")
    changelog(f"- {now()} | missing 실행: 토픽 보유율 {F.has_topic.mean():.3f}, 모형 A/B 진단은 propensity_diag.json | S2.6")

# ============================================================
# [f2_check] F2/F1 정의 점검 (읽기 전용)
# ============================================================
def st_f2_check():
    hdr("[f2_check] F2 가중치 정의와 F1 열 점검")
    F1 = pd.read_csv(DATA / "F1_papers.csv", low_memory=False); F2 = pd.read_csv(DATA / "F2_author_paper.csv"); R = pd.read_csv(DATA / "F2_risk_names.csv")
    print("F1 in_sample:", F1.in_sample.value_counts().to_dict(), "| has_topic:", F1.has_topic.value_counts().to_dict(), "| (topic150 결측과 has_topic 일치:", bool((F1.topic150.notna() == F1.has_topic).all()), ")")
    print("in_sample x has_topic:\n", pd.crosstab(F1.in_sample, F1.has_topic).to_string())
    print("창(2007+) 안 in_sample False 논문:", int(((~F1.in_sample) & (F1.year >= WINDOW)).sum()), "(S1 국가 층은 in_sample을 거르지 않았음. 0이 아니면 2.6d 정의와 대조)")
    try:
        fv = set(json.loads((S0 / "PREREG.json").read_text(encoding="utf-8"))["event"]["fixed_venues"]); fx = set(F1[F1.fixed_venue].venue_short)
        print(f"F1.fixed_venue 저널 {len(fx)}개 vs PREREG 고정 저널 {len(fv)}개 | 같음: {fx == fv}")
        if fx != fv:
            print("   F1에만 있음:", sorted(fx - fv), "| PREREG에만 있음:", sorted(fv - fx))
            for v in sorted(fx ^ fv): q = F1[F1.venue_short == v]; print(f"   {v}: 논문 {len(q):,}편, 연도 {q.year.min()}~{q.year.max()}, F1.fixed_venue={bool(q.fixed_venue.any())}")
            print("   → S0 CHANGELOG에서 이 저널을 고정 목록에서 뺀(또는 넣은) 사유를 확인하세요. 분석은 PREREG 목록을 씁니다.")
    except Exception as e: print("PREREG 고정 저널 대조 실패:", e)
    g = F2.groupby("pid").agg(rows=("w", "size"), wsum=("w", "sum"), n=("n_authors", "first"), wmin=("w", "min"), wmax=("w", "max")).reset_index()
    print(f"\nF2 논문 {len(g):,}편 | F1 has_topic 논문 {int(F1.has_topic.sum()):,} | F2 pid가 F1 has_topic에 속함: {g.pid.isin(F1[F1.has_topic].pid).mean():.1%}")
    print(f"행 수 == n_authors(저자 전원 보존) 논문 비율: {(g.rows == g.n).mean():.1%} | 행 보존율(행/n_authors 합): {g.rows.sum() / g.n.sum():.1%}")
    print(f"w == 1/n_authors 인 행: {(np.abs(F2.w - 1 / F2.n_authors) < 1e-9).mean():.1%} | w == 1/(그 논문의 F2 행 수) 인 논문: {(np.abs(g.wmin - 1 / g.rows) < 1e-9).mean():.1%}")
    print("논문별 w 합 분위수:", g.wsum.quantile([0, .05, .25, .5, .95, 1]).round(3).to_dict(), f"| 합이 1(±1e-6)인 논문 {(np.abs(g.wsum - 1) < 1e-6).mean():.1%}")
    miss = F1[F1.has_topic & ~F1.pid.isin(g.pid)]
    print(f"has_topic인데 F2에 없는 논문 {len(miss):,}편(전원이 위험군 이름이어서 빠졌을 가능성): n_authors 분포 {miss.n_authors.value_counts().head(5).to_dict()}, 연도 중앙값 {miss.year.median():.0f}")
    print(f"위험군 이름 {len(R):,}개(ambiguous {int(R.ambiguous.sum())}, heavy {int(R.heavy.sum())}) | F2 행 중 위험군 이름 {F2.name_norm.isin(R.name_norm).mean():.2%}")
    m = F2.drop_duplicates("pid").merge(F1[["pid", "topic150"]], on="pid", suffixes=("", "_f1")); print(f"F2.topic150 == F1.topic150: {(m.topic150 == m.topic150_f1).mean():.1%}")
    print("\n해석: w가 1/(F2 행 수)이고 합이 모두 1이면 F2 = 위험군을 뺀 뒤 재정규화한 가중치(equal). inv_n_authors는 1/n_authors로 따로 만들어야 함.")

# ============================================================
# [risk] 위험군 재현율 2.2 (F2_risk_names 플래그 vs F7의 이름당 OpenAlex ID 수)
# ============================================================
def st_risk():
    hdr("[risk] 위험군 플래그 precision/recall (이름당 OpenAlex ID 2개 이상 = 분리된 사람의 근사 정답)"); check_prereg()
    R = pd.read_csv(DATA / RISK_FILE); D = pd.read_csv(DATA / F7_FILE, low_memory=False).dropna(subset=["name_norm"]); F1 = pd.read_csv(DATA / "F1_papers.csv", usecols=["pid", "year"])
    cov = D.merge(F1, on="pid").groupby("year").size(); print("F7 행의 연도 분포(10년 단위):", cov.groupby(cov.index // 10 * 10).sum().to_dict(), "| F7은 일부 authorship만 담고 있을 수 있음: 이 범위가 평가 범위")
    X = pd.DataFrame({"n_ids": D.groupby("name_norm").oa_id.nunique(), "n_rows": D.groupby("name_norm").size()}); X["multi"] = X.n_ids >= 2
    X = X.join(R.set_index("name_norm")[["ambiguous", "heavy"]]); X["ambiguous"] = X.ambiguous.fillna(False).astype(bool); X["heavy"] = X.heavy.fillna(False).astype(bool)
    print(f"F7 이름 {len(X):,}개 | 근사 정답(ID>=2) {int(X.multi.sum()):,} | 위험군 이름 중 F7에 없는 것 {int((~R.name_norm.isin(X.index)).sum())}/{len(R)}")
    out = []
    for scope, d in [("전체 이름", X), ("F7 행 2개 이상 이름", X[X.n_rows >= 2])]:
        for nm, fl in [("ambiguous", d.ambiguous), ("heavy", d.heavy), ("ambiguous|heavy", d.ambiguous | d.heavy)]:
            tp = int((d.multi & fl).sum()); prec = tp / max(int(fl.sum()), 1); rec = tp / max(int(d.multi.sum()), 1)
            out.append(dict(scope=scope, flag=nm, n_names=len(d), n_multi=int(d.multi.sum()), n_flag=int(fl.sum()), tp=tp, precision=round(prec, 3), recall=round(rec, 3)))
    O = pd.DataFrame(out); print(O.to_string(index=False)); O.to_csv(S2 / "risk_names_recall.csv", index=False)
    print("※ 정답이 근사입니다: 한 사람의 ID 분할도 ID>=2로 잡히고, 이름당 행이 1개뿐이면 ID>=2가 불가능합니다. 그래서 행 2개 이상 이름 기준을 병기했습니다. 동결된 위험군 변형 7종(PREREG variant_names)별 분해는 변형 정의 열이 이 파일에 없어 하지 않음")
    changelog(f"- {now()} | risk 실행(F2_risk_names 플래그 vs F7 이름당 ID 수): {out[-1]['flag']} / {out[-1]['scope']} precision {out[-1]['precision']}, recall {out[-1]['recall']} | S2.2")

# ============================================================
# [risk_selection] 위험군 이름 제외가 국가 구성에 주는 선택 효과 (F2에 없는 authorship = 제외된 저자)
# ============================================================
def st_risk_selection():
    hdr("[risk_selection] 위험군 이름 제외의 국가 선택 효과 (2007년 이후, 주제 논문)"); check_prereg()
    F = load_F1X(); A = build_authorship(F).merge(F[["pid", "year"]], on="pid")
    F2 = pd.read_csv(DATA / "F2_author_paper.csv", usecols=["pid", "name_norm", "author_pos"]); F2["pid"] = F2.pid.astype(str); F2["rank"] = F2.author_pos - 1
    F7 = pd.read_csv(DATA / F7_FILE, dtype={"pid": str}).dropna(subset=["name_norm"])
    j = F7.merge(F2[["pid", "rank", "name_norm"]], on=["pid", "rank"], suffixes=("_f7", "_f2"))
    print(f"[정렬 가정 검증] F7(pid, rank)와 F2(pid, author_pos-1) 매칭 {len(j):,}행, 이름 일치율 {(j.name_norm_f7 == j.name_norm_f2).mean():.1%} (author_pos = rank+1 가정)")
    T = A[A.pid.isin(set(F2.pid))].merge(F2[["pid", "rank"]].assign(kept=True), on=["pid", "rank"], how="left"); T["kept"] = T.kept.fillna(False).astype(bool)
    f2rows = int(F2.pid.isin(set(T.pid)).sum()); print(f"[정합] 창 안 주제 논문 {T.pid.nunique():,}편 | F2 행 {f2rows:,} vs authorship_level에서 F2와 매칭된 행 {int(T.kept.sum()):,}: {'PASS' if f2rows == int(T.kept.sum()) else 'FAIL(정렬 가정 또는 저자 순서 불일치 의심)'}")
    print(f"제외된 authorship 비중 {(~T.kept).mean():.1%}")
    T["c1"] = T.cs_main.str.split("|").str[0].replace("", "UNK"); top = T.c1.value_counts().head(8).index; T["cg"] = np.where(T.c1.isin(top), T.c1, "other")
    print("국가군별 제외 비중:\n", T.groupby("cg").kept.agg(n="size", dropped=lambda s: 1 - s.mean()).sort_values("n", ascending=False).round(3).to_string())
    Tk = T[T.kept].copy(); Tk_eq = Tk.copy(); Tk_eq["n"] = Tk_eq.groupby("pid")["rank"].transform("size")
    parts = {"전체 authorship(S1 방식)": country_mass(T, "cs_main", "inv_n_authors"), "equal(제외 후 재정규화)": country_mass(Tk_eq, "cs_main", "equal"), "inv_n(제외 질량 손실)": country_mass(Tk, "cs_main", "inv_n_authors")}
    yr = F.set_index("pid").year; rows = []
    for nm, M in parts.items():
        M = M.assign(year=M.pid.map(yr)); M["per"] = pd.cut(M.year, [2006, 2013, 2019, 2025], labels=["2007-13", "2014-19", "2020-25"])
        for per, g in M.groupby("per", observed=True):
            tot = g.w.sum(); kn = g[~g.country.isin(["UNK", "ZZ_former"])]; kt = kn.w.sum()
            for c in ["CN", "US", "HK"]: rows.append(dict(scheme=nm, period=str(per), country=c, share_incl_unk=g[g.country == c].w.sum() / tot, share_known=kn[kn.country == c].w.sum() / kt, mass=tot))
    R = pd.DataFrame(rows); R.to_csv(S2 / "risk_selection_country_shares.csv", index=False)
    print("\n국가 몫(국가 아는 질량 분모): 제외가 국가 구성을 바꾸는지\n", R.pivot_table(index=["country", "period"], columns="scheme", values="share_known").round(3).to_string())
    print("※ 위험군은 흔한 이름이라 동아시아 저자가 많이 빠질 수 있음: 저자 층 결과(S6, S7.2)의 지역 구성은 이 선택을 한계로 보고. 국가 층(S7)은 제외하지 않은 값이 주 분석")
    changelog(f"- {now()} | risk_selection 실행: 제외 authorship {(~T.kept).mean():.3f}, 국가별 제외 비중과 몫 차이는 risk_selection_country_shares.csv | S2.2, S6.6 범위 보고")

# ============================================================
# [commit]
# ============================================================
def st_commit():
    hdr("[commit] S2 산출물 해시 + 커밋 + 태그"); check_prereg()
    M = [dict(file=str(f.relative_to(ROOT)), sha256=sha_f(f)) for f in sorted(S2.glob("*")) if f.is_file() and f.name != "S2_MANIFEST.csv" and f.stat().st_size < 200e6]
    pd.DataFrame(M).assign(at=now()).to_csv(S2 / "S2_MANIFEST.csv", index=False); print(f"manifest {len(M)}개")
    if not COMMIT: print("COMMIT=False: 커밋 안 함"); return
    tag = TAG_NAME or f"S2-stageAB-{pd.Timestamp.now().strftime('%Y-%m-%d')}"
    if git("tag", "-l", tag).stdout.strip(): raise Halt(f"태그 {tag} 이미 있음")
    big = [f.name for f in S2.glob("*") if f.is_file() and f.stat().st_size > 50e6]
    if big: print("⚠ 50MB 초과 파일(커밋 용량 주의):", big)
    git("add", "--", "paper1/02_S2", check=True); c = git("commit", "-m", "S2 measurement stage A/B outputs"); print((c.stdout + c.stderr).strip()[:300]); git("tag", "-a", tag, "-m", "S2 stage A/B", check=True); print("태그:", tag)

FUNCS = {"schema": st_schema, "f2_check": st_f2_check, "prereg": st_prereg, "clean_flags": st_clean_flags, "country_rec": st_country_rec, "weights_country": st_weights_country,
         "unk_resid": st_unk_resid, "missing": st_missing, "risk": st_risk, "risk_selection": st_risk_selection, "commit": st_commit}

if __name__ == "__main__":
    assert S0.exists() and S1.exists(), "ROOT를 확인하세요"; S2.mkdir(parents=True, exist_ok=True); print(f"ROOT={ROOT} | STEPS={STEPS}")
    try:
        for s in STEPS: FUNCS[s]()
        print("\n✔ 요청한 단계 완료")
    except Halt as e: print(f"\n⛔ 중단: {e}")
