import os
import time
import json
from pathlib import Path
from playwright.sync_api import Page, BrowserContext


class PlaywrightController:
    def __init__(self, context: BrowserContext, outdir: str, config: dict):
        self.context = context
        self.page: Page = None
        self.outdir = outdir
        Path(outdir).mkdir(parents=True, exist_ok=True)
        self.config = config or {}
        self._storage_path = os.path.join(outdir, "cookies.json")
        self.captured_names = set()

    def set_page(self, page: Page):
        self.page = page

    # ---------------- NAVIGATION ----------------
    def goto(self, url: str):
        if not url:
            print("[Controller] Invalid URL for navigation: None or empty")
            return
        try:
            url = url.strip().strip("`'\"")
            if not url.startswith("http"):
                print(f"[Controller] Invalid URL: {url}")
                return
            self.page.goto(url, wait_until="networkidle", timeout=15000)
        except Exception as e:
            print(f"[Controller] goto error (networkidle): {e}")
            try:
                self.page.goto(url, wait_until="load", timeout=15000)
            except Exception as e2:
                print(f"[Controller] fallback goto error: {e2}")

    # ---------------- CAPTURE ----------------
    def capture(self, label: str):
        if label in self.captured_names:
            return "", None
        self.captured_names.add(label)
        try:
            dom = self.page.content()
        except Exception as e:
            print(f"[WARN] capture failed for '{label}': {e}")
            dom = "<no DOM captured>"
        try:
            path = os.path.join(self.outdir, f"{label}.png")
            self.page.screenshot(path=path, full_page=True)
        except Exception as e:
            print(f"[WARN] screenshot failed for '{label}': {e}")
            path = None
        return dom, path

    # ---------------- ACTION EXECUTION ----------------
    def execute_action(self, action: dict):
        if not action:
            return {"error": "no_action_provided"}
        typ = action.get("type") or action.get("action")
        try:
            if typ in ("fill", "type", "set_value"):
                selector = action.get("selector")
                text = action.get("text", "") or action.get("value", "")
                if selector:
                    self.page.fill(selector, text)
                    return {"status": "filled", "selector": selector}
                el = self.page.query_selector("input, textarea")
                if el:
                    el.fill(text)
                    return {"status": "filled_first_input"}
                return {"status": "no_input_found"}

            elif typ == "click":
                selector = action.get("selector")
                by_text = action.get("by_text", False)
                text = action.get("text")
                if by_text and text:
                    el = self.page.query_selector(f"text={text}")
                    if el:
                        el.click()
                        return {"status": "clicked_by_text"}
                    el = self.page.query_selector(f"*:has-text(\"{text}\")")
                    if el:
                        el.click()
                        return {"status": "clicked_by_text_fallback"}
                    return {"status": "no_element_by_text"}
                if selector:
                    el = self.page.query_selector(selector)
                    if el:
                        el.click()
                        return {"status": "clicked", "selector": selector}
                    return {"status": "no_element", "selector": selector}
                return {"error": "no_selector_for_click"}

            elif typ == "press":
                key = action.get("key", "Enter")
                self.page.keyboard.press(key)
                return {"status": "pressed", "key": key}

            elif typ == "scroll":
                distance = action.get("distance", 500)
                self.page.evaluate(f"window.scrollBy(0, {distance});")
                return {"status": "scrolled", "distance": distance}

            elif typ == "wait":
                time.sleep(action.get("seconds", 1))
                return {"status": "waited"}

            else:
                return {"error": "unknown_action_type", "provided": action}
        except Exception as e:
            return {"error": f"execute_action_failed:{e}"}

    # ---------------- COOKIES ----------------
    def apply_system_cookies(self) -> bool:
        try:
            if os.path.exists(self._storage_path):
                with open(self._storage_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                cookies = data.get("cookies") or []
                if cookies:
                    self.context.add_cookies(cookies)
                    print("[Controller] Loaded cookies from storage state.")
                    return True
        except Exception as e:
            print(f"[Controller] apply_system_cookies error: {e}")
        return False

    def save_storage_state(self, path=None):
        if not path:
            path = self._storage_path
        try:
            state = self.page.context.storage_state()
            with open(path, "w") as f:
                json.dump(state, f, indent=2)
            print(f"[Controller] Saved cookies to {path}")
        except Exception as e:
            print(f"[WARN] Failed to save cookies: {e}")

    def preload_cookies(self, cookies_path: str):
        try:
            with open(cookies_path, "r") as f:
                cookies = json.load(f)
            self.context.add_cookies(cookies)
            print(
                f"[Controller] Injected {len(cookies)} cookies into session.")
        except Exception as e:
            print(f"[WARN] Failed to preload cookies: {e}")

    def is_logged_in(self) -> bool:
        try:
            for c in self.context.cookies():
                if any(k in c["name"].lower() for k in ["session", "auth", "token", "jwt", "sid"]):
                    return True
        except Exception:
            pass
        try:
            dom = self.page.content().lower()
            if not any(x in dom for x in ["sign in", "login", "password", "create account"]):
                return True
        except Exception:
            pass
        return False

    # ---------------- LOGIN PROMPT ----------------
    def show_manual_login_prompt(self, timeout: int = 120):
        js = f"""
        (() => {{
            const div = document.createElement('div');
            div.id = 'manual-login-banner';
            div.style = "position:fixed;top:10px;right:10px;z-index:999999;background:#fff4cc;padding:10px;border-radius:8px;border:1px solid #d4b000;font-size:13px;";
            div.innerHTML = `⚠️ Please login manually within <span id='ml-timer'>{timeout}</span>s`;
            document.body.appendChild(div);
            let t={timeout};
            const timer=setInterval(()=>{{
                t--; 
                const el=document.getElementById('ml-timer');
                if(el) el.innerText=t;
                if(t<=0){{clearInterval(timer);div.remove();}}
            }},1000);
        }})();
        """
        try:
            self.page.evaluate(js)
        except Exception:
            pass

    def remove_manual_login_prompt(self):
        try:
            self.page.evaluate(
                "const e=document.getElementById('manual-login-banner');if(e)e.remove();")
        except Exception:
            pass
