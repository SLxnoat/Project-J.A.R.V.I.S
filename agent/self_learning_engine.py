"""
╔══════════════════════════════════════════════════════════════════════════════════╗
║          JARVIS MARK XXXIX — Self-Learning / Self-Correction Engine             ║
║          Agent Module: agent/self_learning_engine.py                            ║
║                                                                                 ║
║  Architecture : Generator → Executor → Critic → Router (Reflexion cycle)       ║
║  Graph Engine : LangGraph StateGraph with typed TypedDict channels              ║
║  LLM Backend  : Google Gemini API (google.generativeai)                         ║
║  Paradigm     : Strict OOP — all logic encapsulated in SelfLearningEngine       ║
╚══════════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
import textwrap
import time
import traceback
from pathlib import Path
from typing import Any, Callable, Literal, Optional, TypedDict

# ── LangGraph imports ─────────────────────────────────────────────────────────
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

# ── Logging ───────────────────────────────────────────────────────────────────
log = logging.getLogger("JARVIS.SLE")
log.setLevel(logging.DEBUG)
if not log.handlers:
    _h = logging.StreamHandler(sys.stdout)
    _h.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s  [SLE] %(levelname)-8s  %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    log.addHandler(_h)


# ══════════════════════════════════════════════════════════════════════════════
#  §1  CONSTANTS & CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

_BASE_DIR         = Path(__file__).resolve().parent.parent
_API_CONFIG_PATH  = _BASE_DIR / "config" / "api_keys.json"

_MAX_RETRY_COUNT  : int = 3    # Maximum Reflexion cycles before hard-stop
_EXECUTOR_TIMEOUT : int = 120  # Seconds allowed per code execution

_GENERATOR_MODEL  = "gemini-2.5-flash"
_CRITIC_MODEL     = "gemini-2.5-flash-lite"


# ══════════════════════════════════════════════════════════════════════════════
#  §2  ENUMERATIONS
# ══════════════════════════════════════════════════════════════════════════════

class NodeRoute(str):
    """Deterministic routing tokens emitted by the Router function."""
    REGENERATE = "regenerate"
    TERMINATE  = "terminate"


class ExecutionStatus(str):
    """Canonical execution result labels."""
    SUCCESS = "success"
    FAILURE = "failure"
    PENDING = "pending"


# ══════════════════════════════════════════════════════════════════════════════
#  §3  STATE SCHEMA — LangGraph TypedDict Channel
# ══════════════════════════════════════════════════════════════════════════════

class LearningState(TypedDict, total=False):
    """
    Immutable state envelope that flows through every node in the Reflexion graph.

    Fields
    ------
    task_description : str
        Natural-language description of what the code/command must accomplish.
        Injected once at graph entry; never mutated by nodes.

    current_code_or_command : str
        The Python code block or shell command under active evaluation.
        Re-written by node_generate_or_adapt on each Reflexion iteration.

    execution_output : str
        Captured stdout from the last subprocess execution.

    error_payload : str
        Full traceback / stderr string from the last failed execution.
        Empty string when execution succeeded.

    critique_feedback : str
        Structured verbal improvement directive produced by node_critique_and_reflect.
        Consumed by node_generate_or_adapt on the next cycle.

    retry_counter : int
        Monotonically incrementing integer. Bounded by _MAX_RETRY_COUNT.

    is_valid : bool
        True only when node_execute_and_observe confirms clean execution.
        The Router reads this flag to branch between REGENERATE and END.

    execution_status : str
        Label for the last execution outcome (success | failure | pending).

    transition_log : list[dict[str, Any]]
        Append-only list of structured log entries. One dict per node traversal.

    tool_name : str
        Name of the originating JARVIS action module (e.g. "code_helper").
        Injected for context enrichment in LLM prompts.

    speak_callback : Optional[Callable[[str], None]]
        Optional reference to JarvisLive.speak — allows verbal progress updates.
    """

    task_description         : str
    current_code_or_command  : str
    execution_output         : str
    error_payload            : str
    critique_feedback        : str
    retry_counter            : int
    is_valid                 : bool
    execution_status         : str
    transition_log           : list[dict[str, Any]]
    tool_name                : str
    speak_callback           : Optional[Callable[[str], None]]


# ══════════════════════════════════════════════════════════════════════════════
#  §4  PROMPT TEMPLATES
# ══════════════════════════════════════════════════════════════════════════════

_GENERATOR_SYSTEM = textwrap.dedent("""\
    You are JARVIS's code synthesis module — part of a self-healing Reflexion loop.

    Your sole purpose is to produce a complete, correct, self-contained Python script
    that accomplishes the task below.  The script will be executed directly via
    subprocess with no human intervention.

    MANDATORY RULES:
    - Return ONLY raw Python code. Zero markdown, zero explanation, no triple backticks.
    - Install any missing third-party packages with `subprocess.check_call([sys.executable, "-m", "pip", "install", ...])`
      inside the script itself.
    - Handle all I/O paths using `pathlib.Path`.
    - Print a one-line success summary to stdout on completion.
    - Catch and re-raise exceptions with full tracebacks so the Critic can inspect them.
    - NEVER produce infinite loops, blocking I/O without a timeout, or destructive filesystem commands.

    When a `critique_feedback` block is provided, you MUST address every point
    in it before emitting the revised script.
