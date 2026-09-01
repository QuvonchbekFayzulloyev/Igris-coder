import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tools.python_tools import _python_exec
from tools.workspace import Workspace

ws = Workspace(tempfile.mkdtemp())
r = _python_exec(ws, {"code": "print(1/0)"})
print("ok flag      =", r.get("ok"))
print("returncode   =", r.get("returncode"))
print("stderr       =", repr(r.get("stderr")))
print("has ERROR    =", "ERROR" in (r.get("stderr") or ""))
