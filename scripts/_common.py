"""
norteia-lead-recon: utilities compartidas (cache, normalización, detección de proyecto, observations).

NO importa nada de las fuentes — es la base sobre la que ellas se montan.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Paths

HOME = Path.home()
SKILL_DIR = Path(__file__).resolve().parent.parent
CACHE_ROOT = HOME / ".claude" / ".cache" / "lead-recon"
OBSERVATIONS_PATH = HOME / ".claude" / "observations.jsonl"
OPERATOR_STATE_PATH = HOME / ".claude" / "skills" / "_operator-state.json"
PROJECTS_REGISTRY_PATH = HOME / ".claude" / "skills" / "_projects.json"


def today_dir() -> Path:
    """Returns the cache dir for today, creating it if needed."""
    d = CACHE_ROOT / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    d.mkdir(parents=True, exist_ok=True)
    return d


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%H%M%S")


# ---------------------------------------------------------------------------
# Cache

@dataclass
class CacheConfig:
    namespace: str
    ttl_seconds: Optional[int] = 60 * 60 * 24  # 24h default; None = forever


def _cache_key(namespace: str, key: str) -> Path:
    """Returns the cache file path for a given namespace+key."""
    safe = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    d = HOME / ".claude" / ".cache" / "lead-recon" / "_kv" / namespace
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{safe}.json"


def cache_get(cfg: CacheConfig, key: str) -> Optional[Any]:
    p = _cache_key(cfg.namespace, key)
    if not p.exists():
        return None
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if cfg.ttl_seconds is not None:
        age = time.time() - payload.get("_ts", 0)
        if age > cfg.ttl_seconds:
            return None
    return payload.get("value")


def cache_set(cfg: CacheConfig, key: str, value: Any) -> None:
    p = _cache_key(cfg.namespace, key)
    p.write_text(
        json.dumps({"_ts": time.time(), "_key": key, "value": value}, ensure_ascii=False),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# NIF / razón social normalization

_NIF_RE = re.compile(r"^[A-HJNPQRSUVW]\d{7}[0-9A-J]$|^\d{8}[A-Z]$|^[XYZ]\d{7}[A-Z]$", re.IGNORECASE)


def is_valid_nif(s: str) -> bool:
    """Loose validation for Spanish NIF/CIF/NIE formats. Doesn't validate check digit."""
    if not s:
        return False
    return bool(_NIF_RE.match(s.strip().upper()))


def normalize_nif(s: str) -> str:
    return (s or "").strip().upper().replace("-", "").replace(" ", "")


def normalize_razon_social(s: str) -> str:
    """Lowercase, remove diacritics, collapse whitespace, drop legal-form noise."""
    if not s:
        return ""
    s = s.strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    # Drop common legal forms for fuzzy matching
    for noise in [", s.l.", " s.l.", " sl", ", s.a.", " s.a.", " sa", " s.l.u.", " slu",
                  " s.coop.", " sccl", " scoop", ", c.b.", " cb", ", s.c.", " sc"]:
        if s.endswith(noise):
            s = s[: -len(noise)]
    s = re.sub(r"\s+", " ", s).strip()
    return s


def levenshtein(a: str, b: str) -> int:
    """Iterative Levenshtein. Used for fuzzy razón social dedup."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr[j] = min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[-1]


# ---------------------------------------------------------------------------
# Operator state read/write

def read_operator_state() -> dict:
    if not OPERATOR_STATE_PATH.exists():
        return {}
    try:
        return json.loads(OPERATOR_STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def update_operator_state_section(section: str, value: Any) -> bool:
    """Merges `value` into top-level `section` of _operator-state.json. Idempotent."""
    state = read_operator_state()
    if not state:
        return False
    state[section] = value
    state["lastUpdated"] = now_iso()
    OPERATOR_STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return True


# ---------------------------------------------------------------------------
# Observations (Sinapsis)

def emit_observation(obs_type: str, payload: dict) -> None:
    """Appends a JSONL line to ~/.claude/observations.jsonl with the operator's schema."""
    obs = {
        "ts": now_iso(),
        "type": obs_type,
        "skill": "norteia-lead-recon",
        "session": os.environ.get("CLAUDE_SESSION_ID", "unknown"),
        "payload": payload,
    }
    OBSERVATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OBSERVATIONS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obs, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Project runner detection (Mapeador de Leads — autodetect)

