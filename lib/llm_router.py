import json
import re
import torch
from typing import Dict, Optional
from transformers import AutoTokenizer, AutoModelForCausalLM
from huggingface_hub import login

from .validation_layer import get_validator, validate_and_ground_response

tokenizer = None
model = None

# Qwen2.5-3B-Instruct configuration
MODEL_NAME = "Qwen/Qwen2.5-3B-Instruct"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

import os
try:
    from dotenv import load_dotenv
    load_dotenv("config.env")
    try:
        hf_token = os.getenv("HF_TOKEN")
        if hf_token:
            login(hf_token)
    except:
        pass
except ImportError:
    pass


def load_model():
    """Load Qwen2.5-3B-Instruct model from Hugging Face."""
    global model, tokenizer
    if model is None or tokenizer is None:
        try:
            print(f"Loading {MODEL_NAME}...")
            tokenizer = AutoTokenizer.from_pretrained(
                MODEL_NAME,
                trust_remote_code=True,
                device_map=DEVICE
            )
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
            
            model = AutoModelForCausalLM.from_pretrained(
                MODEL_NAME,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map=DEVICE,
                trust_remote_code=True
            )
            model.eval()
            print(f"✓ Model loaded on {DEVICE}")
        except Exception as e:
            print(f"✗ Failed to load model: {e}")
            raise


def call_llm(prompt):
    if model is None or tokenizer is None:
        load_model()
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    outputs = model.generate(
        **inputs,
        max_new_tokens=100,
        num_beams=2,
        repetition_penalty=2.0,
        length_penalty=1.0,
        early_stopping=True,
        do_sample=False
    )
    return tokenizer.decode(outputs[0], skip_special_tokens=True)


# ─────────────────────────────────────────────
# JSON EXTRACTION
# ─────────────────────────────────────────────

def _extract_json(text: str) -> Dict:
    if not text:
        raise ValueError("Empty response from LLM")

    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    depth = 0
    start_pos = -1
    in_string = False
    escape_next = False

    for i, char in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if char == '\\':
            escape_next = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == '{':
            if depth == 0:
                start_pos = i
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0 and start_pos >= 0:
                json_str = text[start_pos:i+1]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    start_pos = -1

    raise ValueError(f"No valid JSON found in LLM output: {text[:200]}")


# ─────────────────────────────────────────────
# VALIDATION — now receives user_query
# ─────────────────────────────────────────────

_PHASES = ["taxi", "takeoff", "climb", "cruise", "descent", "approach", "landing"]
_DURATION_KEYWORDS = ["duration", "how long", "long is", "long was", "time spent", "time", "when"]
_METRIC_KEYWORDS = ["ias", "altitude", "alt", "ground speed", "gndspd",
                    "vertical speed", "vspd", "pitch"]
_PHASE_OVERVIEW_KEYWORDS = ["overview", "summary", "details", "info", "about",
                            "tell me", "tell", "describe", "explain"]


def _is_valid_llm_result(result: Dict, user_query: str = "") -> bool:
    """
    Validate LLM result AND cross-check it makes sense for the query.
    """
    if not isinstance(result, dict):
        return False

    intent = result.get("intent")

    if intent in (None, "", "unsupported"):
        return False

    q = user_query.lower()

    # ── Cross-check list_phases against query content ──────────────
    # If LLM says list_phases but query has a specific phase + duration/metric/overview
    # keyword, it clearly misrouted — reject it
    if intent == "list_phases":
        has_specific_phase = any(p in q for p in _PHASES)
        has_duration = any(w in q for w in _DURATION_KEYWORDS)
        has_metric = any(m in q for m in _METRIC_KEYWORDS)
        has_phase_overview = any(w in q for w in _PHASE_OVERVIEW_KEYWORDS)

        if has_specific_phase and (has_duration or has_metric or has_phase_overview):
            return False
        # Otherwise list_phases is valid (e.g. "what are the phases?")
        return True

    # ── flight_overview is always valid ───────────────────────────
    if intent == "flight_overview":
        return True

    # ── phase_duration requires a phase in the query ──────────────
    if intent in ("phase_duration", "duration"):
        if not result.get("phase"):
            # Phase missing from result — check if query has one
            detected = next((p for p in _PHASES if p in q), None)
            if detected:
                # Fix it rather than reject
                result["phase"] = detected.upper()
                print(f"  [Validator] Injected missing phase: {detected.upper()}")
            # Even without phase it's a valid duration intent
        return True

    # ── metric requires both phase and metric ─────────────────────
    if intent in ("metric", "metric_query"):
        if not result.get("metric"):
            return False
        return True

    # ── phase_overview, subphase intents ─────────────────────────
    if intent in ("phase_overview", "subphase_detail",
                  "subphase_metric", "segment_query"):
        return True

    # Unknown intent — reject
    print(f"  [Validator] Unknown intent: {intent}")
    return False


