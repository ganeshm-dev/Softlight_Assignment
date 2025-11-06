# Code/main.py
import argparse
import json
import os
from Code.agent import Agent
from pathlib import Path


def load_config(path: str):
    # Accept relative to module or absolute
    if not os.path.exists(path):
        # try Code/ path fallback
        alt = os.path.join(os.path.dirname(__file__), path)
        if os.path.exists(alt):
            path = alt
        else:
            raise FileNotFoundError(f"Missing config file at: {path}")
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # Allow env var override for API key
    env_key = os.getenv("GEMINI_API_KEY")
    if env_key:
        cfg["gemini_api_key"] = env_key

    cfg["gemini_model"] = os.getenv(
        "GEMINI_MODEL", cfg.get("gemini_model", "gemini-2.5-flash"))
    cfg["gemini_endpoint"] = os.getenv(
        "GEMINI_ENDPOINT",
        f"https://generativelanguage.googleapis.com/v1beta/models/{cfg['gemini_model']}:generateContent"
    )
    return cfg


def ensure_outdir(path):
    Path(path).mkdir(parents=True, exist_ok=True)
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=False,
                        help="Starting URL (optional)")
    parser.add_argument("--task", required=True,
                        help="Agent task e.g. 'Create a project in Linear named X'")
    parser.add_argument("--outdir", default="./output",
                        help="Directory for screenshots/report")
    parser.add_argument("--config", default="config.json",
                        help="Path to config.json")
    args = parser.parse_args()

    config = load_config(args.config)
    outdir = ensure_outdir(args.outdir)

    agent = Agent(config=config, outdir=outdir)
    report = agent.run(start_url=args.url, task=args.task)

    report_path = os.path.join(outdir, "report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"Done — report written to {report_path}")


if __name__ == "__main__":
    main()
