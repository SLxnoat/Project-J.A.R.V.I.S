import json
import re
import sys
from pathlib import Path
from enum import Enum


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR        = get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"


class ErrorDecision(Enum):
    RETRY       = "retry"      
    SKIP        = "skip"       
    REPLAN      = "replan"     
    ABORT       = "abort"    


ERROR_ANALYST_PROMPT = """You are the Diagnostics and Recovery Engine of the J.A.R.V.I.S. (Mark XXXIX) Agentic System.
A step in the execution plan has failed. Analyze the execution context, tool parameters, and error traceback to decide the optimal recovery path.

## RECOVERY TAXONOMY
- `retry`: Select this ONLY for transient, non-persistent issues (e.g. network timeout, temporary file lock, API rate limiting, timing race condition). The action is structurally correct and likely to succeed if repeated.
- `skip`: Select this if the failed step is non-essential, and subsequent steps can still succeed or complete the overall goal without it.
- `replan`: Select this if the step failed due to logical errors, incorrect tool parameters, invalid file paths, syntax errors, or wrong tool selection. A new approach or a different tool configuration is required.
- `abort`: Select this if the task is fundamentally impossible, breaches security boundaries, requires missing permissions, or is unsafe to continue.

## DIAGNOSTIC INSTRUCTIONS
- Formulate a precise, 1-sentence diagnostic explanation of the root cause.
- If decision is `replan`, provide a detailed `fix_suggestion` detailing what alternative tool or parameters should be tried (e.g., "Use web_search to find the correct download link instead of downloading directly").
- If decision is `retry`, set `max_retries` to 1 or 2 (maximum 2). For all other decisions, set to 0.
- Formulate a polite, calm notification message to the user (`user_message`) of maximum 15 words, addressing them as "sir".

## OUTPUT JSON SCHEMA CONTRACT
Return ONLY a valid JSON object. Do not include markdown formatting (e.g., no ```json), no explanations, and no trailing text.

{
  "decision": "retry|skip|replan|abort",
  "reason": "Precise root cause description.",
  "fix_suggestion": "Actionable correction steps if replanning, otherwise empty string.",
  "max_retries": 0,
  "user_message": "Calm, polite update to the user, sir."
}
"""


def _get_api_key() -> str:
    with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]


def analyze_error(
    step: dict,
    error: str,
    attempt: int = 1,
    max_attempts: int = 2
) -> dict:
    """
    Analyzes a failed step and returns a recovery decision.

    Args:
        step         : The step dict that failed
        error        : Error message/traceback
        attempt      : Current attempt number
        max_attempts : How many times we've already tried

    Returns:
        {
            "decision": ErrorDecision,
            "reason": str,
            "fix_suggestion": str,
            "max_retries": int,
            "user_message": str
        }
    """
    import google.generativeai as genai

    if attempt >= max_attempts:
        print(f"[ErrorHandler] ⚠️ Max attempts reached for step {step.get('step')} — forcing replan")
        return {
            "decision":      ErrorDecision.REPLAN,
            "reason":        f"Failed {attempt} times: {error[:100]}",
            "fix_suggestion": "Try a completely different approach or tool",
            "max_retries":   0,
            "user_message":  "Trying a different approach, sir."
        }

    genai.configure(api_key=_get_api_key())
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash-lite",
        system_instruction=ERROR_ANALYST_PROMPT
    )

    prompt = f"""Failed step:
Tool: {step.get('tool')}
Description: {step.get('description')}
Parameters: {json.dumps(step.get('parameters', {}), indent=2)}
Critical: {step.get('critical', False)}

Error:
{error[:500]}

Attempt number: {attempt}"""

    try:
        response = model.generate_content(prompt)
        text     = response.text.strip()
        text     = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()

        result = json.loads(text)
        decision_str = result.get("decision", "replan").lower()
        decision_map = {
            "retry":  ErrorDecision.RETRY,
            "skip":   ErrorDecision.SKIP,
            "replan": ErrorDecision.REPLAN,
            "abort":  ErrorDecision.ABORT,
        }
        result["decision"] = decision_map.get(decision_str, ErrorDecision.REPLAN)


        if step.get("critical") and result["decision"] == ErrorDecision.SKIP:
            result["decision"]     = ErrorDecision.REPLAN
            result["user_message"] = "This step is critical — finding alternative approach, sir."

        print(f"[ErrorHandler] Decision: {result['decision'].value} — {result.get('reason', '')}")
        return result

    except Exception as e:
        print(f"[ErrorHandler] ⚠️ Analysis failed: {e} — defaulting to replan")
        return {
            "decision":       ErrorDecision.REPLAN,
            "reason":         str(e),
            "fix_suggestion": "Try alternative approach",
            "max_retries":    1,
            "user_message":   "Encountered an issue, adjusting approach, sir."
        }


def generate_fix(step: dict, error: str, fix_suggestion: str) -> dict:
    """
    When decision is REPLAN and a fix suggestion exists,
    generates a replacement step using generated_code as fallback.

    Returns a modified step dict.
    """
    import google.generativeai as genai

    genai.configure(api_key=_get_api_key())
    model = genai.GenerativeModel(model_name="gemini-2.0-flash")

    prompt = f"""You are an expert debugger and recovery agent. A task step has failed, and we need a revised solution.

## FAILURE CONTEXT
- Failed Step: Tool [{step.get('tool')}] doing "{step.get('description')}"
- Parameters: {json.dumps(step.get('parameters', {}), indent=2)}
- Error Details: {error[:300]}
- Recovery Fix Suggestion: {fix_suggestion}

## INSTRUCTION
Write a robust, fully working Python script that achieves the intended goal while resolving the error.
- Implement correct imports, handle edge cases, and add appropriate error checking.
- Do NOT output any explanations, markdown blocks, or comments. Output ONLY raw, executable Python code.
"""

    try:
        response = model.generate_content(prompt)
        code = response.text.strip()
        code = re.sub(r"```(?:python)?", "", code).strip().rstrip("`").strip()

        return {
            "step":        step.get("step"),
            "tool":        "code_helper",
            "description": f"Auto-fix for: {step.get('description')}",
            "parameters": {
                "action":      "run",
                "description": fix_suggestion,
                "code":        code,
                "language":    "python"
            },
            "depends_on": step.get("depends_on", []),
            "critical":   step.get("critical", False)
        }

    except Exception as e:
        print(f"[ErrorHandler] ⚠️ Fix generation failed: {e}")
        return {
            "step":        step.get("step"),
            "tool":        "generated_code",
            "description": f"Fallback for: {step.get('description')}",
            "parameters":  {"description": step.get("description", "")},
            "depends_on":  step.get("depends_on", []),
            "critical":    step.get("critical", False)
        }