def detect_project_runners() -> dict:
    """
    Detects whether a sister project (e.g. "Mapeador de Leads") has live
    runners we should delegate to instead of using the skill's mini-parsers.

    Resolution order (first match wins):
      1. env var LEAD_RECON_PROJECT_ROOT (explicit override).
      2. ~/lead-recon-project (XDG-friendly default).
      3. Common operator workspaces under ~/Desktop/<workspace>/<project>.

    Returns:
        {
            "borme_parser_url": str | None,    # apps/borme-parser HTTP endpoint
            "worker_py_url": str | None,       # apps/worker-py HTTP endpoint
            "postgres_url": str | None,        # for --ingest mode
            "project_root": str | None,
        }
    """
    candidates: list[Path] = []
    env_override = os.environ.get("LEAD_RECON_PROJECT_ROOT")
    if env_override:
        candidates.append(Path(env_override))
    # Portable defaults — auto-detect common workspace locations
    candidates.extend([
        HOME / "lead-recon-project",
        HOME / "Desktop" / "lead-recon-project",
        HOME / "OneDrive" / "Desktop" / "lead-recon-project",
    ])
    project_root = next((p for p in candidates if p.exists()), None)

    result = {
        "borme_parser_url": None,
        "worker_py_url": None,
        "postgres_url": None,
        "project_root": str(project_root) if project_root else None,
    }
    if not project_root:
        return result

    # Detect built apps via dist/ presence
    if (project_root / "apps" / "borme-parser" / "dist").exists():
        result["borme_parser_url"] = os.environ.get("BORME_PARSER_URL", "http://localhost:3030")
    if (project_root / "apps" / "worker-py").exists():
        result["worker_py_url"] = os.environ.get("WORKER_PY_URL", "http://localhost:8000")

    # Detect postgres URL from .env.local of apps/web
    env_local = project_root / "apps" / "web" / ".env.local"
    if env_local.exists():
        for line in env_local.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("DATABASE_URL=") or line.startswith("POSTGRES_URL="):
                result["postgres_url"] = line.split("=", 1)[1].strip().strip('"')
                break

    return result


# ---------------------------------------------------------------------------
# CNAE mapping helpers

def load_cnae_mapping() -> dict:
    p = SKILL_DIR / "mappings" / "cnae.json"
    return json.loads(p.read_text(encoding="utf-8"))


def resolve_sector(input_str: str) -> dict:
    """
    Given a free-text sector ("asesoría fiscal" or "6920"), returns:
        {"input": ..., "cnae": [...], "matched_via": "exact|alias|cnae|fuzzy|none", "label": "..."}
    """
    mapping = load_cnae_mapping()
    sectors = mapping.get("sectors", {})
    norm = (input_str or "").strip().lower()

    # 1) Direct CNAE code (4 digits)
    if re.fullmatch(r"\d{4}", norm):
        for label, data in sectors.items():
            if norm in data.get("cnae", []) or norm in data.get("alsoCheck", []):
                return {"input": input_str, "cnae": [norm], "matched_via": "cnae", "label": label}
        return {"input": input_str, "cnae": [norm], "matched_via": "cnae", "label": None}

    # 2) Exact label match
    if norm in sectors:
        data = sectors[norm]
        return {
            "input": input_str,
            "cnae": data["cnae"] + data.get("alsoCheck", []),
            "matched_via": "exact",
            "label": norm,
        }

    # 3) Alias match
    for label, data in sectors.items():
        if norm in [a.lower() for a in data.get("aliases", [])]:
            return {
                "input": input_str,
                "cnae": data["cnae"] + data.get("alsoCheck", []),
                "matched_via": "alias",
                "label": label,
            }

    # 4) Fuzzy: substring or Levenshtein ≤ 3 against labels and aliases
    norm_clean = normalize_razon_social(norm)
    best = None
    best_dist = 4
    for label, data in sectors.items():
        candidates = [label] + data.get("aliases", [])
        for c in candidates:
            cn = normalize_razon_social(c)
            if not cn:
                continue
            d = levenshtein(norm_clean, cn)
            if d < best_dist:
                best_dist = d
                best = (label, data)
    if best:
        label, data = best
        return {
            "input": input_str,
            "cnae": data["cnae"] + data.get("alsoCheck", []),
            "matched_via": "fuzzy",
            "label": label,
        }

    return {"input": input_str, "cnae": [], "matched_via": "none", "label": None}


