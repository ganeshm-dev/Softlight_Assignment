# Code/prompts.py
from textwrap import dedent
import json


def build_feedback_prompt(task: str, last_plan: dict, action_result: dict, dom_snapshot: str) -> str:
    prompt = dedent(f"""
    You are an expert UI automation planner. High-level task:
    {task}

    Previous plan:
    {json.dumps(last_plan, ensure_ascii=False)}

    Action result:
    {json.dumps(action_result, ensure_ascii=False)}

    Current HTML snapshot (trimmed):
    {dom_snapshot[:16000]}

    Did the last action make progress? If yes, plan the next single action in JSON format:
      {{ "action": "<click|type|press|scroll|wait|select|hover>", "selector": "<css selector>", "text|value": "<text if needed>", "desc": "<short human description>" }}
    If the task is complete, respond with: {{ "verdict":"done" }}.
    Answer ONLY with the JSON object or array when asked to produce a plan.
    """).strip()
    return prompt


def build_ui_plan_prompt(task: str, dom_snapshot: str) -> str:
    """
    This prompt asks Gemini to produce a micro-detailed step-by-step UI plan.
    It forbids constructing URLs or relying on navigation-by-url parameters. Each step must be explicit.
    Returns only strict JSON: an array of objects, each with:
      - action: one of ["click","type","select","wait","press","scroll","hover"]
      - selector: CSS selector (required for actionable steps)
      - value/text: for typing/selecting
      - desc: short human description (micro-detailed)
    """
    example = [
        {
            "action": "click",
            "selector": "button[data-testid='new-project']",
            "desc": "Click the New Project button to open the 'Create project' modal"
        },
        {
            "action": "type",
            "selector": "input[name='name']",
            "value": "AI Test Project",
            "desc": "Type the project name into the name input"
        },
        {
            "action": "click",
            "selector": "button[type='submit']",
            "desc": "Click the Create/Save button to create the project"
        }
    ]
    prompt = dedent(f"""
    You are a precise browser automation planner. The user task is:
    {task}

    Here is the current DOM snapshot (trimmed):
    {dom_snapshot[:16000]}

    Produce a JSON array (and ONLY a JSON array) of step objects. Each step object must include:
      - "action": one of ["click","type","select","wait","press","scroll","hover"]
      - "selector": CSS selector to target the element (required for click/type/select/hover)
      - For typing/select: "value" (or "text")
      - "desc": short human-readable micro-detailed description of the step

    Important constraints:
    - Do NOT return navigation by constructing or changing the URL. Use in-page actions only (clicks, presses).
    - Each step must be atomic and micro-detailed (no merging steps).
    - Prefer stable selectors (data- attributes, role-based selectors). If impossible, use CSS that clearly targets the intended element.
    - If waiting for elements is necessary, include an explicit step with action "wait" and "selector" or "seconds".
    - Keep the plan focused to complete the user's high-level task without side effects.

    Example output (strict JSON):
    {json.dumps(example, ensure_ascii=False, indent=2)}

    Return only JSON.
    """).strip()
    return prompt