""")

_GENERATOR_USER_TEMPLATE = textwrap.dedent("""\
    TASK:
    {task_description}

    TOOL CONTEXT:
    {tool_name}

    PREVIOUS CODE (attempt #{retry_counter}):
    {previous_code}

    LAST ERROR TRACEBACK:
    {error_payload}

    CRITIC'S IMPROVEMENT DIRECTIVES:
    {critique_feedback}

    Produce the corrected, complete Python script now:
""")

_CRITIC_SYSTEM = textwrap.dedent("""\
    You are JARVIS's Critic — an LLM-as-a-judge arbiter inside a Reflexion loop.

    Given a Python script, its stdout, and its error traceback, produce a concise,
    surgical improvement directive.

    OUTPUT FORMAT — respond with a JSON object ONLY, no markdown:
    {
      "root_cause"   : "One precise sentence identifying the fundamental failure.",
      "fix_steps"    : ["Step 1: ...", "Step 2: ...", "Step 3: ..."],
      "severity"     : "critical | recoverable | cosmetic",
      "is_fixable"   : true
    }

    Do NOT include code in your response. The Generator will act on your directives.
""")

_CRITIC_USER_TEMPLATE = textwrap.dedent("""\
    TASK THAT WAS ATTEMPTED:
    {task_description}

    CODE THAT WAS EXECUTED (attempt #{retry_counter}):
    {current_code}

    STDOUT (first 1000 chars):
    {execution_output}

    STDERR / TRACEBACK (first 2000 chars):
    {error_payload}

    Provide your critique now:
""")


# ══════════════════════════════════════════════════════════════════════════════
#  §5  INTERNAL UTILITY HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _load_gemini_api_key() -> str:
    """
    Load the Gemini API key from the project's api_keys.json config.
    Mirrors the same resolution logic used across the JARVIS codebase.

    Raises
    ------
    RuntimeError
        If the key cannot be found in either environment or JSON config.
    """
    import os

    env_key = os.getenv("GEMINI_API_KEY")
    if env_key:
        return env_key

    if _API_CONFIG_PATH.exists():
        try:
            data = json.loads(_API_CONFIG_PATH.read_text(encoding="utf-8"))
            key  = data.get("gemini_api_key") or data.get("GEMINI_API_KEY")
            if key:
                return key
        except Exception as exc:
            raise RuntimeError(
                f"[SLE] Failed to parse api_keys.json: {exc}"
            ) from exc

    raise RuntimeError(
        "[SLE] GEMINI_API_KEY not found in environment or config/api_keys.json."
    )


def _strip_code_fences(raw: str) -> str:
    """Remove any markdown code-fence wrappers the LLM may have emitted."""
    return re.sub(r"```(?:python|py|bash|sh|json)?", "", raw).strip().rstrip("`").strip()


def _append_log_entry(
    state: LearningState,
    node_name: str,
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Append a structured audit entry to the state's transition_log.
    Returns a new list reference — no in-place mutation of state.
    """
    existing: list[dict[str, Any]] = state.get("transition_log", []) or []
    entry = {
        "node"      : node_name,
        "cycle"     : state.get("retry_counter", 0),
        "timestamp" : time.strftime("%H:%M:%S"),
        **payload,
    }
    return [*existing, entry]


# ══════════════════════════════════════════════════════════════════════════════
#  §6  SELF-LEARNING ENGINE — CORE CLASS
# ══════════════════════════════════════════════════════════════════════════════

class SelfLearningEngine:
    """
    Encapsulates the complete Generator -> Executor -> Critic Reflexion cycle
    as a compiled LangGraph StateGraph.

    Usage
    -----
    >>> engine = SelfLearningEngine()
    >>> result = await engine.run(
    ...     task_description = "Download top-5 arXiv papers and save to Desktop/papers.txt",
    ...     tool_name        = "code_helper",
    ...     speak_callback   = jarvis_instance.speak,
    ... )
    >>> print(result["execution_output"])
    >>> print(result["transition_log"])

    Design Invariants
    -----------------
    - All node methods are ``async`` and accept exactly one ``LearningState``.
    - Nodes return a partial state dict; LangGraph merges via channel reducers.
    - The Router is a pure synchronous function — no I/O, no side effects.
    - A single compiled graph instance is cached at class level; thread-safe
      because LangGraph compiles to an immutable execution plan.
    """

    # ── Class-level compiled graph cache (compiled once, reused everywhere) ──
    _compiled_graph: Optional[CompiledStateGraph] = None

    def __init__(self) -> None:
        self._api_key: str = _load_gemini_api_key()

        # Lazy import to avoid circular deps with monolithic main.py
        import google.generativeai as _genai
        _genai.configure(api_key=self._api_key)
        self._genai = _genai

        if SelfLearningEngine._compiled_graph is None:
            SelfLearningEngine._compiled_graph = self._build_graph()
            log.info("LangGraph StateGraph compiled and cached.")

    # ──────────────────────────────────────────────────────────────────────────
    #  §6.1  Graph Builder
    # ──────────────────────────────────────────────────────────────────────────

    def _build_graph(self) -> CompiledStateGraph:
        """
        Construct and compile the Reflexion StateGraph.

        Topology
        --------
        [START]
            |
            v
        node_generate_or_adapt   (Generator)
            |
            v
        node_execute_and_observe (Executor)
            |
            v
        node_critique_and_reflect (Critic)
            |
            v
        _router ---- "regenerate" --> node_generate_or_adapt  (back-edge)
               \\---- "terminate"  --> [END]
        """
        builder: StateGraph = StateGraph(LearningState)

        # ── Register nodes ────────────────────────────────────────────────────
        builder.add_node("generator", self.node_generate_or_adapt)
        builder.add_node("executor",  self.node_execute_and_observe)
        builder.add_node("critic",    self.node_critique_and_reflect)

        # ── Wire linear edges ─────────────────────────────────────────────────
        builder.set_entry_point("generator")
        builder.add_edge("generator", "executor")
        builder.add_edge("executor",  "critic")

        # ── Conditional edge: Router branches critic -> generator | END ───────
        builder.add_conditional_edges(
            "critic",
            self._router,
            {
                NodeRoute.REGENERATE : "generator",
                NodeRoute.TERMINATE  : END,
            },
        )

        return builder.compile()

    # ──────────────────────────────────────────────────────────────────────────
    #  §6.2  NODE — Generator
    # ──────────────────────────────────────────────────────────────────────────

    async def node_generate_or_adapt(
        self,
        state: LearningState,
    ) -> dict[str, Any]:
        """
        **Generator Node** — synthesises or rewrites the Python script.

        On the first cycle (retry_counter == 0), generates code from scratch
        using the task description alone.  On subsequent cycles it receives the
        Critic's structured directives and surgically revises the failing code.

        Parameters
        ----------
        state : LearningState
            Full state envelope injected by the LangGraph runtime.

        Returns
        -------
        dict[str, Any]
            Partial state update containing the new ``current_code_or_command``.
        """
        cycle      = state.get("retry_counter", 0)
        task       = state.get("task_description", "")
        tool       = state.get("tool_name", "unknown")
        prev_code  = state.get("current_code_or_command", "") or "(none — first attempt)"
        error      = state.get("error_payload", "")       or "(no prior error)"
        critique   = state.get("critique_feedback", "")   or "(no prior critique)"
        speak      = state.get("speak_callback")

        log.info(f"[Generator] Cycle {cycle} — composing code for: {task[:60]}...")

        if speak and cycle > 0:
            speak(f"Reflexion cycle {cycle}: adapting code based on critic feedback, sir.")

        prompt = _GENERATOR_USER_TEMPLATE.format(
            task_description  = task,
            tool_name         = tool,
            retry_counter     = cycle,
            previous_code     = prev_code[:3000],
            error_payload     = error[:1500],
            critique_feedback = critique[:1500],
        )

        try:
            model = self._genai.GenerativeModel(
                model_name         = _GENERATOR_MODEL,
                system_instruction = _GENERATOR_SYSTEM,
            )
            loop     = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: model.generate_content(prompt),
            )
            new_code = _strip_code_fences(response.text.strip())

        except Exception as exc:
            log.error(f"[Generator] LLM call failed: {exc}")
            new_code = (
                f"import sys\n"
                f"raise RuntimeError('Generator LLM call failed: {exc!s}')\n"
            )

        log.debug(f"[Generator] Generated {len(new_code)} chars of code.")

        new_log = _append_log_entry(state, "generator", {
            "action"        : "code_synthesised",
            "code_length"   : len(new_code),
            "used_critique" : bool(critique and cycle > 0),
        })

        return {
            "current_code_or_command" : new_code,
            "execution_output"        : "",
            "error_payload"           : "",
            "is_valid"                : False,
            "execution_status"        : ExecutionStatus.PENDING,
            "transition_log"          : new_log,
        }

    # ──────────────────────────────────────────────────────────────────────────
    #  §6.3  NODE — Executor
    # ──────────────────────────────────────────────────────────────────────────

    async def node_execute_and_observe(
        self,
        state: LearningState,
    ) -> dict[str, Any]:
        """
        **Executor Node** — safely runs the generated code in a subprocess sandbox.

        Captures both stdout and stderr precisely.  Never raises externally —
        all exceptions are serialised into ``error_payload`` so the Critic
        can inspect them in the next node.

        Isolation Strategy
        ------------------
        - Writes code to a ``tempfile.NamedTemporaryFile`` (never touches the repo tree).
        - Runs the file via ``subprocess.run([sys.executable, tmp_path], ...)``.
        - Enforces ``_EXECUTOR_TIMEOUT`` hard deadline via subprocess timeout.
        - Deletes the temp file in the ``finally`` block unconditionally.

        Parameters
        ----------
        state : LearningState

        Returns
        -------
        dict[str, Any]
            Partial state update with ``execution_output``, ``error_payload``,
            ``is_valid``, and ``execution_status``.
        """
        import os
        import subprocess
        import tempfile

        code = state.get("current_code_or_command", "")
        log.info(f"[Executor] Running {len(code)}-char script...")

        tmp_path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode     = "w",
                suffix   = ".py",
                delete   = False,
                encoding = "utf-8",
            ) as fh:
                fh.write(code)
                tmp_path = fh.name

            log.debug(f"[Executor] Temp script: {tmp_path}")

            loop   = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    [sys.executable, tmp_path],
                    capture_output = True,
                    text           = True,
                    timeout        = _EXECUTOR_TIMEOUT,
                    cwd            = str(Path.home()),
                ),
            )

            stdout = (result.stdout or "").strip()
            stderr = (result.stderr or "").strip()

            if result.returncode == 0:
                log.info(f"[Executor] SUCCESS. stdout={stdout[:80]!r}")
                new_log = _append_log_entry(state, "executor", {
                    "status"     : ExecutionStatus.SUCCESS,
                    "stdout"     : stdout[:200],
                    "returncode" : 0,
                })
                return {
                    "execution_output" : stdout or "Script completed with no output.",
                    "error_payload"    : "",
                    "is_valid"         : True,
                    "execution_status" : ExecutionStatus.SUCCESS,
                    "transition_log"   : new_log,
                }
            else:
                combined_error = f"returncode={result.returncode}\n\n{stderr}"
                log.warning(f"[Executor] FAILURE. returncode={result.returncode}")
                new_log = _append_log_entry(state, "executor", {
                    "status"     : ExecutionStatus.FAILURE,
                    "returncode" : result.returncode,
                    "stderr"     : stderr[:200],
                })
                return {
                    "execution_output" : stdout,
                    "error_payload"    : combined_error[:3000],
                    "is_valid"         : False,
                    "execution_status" : ExecutionStatus.FAILURE,
                    "transition_log"   : new_log,
                }

        except subprocess.TimeoutExpired:
            tb = f"ExecutionTimeout: Script exceeded {_EXECUTOR_TIMEOUT}s deadline."
            log.error(f"[Executor] TIMEOUT: {tb}")
            new_log = _append_log_entry(state, "executor", {
                "status" : ExecutionStatus.FAILURE,
                "error"  : tb,
            })
            return {
                "execution_output" : "",
                "error_payload"    : tb,
                "is_valid"         : False,
                "execution_status" : ExecutionStatus.FAILURE,
                "transition_log"   : new_log,
            }

        except Exception as exc:
            tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            log.error(f"[Executor] UNHANDLED: {exc}")
            new_log = _append_log_entry(state, "executor", {
                "status"    : ExecutionStatus.FAILURE,
                "traceback" : tb[:300],
            })
            return {
                "execution_output" : "",
                "error_payload"    : tb[:3000],
                "is_valid"         : False,
                "execution_status" : ExecutionStatus.FAILURE,
                "transition_log"   : new_log,
            }

        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    # ──────────────────────────────────────────────────────────────────────────
    #  §6.4  NODE — Critic
    # ──────────────────────────────────────────────────────────────────────────

    async def node_critique_and_reflect(
        self,
        state: LearningState,
    ) -> dict[str, Any]:
        """
        **Critic Node** — LLM-as-a-judge reasoning over the execution outcome.

        When execution succeeded (``is_valid == True``), the Critic performs a
        pass-through and writes a validation entry into the log.

        When execution failed, the Critic queries the LLM for a structured JSON
        critique containing root cause analysis and ordered fix steps.  The
        resulting ``critique_feedback`` string is consumed by the Generator on
        the next cycle.

        Parameters
        ----------
        state : LearningState

        Returns
        -------
        dict[str, Any]
            Partial state update with ``critique_feedback`` and incremented
            ``retry_counter``.
        """
        is_valid = state.get("is_valid", False)
        cycle    = state.get("retry_counter", 0)
        speak    = state.get("speak_callback")

        # ── Pass-through: execution was already valid ─────────────────────────
        if is_valid:
            log.info(f"[Critic] PASS — execution validated at cycle {cycle}.")
            new_log = _append_log_entry(state, "critic", {
                "verdict" : "pass",
                "cycle"   : cycle,
            })
            return {
                "critique_feedback" : "",
                "retry_counter"     : cycle,
                "transition_log"    : new_log,
            }

        # ── Execution failed — generate structured critique ───────────────────
        log.info(f"[Critic] ANALYSING failure at cycle {cycle}...")

        prompt = _CRITIC_USER_TEMPLATE.format(
            task_description  = state.get("task_description", ""),
            retry_counter     = cycle,
            current_code      = (state.get("current_code_or_command") or "")[:2000],
            execution_output  = (state.get("execution_output")         or "")[:1000],
            error_payload     = (state.get("error_payload")            or "")[:2000],
        )

        critique_text: str = ""
        try:
            model = self._genai.GenerativeModel(
                model_name         = _CRITIC_MODEL,
                system_instruction = _CRITIC_SYSTEM,
            )
            loop     = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: model.generate_content(prompt),
            )
            raw_json = _strip_code_fences(response.text.strip())

            critique_data: dict[str, Any] = json.loads(raw_json)
            root_cause = critique_data.get("root_cause", "Unknown root cause.")
            fix_steps  = critique_data.get("fix_steps", [])
            severity   = critique_data.get("severity", "recoverable")
            is_fixable = critique_data.get("is_fixable", True)

            critique_text = (
                f"ROOT CAUSE : {root_cause}\n"
                f"SEVERITY   : {severity}\n"
                f"IS FIXABLE : {is_fixable}\n"
                f"FIX STEPS  :\n"
                + "\n".join(f"  {s}" for s in fix_steps)
            )

            log.info(f"[Critic] Root cause: {root_cause[:80]}")

            if speak:
                speak(f"Critique complete, sir. Severity: {severity}. Regenerating.")

            new_log = _append_log_entry(state, "critic", {
                "verdict"    : "fail",
                "severity"   : severity,
                "is_fixable" : is_fixable,
                "root_cause" : root_cause[:120],
            })

        except (json.JSONDecodeError, Exception) as exc:
            log.warning(f"[Critic] Parse failed ({exc}) — raw fallback.")
            critique_text = (
                f"Critic LLM failed to produce structured output: {exc!s}\n"
                f"Raw executor error:\n"
                + (state.get("error_payload") or "")[:500]
            )
            new_log = _append_log_entry(state, "critic", {
                "verdict" : "fail",
                "error"   : "critic_parse_failure",
            })

        return {
            "critique_feedback" : critique_text,
            "retry_counter"     : cycle + 1,
            "transition_log"    : new_log,
        }

    # ──────────────────────────────────────────────────────────────────────────
    #  §6.5  ROUTER — Deterministic Conditional Branch Function
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _router(state: LearningState) -> str:
        """
        Pure deterministic Router — no I/O, no LLM calls, no side effects.

        Decision Logic
        --------------
        1. ``is_valid == True``               -> NodeRoute.TERMINATE  (success)
        2. ``retry_counter >= MAX_RETRY_COUNT`` -> NodeRoute.TERMINATE  (exhausted)
        3. Otherwise                          -> NodeRoute.REGENERATE (back-edge)

        Parameters
        ----------
        state : LearningState

        Returns
        -------
        str
            One of ``NodeRoute.REGENERATE`` or ``NodeRoute.TERMINATE``.
        """
        is_valid      = state.get("is_valid", False)
        retry_counter = state.get("retry_counter", 0)

        if is_valid:
            log.info(f"[Router] is_valid=True -> TERMINATE")
            return NodeRoute.TERMINATE

        if retry_counter >= _MAX_RETRY_COUNT:
            log.warning(
                f"[Router] retry_counter={retry_counter} >= MAX={_MAX_RETRY_COUNT} "
                f"-> TERMINATE (exhausted)"
            )
            return NodeRoute.TERMINATE

        log.info(f"[Router] retry_counter={retry_counter} -> REGENERATE")
        return NodeRoute.REGENERATE

    # ──────────────────────────────────────────────────────────────────────────
    #  §6.6  PUBLIC ENTRY POINT
    # ──────────────────────────────────────────────────────────────────────────

    async def run(
        self,
        task_description : str,
        tool_name        : str                                = "code_helper",
        initial_code     : str                                = "",
        speak_callback   : Optional[Callable[[str], None]]   = None,
    ) -> LearningState:
        """
        Execute the complete Reflexion cycle for a given task.

        Parameters
        ----------
        task_description : str
            Natural-language description of the code/command goal.
        tool_name : str
            Originating JARVIS tool name for contextual enrichment in prompts.
        initial_code : str
            Optional pre-written code to seed the first cycle.
            When empty, the Generator synthesises entirely from scratch.
        speak_callback : Optional[Callable[[str], None]]
            Optional reference to ``JarvisLive.speak``.  When provided, the
            engine will emit verbal progress updates without blocking the loop.

        Returns
        -------
        LearningState
            Final state after graph termination.  Inspect:
            - ``["execution_output"]``  for success output
            - ``["is_valid"]``          for pass/fail result
            - ``["transition_log"]``    for the full cycle audit trail
        """
        seed_state: LearningState = {
            "task_description"        : task_description,
            "current_code_or_command" : initial_code,
            "execution_output"        : "",
            "error_payload"           : "",
            "critique_feedback"       : "",
            "retry_counter"           : 0,
            "is_valid"                : False,
            "execution_status"        : ExecutionStatus.PENDING,
            "transition_log"          : [],
            "tool_name"               : tool_name,
            "speak_callback"          : speak_callback,
        }

        log.info(
            "\n" + "=" * 72 + "\n"
            "  SelfLearningEngine.run()\n"
            f"  Task     : {task_description[:80]}\n"
            f"  Tool     : {tool_name}\n"
            f"  MaxCycles: {_MAX_RETRY_COUNT}\n"
            + "=" * 72
        )

        graph = SelfLearningEngine._compiled_graph
        assert graph is not None, "Compiled graph must not be None after __init__."

        final_state: LearningState = await graph.ainvoke(seed_state)
        _print_transition_report(final_state)
        return final_state