def province_code(name: str) -> Optional[str]:
    """Normalizes Spanish province name to INE 2-digit code. Returns None if not found."""
    mapping = load_cnae_mapping().get("_provinceCodes", {})
    norm = normalize_razon_social(name or "")
    for k, v in mapping.items():
        if k.startswith("_"):
            continue
        if normalize_razon_social(k) == norm:
            return v
    return None


# ---------------------------------------------------------------------------
# HTTP helper (no external deps, urllib only)

def http_get(url: str, headers: Optional[dict] = None, timeout: int = 15) -> tuple[int, str]:
    """
    Returns (status_code, body_text). Never raises on HTTP errors —
    callers decide what to do with the status code.
    """
    import urllib.request
    import urllib.error
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "norteia-lead-recon/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return e.code, body
    except urllib.error.URLError as e:
        return 0, str(e)
    except Exception as e:  # noqa: BLE001
        return -1, str(e)


# ---------------------------------------------------------------------------
# Output helpers

def write_snapshot(mode: str, payload: dict) -> Path:
    """Writes the JSON snapshot to ~/.claude/.cache/lead-recon/<today>/<mode>-<HHMMSS>.json"""
    out = today_dir() / f"{mode}-{now_compact()}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def write_html_twin(mode: str, html: str) -> Path:
    out = today_dir() / f"{mode}-{now_compact()}.html"
    out.write_text(html, encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# Source availability registry (set by sources + orchestrators at runtime)

class SourceStatus:
    """Per-source status tracker with typed reasons.

    A source NEVER fails silently. The orchestrator must be able to read this
    snapshot and tell the operator *why* a source contributed 0 results — caved
    network, hit zero in the search window, or wasn't executed at all because
    a precondition was missing. Conflating those three is the bug that produced
    leadReconStats.lastTotal:0 in v0.1.0 with no visible cause.

    Status vocabulary (the only allowed values):
      - "ok"            : responded with results
      - "empty_window"  : responded fine but the query window was empty
      - "network_error" : URLError, DNS failure, timeout
      - "http_error"    : HTTP status != 2xx
      - "parse_error"   : response received, couldn't be parsed
      - "not_executed"  : precondition missing (e.g. no Overpass tag, no bbox)
      - "down"          : adapter-internal failure that doesn't fit above
    """

    _ALLOWED = (
        "ok", "empty_window", "network_error", "http_error",
        "parse_error", "not_executed", "down",
    )

    _entries: dict[str, dict] = {}

    @classmethod
    def mark(
        cls,
        source: str,
        status: str,
        count: int = 0,
        reason: str = "",
        error: str = "",
    ) -> None:
        if status not in cls._ALLOWED:
            # Be strict — typos in status names defeat the whole point
            raise ValueError(
                f"SourceStatus.mark: invalid status {status!r} for {source!r}. "
                f"Allowed: {cls._ALLOWED}"
            )
        cls._entries[source] = {
            "status": status,
            "count": int(count),
            "reason": reason,
            "error": error,
        }

    @classmethod
    def reset(cls) -> None:
        cls._entries = {}

    @classmethod
    def snapshot(cls) -> dict[str, dict]:
        """Deep copy of the current per-source status map."""
        return {k: dict(v) for k, v in cls._entries.items()}


if __name__ == "__main__":
    # Self-test (ASCII-safe for Windows cp1252 console)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace") if hasattr(sys.stdout, "reconfigure") else None
    print("Skill dir:", SKILL_DIR)
    print("Cache root:", CACHE_ROOT)
    print("Today dir:", today_dir())
    print("NIF B12345678 valid?", is_valid_nif("B12345678"))
    print("Normalized 'Asesores Perez, S.L.':", normalize_razon_social("Asesores Perez, S.L."))
    print("Sector 'asesoria fiscal' ->", json.dumps(resolve_sector("asesoria fiscal"), ensure_ascii=True))
    print("Sector '6920' ->", json.dumps(resolve_sector("6920"), ensure_ascii=True))
    print("Province 'Sevilla' ->", province_code("Sevilla"))
    print("Project runners:", json.dumps(detect_project_runners(), ensure_ascii=True))
