#!@PYTHON@ -tt

import sys

PY3 = sys.version_info[0] == 3

if PY3:
    def to_ascii(s):
        if s is None or isinstance(s, str):
            return s
        return str(s, 'utf-8')
else:
    def to_ascii(s):
        if s is None or isinstance(s, str):
            return s
