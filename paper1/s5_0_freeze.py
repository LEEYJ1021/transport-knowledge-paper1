# -*- coding: utf-8 -*-
# s5_0_freeze.py: S5 규칙 동결(탐지 실행 전). 순서: ① EV_YEAR_COL=None으로 실행해 사건 파일 열 확인 ② 열 이름 채우고 FREEZE=False 점검 ③ FREEZE=True
# 선행: s5_phi.py 실행(S5_phi.json), git 정리, 사건 파일(EVENTS_FROZEN*.csv)이 S1.9 확정본인지 확인. 모든 수치는 임의 출발값.
import sys, json, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from s5_lib import *

FREEZE, COMMIT = True, True
# 사건 집합 두 개: big(주, 큰 사건: E_share 연도) / entry(보조, 진입 사건: E1_effective_entry 연도). 값은 열 확인 후 확정.
EV_VENUE_COL = "venue_short"
EV_BIG_YEAR_COL, EV_BIG_FLAG_COL = "E_share5", "is_large_event"
EV_ENTRY_YEAR_COL, EV_ENTRY_FLAG_COL = "E1_effective_entry", "is_entry_event"
EV_PENDING_COL = "pending"      # True인 저널은 사건 집합에서 제외하고 기록(AMAR 등)

ev = sorted(S0.glob("EVENTS_FROZEN*.csv"))
if not ev: raise SystemExit("⛔ 00_S0에 EVENTS_FROZEN*.csv 없음. 새로 만들지 말고 위치 확인")
E = pd.read_csv(ev[0], encoding="utf-8-sig")
if not (EV_VENUE_COL and EV_BIG_YEAR_COL and EV_ENTRY_YEAR_COL):
    print("사건 파일:", ev[0].name, "| 열:", list(E.columns)); print(E.head(8).to_string()); raise SystemExit("→ 사건 열 설정을 채우고 다시 실행")
for c in [EV_VENUE_COL, EV_BIG_YEAR_COL, EV_BIG_FLAG_COL, EV_ENTRY_YEAR_COL, EV_ENTRY_FLAG_COL, EV_PENDING_COL]:
    if c not in E.columns: raise SystemExit(f"⛔ 열 {c} 없음")
need = [S5 / "S5_phi.json", S4 / "yearly_venue_topic_counts.npy", S4 / "venues_order.csv", S4 / "topics_order.csv", S4 / "yearly_series_for_S5.csv"]
if any(not p.exists() for p in need): raise SystemExit("⛔ 선행 산출물 없음(s5_phi.py 또는 4.6): " + str([p.name for p in need if not p.exists()]))
PHI = json.loads((S5 / "S5_phi.json").read_text(encoding="utf-8"))["phi"]

