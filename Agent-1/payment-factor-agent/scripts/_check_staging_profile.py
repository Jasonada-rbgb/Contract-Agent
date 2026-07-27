import os, sys, json
os.environ.setdefault("KB_BUNDLE_BASE", "/Volumes/mdna_dev/warranty_agent_staging/uploads/kb_bundle")
sys.path.insert(0, r"C:\Users\ADJ1DE\Documents\Agent Workflow\Agent-1\agent-contract\agent-openai-agents-sdk")
from agent_server.agent import _load_contract

a = _load_contract("BMW", "BMW")
print("type of return:", type(a))
if isinstance(a, dict):
    prof = a.get("profile") or {}
    wps = prof.get("warranty_periods") or []
    print("n warranty_periods:", len(wps))
    for w in wps:
        s = json.dumps(w, ensure_ascii=False)
        up = s.upper()
        if any(k in up for k in ["US", "USA", "PUERTO", "CANADA", "ALLE", "OTHER", "36", "60"]):
            print(s)
else:
    print("repr:", repr(a)[:500])

# also read the raw staging profile.json directly
try:
    from agent_server.agent import _read_volume_text  # if such helper exists
except Exception:
    pass
