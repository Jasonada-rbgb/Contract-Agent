"""Warranty Agent evaluation -- contract-aware regression test suite.

Loads test cases from eval_test_cases/*.json and runs each prompt through the
agent, checking that expected facts appear in the response and that forbidden
facts do not.

Usage:
    uv run agent-evaluate          # run all test cases
    uv run agent-evaluate --oem BMW  # run only BMW cases
"""

import asyncio
import glob
import json
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv(dotenv_path=".env", override=True)
logging.getLogger("mlflow.utils.autologging_utils").setLevel(logging.ERROR)

from agent_server import agent as _agent_mod  # noqa: E402, F401 -- registers @invoke
from agent_server.agent import create_agent

try:
    from agents import Runner, set_default_openai_api, set_default_openai_client
    from databricks_openai import AsyncDatabricksOpenAI
except ImportError:
    Runner = None


def _load_test_cases(oem_filter: str | None = None) -> list[dict]:
    base = os.path.join(os.path.dirname(__file__), "..", "eval_test_cases")
    cases: list[dict] = []
    for path in sorted(glob.glob(os.path.join(base, "*.json"))):
        with open(path, encoding="utf-8") as f:
            file_cases = json.load(f)
        cases.extend(file_cases)
    if oem_filter:
        cases = [c for c in cases if c.get("oem", "").upper() == oem_filter.upper()]
    return cases


async def _run_single(case: dict) -> dict:
    """Run one test case through the agent and return the result."""
    set_default_openai_client(AsyncDatabricksOpenAI())
    set_default_openai_api("chat_completions")

    contracts = [{"oem": case["oem"], "kb_id": case["contract_id"]}]
    ag = create_agent(selected_contracts=contracts)

    tagged_question = (
        f"[Contracts: OEM={case['oem']} contract_id={case['contract_id']}]\n"
        f"{case['question']}"
    )
    messages = [{"role": "user", "content": tagged_question}]

    result = await Runner.run(ag, messages)

    text_parts: list[str] = []
    for item in result.new_items:
        d = item.to_input_item()
        if d.get("type") == "message":
            for c in d.get("content", []):
                if c.get("type") == "output_text":
                    text_parts.append(c.get("text", ""))

    return {
        "id": case["id"],
        "question": case["question"],
        "response": "\n\n".join(text_parts) or "(no response)",
        "expected_facts": case.get("expected_facts", []),
        "must_not_contain": case.get("must_not_contain", []),
    }


def _check_facts(result: dict) -> dict:
    """Check expected/forbidden facts against the response. Simple substring match (case-insensitive)."""
    response_lower = result["response"].lower()

    found = []
    missing = []
    for fact in result["expected_facts"]:
        if fact.lower() in response_lower:
            found.append(fact)
        else:
            missing.append(fact)

    forbidden_found = []
    for bad in result["must_not_contain"]:
        if bad.lower() in response_lower:
            forbidden_found.append(bad)

    passed = len(missing) == 0 and len(forbidden_found) == 0
    return {
        "id": result["id"],
        "passed": passed,
        "facts_found": len(found),
        "facts_expected": len(result["expected_facts"]),
        "missing_facts": missing,
        "forbidden_found": forbidden_found,
    }


def evaluate():
    oem_filter = None
    for arg in sys.argv[1:]:
        if arg.startswith("--oem"):
            if "=" in arg:
                oem_filter = arg.split("=", 1)[1]
            else:
                idx = sys.argv.index(arg)
                if idx + 1 < len(sys.argv):
                    oem_filter = sys.argv[idx + 1]

    cases = _load_test_cases(oem_filter)
    if not cases:
        print("No test cases found.")
        return

    print(f"\n{'='*60}")
    print(f"Running {len(cases)} test case(s)" + (f" for OEM={oem_filter}" if oem_filter else ""))
    print(f"{'='*60}\n")

    results = []
    for i, case in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] {case['id']}: {case['question'][:80]}...")
        try:
            result = asyncio.run(_run_single(case))
            check = _check_facts(result)
            results.append(check)

            status = "PASS" if check["passed"] else "FAIL"
            print(f"  -> {status} ({check['facts_found']}/{check['facts_expected']} facts)")
            if check["missing_facts"]:
                for mf in check["missing_facts"]:
                    print(f"     MISSING: {mf}")
            if check["forbidden_found"]:
                for ff in check["forbidden_found"]:
                    print(f"     FORBIDDEN FOUND: {ff}")
        except Exception as e:
            print(f"  -> ERROR: {e}")
            results.append({"id": case["id"], "passed": False, "error": str(e)})
        print()

    passed = sum(1 for r in results if r.get("passed"))
    total = len(results)
    print(f"{'='*60}")
    print(f"RESULTS: {passed}/{total} passed")
    print(f"{'='*60}")

    if passed < total:
        failed = [r for r in results if not r.get("passed")]
        print("\nFailed cases:")
        for r in failed:
            print(f"  - {r['id']}: {r.get('missing_facts', [])} | forbidden: {r.get('forbidden_found', [])}")
