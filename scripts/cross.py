"""
cross.py — orquestador del modo --cross.

Cruza un input (NIF / razón social / id Mission Control) contra:
- Mission Control CRM (HTTP API si configurada, fallback JSON local).
- Outputs previos de lead-research-brief y meeting-preaudit-brief.
- Observations.jsonl (Sinapsis).
- _operator-state::projectBlueprints y _instincts-index.json.

Output: resumen "qué sabemos / qué falta / próxima skill recomendada".
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (
    HOME, OBSERVATIONS_PATH, OPERATOR_STATE_PATH, emit_observation, http_get,
    is_valid_nif, normalize_nif, normalize_razon_social, now_iso, today_dir,
    write_snapshot,
)


CACHE_LRB = HOME / ".claude" / ".cache" / "lead-research-brief"
CACHE_MPB = HOME / ".claude" / ".cache" / "meeting-preaudit-brief"
INSTINCTS_INDEX = HOME / ".claude" / "skills" / "_instincts-index.json"


def _load_jsonl_lines(path: Path, limit: int = 5000) -> list[dict]:
    """Reads up to `limit` lines (most recent) from a JSONL file."""
    if not path.exists():
        return []
    lines: list[str] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        # cheap tail: read all then take last N (operator's observation files are small enough)
        for line in f:
            lines.append(line)
    out: list[dict] = []
    for ln in lines[-limit:]:
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out


def search_mission_control(needle: str) -> list[dict]:
    """
    Tries HTTP API first (env MISSION_CONTROL_API_URL + _API_KEY), falls
    back to local JSON file under ~/Mission Control/ or projectroot/data/.
    """
    api_url = os.environ.get("MISSION_CONTROL_API_URL")
    api_key = os.environ.get("MISSION_CONTROL_API_KEY")
    matches: list[dict] = []

    if api_url and api_key:
        url = f"{api_url.rstrip('/')}/leads/search?q={needle}"
        status, body = http_get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=10)
        if status == 200:
            try:
                data = json.loads(body)
                matches.extend(data if isinstance(data, list) else data.get("results", []))
            except json.JSONDecodeError:
                pass
        else:
            emit_observation("source_unavailable", {"source": "MissionControl-API", "status": status})

    # Fallback: local JSON. Resolution order:
    #   1. env var MISSION_CONTROL_LEADS_PATH (explicit override)
    #   2. ~/mission-control/leads.json (XDG-friendly default)
    #   3. ~/Desktop/mission-control/leads.json
    candidates = []
    env_path = os.environ.get("MISSION_CONTROL_LEADS_PATH")
    if env_path:
        candidates.append(Path(env_path))
    candidates.extend([
        HOME / "mission-control" / "leads.json",
        HOME / "Desktop" / "mission-control" / "leads.json",
        HOME / "OneDrive" / "Desktop" / "mission-control" / "leads.json",
    ])
    for path in candidates:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for lead in (data if isinstance(data, list) else data.get("leads", [])):
                blob = json.dumps(lead, ensure_ascii=False).lower()
                if needle.lower() in blob:
                    matches.append(lead)
        except (json.JSONDecodeError, OSError):
            continue
    return matches


def search_brief_outputs(cache_dir: Path, needle: str) -> list[dict]:
    """Returns metadata of brief output files that mention `needle`."""
    if not cache_dir.exists():
        return []
    out: list[dict] = []
    for f in cache_dir.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix not in (".json", ".html", ".md", ".docx", ".txt"):
            continue
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            continue
        if needle.lower() in content.lower():
            out.append({
                "path": str(f),
                "size": f.stat().st_size,
                "mtime": f.stat().st_mtime,
            })
    return out


def search_observations(needle: str) -> list[dict]:
    obs = _load_jsonl_lines(OBSERVATIONS_PATH, limit=5000)
    matches: list[dict] = []
    for o in obs:
        blob = json.dumps(o, ensure_ascii=False).lower()
        if needle.lower() in blob:
            matches.append(o)
    return matches[-50:]  # last 50 matches


def search_instincts(needle: str) -> list[dict]:
    if not INSTINCTS_INDEX.exists():
        return []
    try:
        data = json.loads(INSTINCTS_INDEX.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    matches: list[dict] = []
    instincts = data.get("instincts") or data
    if isinstance(instincts, dict):
        instincts = list(instincts.values())
    for inst in instincts:
        if not isinstance(inst, dict):
            continue
        blob = json.dumps(inst, ensure_ascii=False).lower()
        if needle.lower() in blob:
            matches.append({
                "id": inst.get("id"),
                "summary": inst.get("summary") or inst.get("description"),
            })
    return matches[:20]


def cross(input_str: str) -> dict:
    needle = input_str.strip()
    nif_form = normalize_nif(needle) if is_valid_nif(needle) else None
    name_form = normalize_razon_social(needle)

    # Search with both forms — wider net
    queries = [q for q in [needle, nif_form, name_form] if q]

    mc_results: list[dict] = []
    lrb_results: list[dict] = []
    mpb_results: list[dict] = []
    obs_results: list[dict] = []
    inst_results: list[dict] = []

    for q in queries:
        mc_results.extend(search_mission_control(q))
        lrb_results.extend(search_brief_outputs(CACHE_LRB, q))
        mpb_results.extend(search_brief_outputs(CACHE_MPB, q))
        obs_results.extend(search_observations(q))
        inst_results.extend(search_instincts(q))

    # Dedup by representative key
    def _dedup(items: list, key: str) -> list:
        seen, out = set(), []
        for it in items:
            k = it.get(key) if isinstance(it, dict) else None
            if k and k in seen:
                continue
            if k:
                seen.add(k)
            out.append(it)
        return out

    mc_results = _dedup(mc_results, "id")
    lrb_results = _dedup(lrb_results, "path")
    mpb_results = _dedup(mpb_results, "path")
    inst_results = _dedup(inst_results, "id")

    # Compute "missing" pieces
    found_any_brief = bool(lrb_results)
    found_meeting = bool(mpb_results)
    found_in_mc = bool(mc_results)
    missing = []
    if not found_in_mc:
        missing.append("missionControl-entry")
    if not found_any_brief:
        missing.append("lead-research-brief")
    if not found_meeting:
        missing.append("meeting-preaudit-brief")

    next_skill = None
    if not found_in_mc:
        next_skill = "norteia-crm-patterns (registrar en Mission Control)"
    elif not found_any_brief:
        next_skill = "lead-research-brief"
    elif not found_meeting:
        next_skill = "meeting-preaudit-brief"
    else:
        next_skill = "norteia-contracts (preparar pack contractual)"

    payload = {
        "schemaVersion": "1.0.0",
        "skill": "norteia-lead-recon",
        "mode": "cross",
        "timestamp": now_iso(),
        "input": needle,
        "found": {
            "missionControl": mc_results,
            "leadResearchBrief": lrb_results,
            "meetingPreauditBrief": mpb_results,
            "observations": obs_results[-20:],
            "instincts": inst_results,
        },
        "missing": missing,
        "nextRecommendedSkill": next_skill,
        "warnings": [],
    }

    snapshot_path = write_snapshot("cross", payload)
    payload["writes"] = {"snapshot": str(snapshot_path)}

    emit_observation("tool_lead_recon", {
        "phase": "cross.complete",
        "input": needle,
        "missionControlHits": len(mc_results),
        "briefHits": len(lrb_results) + len(mpb_results),
        "next": next_skill,
    })
    return payload


def main() -> None:
    p = argparse.ArgumentParser(description="norteia-lead-recon — cross orchestrator")
    p.add_argument("--input", required=True)
    args = p.parse_args()
    payload = cross(args.input)
    print(json.dumps({
        "input": payload["input"],
        "summary": {
            "missionControl": len(payload["found"]["missionControl"]),
            "leadResearchBrief": len(payload["found"]["leadResearchBrief"]),
            "meetingPreauditBrief": len(payload["found"]["meetingPreauditBrief"]),
            "observations": len(payload["found"]["observations"]),
            "instincts": len(payload["found"]["instincts"]),
        },
        "missing": payload["missing"],
        "nextRecommendedSkill": payload["nextRecommendedSkill"],
        "writes": payload["writes"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
