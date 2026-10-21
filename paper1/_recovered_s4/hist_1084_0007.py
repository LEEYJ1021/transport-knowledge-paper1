# -*- coding: utf-8 -*-
# PA-0 재현성 정리 단일 셀. MODE: "find"(S4 코드 탐색, 읽기 전용) -> "verify"(manifest 해시 검증, 읽기 전용) -> "commit"(정리 커밋·태그)
# commit은 DRY=True면 계획만 출력. 결과·판정은 바꾸지 않는 정리 작업.
import json, re, hashlib, sqlite3, tarfile, subprocess
from pathlib import Path
import pandas as pd

MODE = "find"
DRY = True
ROOT = Path.home() / "Research/Minnesota_Transport"; P1 = ROOT/"paper1"
now = lambda: pd.Timestamp.now().isoformat(timespec="seconds"); d_ = pd.Timestamp.now().strftime("%Y-%m-%d")
sha_f = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
git = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
class Halt(Exception): pass
HEX = re.compile(r"^[0-9a-f]{64}$")

def find():
    pat = re.compile(r"s4_main|s4_6_rotation|s4_6b|floor_check|journal_decomposition|topic_quadrants")
    print("[paper1 직하 .py]", sorted(p.name for p in P1.glob("*.py")))
    hits = list(ROOT.rglob("s4*.py")) + list(ROOT.rglob("*s4*.ipynb"))
    print("[s4 이름 파일]", [str(p.relative_to(ROOT)) for p in hits if ".git" not in p.parts][:20])
    for nb in ROOT.rglob("*.ipynb"):
        if ".git" in nb.parts or "oa_raw" in nb.parts: continue
        try: cells = json.loads(nb.read_text(encoding="utf-8")).get("cells", [])
        except Exception: continue
        n = [i for i, c in enumerate(cells) if c.get("cell_type") == "code" and pat.search("".join(c.get("source", [])))]
        if n: print(f"[노트북 코드 셀 일치] {nb.relative_to(ROOT)} | 셀 {len(n)}개 (예: {n[:6]}) | 수정 {pd.Timestamp(nb.stat().st_mtime, unit='s'):%Y-%m-%d %H:%M}")
    hist = Path.home()/".ipython/profile_default/history.sqlite"
    if hist.exists():
        con = sqlite3.connect(hist); r = con.execute("select session, line, source from history").fetchall(); m = [(s, l) for s, l, src in r if pat.search(src or "")]
        print(f"[IPython 히스토리 일치] {len(m)}줄, 세션 {sorted({s for s, _ in m})[:8]} (sqlite 직접 조회로 복구 가능)")
    print("※ 코드가 나오면 paper1/s4_main.py 등으로 저장하고, 저장본 실행 여부와 무관하게 '산출물은 manifest 해시로 검증됨, 코드는 복구본'이라고 CHANGELOG에 적으세요.")

def collect_hashes(o, out, key=None):
    if isinstance(o, dict):
        for k, v in o.items():
            if isinstance(v, str) and HEX.match(v): out.append((k if "/" in str(k) or "." in str(k) else key, v))
            else: collect_hashes(v, out, k)
    elif isinstance(o, list):
        for v in o:
            if isinstance(v, dict) and "sha256" in v and any(f in v for f in ("file", "name", "path")): out.append((v.get("file") or v.get("name") or v.get("path"), v["sha256"]))
            else: collect_hashes(v, out, key)

def verify():
    tot = {"일치": 0, "불일치": [], "파일없음": [], "이름 해석 불가": 0}
    for mf in sorted(P1.glob("0[1-8]_*/*MANIFEST*.json")) + sorted(P1.glob("0[1-8]_*/*_meta*.json")):
        try: J = json.loads(mf.read_text(encoding="utf-8"))
        except Exception as e: print("읽기 실패", mf.name, e); continue
        pairs = []; collect_hashes(J, pairs)
        for name, h in pairs:
            if not name: tot["이름 해석 불가"] += 1; continue
            cand = [mf.parent/name, ROOT/name, P1/name]; f = next((c for c in cand if c.exists() and c.is_file()), None)
            if f is None: tot["파일없음"].append(f"{mf.name}:{name}"); continue
            if sha_f(f) == h: tot["일치"] += 1
            else: tot["불일치"].append(f"{mf.name}:{name}")
    print("[manifest 검증]", {k: (len(v) if isinstance(v, list) else v) for k, v in tot.items()})
    for k in ("불일치", "파일없음"):
        if tot[k]: print(f" {k} 예:", tot[k][:15])
    return tot