SPEC = dict(
    version=1, seed=2026, decision_status="모든 수치는 임의 출발값. 탐지 결과 열람 전에 동결. 4.6·4.6b 산출물은 동결 전에 열람했음(완전 비열람 아님).",
    principle="탐지는 사건 정보 없이 데이터만으로. 사건은 탐지 뒤 대조에만. 주 시나리오 NONE이므로 사건 대조는 민감도. 인과 해석 금지.",
    window=[2000, 2025], samples=SAMPLES, fixed_venues="PREREG.json의 fixed_venues 14개(F1 fixed_venue 열 사용 금지)",
    detection=dict(transform="x=sqrt(연도별 토픽 비중)", weight="w_t=4*n_t (within 표본은 n_t=전체 논문 수)", method="인접 연도 제약 군집화(동적계획)",
                   min_len=3, k_max=6, penalty="pen_per_segment = c*phi_s*(K-1)*log(T), 선택 k = argmin(cost_k + pen*k)",
                   c_primary=1.0, c_grid=[0.5, 1.0, 2.0], phi=PHI, phi_rule="max(1, N1 k=1 비용 중앙값/((T-1)(K-1))), s5_phi.py B=300",
                   univariate="주제 유효수, HHI, D3 점유율 각각 BIC 분할(교차 확인용, 판정 아님)"),
    bootstrap=dict(B=500, unit="연도x저널 셀 내 다항 재표집, 매번 선택 절차 전체 반복", report="변화점별 +-1년 재현율, 가까운 변화점의 5~95% 구간"),
    nulls=dict(B=500, N0="셀 크기만 유지하고 모든 논문을 무작위 배분(구조 전무)", N1="저널 안에서 연도 라벨 섞기(저널 규모 유지, 저널 내 시간 구조 제거)",
               N2="저널x토픽별 선형 추세(가중 OLS, 0 절단) + 관측 셀 크기 다항 표집(저널 구성은 관측 그대로)",
               stats=["k_sel", "R_ksel=1-cost_k/cost_1", "jump=선택 변화점 최대 Hellinger 점프"], primary_stat="R_ksel", alpha=0.05, p="(1+#{null>=obs})/(1+B)",
               pass_rule="N1과 N2 모두에서 R_ksel p<0.05 (N0는 참고)", deviation_from_plan="계획서의 '주제 라벨을 저널x연도 셀 안에서 섞기'는 셀 내 개수가 불변이라 무의미해 N1로 대체"),
    split_half=dict(B=200, tol=1, pass_min=0.50, samples=["all", "within"], cross_fit="한쪽 분할로 구간을 정하고 다른 쪽 비용 감소율 보고"),
    robust=dict(detrended=True, exclude_years=[2007, 2020, 2025], exclude_cells=[["T-IV", 2025], ["T-ITS", 2008], ["JPT", 2019]],
                A_grade_only=dict(tol=1, jump_tol=0.30), ipw_hook="yearly_venue_topic_counts_ipw.npy가 있으면 관측 탐지만 재실행",
                artifact_rule="변화점이 [2007,2020,2025] +-1년이면 '측정 아티팩트 후보' 표기(제거 아님)"),
    events=dict(file=ev[0].name, sha256=sha_f(ev[0]), venue_col=EV_VENUE_COL, pending_col=EV_PENDING_COL, sets=dict(big=dict(year_col=EV_BIG_YEAR_COL, flag_col=EV_BIG_FLAG_COL), entry=dict(year_col=EV_ENTRY_YEAR_COL, flag_col=EV_ENTRY_FLAG_COL), size=dict(year_col=EV_BIG_YEAR_COL, flag_col=None, elig_col='is_event_eligible', size_col='event_size', top_frac=0.5)), set_note='big=파일의 is_large_event(기준은 n_papers_at_large 유무로 추정, 생성 코드 미확인, TR-C는 event_size<0) / size=계획서 원 규칙(eligible 중 event_size 상위 50%) / entry=진입 사건. pending(TR-E, AMAR)은 제외', tol=1, circ_B=2000,
                tests="(i) 변화점 중 큰 사건 +-1년 비율 (ii) 큰 사건 중 +-1년 내 변화점 비율, 귀무=사건 연도 공통 순환이동",
                content="일치 변화점의 저널 간 성분 비중, 신규 저널 초기 3년 벡터와 변화 벡터의 코사인(다른 저널 귀무)"),
    typology=dict(rule="탐지 없음(N1,N2 미통과) / 내재(within 표본에서도 +-1년 탐지; 사건 일치면 '내재(사건일치)', 불일치면 '미설명 전환') / 구성(all에서만 탐지, 저널 간 성분>=0.5) / 그 외 '혼합·미분류'",
                  note="유형 규칙의 세부(저널 간 성분 0.5, within 탐지 +-1년)는 구현 선택"),
    geography_renewal="S5에서는 주제 구조만 탐지. 지리(2007~)와 갱신 방식(저자 층)은 S7·S6 직전 별도 동결",
    caveats=["분석 집합은 임베딩 보유 논문 83.9%", "부트스트랩·귀무는 논문 독립을 가정해 낙관적일 수 있음", "N2는 저널 구성을 관측 그대로 유지",
             "phi는 N1 기반이라 구성 신호를 일부 포함(보수적)", "S4 안정성은 경계 통과(0.700)"],
    fallback="귀무와 구분되지 않으면 '연속 변화' 서술로 전환(체제 서사 철회). S6·S7은 유지",
)
h = sha_b(json.dumps(SPEC, sort_keys=True, ensure_ascii=False).encode()); print("S5-0 해시(예정)", h[:12], "| 사건 파일", ev[0].name, SPEC["events"]["sha256"][:12]); print("phi:", PHI)
p = S5 / "S5_0_PREREG.json"
if p.exists():
    old = json.loads(p.read_text(encoding="utf-8")); raise SystemExit("이미 동결됨: 동일" if old["sha256"] == h else "⛔ 동결본과 다름. 새 버전으로 분리하고 CHANGELOG에 사유 기록")
if not FREEZE: raise SystemExit("(점검만) 확정 후 FREEZE=True")

refs_p = [Path(__file__).resolve().parent / "s5_lib.py", S5 / "S5_phi.json", ev[0], S0 / "PREREG.json"] + need[1:] + \
         [S4 / f for f in ["yearly_topic_shares_all.npy", "yearly_topic_shares_fixed.npy", "yearly_topic_shares_within.npy", "yearly_js_poolfloor_check.csv", "rotation_index_periods.csv"]]
refs = {str(q.relative_to(ROOT)): sha_f(q) for q in refs_p if q.exists()}
S5.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(dict(SPEC, created=now(), sha256=h, reference_hashes_at_freeze=refs), ensure_ascii=False, indent=1), encoding="utf-8")
(S5 / "CHANGELOG_S5.md").write_text(f"# CHANGELOG S5 (날짜 | 변경 | 사유 | 영향)\n\n- {now()} | S5-0 동결(해시 {h[:12]}): 제약 군집화, phi {PHI}, 귀무 N0/N1/N2, 반분, 아티팩트·추세 제거 재탐지, 사건 대조(S0 동결본 해시 {SPEC['events']['sha256'][:12]}). "
                                    f"4.6·4.6b 산출물은 동결 전에 열람. 모든 수치는 임의 출발값. 계획서의 라벨 순열은 N1로 대체 | S5 설계 | S5 전체\n", encoding="utf-8")
print("저장:", p.name, "| 참조 해시", len(refs), "개")
if COMMIT:
    g = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
    tag = f"S5-0-freeze-{pd.Timestamp.now().strftime('%Y-%m-%d')}"
    if g("tag", "-l", tag).stdout.strip(): raise SystemExit(f"⛔ 태그 {tag} 이미 있음")
    files = [str(q.relative_to(ROOT)) for q in [S5 / "S5_0_PREREG.json", S5 / "CHANGELOG_S5.md", S5 / "S5_phi.json", Path(__file__).resolve().parent / "s5_lib.py",
                                                  Path(__file__).resolve().parent / "s5_phi.py", Path(__file__).resolve()] if q.exists()]
    a = g("add", "--", *files)
    if a.returncode: raise SystemExit("⛔ git add 실패: " + a.stderr.strip())
    c = g("commit", "-m", "S5-0 freeze")
    if c.returncode: raise SystemExit("⛔ 커밋 실패: " + (c.stderr or c.stdout).strip())
    t = g("tag", "-a", tag, "-m", "S5-0 freeze")
    if t.returncode: raise SystemExit("⛔ 태그 실패: " + t.stderr.strip())
    print(c.stdout.strip()[:200], "| 태그:", tag)