# -*- coding: utf-8 -*-
# S4 코드 복구 + S5 연결 정보 점검. 새 폴더 paper1/_recovered_s4/ 에만 쓰기. 기존 파일 수정 없음.
import json, re, sqlite3, ast
from pathlib import Path
import pandas as pd
MODE = "recover"      # "recover" | "s5info"
ROOT = Path.home() / "Research/Minnesota_Transport"; P1 = ROOT/"paper1"; OUT = P1/"_recovered_s4"

def recover():
    OUT.mkdir(exist_ok=True); pat = re.compile(r"s4_main|s4_6_rotation|s4_6b|floor_check|journal_decomposition|topic_quadrants|rotation_index")
    nb = P1/"S4. 신생·쇠퇴의 재정의.ipynb"; cells = json.loads(nb.read_text(encoding="utf-8"))["cells"]
    print(f"[노트북] {nb.name} | 전체 셀 {len(cells)} | 수정 {pd.Timestamp(nb.stat().st_mtime, unit='s'):%Y-%m-%d %H:%M}")
    for i, c in enumerate(cells):
        if c.get("cell_type") != "code": continue
        src = "".join(c.get("source", []))
        (OUT/f"nb_cell_{i:02d}.py").write_text(src, encoding="utf-8")
        out = "".join("".join(o.get("text", [])) for o in c.get("outputs", []) if o.get("output_type") == "stream")
        first = src.strip().splitlines()[0][:110] if src.strip() else ""
        flag = "◀ 일치" if pat.search(src) else ""
        try: ast.parse(src); ok = "구문 OK"
        except SyntaxError: ok = "구문 오류(매직 명령 포함 가능)"
        print(f"  셀 {i:02d} | {len(src):6,}자 | 출력 {len(out):6,}자 | {ok} | {first} {flag}")
    h = Path.home()/".ipython/profile_default/history.sqlite"
    if h.exists():
        con = sqlite3.connect(h); rows = [(s, l, src) for s, l, src in con.execute("select session, line, source from history order by session, line") if pat.search(src or "")]
        for s, l, src in rows: (OUT/f"hist_{s}_{l:04d}.py").write_text(src, encoding="utf-8")
        print(f"\n[IPython 히스토리] {len(rows)}줄 저장: " + ", ".join(f"{s}:{l}({len(src):,}자)" for s, l, src in rows))
    print(f"\n저장 위치: {OUT}\n※ 셀·히스토리는 수정본이 여러 번 섞여 있을 수 있음: 어느 것이 '산출물을 만든 최종 실행본'인지는 파일의 s4_meta.json·MANIFEST 시각과 비교해 사람이 확정.")
    for f in ["S4_meta.json", "S4_MANIFEST.json"]:
        p = P1/"04_S4"/f
        if p.exists(): print(f"  {f} 수정 {pd.Timestamp(p.stat().st_mtime, unit='s'):%Y-%m-%d %H:%M:%S}")

def s5info():
    for fn in ["s5_lib.py", "s5_detect.py"]:
        t = (P1/fn).read_text(encoding="utf-8"); tree = ast.parse(t); print(f"\n[{fn}] {len(t.splitlines())}줄")
        for n in tree.body:
            if isinstance(n, ast.FunctionDef): print(f"  def {n.name}({', '.join(a.arg for a in n.args.args)})  # {(ast.get_docstring(n) or '').splitlines()[0][:70] if ast.get_docstring(n) else ''}")
            elif isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id.isupper(): print(f"  {n.targets[0].id} = {ast.unparse(n.value)[:90]}")
    for p in list((P1/"05_S5").glob("regime_nulls*.csv")) + list((P1/"05_S5").glob("regime_breaks*.csv")):
        d = pd.read_csv(p, nrows=3); print(f"\n[{p.name}] 열: {list(d.columns)}")
    print("\n※ 위 함수 목록(특히 비용·벌점·귀무 시뮬레이션 관련)을 붙여 주세요.")

{"recover": recover, "s5info": s5info}[MODE]()