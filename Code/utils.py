# Code/utils.py
import json
import os
from datetime import datetime


def save_step_metadata(outdir, step_idx, dom_snapshot, plan=None, action_result=None):
    """
    Saves metadata for automation steps.
    Works even if some arguments are missing.
    """
    os.makedirs(outdir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    metadata = {
        "step_index": step_idx,
        "timestamp": timestamp,
    }

    # If dom_snapshot is a dict (old call patterns) support both
    if isinstance(dom_snapshot, dict) and plan is None:
        metadata["data"] = dom_snapshot
        if action_result is not None:
            metadata["extra"] = action_result
    else:
        metadata["plan"] = plan
        metadata["action_result"] = action_result

    # Save metadata JSON
    try:
        with open(os.path.join(outdir, f"step_{step_idx:03d}_meta.json"), "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[WARN] Failed to save metadata for step {step_idx}: {e}")

    # Save DOM snapshot if it looks like HTML/text
    try:
        if isinstance(dom_snapshot, str) and len(dom_snapshot.strip()) > 0:
            with open(os.path.join(outdir, f"step_{step_idx:03d}_dom.html"), "w", encoding="utf-8") as f:
                f.write(dom_snapshot)
    except Exception as e:
        print(f"[WARN] Failed to save DOM snapshot for step {step_idx}: {e}")

    print(f"✅ Saved metadata for step {step_idx}")
