#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""문단 요약 인덱스 출력: 코드별 문단번호 + 앞 N자. 경과규정/삭제 문단 제외."""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from corpus import load

N = int(os.environ.get('N', '110'))
MAX = int(os.environ.get('MAX', '0'))
SKIP = int(os.environ.get('SKIP', '0'))
d = load()
SKIP_RE = re.compile(r'(삭제함|삭제하였다|회계연도부터 적용한다|에 따라 문단)')
for code in sys.argv[1:]:
    print('#' * 10, code, d[code]['title'])
    n = 0
    for i, (k, v) in enumerate(d[code]['paras'].items()):
        t = re.sub(r'\s+', ' ', v).strip()
        if SKIP_RE.search(t[:160]):
            continue
        if i < SKIP:
            continue
        n += 1
        if MAX and n > MAX:
            break
        print(f'[{k}] {t[:N]}')
