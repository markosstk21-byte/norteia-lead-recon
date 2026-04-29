"""
analyze.py — orquestador del modo --analyze.

Recibe NIF o razón social. Cruza BORME (timeline) + Cartociudad + PLACSP +
Infosubvenciones + AEPD + scraping web. Si --premium, marca slot para
Registradores (no implementado en este MVP — placeholder explícito).
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (
    SourceStatus, emit_observation, is_valid_nif, normalize_nif,
    now_iso, today_dir, write_html_twin, write_snapshot,
)

import aepd
import borme
import cartociudad
import domain_resolver
import infosubvenciones
import placsp


def analyze(input_str: str, premium: bool = False) -> dict:
    """Main analyze pipeline."""
    nif: Optional[str] = None
    razon_social: Optional[str] = None
    if is_valid_nif(input_str):
        nif = normalize_nif(input_str)
    else:
        razon_social = input_str.strip()

    payload: dict[str, Any] = {
        "schemaVersion": "1.0.0",
        "skill": "norteia-lead-recon",
        "mode": "analyze",
        "premium": premium,
        "timestamp": now_iso(),
        "input": {"raw": input_str, "nif": nif, "razon_social": razon_social},
        "company": {},
        "registralTimeline": [],
        "address": None,
        "publicSector": {"contracts": [], "subsidies": []},
        "compliance": {},
        "web": {},
        "premiumData": None,
        "sourcesAvailability": {},
        "writes": {},
        "warnings": [],
    }

    if not nif:
        payload["warnings"].append(
            "Entrada es razón social (no NIF). El timeline BORME requiere NIF — "
            "se devuelve análisis parcial. Para completarlo, ejecuta primero --discover "
            "filtrando por la razón social y obtén el NIF correcto."
        )

    # --- Parallel: BORME timeline + PLACSP contracts + subvenciones + AEPD ---
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures: dict = {}
        if nif:
            futures[pool.submit(borme.analyze_by_nif, nif)] = "BORME"
            futures[pool.submit(placsp.by_nif, nif, 5)] = "PLACSP"
            futures[pool.submit(infosubvenciones.by_nif, nif)] = "Infosubvenciones"
            futures[pool.submit(aepd.lookup_dpo, nif, None)] = "AEPD"
        elif razon_social:
            futures[pool.submit(aepd.lookup_dpo, None, razon_social)] = "AEPD"

        for fut in as_completed(futures):
            src = futures[fut]
            try:
                result = fut.result()
            except Exception as e:  # noqa: BLE001
                emit_observation("source_unavailable", {"source": src, "error": str(e)})
                continue
            if src == "BORME":
                payload["registralTimeline"] = result.get("timeline", [])
                if result.get("note"):
                    payload["warnings"].append(f"BORME: {result['note']}")
            elif src == "PLACSP":
                payload["publicSector"]["contracts"] = result or []
            elif src == "Infosubvenciones":
                payload["publicSector"]["subsidies"] = result or []
            elif src == "AEPD":
                payload["compliance"] = {
                    "dpoRegistered": result.get("registered", False),
                    "method": result.get("method"),
                    "signal": "alta-madurez-compliance" if result.get("registered") else "no-dpo-detected",
                }

    # --- Domain resolution + web scraping (sequential — depends on razón social) ---
    if razon_social:
        domain_info = domain_resolver.resolve(razon_social)
        payload["web"] = {
            "domain": domain_info.get("resolved"),
            "resolved_via": domain_info.get("via"),
            "confidence": domain_info.get("confidence"),
            "candidates": domain_info.get("candidates", [])[:5],
        }

    # --- Premium slot ---
    if premium:
        payload["premiumData"] = {
            "source": "Registradores.org",
            "implemented": False,
            "note": (
                "Modo --premium reservado para integración con registradores.org. "
                "Coste estimado: nota simple ~€10, cuentas anuales ~€10. "
                "Implementación pendiente (sesión #3b) — requiere flow de pago + scraping autenticado."
            ),
            "estimatedCost": {"min": 10, "max": 30, "currency": "EUR"},
        }

    payload["sourcesAvailability"] = SourceStatus.snapshot()

    # --- Recommendation heuristic ---
    qualified = []
    reason_parts = []
    if payload["compliance"].get("dpoRegistered"):
        qualified.append("formacion-eu-ai-act")
        reason_parts.append("DPO registrado")
    if payload["publicSector"]["subsidies"]:
        qualified.append("lidera-ia")
        reason_parts.append("ha recibido subvenciones (capacidad de inversión)")
    if payload["publicSector"]["contracts"]:
        qualified.append("auditoria-ia")
        reason_parts.append("contrata con sector público (compliance-sensitive)")
    payload["recommendation"] = {
        "qualifiedFor": qualified,
        "reason": "; ".join(reason_parts) if reason_parts else "Datos insuficientes — completar con lead-research-brief",
    }

    # --- Persist ---
    snapshot_path = write_snapshot("analyze", payload)
    html_path = _render_html_twin(payload)
    payload["writes"] = {
        "snapshot": str(snapshot_path),
        "htmlTwin": str(html_path) if html_path else None,
    }

    emit_observation("tool_lead_recon", {
        "phase": "analyze.complete",
        "nif": nif,
        "premium": premium,
        "qualifiedFor": qualified,
    })
    return payload


def _render_html_twin(payload: dict) -> Optional[Path]:
    template_path = Path(__file__).resolve().parent.parent / "templates" / "analyze.html.jinja"
    if not template_path.exists():
        return None
    template = template_path.read_text(encoding="utf-8")
    rendered = template.replace("{{PAYLOAD_JSON}}", json.dumps(payload, ensure_ascii=False))
    title = payload["input"]["razon_social"] or payload["input"]["nif"] or "Análisis"
    rendered = rendered.replace("{{TITLE}}", f"Analyze: {title}")
    return write_html_twin("analyze", rendered)


def main() -> None:
    p = argparse.ArgumentParser(description="norteia-lead-recon — analyze orchestrator")
    p.add_argument("--input", required=True, help="NIF/CIF o razón social")
    p.add_argument("--premium", action="store_true", help="Incluye Registro Mercantil (€10-30, requiere confirmación humana)")
    args = p.parse_args()

    if args.premium:
        print("WARN: --premium activado. Coste estimado €10-30 por consulta a registradores.org.")
        print("WARN: La integración con registradores.org NO está implementada en este MVP.")

    payload = analyze(args.input, args.premium)
    print(json.dumps({
        "input": payload["input"],
        "registralTimelineCount": len(payload["registralTimeline"]),
        "contractsCount": len(payload["publicSector"]["contracts"]),
        "subsidiesCount": len(payload["publicSector"]["subsidies"]),
        "compliance": payload["compliance"],
        "web": payload["web"],
        "recommendation": payload["recommendation"],
        "warnings": payload["warnings"],
        "writes": payload["writes"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
