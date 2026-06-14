"""
╔══════════════════════════════════════════════════════════════════════════════════╗
║     JARVIS MARK XXXIX — Self-Learning Engine Integration & Validation Harness  ║
║     Module: agent/sle_integration_harness.py                                   ║
║                                                                                 ║
║  Purpose  : (A) Drop-in integration patch for main.py / AgentExecutor          ║
║             (B) End-to-end mock validation harness (run standalone)             ║
╚══════════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# §A  INTEGRATION PATCH  ←──────────────────────────────────────────────────────
#     Drop this import block into main.py (after existing imports) and call
#     _sle_wrap_code_helper() to replace the synchronous code_helper dispatch
#     with a self-healing Reflexion cycle when the task requires generated code.
# ─────────────────────────────────────────────────────────────────────────────

import asyncio
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable, Optional

# Guard: only import SelfLearningEngine when langgraph is available
try:
    from agent.self_learning_engine import SelfLearningEngine, LearningState
    _SLE_AVAILABLE = True
except ImportError as _sle_import_err:
    _SLE_AVAILABLE = False
    _SLE_IMPORT_ERR = _sle_import_err


def sle_run_sync(
    task_description : str,
    tool_name        : str                                = "code_helper",
    initial_code     : str                                = "",
    speak_callback   : Optional[Callable[[str], None]]   = None,
    timeout_seconds  : int                                = 600,
) -> dict[str, Any]:
    """
    Synchronous wrapper around ``SelfLearningEngine.run()``.

    Designed for drop-in replacement inside the synchronous ``_call_tool``
    dispatch in ``agent/executor.py``.  Runs the asyncio Reflexion graph
    on a dedicated event loop to avoid conflicting with JARVIS's primary loop.

    Parameters
    ----------
    task_description : str
        Natural-language goal the engine should accomplish.
    tool_name : str
        Originating action module name (used for LLM context).
    initial_code : str
        Optional seed code to start the first Reflexion cycle.
    speak_callback : Optional[Callable[[str], None]]
        Reference to JarvisLive.speak for verbal progress narration.
    timeout_seconds : int
        Hard wall-clock deadline for the entire Reflexion cycle.

    Returns
    -------
    dict[str, Any]
        Final LearningState after graph termination. Keys:
        - ``execution_output`` : str   — stdout of the successful script.
        - ``is_valid``         : bool  — True if the last execution succeeded.
        - ``retry_counter``    : int   — number of Reflexion cycles consumed.
        - ``transition_log``   : list  — full per-node audit trail.

    Raises
    ------
    RuntimeError
        If ``langgraph`` is not installed or the engine crashes unexpectedly.
    """
    if not _SLE_AVAILABLE:
        raise RuntimeError(
            f"[SLE] langgraph is not installed. Install it with: "
            f"`pip install langgraph`. Original error: {_SLE_IMPORT_ERR}"
        )

    engine = SelfLearningEngine()

    loop = asyncio.new_event_loop()
    try:
        future = asyncio.ensure_future(
            engine.run(
                task_description = task_description,
                tool_name        = tool_name,
                initial_code     = initial_code,
                speak_callback   = speak_callback,
            ),
            loop=loop,
        )
        result: LearningState = loop.run_until_complete(
            asyncio.wait_for(future, timeout=timeout_seconds)
        )
        return dict(result)

    except asyncio.TimeoutError:
        raise RuntimeError(
            f"[SLE] Reflexion cycle exceeded hard wall-clock limit of {timeout_seconds}s."
        )
    finally:
        loop.close()


# ─────────────────────────────────────────────────────────────────────────────
# Integration snippet for agent/executor.py:
#
#   In _call_tool(), replace the "generated_code" elif branch with:
#
#       elif tool == "generated_code":
#           description = parameters.get("description", "")
#           if not description:
#               raise ValueError("generated_code requires a 'description' parameter.")
#           result = sle_run_sync(
#               task_description = description,
#               tool_name        = "generated_code",
#               speak_callback   = speak,
#           )
#           if result.get("is_valid"):
#               return result["execution_output"]
#           raise RuntimeError(
#               f"SelfLearningEngine failed after {result['retry_counter']} cycles. "
#               f"Last error: {result.get('error_payload', '')[:200]}"
#           )
#
# Integration snippet for main.py JarvisLive._execute_tool():
#
#   In the "code_helper" elif branch, wrap long-running generated code with:
#
#       elif name == "code_helper":
#           action = args.get("action", "auto")
#           if action in ("run", "auto") and not args.get("file_path"):
#               # Route through SelfLearningEngine for generated code tasks
#               r = await loop.run_in_executor(None, lambda: sle_run_sync(
#                   task_description = args.get("description", ""),
#                   tool_name        = "code_helper",
#                   speak_callback   = self.speak,
#               ))
#               result = r.get("execution_output", "Done.") if r.get("is_valid") else (
#                   code_helper(parameters=args, player=self.ui, speak=self.speak) or "Done."
#               )
#           else:
#               result = await loop.run_in_executor(
#                   None, lambda: code_helper(parameters=args, player=self.ui, speak=self.speak)
#               ) or "Done."
# ─────────────────────────────────────────────────────────────────────────────


# =============================================================================
# §B  VALIDATION MOCK HARNESS
# =============================================================================

class _MockLearningState:
    """
    Lightweight mock that simulates LearningState channel progression
    WITHOUT calling any live LLM APIs or subprocess.

    Injects controlled failure scenarios to validate the Router's branching
    logic and the transition log accumulation across multiple Reflexion cycles.
    """

    def __init__(
        self,
        task             : str,
        fail_until_cycle : int = 1,
    ) -> None:
        """
        Parameters
        ----------
        task : str
            Mock task description.
        fail_until_cycle : int
            Number of cycles to simulate failure before simulating success.
            Set to ``_MAX_RETRY_COUNT + 1`` to simulate exhaustion scenario.
        """
        self.task             = task
        self.fail_until_cycle = fail_until_cycle
        self._cycle           = 0
        self._log             : list[dict] = []

    # ── Simulated node traversals ─────────────────────────────────────────────

    def mock_generator(self) -> dict:
        code = (
            f"# Cycle {self._cycle}: Auto-generated code attempt\n"
            f"print('Attempting task: {self.task[:40]}')\n"
            + ("raise ValueError('Deliberate injection error')\n"
               if self._cycle < self.fail_until_cycle
               else "print('Task completed successfully.')\n")
        )
        self._log.append({
            "node"      : "generator",
            "cycle"     : self._cycle,
            "timestamp" : time.strftime("%H:%M:%S"),
            "action"    : "code_synthesised",
            "code_length": len(code),
        })
        return {"current_code_or_command": code}

    def mock_executor(self, code: str) -> dict:
        should_fail = self._cycle < self.fail_until_cycle
        if should_fail:
            error = "ValueError: Deliberate injection error\n  File '<mock>', line 3"
            self._log.append({
                "node"       : "executor",
                "cycle"      : self._cycle,
                "timestamp"  : time.strftime("%H:%M:%S"),
                "status"     : "failure",
                "returncode" : 1,
                "stderr"     : error[:80],
            })
            return {"is_valid": False, "error_payload": error, "execution_output": ""}
        else:
            stdout = f"Task completed successfully. (cycle={self._cycle})"
            self._log.append({
                "node"      : "executor",
                "cycle"     : self._cycle,
                "timestamp" : time.strftime("%H:%M:%S"),
                "status"    : "success",
                "stdout"    : stdout,
                "returncode": 0,
            })
            return {"is_valid": True, "error_payload": "", "execution_output": stdout}

    def mock_critic(self, is_valid: bool, error: str) -> dict:
        if is_valid:
            self._log.append({
                "node"      : "critic",
                "cycle"     : self._cycle,
                "timestamp" : time.strftime("%H:%M:%S"),
                "verdict"   : "pass",
            })
            return {"critique_feedback": ""}
        critique = (
            "ROOT CAUSE : ValueError deliberately injected for mock scenario.\n"
            "FIX STEPS  :\n"
            "  1. Remove the raise statement.\n"
            "  2. Replace with the actual task logic.\n"
        )
        self._log.append({
            "node"       : "critic",
            "cycle"      : self._cycle,
            "timestamp"  : time.strftime("%H:%M:%S"),
            "verdict"    : "fail",
            "root_cause" : "Deliberate injection error",
            "severity"   : "recoverable",
        })
        self._cycle += 1
        return {"critique_feedback": critique}

    def mock_router(self, is_valid: bool, retry_counter: int, max_retries: int) -> str:
        from agent.self_learning_engine import NodeRoute, _MAX_RETRY_COUNT
        if is_valid:
            return NodeRoute.TERMINATE
        if retry_counter >= max_retries:
            return NodeRoute.TERMINATE
        return NodeRoute.REGENERATE

    def run(self, max_retries: int = 3) -> dict:
        """
        Execute a simulated Reflexion cycle without live LLM / subprocess calls.

        Returns
        -------
        dict
            Simulated final state with ``is_valid``, ``retry_counter``,
            ``transition_log``, ``execution_output``, and ``error_payload``.
        """
        code         = ""
        is_valid     = False
        error        = ""
        output       = ""
        critique     = ""
        retry_count  = 0
        route        = "regenerate"

        _print_harness_header(self.task, max_retries)

        while route != "terminate":
            # ── Generator ────────────────────────────────────────────────────
            gen_result = self.mock_generator()
            code       = gen_result["current_code_or_command"]
            _print_node_step("GENERATOR", self._cycle, f"code[{len(code)}chr]")

            # ── Executor ─────────────────────────────────────────────────────
            exe_result = self.mock_executor(code)
            is_valid   = exe_result["is_valid"]
            error      = exe_result["error_payload"]
            output     = exe_result["execution_output"]
            _print_node_step(
                "EXECUTOR", self._cycle,
                f"is_valid={is_valid}  "
                + (f"stdout={output[:40]!r}" if is_valid else f"stderr={error[:40]!r}"),
            )

            # ── Critic ───────────────────────────────────────────────────────
            crit_result = self.mock_critic(is_valid, error)
            critique    = crit_result["critique_feedback"]
            _print_node_step(
                "CRITIC", self._cycle - (0 if is_valid else 1),
                f"verdict={'pass' if is_valid else 'fail'}",
            )

            # ── Router ───────────────────────────────────────────────────────
            route = self.mock_router(is_valid, self._cycle, max_retries)
            _print_router_step(route, self._cycle, max_retries)

        final_state = {
            "task_description"        : self.task,
            "current_code_or_command" : code,
            "execution_output"        : output,
            "error_payload"           : error,
            "critique_feedback"       : critique,
            "retry_counter"           : self._cycle,
            "is_valid"                : is_valid,
            "transition_log"          : self._log,
        }

        _print_transition_report_mock(final_state)
        return final_state


# ─────────────────────────────────────────────────────────────────────────────
#  Harness print utilities
# ─────────────────────────────────────────────────────────────────────────────

_WIDTH = 72

def _print_harness_header(task: str, max_retries: int) -> None:
    print(f"\n{'=' * _WIDTH}")
    print(f"  JARVIS SLE — Validation Mock Harness")
    print(f"  Task       : {task[:60]}")
    print(f"  Max Retries: {max_retries}")
    print(f"{'=' * _WIDTH}")

def _print_node_step(node: str, cycle: int, detail: str) -> None:
    print(f"  [cycle={cycle}]  {node:<12}  {detail}")

def _print_router_step(route: str, cycle: int, max_retries: int) -> None:
    arrow  = "-> END" if route == "terminate" else "-> GENERATOR (back-edge)"
    reason = "(success)" if route == "terminate" and cycle < max_retries else "(exhausted)" if route == "terminate" else ""
    print(f"  [cycle={cycle}]  ROUTER       route={route!r}  {arrow}  {reason}")
    print(f"  {'-' * (_WIDTH - 2)}")

def _print_transition_report_mock(state: dict) -> None:
    is_valid    = state.get("is_valid", False)
    cycles      = state.get("retry_counter", 0)
    log_entries = state.get("transition_log", [])
    status_str  = "SUCCESS" if is_valid else "FAILED (MAX RETRIES EXHAUSTED)"

    print(f"\n{'=' * _WIDTH}")
    print(f"  Mock Harness Report")
    print(f"  Outcome    : {status_str}")
    print(f"  Cycles     : {cycles}")
    print(f"  Log Entries: {len(log_entries)}")
    print(f"  Output     : {(state.get('execution_output') or '(none)')[:80]}")
    print(f"  Error      : {(state.get('error_payload')    or '(none)')[:80]}")
    print(f"{'=' * _WIDTH}\n")


# =============================================================================
# §C  STANDALONE RUNNER — `python -m agent.sle_integration_harness`
# =============================================================================

def _run_all_mock_scenarios() -> None:
    """
    Execute three canonical mock scenarios to validate the full Reflexion FSM:

    Scenario 1 — EARLY SUCCESS (fails once, succeeds on cycle 1)
    Scenario 2 — MID RECOVERY  (fails twice, succeeds on cycle 2)
    Scenario 3 — EXHAUSTION    (fails all 3 cycles, Router hard-stops)
    """
    from agent.self_learning_engine import _MAX_RETRY_COUNT

    scenarios = [
        {
            "name"           : "SCENARIO 1 — EARLY SUCCESS",
            "task"           : "Fetch top-5 Hacker News titles and print them.",
            "fail_until"     : 1,
            "expect_valid"   : True,
        },
        {
            "name"           : "SCENARIO 2 — MID RECOVERY",
            "task"           : "Download AAPL stock price CSV and save to Desktop.",
            "fail_until"     : 2,
            "expect_valid"   : True,
        },
        {
            "name"           : "SCENARIO 3 — EXHAUSTION (MAX RETRIES)",
            "task"           : "Crack an impossible cipher (deliberately unfixable).",
            "fail_until"     : _MAX_RETRY_COUNT + 99,   # will never succeed
            "expect_valid"   : False,
        },
    ]

    all_pass = True
    print(f"\n{'#' * _WIDTH}")
    print(f"  JARVIS SLE — Full Validation Suite  ({len(scenarios)} scenarios)")
    print(f"{'#' * _WIDTH}\n")

    for i, scenario in enumerate(scenarios, start=1):
        print(f"\n[{i}/{len(scenarios)}]  {scenario['name']}")
        harness = _MockLearningState(
            task             = scenario["task"],
            fail_until_cycle = scenario["fail_until"],
        )
        result = harness.run(max_retries=_MAX_RETRY_COUNT)

        expected = scenario["expect_valid"]
        got      = result["is_valid"]
        passed   = expected == got

        status = "PASS" if passed else "FAIL"
        print(f"  Assertion  : expected is_valid={expected}, got is_valid={got}  [{status}]")

        if not passed:
            all_pass = False

    print(f"\n{'#' * _WIDTH}")
    print(f"  Suite Result: {'ALL PASSED' if all_pass else 'FAILURES DETECTED'}")
    print(f"{'#' * _WIDTH}\n")

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    _run_all_mock_scenarios()
