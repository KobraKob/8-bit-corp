import json
import re
from typing import Any, Dict


def extract_and_repair_json(raw_text: str) -> Dict[str, Any]:
    """Defensively extracts and parses JSON from raw LLM output, stripping fences and trailing fluff."""
    text = raw_text.strip()

    # 1. Strip markdown code fences if present (```json ... ``` or ``` ...)
    fence_pattern = r"^```(?:json)?\s*([\s\S]*?)\s*```$"
    match = re.search(fence_pattern, text, re.IGNORECASE)
    if match:
        text = match.group(1).strip()

    # 2. Try direct json.loads
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 3. Locate the first '{' and last '}'
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidate = text[first_brace : last_brace + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            # 4. Remove trailing commas before closing braces/brackets
            candidate = re.sub(r",\s*([\]}])", r"\1", candidate)
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

    raise ValueError(f"Unable to parse valid JSON from text: {raw_text[:200]}")
