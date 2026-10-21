# -*- coding: utf-8 -*-
# 사후분석 보조(Wilson 구간, 동결 검증, 특수 모드 디스패치). pa_common.py는 수정하지 않음. 미실행.
from pa_common import *

def wilson(k, n, z=1.96):
    if n == 0: return (np.nan, np.nan)
    p = k/n; d = 1 + z*z/n; c = (p + z*z/(2*n))/d; h = z*np.sqrt(p*(1-p)/n + z*z/(4*n*n))/d
    return float(c - h), float(c + h)

def guard(name, PLAN):
    BP = PA/f"PA_{name}_PLAN.json"; script = f"pa_{name.lower()}.py"
    if not BP.exists(): raise Halt("먼저 freeze")
    sp = json.loads(BP.read_text(encoding="utf-8"))
    if sp["sha256"] != spec_hash(sp) or sp["sha256"] != spec_hash(PLAN): raise Halt("동결 파일과 현재 계획이 다릅니다")
    if not git("tag", "-l", f"PA-{name}-plan-*").stdout.strip(): raise Halt("tag 단계를 먼저 실행하세요")
    for fn in ["pa_common.py", script]:
        if sp["refs"].get(fn) != sha_f(P1/fn): raise Halt(f"{fn}이 동결 시점과 다름(수정했다면 v2 계획으로 분리)")
    return sp

def special(name, PLAN, handlers):
    """argv[1]이 handlers에 있으면 동결 검증 후 실행하고 True 반환."""
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode not in handlers: return False
    try: handlers[mode](guard(name, PLAN))
    except Halt as e: print(f"⛔ 중단: {e}")
    return True