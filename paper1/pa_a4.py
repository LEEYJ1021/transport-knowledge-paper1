# -*- coding: utf-8 -*-
# PA-A4: 항목별 동결·열람·정정 이력 표(부록용) 생성. 읽기 전용(분석 아님). 미실행. python3 pa_a4.py
from pa_common import *
import csv
MANUAL = {   # 지금까지 대화에서 확인된 사실(자동 추출이 못 잡는 것). 필요하면 고치세요
    "0": "10-21 12:31:17 'oa_raw 외부 복사 완료' 기록은 12:31:33에 정정(복사 실패, 외부 백업 미완료). 잘못된 S4 태그 2개 삭제 기록. 정리 커밋 날짜는 생성일이 아님",
    "A1": "run 1은 inject() NaN 오류로 무효(삭제하지 않고 커밋), run 2가 동결 사양. 코드 패치 2건은 사양 불변. 탐색 확장(δ 0.25/0.35/0.45, 연속 꺾은선 BIC)은 동결 밖·판독 미사용. v2 동결 전 s5_lib 소스·N2 요약 열람",
    "B2": "동결은 노트북 셀에서 실행(18:18), 스크립트는 사후 저장(해시 일치 확인). QUICK 출력에 관측 기술 표·요약이 포함되어 열람",
    "B7a": "첫 시도 코드 오류(람다 언패킹, 사양 불변)로 중단·수정. 기간별 결측률 열람",
    "B3a": "실행 2회(실수, 결정적이라 결과 동일). 정의 확인 기록 시각은 실행 이후이나 계획에 정의 열람 명시",
    "B8a": "붙여넣기 중 화면이 섞여 보였으나 계획 JSON·파일 정상 확인(grep -c 기준 오류는 설명 오류였음)",
    "B7b": "실행 로그 파일 없음(결과 CSV와 changelog 수치로 대체)",
}
NOT_DONE = {   # 아직 계획 파일이 없는 항목의 사유(실행하면 표에서 '완료'로 바뀜)
    "B6": "연구자 수작업(ORCID·50쌍) 필요, 인력 미정", "B8-2": "사전 v3 작성·새 25편 이중 코딩 필요, 인력 미정",
}
def norm(s): return re.sub(r"\(v2\)|-v2$", "", s.replace("PA-", "")).strip()
plans = {}
for f in sorted(PA.glob("PA_*_PLAN*.json")):
    m = re.match(r"PA_(.+?)_PLAN(_v2)?\.json$", f.name)
    if m: j = json.loads(f.read_text(encoding="utf-8")); plans.setdefault(m.group(1), []).append(dict(file=f.name, hash=j.get("sha256", "")[:12], created=j.get("created", ""), parent=j.get("parent", j.get("supersedes_sha256", ""))))
tags = {}; remote = set(l.split("refs/tags/")[1].replace("^{}", "") for l in git("ls-remote", "--tags", "origin").stdout.splitlines() if "refs/tags/" in l)
for l in git("for-each-ref", "--format=%(refname:short)|%(creatordate:iso-strict)", "refs/tags").stdout.splitlines():
    n, t = l.split("|"); m = re.match(r"^PA-(.+?)-(plan-v2|plan|code|fullrun|results|explore-code|explore-results|run\d+-[a-z]+|repo-cleanup)-\d{4}-\d{2}-\d{2}$", n)
    if m: tags.setdefault(norm(m.group(1)), []).append((m.group(2), n, t, n in remote))
logs = {}
for ln in CL.read_text(encoding="utf-8").splitlines():
    if not re.match(r"^- \d{4}-\d{2}-\d{2}T", ln): continue
    parts = [p.strip() for p in ln.split(" | ")]; body = " | ".join(parts[1:]); m = re.match(r"(PA-[A-Za-z0-9]+)", body); it = norm(m.group(1)) if m else "기타"
    logs.setdefault(it, []).append((parts[0][2:], body))
items = sorted(set(plans) | set(tags) | set(logs) | set(NOT_DONE) - {"기타"}, key=lambda x: (x != "0", x))
rows = []
for it in items:
    pl = plans.get(it, []); tg = tags.get(it, []); lg = logs.get(it, [])
    ptag = next((t for t in tg if t[0].startswith("plan")), None); rtag = [t for t in tg if t[0] == "results"]
    viewed = " // ".join(b[:110] for _, b in lg if "열람" in b and "미열람" not in b[:8])[:380]; fixes = ";".join(t for t, b in lg if re.search(r"정정|코드 오류|패치|중복", b))
    rows.append(dict(item=it, status=("계획 없음: " + NOT_DONE[it]) if it in NOT_DONE and not pl else ("완료" if rtag else ("진행/기록만" if pl else "기록만")), plan_hash=";".join(p["hash"] for p in pl), plan_created=pl[0]["created"] if pl else "",
                     plan_tag=ptag[1] if ptag else "", plan_tag_time=ptag[2] if ptag else "", results_tag=";".join(t[1] for t in rtag), results_tag_time=";".join(t[2] for t in rtag), tags_on_origin=all(t[3] for t in tg) if tg else "",
                     n_changelog_lines=len(lg), viewed_notes=viewed, correction_times=fixes, manual_note=MANUAL.get(it, "")))
T = pd.DataFrame(rows); T.to_csv(PA/"PA_A4_audit_table.csv", index=False, encoding="utf-8-sig")
with (PA/"PA_A4_audit_table.md").open("w", encoding="utf-8") as f:
    f.write("# [Post-hoc] 동결·열람·정정 이력 (PA_CHANGELOG.md, git 태그, 계획 JSON에서 생성)\n\n| 항목 | 상태 | 계획 해시 | 계획 태그 시각 | 결과 태그 시각 | 원격 | 열람·정정·비고 |\n|---|---|---|---|---|---|---|\n")
    for r in rows: f.write(f"| {r['item']} | {r['status']} | {r['plan_hash']} | {r['plan_tag_time'][:19]} | {r['results_tag_time'][:19]} | {r['tags_on_origin']} | {(r['viewed_notes'] + ' ' + r['manual_note']).strip()[:300]} |\n")
    f.write("\n기록의 오류(코드 오류, 백업 완료 오기재, 해석 메모 중복)는 삭제하지 않고 정정 줄로 남겼다. S0~S8의 판정은 어떤 항목에서도 변경하지 않았다.\n")
bad = [(t, b[:80]) for ls in logs.values() for t, b in ls if "본 결과 변경" in b and not re.search(r"본 결과 변경[^:]*:\s*없음", b)]
print(len(rows), "항목 →", PA/"PA_A4_audit_table.csv", "/ .md"); print(T[["item", "status", "plan_hash", "n_changelog_lines", "tags_on_origin"]].to_string(index=False))
print("\n'본 결과 변경: 없음'이 아닌 changelog 줄:", bad if bad else "없음(모든 줄 '없음')")