# ══════════════════════════════════════════════════════════════════════════════
#  §7  TRANSITION LOG REPORTER
# ══════════════════════════════════════════════════════════════════════════════

def _print_transition_report(state: LearningState) -> None:
    """
    Pretty-print the full cycle transition log to stdout after graph termination.

    Outputs a structured ASCII table of every node traversal, along with the
    final execution outcome and output/error summary.
    """
    log_entries : list[dict] = state.get("transition_log") or []
    is_valid    : bool       = state.get("is_valid", False)
    cycles      : int        = state.get("retry_counter", 0)
    status_str  : str        = "SUCCESS" if is_valid else "FAILED"

    width = 72
    sep   = "-" * width

    print(f"\n{'=' * width}")
    print(f"  JARVIS Self-Learning Engine -- Execution Report")
    print(f"  Outcome : {status_str}  |  Cycles : {cycles}  |  Log Entries : {len(log_entries)}")
    print(f"{'=' * width}")

    for i, entry in enumerate(log_entries, start=1):
        node      = entry.get("node",      "?")
        cycle_n   = entry.get("cycle",     "?")
        timestamp = entry.get("timestamp", "?")
        details   = {
            k: v for k, v in entry.items()
            if k not in ("node", "cycle", "timestamp")
        }
        detail_str = "  ".join(f"{k}={v!r}" for k, v in details.items())
        print(f"  [{i:02d}]  {timestamp}  [{node:<10}]  cycle={cycle_n}  {detail_str}")

    print(sep)
    output = (state.get("execution_output") or "(no output)")[:120]
    error  = (state.get("error_payload")    or "(no error)")[:120]
    print(f"  FINAL OUTPUT : {output}")
    print(f"  FINAL ERROR  : {error}")
    print(f"{'=' * width}\n")
