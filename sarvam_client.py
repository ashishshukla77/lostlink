import json
import os
from pathlib import Path


def load_api_key():
    key = os.environ.get("SARVAM_API_KEY", "").strip()
    if key:
        return key
    try:
        import streamlit as st
        key = str(st.secrets.get("SARVAM_API_KEY", "")).strip()
        if key:
            return key
    except Exception:
        pass
    env_file = Path(__file__).with_name(".env")
    if not env_file.exists():
        return ""
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        if line.strip().startswith("SARVAM_API_KEY="):
            return line.split("=", 1)[1].strip().strip("\"'")
    return ""


def analyze_candidates(matches):
    """Return validated Sarvam analyses; return None when no key or request fails."""
    key = load_api_key()
    if not key:
        return None

    public_pairs = []
    for match in matches:
        public_pairs.append({
            "pair_id": match["pair_id"],
            "lost": {k: match["lost"].get(k, "") for k in ("name", "description", "category", "color", "location", "reported_at")},
            "found": {k: match["found"].get(k, "") for k in ("name", "description", "category", "color", "location", "reported_at")},
            "deterministic_signals": match["signals"],
            "known_conflicts": match["conflicts"],
        })

    schema = {
        "type": "object",
        "properties": {
            "matches": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "pair_id": {"type": "string"},
                        "match_likelihood": {"type": "integer", "minimum": 0, "maximum": 100},
                        "explanation": {"type": "string"},
                        "supporting_details": {"type": "array", "items": {"type": "string"}},
                        "uncertain_details": {"type": "array", "items": {"type": "string"}},
                        "verification_prompts": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["pair_id", "match_likelihood", "explanation", "supporting_details", "uncertain_details", "verification_prompts"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["matches"],
        "additionalProperties": False,
    }
    prompt = (
        "Assess possible lost-and-found matches. These are suggestions only, never declare an item verified. "
        "Use only the public fields provided. Do not infer or reveal private identifying details. "
        "Respect known conflicts; a colour or category contradiction should lower likelihood. "
        "Suggest safe, generic verification prompts that do not disclose an answer. "
        "Return one entry for each pair_id in the required JSON schema.\n\n"
        + json.dumps(public_pairs, ensure_ascii=False)
    )

    try:
        from sarvamai import SarvamAI

        client = SarvamAI(api_subscription_key=key)
        response = client.chat.completions(
            model="sarvam-105b",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_schema", "json_schema": {"name": "lostlink_matches", "strict": True, "schema": schema}},
            temperature=0.1,
        )
        parsed = json.loads(response.choices[0].message.content)
        allowed_ids = {item["pair_id"] for item in matches}
        validated = {}
        for item in parsed.get("matches", []):
            if not isinstance(item, dict) or item.get("pair_id") not in allowed_ids:
                continue
            likelihood = item.get("match_likelihood")
            explanation = item.get("explanation")
            if not isinstance(likelihood, int) or not 0 <= likelihood <= 100 or not isinstance(explanation, str):
                continue

            def clean_list(value, limit=3):
                if not isinstance(value, list):
                    return []
                return [entry.strip()[:180] for entry in value if isinstance(entry, str) and entry.strip()][:limit]

            validated[item["pair_id"]] = {
                "match_likelihood": likelihood,
                "explanation": explanation.strip()[:500],
                "supporting_details": clean_list(item.get("supporting_details")),
                "uncertain_details": clean_list(item.get("uncertain_details")),
                "verification_prompts": clean_list(item.get("verification_prompts")),
            }
        return validated
    except Exception:
        # Keep the demo usable without surfacing provider details or secrets.
        return None
