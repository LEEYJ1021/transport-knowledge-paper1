# -*- coding: utf-8 -*-
# s5_0_freeze.py: S5 규칙 동결(탐지 코드 실행 전). FREEZE=False로 점검 후 True.
import json, hashlib, subprocess
from pathlib import Path
import pandas as pd
FREEZE, COMMIT = False, True
ROOT = Path.home() / "Research/Minnesota_Transport"; S0, S4, S5 = ROOT / "paper1/00_S0", ROOT / "paper1/04_S4", ROOT / "paper1/05_S5"
now = lambda: pd.Timestamp.now().isoformat(timespec="seconds"); sha_b = lambda b: hashlib.sha256(b).hexdigest(); sha_f = lambda p: sha_b(Path(p).read_bytes())
ev = sorted(S0.glob("EVENTS_FROZEN*")); ev_csv = [p for p in ev if p.suffix == ".csv"]
if not ev_csv: raise SystemExit("⛔ 00_S0에서 EVENTS_FROZEN*.csv를 찾지 못했습니다. 사건 목록 위치를 확인하세요(새로 만들지 마세요)")
SPEC = dict(
    version=1, seed=2026, decision_status="모든 수치는 임의 출발값. 탐지 결과 열람 전에 동결.",
    principle="탐지는 사건 정보 없이 데이터만으로. 사건은 탐지 뒤 대조에만 사용. 주 시나리오 NONE이므로 사건 대조는 민감도 보고.",
    inputs=dict(series="paper1/04_S4/yearly_topic_shares_{all,fixed,within}.npy, yearly_series_for_S5.csv", window=[2000, 2025],
                geography="S1 창(2007~)만, 별도 시계열(S7 직전 구축). 이 동결에서는 주제 구조(a)만 탐지 대상", renewal="갱신 방식(b)은 저자 층이라 S6 직전으로 이월"),
    samples=["all", "fixed14", "within(저널 가중 고정, 저널 내 성분)"],
    detection=dict(method="인접 연도만 묶는 제약 군집화(동적계획 분할), 구간 비용=구간 내 연도 벡터의 제곱거리 합(JS 거리 제곱 근사 대신 sqrt-share Hellinger 변환 후 유클리드)",
                   n_segments="BIC형 벌점으로 선택, 벌점 = c * K_eff * log(T)", penalty_c=1.0, min_len=3, k_max=6,
                   secondary="변화점 위치는 단변량(주제 유효수, HHI) Bai-Perron형 분할로 교차 확인"),
    uncertainty=dict(block="논문 부트스트랩을 연도 x 저널 셀 안에서 복원추출", B=500, report="변화 시점의 90% 구간"),
    nulls=dict(label_permutation=dict(rule="주제 라벨을 저널 x 연도 셀 안에서 섞고 같은 탐지를 반복", B=500),
               gradual_trend=dict(rule="토픽 비중이 2000~2025 선형으로 변한다고 두고 연도별 표본 크기로 다항 표집", B=500, slope="관측 선형 기울기 추정치 사용"),
               pass="관측 구간 수가 두 귀무 분포의 상위 5% 밖(p<0.05) 또는 관측 최대 JS 점프가 귀무 상위 5% 밖"),
    split_half=dict(rule="유효 149개 토픽을 무작위 반분, 한쪽에서 찾은 변화점이 다른 쪽에서 +-1년 내 재현되는 비율", B=200, pass_min=0.50),
    detrended=dict(rule="각 토픽 비중에서 선형 추세 제거 후 재탐지, 변화점 유지 여부 비교"),
    artifact_flags=dict(years=[2007, 2020, 2025], reason="임베딩 보유율 꺾임(2007), 2020 논문 수 급증, 2025 보유율 하락·부분연도 가능성, T-IV 2025와 T-ITS 2008은 저널 단위 표시",
                        rule="탐지된 변화점이 표시 연도 +-1년이면 '측정 아티팩트 후보' 표기. 제거하지는 않음. 해당 연도 제외 재탐지를 민감도로 병행"),
    events=dict(file=ev_csv[0].name, sha256=sha_f(ev_csv[0]), E2_rule="연간 코퍼스 비중이 처음 2%를 넘는 해", tol_years=1, big_event="비중 증가폭 상위 50%",
                circular_shift_B=2000, tests="(i) 변화점 중 큰 사건 +-1년 비율, (ii) 큰 사건 중 +-1년 내 변화점 비율, 귀무=사건 날짜 순환이동",
                status="사건 목록은 S0 동결본을 그대로 사용. 탐지 결과 열람 후 수정 금지"),
    typology="구성 체제 / 내재 체제 / 미설명 전환 / 탐지 없음 (5.7 정의 그대로)",
    interpretation="체제 구간 비교는 기술적 비교이며 인과로 쓰지 않음. 2008 금융위기, 딥러닝, COVID는 탐색적 대조",
    fallback="귀무와 구분되지 않으면 '연속 변화' 서술로 전환",
    caveats=["분석 집합은 임베딩 보유 논문 83.9%, 보유율 연도 편중", "S4 안정성은 경계 통과(0.700)", "토픽은 제목 기반 K-means 150 고정(K 민감도는 별도)"],
)
h = sha_b(json.dumps(SPEC, sort_keys=True, ensure_ascii=False).encode()); print("S5-0 해시(예정)", h[:12], "| 사건 파일", ev_csv[0].name, SPEC["events"]["sha256"][:12])
p = S5 / "S5_0_PREREG.json"
if p.exists():
    old = json.loads(p.read_text(encoding="utf-8"))
    raise SystemExit("이미 동결됨: 동일" if old["sha256"] == h else "⛔ 동결된 규칙과 다릅니다. 새 버전으로 분리하고 CHANGELOG에 사유를 쓰세요")
if not FREEZE: raise SystemExit("(점검만) 확정 후 FREEZE=True")
need = ["yearly_series_for_S5.csv", "yearly_topic_shares_all.npy"]
if any(not (S4 / f).exists() for f in need): raise SystemExit("⛔ 4.6 산출물이 없습니다. s4_6_rotation.py를 먼저 실행하세요")
S5.mkdir(parents=True, exist_ok=True)
refs = {f: sha_f(S4 / f) for f in need + ["yearly_topic_shares_fixed.npy", "yearly_topic_shares_within.npy"]}
p.write_text(json.dumps(dict(SPEC, created=now(), sha256=h, reference_hashes_at_freeze=refs), ensure_ascii=False, indent=1), encoding="utf-8")
(S5 / "CHANGELOG_S5.md").write_text(f"# CHANGELOG S5\n\n- {now()} | S5-0 동결(해시 {h[:12]}): 제약 군집화, 두 귀무, 반분 재현, 아티팩트 표시, 사건 대조(S0 동결본 해시 {SPEC['events']['sha256'][:12]}). 4.6 산출물은 동결 전에 열람(시계열 JS 상위 연도 확인)했음. 모든 수치는 임의 출발값\n", encoding="utf-8")
print("저장:", p.name)
if COMMIT:
    g = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
    tag = f"S5-0-freeze-{pd.Timestamp.now().strftime('%Y-%m-%d')}"
    g("add", "--", "paper1/05_S5"); print(g("commit", "-m", "S5-0 freeze").stdout.strip()[:200]); g("tag", "-a", tag, "-m", "S5-0 freeze"); print("태그:", tag)