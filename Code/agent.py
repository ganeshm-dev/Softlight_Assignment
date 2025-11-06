import time
import json
import os
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
from .playwright_controller import PlaywrightController
from .gemini_client import GeminiClient
from .prompts import build_feedback_prompt, build_ui_plan_prompt
from .utils import save_step_metadata

# Manual login timeout (seconds)
MANUAL_LOGIN_TIMEOUT = 120


class Agent:
    def __init__(self, config: dict, outdir: str):
        self.config = config or {}
        self.outdir = outdir
        self.max_steps = self.config.get("max_steps", 20)
        self.gemini = GeminiClient(self.config)
        self.controller = None
        self.last_dom_snapshot = None

    def _clean_url(self, url: str) -> str:
        """Remove junk and ensure it’s a valid navigable URL."""
        if not url:
            return ""
        url = url.strip().strip("`'\"")
        if not url.lower().startswith("http"):
            return ""
        # Clean any malformed params Gemini sometimes appends
        url = url.replace(" ", "%20").replace("\\", "")
        return url

    def get_ui_plan_from_gemini(self, task: str, dom_snapshot: str):
        prompt = build_ui_plan_prompt(task, dom_snapshot)
        return self.gemini.plan_action(prompt)

    def execute_ui_plan(self, ui_plan, max_retries=2):
        """Execute structured UI actions returned by Gemini."""
        results = []
        if not isinstance(ui_plan, list):
            return {"error": "ui_plan_not_list", "raw": ui_plan}

        for idx, step in enumerate(ui_plan):
            typ = step.get("action") or step.get("type")
            selector = step.get("selector") or step.get(
                "sel") or step.get("query")
            value = step.get("value") or step.get("text") or step.get("fill")
            result = None

            for attempt in range(max_retries + 1):
                try:
                    action_dict = {}
                    if typ in ("fill", "type", "set_value"):
                        action_dict = {"type": "fill",
                                       "selector": selector, "text": value or ""}
                    elif typ == "click":
                        if selector:
                            action_dict = {"type": "click",
                                           "selector": selector}
                        elif step.get("by_text"):
                            action_dict = {
                                "type": "click", "by_text": True, "text": step.get("text")}
                    elif typ == "press":
                        action_dict = {"type": "press",
                                       "key": step.get("key", "Enter")}
                    elif typ == "wait":
                        action_dict = {"type": "wait",
                                       "seconds": step.get("seconds", 1)}
                    elif typ == "scroll":
                        action_dict = {
                            "type": "scroll",
                            "direction": step.get("direction", "down"),
                            "distance": step.get("distance", 500),
                        }
                    elif typ in ("select", "select_option"):
                        if selector and "value" in step:
                            self.controller.page.select_option(
                                selector, step["value"])
                            result = {"status": "selected",
                                      "selector": selector, "value": step["value"]}
                        else:
                            result = {
                                "error": "select_missing_selector_or_value"}
                        break
                    elif typ == "hover":
                        if selector:
                            self.controller.page.hover(selector)
                            result = {"status": "hovered",
                                      "selector": selector}
                        else:
                            result = {"error": "hover_no_selector"}
                        break
                    else:
                        result = {"error": "unknown_action", "provided": step}
                        break

                    if action_dict:
                        result = self.controller.execute_action(action_dict)

                except Exception as e:
                    result = {"error": f"exception:{e}"}

                if isinstance(result, dict) and (result.get("status") or not result.get("error")):
                    break
                time.sleep(0.5)

            results.append({"step_index": idx, "step": step, "result": result})

            # Recovery path if something fails
            if isinstance(result, dict) and result.get("error"):
                print(
                    f"[Agent] Step {idx} failed: {result}. Asking Gemini for recovery.")
                try:
                    dom_snapshot = self.controller.page.content()
                except Exception:
                    dom_snapshot = ""
                feedback = build_feedback_prompt(
                    task="", last_plan=step, action_result=result, dom_snapshot=dom_snapshot
                )
                repl = self.gemini.plan_action(feedback)
                repl_action = repl.get("action") if isinstance(
                    repl, dict) else None
                if repl_action:
                    print(
                        f"[Agent] Executing repl action from Gemini: {repl_action}")
                    repl_res = self.controller.execute_action(repl_action)
                    results.append(
                        {"repl_step": repl_action, "repl_result": repl_res})

        return results

    def _capture_unique_state(self, label: str):
        """Avoid duplicate screenshots and DOM snapshots."""
        try:
            dom_snapshot = self.controller.page.content()
            if self.last_dom_snapshot != dom_snapshot:
                self.last_dom_snapshot = dom_snapshot
                return self.controller.capture(label)
            else:
                print(f"[Agent] Skipping duplicate snapshot for '{label}'")
                return dom_snapshot, None
        except Exception as e:
            print(f"[WARN] Snapshot capture failed for '{label}': {e}")
            return "", None

    def run(self, start_url: str = "https://www.google.com", task: str = None):
        """Main agent flow."""
        results = {"task": task, "start_url": start_url, "steps": []}

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=not self.config.get("headful", False))
            context = browser.new_context(viewport=self.config.get("viewport"))
            self.controller = PlaywrightController(
                context=context, outdir=self.outdir, config=self.config)
            page = context.new_page()
            self.controller.set_page(page)

            cookies_path = os.path.join(self.outdir, "cookies.json")
            logged_in = False

            # --- Step 1: Start always from Google ---
            print(f"[Agent] Starting from {start_url}")
            self.controller.goto(start_url)
            time.sleep(2)

           # --- Step 2: Handle login flow (auto or manual) ---
            self.base_url = None
            logged_in = False

            if os.path.exists(cookies_path):
                print("[Agent] Existing cookies found — injecting...")
                self.controller.preload_cookies(cookies_path)
                self.controller.goto(start_url or "https://www.google.com")
                time.sleep(3)
                if self.controller.is_logged_in():
                    print("[Agent] ✅ Logged in automatically using cookies.")
                    logged_in = True
                else:
                    print(
                        "[Agent] ⚠️ Cookies invalid or expired — removing and reattempting manual login.")
                    os.remove(cookies_path)

            if not logged_in:
                # --- Step 3: Ask Gemini for base website and perform manual login ---
                print("[Agent] No valid cookies — asking Gemini for base website...")
                base_prompt = (
                    f"Task: {task}\n"
                    "Respond with ONLY the clean base website URL (e.g., https://linear.app) where this task would be performed. "
                    "Do not include /login or any explanations — only the root URL."
                )
                base_resp = self.gemini.plan_action(base_prompt)

                if isinstance(base_resp, dict):
                    base_url = base_resp.get("url") or str(
                        base_resp.get("raw_text", "")).strip()
                else:
                    base_url = str(base_resp).strip()

                # Fallback: extract first https:// URL if Gemini adds junk
                import re
                match = re.search(r"https?://[^\s'\"]+", base_url)
                if match:
                    base_url = match.group(0)

                self.base_url = self._clean_url(base_url)
                if not self.base_url:
                    print(
                        "[WARN] Gemini failed to provide base URL. Defaulting to Google.")
                    self.base_url = "https://www.google.com"

                login_url = f"{self.base_url.rstrip('/')}/login"
                print(f"[Agent] Navigating to login page: {login_url}")
                self.controller.goto(login_url)
                self.controller.show_manual_login_prompt(MANUAL_LOGIN_TIMEOUT)

                start_time = time.time()
                while time.time() - start_time < MANUAL_LOGIN_TIMEOUT:
                    if self.controller.is_logged_in():
                        print(
                            "[Agent] ✅ Login detected — saving cookies and resuming.")
                        self.controller.remove_manual_login_prompt()
                        try:
                            self.controller.save_storage_state()
                            print("[Agent] ✅ Cookies saved after manual login.")
                        except Exception as e:
                            print(f"[WARN] Failed to save cookies: {e}")
                        logged_in = True
                        break
                    time.sleep(3)

                if not logged_in:
                    print(
                        f"[Agent] Manual login not completed in {MANUAL_LOGIN_TIMEOUT}s.")
                    self.controller.remove_manual_login_prompt()
                    return {"error": "login_timeout"}

            # --- Step 4: Ask Gemini for task-specific URL ---
            print("[Agent] Asking Gemini for task-specific URL...")
            task_url_prompt = (
                f"Task: {task}\n"
                "You are to output ONLY the clean, fully qualified URL (https...) where this task can be done. "
                "Do not include quotes, backticks, or explanations — just the URL itself."
            )
            task_specific_url = self.gemini.plan_action(task_url_prompt)
            if isinstance(task_specific_url, dict):
                task_specific_url = (
                    task_specific_url.get("url")
                    or str(task_specific_url.get("raw_text", "")).strip()
                )
            else:
                task_specific_url = str(task_specific_url).strip()

            task_specific_url = self._clean_url(task_specific_url)
            if not task_specific_url:
                print(
                    "[WARN] Gemini did not provide a valid task-specific URL. Staying on current page.")
                task_specific_url = self.controller.page.url
            else:
                print(f"[Agent] Gemini provided task URL: {task_specific_url}")

            # --- Step 5: Navigate to task URL ---
            print(f"[Agent] Navigating to: {task_specific_url}")
            self.controller.goto(task_specific_url)
            self._capture_unique_state("task_page_loaded")

            # --- Step 6: Save metadata ---
            dom, _ = self.controller.capture("aligned_authenticated_page")
            step_meta = {"step": 0, "action": "task_page_ready",
                         "url": task_specific_url}
            save_step_metadata(self.outdir, 0, step_meta, None, None)
            results["steps"].append(step_meta)

            # --- Step 7: Request and execute UI plan ---
            print("[Agent] Requesting structured UI plan from Gemini...")
            dom_snapshot = self.controller.page.content()
            ui_plan_resp = self.get_ui_plan_from_gemini(task, dom_snapshot)

            # Normalize JSON
            if isinstance(ui_plan_resp, str):
                try:
                    ui_plan = json.loads(ui_plan_resp)
                except Exception:
                    return {"error": "ui_plan_not_parseable", "raw": ui_plan_resp}
            elif isinstance(ui_plan_resp, dict):
                ui_plan = ui_plan_resp.get("plan") or ui_plan_resp.get(
                    "steps") or ui_plan_resp
            else:
                ui_plan = ui_plan_resp

            print("[Agent] Executing UI plan...")
            execution_results = self.execute_ui_plan(ui_plan)
            results["steps"].append({"ui_plan_execution": execution_results})

            browser.close()
            print("✅ Automation completed successfully.")
            return results