# ─────────────────────────────────────────────
# SANITY OVERRIDE — catches confident misroutes
# ─────────────────────────────────────────────

def _sanity_override(result: Dict, user_query: str) -> Dict:
    """
    Override obviously wrong intents using high-confidence keyword rules.
    Only fires when the signal is unambiguous.
    """
    q = user_query.lower().strip()
    current_intent = result.get("intent")

    detected_phase = next((p for p in _PHASES if p in q), None)
    has_duration = any(w in q for w in _DURATION_KEYWORDS)
    has_metric = any(m in q for m in _METRIC_KEYWORDS)

    # Rule 1: duration keyword + specific phase → must be phase_duration
    if has_duration and detected_phase and current_intent != "phase_duration":
        return {
            **result,
            "intent": "phase_duration",
            "phase": detected_phase.upper()
        }

    # Rule 2: metric keyword + phase → must be metric
    if has_metric and detected_phase and current_intent not in ("metric", "metric_query"):
        # Only override if there's no ambiguity with duration
        if not has_duration:
            return {
                **result,
                "intent": "metric",
                "phase": detected_phase.upper()
            }

    # Rule 3: "list phases" type query but got a phase-specific intent
    list_signals = ["all phases", "list phases", "what phases",
                    "which phases", "how many phases"]
    if any(sig in q for sig in list_signals) and current_intent != "list_phases":
        return {**result, "intent": "list_phases", "phase": None}

    return result  # no override needed


# ─────────────────────────────────────────────
# MAIN ENTRY: parse_query
# ─────────────────────────────────────────────

def parse_query(user_query: str, data_info: dict) -> Dict:
    """
    Parse query: LLM first, rule-based fallback, sanity override last.
    
    Flow:
      1. Try LLM → validate result against query
      2. If invalid → rule-based parser
      3. Sanity override on final result
    """
    llm_result = None

    # Step 1: Try LLM
    try:
        llm_result = _llm_parse_only(user_query, data_info)
    except Exception as e:
        pass

    # Step 2: Validate LLM result against query
    if _is_valid_llm_result(llm_result, user_query):
        final = llm_result
    else:
        final = _local_rule_parser(user_query)

    # Step 3: Sanity override — catches confident misroutes from either parser
    final = _sanity_override(final, user_query)

    return final


# ─────────────────────────────────────────────
# LLM PARSING — clean, no internal fallback
# ─────────────────────────────────────────────

def _llm_parse_only(user_query: str, data_info: dict) -> Dict:
    """
    Call LLM and extract JSON. 
    Does NOT fall back to rule parser internally — 
    that's parse_query's job.
    Raises exception if LLM fails so parse_query can handle it cleanly.
    """
    prompt = f"""You are a strict JSON intent parser for a flight analytics system.

You MUST return ONLY valid JSON.
No markdown. No explanation. No extra text.

AVAILABLE PHASES:
TAXI, TAKEOFF, CLIMB, CRUISE, DESCENT, APPROACH, LANDING

METRICS:
IAS, AltMSL, GndSpd, VSpd, Pitch

AGGREGATIONS:
min, max, avg, start, end

If something is not present, return null.
If unsupported, set intent to "unsupported".

EXAMPLES:

User: What are the flight phases?
Output:
{{"intent": "list_phases", "phase": null, "subphase": null, "segment": null, "metric": null, "agg": null}}

User: taxi duration
Output:
{{"intent": "phase_duration", "phase": "TAXI", "subphase": null, "segment": null, "metric": null, "agg": null}}

User: duration of cruise
Output:
{{"intent": "phase_duration", "phase": "CRUISE", "subphase": null, "segment": null, "metric": null, "agg": null}}

User: how long is the climb phase
Output:
{{"intent": "phase_duration", "phase": "CLIMB", "subphase": null, "segment": null, "metric": null, "agg": null}}

User: cruise phase duration
Output:
{{"intent": "phase_duration", "phase": "CRUISE", "subphase": null, "segment": null, "metric": null, "agg": null}}

User: max ias during climb
Output:
{{"intent": "metric", "phase": "CLIMB", "subphase": null, "segment": null, "metric": "IAS", "agg": "max"}}

User: tell me about the cruise phase
Output:
{{"intent": "phase_overview", "phase": "CRUISE", "subphase": null, "segment": null, "metric": null, "agg": null}}

AVAILABLE DATA:
{json.dumps(data_info)}

USER QUERY:
{user_query}

Output:"""

    raw = call_llm(prompt)

    if not raw or not raw.strip():
        raise ValueError("LLM returned empty response")

    parsed = _extract_json(raw)

    if not isinstance(parsed, dict):
        raise ValueError(f"LLM returned non-dict: {parsed}")

    # Normalize null-like strings
    for k in ("phase", "metric", "agg", "subphase"):
        v = parsed.get(k)
        if isinstance(v, str) and v.strip().lower() in ("null", "none", ""):
            parsed[k] = None

    # Normalize phase to uppercase
    ph = parsed.get("phase")
    if isinstance(ph, str) and ph.strip():
        parsed["phase"] = ph.upper()

    # Normalize segment to int
    seg = parsed.get("segment")
    if isinstance(seg, str):
        parsed["segment"] = int(seg) if seg.strip().isdigit() else None

    return parsed