def commit():
    tot = verify()
    if tot["불일치"]: raise Halt("해시 불일치가 있습니다: 원인(동결 이후 파일 변경, 줄바꿈 등)을 확인한 뒤 진행하세요")
    gi = ROOT/".gitignore"; cur = gi.read_text(encoding="utf-8") if gi.exists() else ""
    add_ign = [x for x in ["paper1/01_S1/oa_raw/", "paper1/01_S1/_backup_before_income_tv/", "archive/*.tar.gz"] if x not in cur]
    sz = []
    for f in git("ls-files", "-o", "--exclude-standard", "paper1").stdout.splitlines():
        if any(f.startswith(x.rstrip("/*")) for x in add_ign if x.endswith("/")): continue
        s = (ROOT/f).stat().st_size
        if s > 30e6: sz.append((f, round(s/1e6, 1)))
    if sz: raise Halt(f"30MB 초과 미추적 파일(무시 목록 또는 LFS 검토): {sz}")
    tg = {t: git("rev-list", "-n", "1", t).stdout.strip() for t in ["S4-main-2026-10-16", "S4-final-2026-10-16"]}
    on_origin = git("ls-remote", "--tags", "origin").stdout
    del_t = [t for t, c in tg.items() if c.startswith("33b3912") and t not in on_origin]
    print("삭제할 잘못된 태그(로컬 전용, 33b3912 가리킴):", del_t); print(".gitignore 추가:", add_ign)
    print("커밋 1: paper1/02_S2 03_S3 04_S4 | 커밋 2: 나머지 paper1 변경(CHANGELOG, S1 파일, S0 노트북, 09_PA) + .gitignore")
    note = (f"- {now()} | 재현성 정리(PA-0): 잘못된 태그 S4-main-2026-10-16, S4-final-2026-10-16(실제로는 S3 CHANGELOG 커밋 33b3912을 가리킴, S4 산출물 미포함)을 로컬 삭제. "
            f"S2·S3·S4 산출물은 2026-10-16 이전에 생성됐으나 미추적이었고, 이번에 manifest 해시 {tot['일치']}건 일치를 확인한 뒤 {d_}에 처음 커밋. 커밋 날짜는 생성일이 아님 | 본 결과 변경: 없음\n")
    if DRY: print("\nDRY=True: 변경 없음. 위 계획이 맞으면 DRY=False로 다시 실행."); return
    for t in del_t: print("tag -d", t, git("tag", "-d", t).stdout.strip())
    if add_ign: gi.write_text(cur.rstrip("\n") + "\n" + "\n".join(add_ign) + "\n", encoding="utf-8")
    for f in [P1/"04_S4/CHANGELOG_S4.md", P1/"09_PA/PA_CHANGELOG.md"]:
        with f.open("a", encoding="utf-8") as h: h.write(note)
    r = git("add", "-A", "--", "paper1/02_S2", "paper1/03_S3", "paper1/04_S4"); print("add1", r.returncode, r.stderr.strip())
    r = git("commit", "-m", "Record S2/S3/S4 outputs (created before S5; manifest-verified, no result change)"); print("commit1", r.returncode, (r.stdout + r.stderr)[:160])
    r = git("tag", "-a", f"S4-results-recommit-{d_}", "-m", "S4(S2,S3) outputs first committed; verified against manifests"); print("tag", r.returncode, r.stderr.strip())
    r = git("add", "-A", "--", "paper1", ".gitignore"); print("add2", r.returncode, r.stderr.strip())
    r = git("commit", "-m", "PA-0 cleanup: changelogs, S1 files, gitignore for raw data"); print("commit2", r.returncode, (r.stdout + r.stderr)[:160])
    print("[tags]", git("tag", "--sort=-creatordate").stdout.split()[:8], "\n[미추적 잔여]", git("status", "--short", "--", "paper1").stdout[:300] or "없음")

try: {"find": find, "verify": verify, "commit": commit}[MODE]()
except Halt as e: print(f"⛔ 중단: {e}")