# ─────────────────────────────────────────────
# RULE-BASED PARSER — unchanged logic, better debug
# ─────────────────────────────────────────────

def _local_rule_parser(query: str) -> Dict:
    """Deterministic rule-based intent parser."""
    q = query.lower()

    intent = "unsupported"
    phase = None
    subphase = None
    segment = None
    metric = None
    agg = None

    phases = ["taxi", "takeoff", "climb", "cruise",
              "descent", "approach", "landing"]

    metrics_map = {
        "ias": "IAS",
        "altitude": "AltMSL",
        "alt": "AltMSL",
        "ground speed": "GndSpd",
        "gnd spd": "GndSpd",
        "gndspd": "GndSpd",
        "vertical speed": "VSpd",
        "vspd": "VSpd",
        "pitch": "Pitch",
    }

    agg_map = {
        "min": "min", "minimum": "min",
        "max": "max", "maximum": "max",
        "avg": "avg", "average": "avg", "mean": "avg",
        "start": "start", "beginning": "start",
        "end": "end",
    }

    # Priority 1: Metric queries
    has_metric = any(m in q for m in metrics_map.keys())

    if has_metric:
        intent = "metric"
        for k, v in metrics_map.items():
            if k in q:
                metric = v
                break
        for p in phases:
            if p in q:
                phase = p.upper()
                break
        for k, v in agg_map.items():
            if k in q:
                agg = v
                break
        if not agg:
            agg = "avg"

        return {
            "intent": intent, "phase": phase, "subphase": subphase,
            "segment": segment, "metric": metric, "agg": agg,
        }

    # Priority 2: List phases
    if (("phase" in q or "phases" in q) and
            any(x in q for x in ["all", "list", "what", "which",
                                  "how many", "in flight"])):
        intent = "list_phases"

    # Priority 3: Flight overview
    elif "flight summary" in q or "flight overview" in q:
        intent = "flight_overview"

    # Priority 4: Phase duration
    elif any(w in q for w in ["duration", "how long", "long is", "long was", "time spent", "time", "when"]):
        intent = "phase_duration"
        for p in phases:
            if p in q:
                phase = p.upper()
                break

    # Priority 5: Phase overview
    elif any(x in q for x in ["overview", "summary", "details", "info",
                                "tell me", "tell", "about", "describe", "explain"]):
        intent = "phase_overview"
        q_temp = q.replace("liftoff", "takeoff")
        for p in phases:
            if p in q_temp:
                phase = p.upper()
                break

    # Priority 6: Subphases and segments
    else:
        subphase_map = {
            "lift off": "lift off", "liftoff": "lift off",
            "lift-off": "lift off", "takeoff roll": "takeoff roll",
            "roll for takeoff": "takeoff roll", "landing roll": "landing roll",
            "flare": "flare", "touch down": "touchdown",
            "touchdown": "touchdown", "low ias": "low ias",
        }

        for k, v in subphase_map.items():
            if k in q:
                if any(x in q for x in ["overview", "summary", "details", "info"]):
                    intent = "subphase_detail"
                    subphase = v
                elif any(x in q for x in ["min", "max", "average",
                                            "avg", "mean", "start", "end"]):
                    intent = "subphase_metric"
                    subphase = v
                else:
                    intent = ("subphase_metric" if any(m in q for m in metrics_map)
                              else "subphase_detail")
                    subphase = v
                break

        seg_match = re.search(
            r"\b(taxi|takeoff|climb|cruise|descent|approach|landing)"
            r"\s*-?\s*(\d+)\b", q
        )
        if not seg_match:
            seg_match = re.search(
                r"\b(taxi|takeoff|climb|cruise|descent|approach|landing)"
                r"(\d+)\b", q
            )
        if seg_match:
            phase = seg_match.group(1).upper()
            try:
                segment = int(seg_match.group(2))
            except Exception:
                segment = None
            intent = "segment_query"

    return {
        "intent": intent, "phase": phase, "subphase": subphase,
        "segment": segment, "metric": metric, "agg": agg,
    }


# Keep this for backward compatibility if anything imports it
def llm_parse_query(user_query: str, data_info: dict) -> Dict:
    """Backward-compatible wrapper — use parse_query instead."""
    return parse_query(user_query, data_info)

