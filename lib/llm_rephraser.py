# llm_rephraser.py  (Option B version)

import re
from typing import Dict, Any, Optional
from .llm_router import call_llm   # your existing LLM caller


# ─────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────

def rephrase_answer(query: str, result: Dict[str, Any]) -> str:
    """
    Rephrase a structured result using LLM with strict fact injection.
    If hallucination is detected, use LLM with corrected values to generate better answer.
    """

    if not isinstance(result, dict):
        return "I received an unexpected response format."

    if "error" in result:
        return f"I couldn't answer that: {result['error']}"

    # Step 1: Build the ground-truth factual sentence
    # This is what MUST appear in the final answer
    factual_answer = _build_factual_answer(result)

    if not factual_answer:
        return "I found data but couldn't format a response."

    # Step 2: Build a very constrained prompt
    prompt = _build_constrained_prompt(query, factual_answer, result)

    # Step 3: Call LLM
    try:
        raw_output = call_llm(prompt)
        rephrased = _extract_rephrased(raw_output, prompt)
    except Exception:
        return factual_answer   # safe fallback

    # Step 4: Validate — did the LLM keep the real numbers?
    if not _contains_key_values(rephrased, result):
        # Use LLM with corrected values to generate better answer
        corrected_prompt = _build_hallucination_correction_prompt(query, factual_answer, result, rephrased)
        try:
            corrected_output = call_llm(corrected_prompt)
            corrected_answer = _extract_rephrased(corrected_output, corrected_prompt)
            
            # Validate the corrected answer
            if _contains_key_values(corrected_answer, result):
                return corrected_answer
            else:
                return factual_answer
        except Exception:
            return factual_answer

    return rephrased


# ─────────────────────────────────────────────
# LAYER 2: BUILD THE LOCKED FACTUAL ANSWER
# ─────────────────────────────────────────────

def _build_factual_answer(result: Dict) -> str:
    """
    Convert result dict into a plain factual sentence.
    This sentence contains all the real numbers — the LLM
    must preserve these exactly.
    
    This is the most important function in Option B.
    """

    intent = result.get("intent") or _infer_intent(result)
    phase = _phase_name(result.get("phase", ""))

    # ── Duration ──────────────────────────────────────
    if intent == "phase_duration":
        duration_sec = result.get("total_duration_seconds") or result.get("duration_seconds", 0) 
        segments = result.get("total_segments") or result.get("segment_count", 1)
        time_str = _format_time(duration_sec)

        fact = f"The {phase} phase duration is {time_str}"
        if isinstance(segments, int) and segments > 1:
            fact += f" across {segments} segments"
        return fact + "."

    # ── Single metric ──────────────────────────────────
    elif intent in ("metric", "metric_query"):
        metric = result.get("metric", "value")
        agg = result.get("agg", "value")
        value = result.get("value")
        unit = result.get("unit", "")

        if value is None:
            return f"No {metric} data found for {phase} phase."

        agg_words = {
            "max": "maximum", "min": "minimum",
            "avg": "average", "start": "starting", "end": "ending"
        }
        agg_label = agg_words.get(agg, agg)
        unit_str = f" {unit}" if unit else ""

        return (
            f"The {agg_label} {metric} in the {phase} phase "
            f"is {_format_value(value)}{unit_str}."
        )

    # ── List phases ────────────────────────────────────
    elif intent == "list_phases":
        phases = result.get("phases", [])
        names = [_phase_name(p) for p in phases]
        return f"The flight has {len(phases)} phases: {', '.join(names)}."

    # ── Phase overview ─────────────────────────────────
    elif intent == "phase_overview":
        # Use detailed narrative summary if available
        if "detailed_summary" in result:
            return result["detailed_summary"]
        
        # Fallback to old format
        duration_sec = result.get("duration_seconds", 0)
        time_str = _format_time(duration_sec)
        segments = result.get("segment_count", 1)

        facts = [f"The {phase} phase lasted {time_str}"]

        if isinstance(segments, int) and segments > 1:
            facts.append(f"it covered {segments} segments")

        metric_keys = {
            "avg_IAS":    ("average IAS",      result.get("unit_IAS",    "knots")),
            "max_IAS":    ("peak IAS",          result.get("unit_IAS",    "knots")),
            "avg_AltMSL": ("average altitude",  result.get("unit_Alt",    "ft")),
            "max_AltMSL": ("peak altitude",     result.get("unit_Alt",    "ft")),
            "avg_VSpd":   ("average vspd",      result.get("unit_VSpd",   "fpm")),
        }
        for key, (label, unit) in metric_keys.items():
            val = result.get(key)
            if val is not None:
                facts.append(f"{label} was {_format_value(val)} {unit}")

        return ". ".join(facts) + "."

    # ── Flight overview ────────────────────────────────
    elif intent == "flight_overview":
        parts = []
        
        # Duration + phases
        total = result.get("total_duration_seconds", 0)
        time_str = _format_time(total)
        
        # Number of phases
        phase_breakdown = result.get("phase_breakdown", [])
        unique_phases = set()
        if phase_breakdown:
            for seg in phase_breakdown:
                if isinstance(seg, dict) and "phase" in seg:
                    unique_phases.add(seg["phase"])
        
        if unique_phases:
            duration_part = f"This flight lasted {time_str} across {len(unique_phases)} distinct phases"
        else:
            duration_part = f"This flight lasted {time_str}"
        parts.append(duration_part)
        
        # Altitude statistics
        altitude_info = result.get("altitude", {})
        alt_min = altitude_info.get("min")
        alt_max = altitude_info.get("max")
        alt_avg = altitude_info.get("avg")
        
        if alt_min is not None and alt_max is not None:
            alt_str = f"Altitudes ranged from {int(round(alt_min))} to {int(round(alt_max))} feet"
            if alt_avg is not None:
                alt_str += f" (averaging {int(round(alt_avg))} feet)"
            parts.append(alt_str)
        
        # Speed (IAS) statistics
        ias_info = result.get("ias", {})
        ias_min = ias_info.get("min")
        ias_max = ias_info.get("max")
        ias_avg = ias_info.get("avg")
        
        if ias_min is not None and ias_max is not None:
            # Format minimum speed
            if ias_min < 1:
                ias_min_str = "a near standstill"
            else:
                ias_min_str = f"{_format_value(ias_min)} knots"
            
            # Format maximum speed
            ias_max_str = f"{_format_value(ias_max)} knots"
            
            speed_str = f"Airspeed ranged from {ias_min_str} to {ias_max_str}"
            if ias_avg is not None and ias_avg > 0:
                speed_str += f" (averaging {_format_value(ias_avg)} knots)"
            parts.append(speed_str)
        
        # Ground speed if available
        gnd_info = result.get("gnd_speed", {})
        gnd_max = gnd_info.get("max")
        if gnd_max is not None and gnd_max > 0:
            parts.append(f"Ground speed peaked at {_format_value(gnd_max)} knots")
        
        # Vertical speed statistics if available
        vspd_info = result.get("vspd", {})
        vspd_max = vspd_info.get("max")
        if vspd_max is not None and vspd_max > 0:
            parts.append(f"Maximum climb rate reached {_format_value(vspd_max)} feet per minute")
        
        return ". ".join(parts) + "."

    return ""   # unknown intent → caller will handle


# ─────────────────────────────────────────────
# LAYER 3: BUILD THE CONSTRAINED PROMPT
# ─────────────────────────────────────────────

def _build_constrained_prompt(
    query: str,
    factual_answer: str,
    result: Dict
) -> str:
    """
    Build a prompt that leaves the LLM NO room to change numbers.
    
    Key techniques used here:
    1. Tell the model its ONLY job is word choice, not facts
    2. Give it the factual answer as a constraint, not a suggestion
    3. Ask for ONE sentence so it can't ramble
    4. Explicitly forbid adding information
    """

    intent = result.get("intent", "")

    # Tailor the instruction slightly by intent type
    if intent == "phase_duration":
        task = "Rewrite this as a friendly one-sentence answer about flight duration."
    elif intent in ("metric", "metric_query"):
        task = "Rewrite this as a friendly one-sentence answer about a flight metric."
    elif intent == "list_phases":
        task = "Rewrite this as a friendly one-sentence answer listing the phases."
    else:
        task = "Rewrite this as a friendly one-sentence answer."

    prompt = f"""You are a flight data assistant. {task}

RULES:
- Use ONLY the facts provided below. Do not add, change, or invent any numbers.
- Output exactly ONE sentence.
- Do not repeat the question.
- Do not add any explanation or extra information.

FACTS (do not change these values):
{factual_answer}

User asked: {query}

Your one-sentence answer:"""

    return prompt


def _build_hallucination_correction_prompt(
    query: str,
    factual_answer: str,
    result: Dict,
    incorrect_answer: str
) -> str:
    """
    Build a prompt that tells the LLM it made an error and provides correct values.
    This is used when the LLM hallucinates but we have the correct data.
    
    The prompt:
    1. Explains the error that was detected
    2. Provides the correct values explicitly
    3. Asks the LLM to generate a corrected response
    """
    
    intent = result.get("intent", "")
    
    # Build correction message explaining what went wrong
    correction_msg = f"""I asked you to answer: {query}

You responded: "{incorrect_answer}"

However, I detected an error in your response. The actual data shows:
{factual_answer}

Please provide a corrected one-sentence answer that includes the RIGHT VALUES."""
    
    prompt = f"""You are a flight data assistant. You made an error in your previous response, and I am providing the correct information.

CORRECTION REQUIRED:
{correction_msg}

RULES:
- Use ONLY the correct facts provided below. Do not change or round any numbers.
- Output exactly ONE sentence.
- Be friendly and natural.
- Do NOT mention that you made an error or that this is a correction.

CORRECT FACTS:
{factual_answer}

Your corrected one-sentence answer:"""
    
    return prompt


# ─────────────────────────────────────────────
# LAYER 4: VALIDATION
# ─────────────────────────────────────────────

def _contains_key_values(text: str, result: Dict) -> bool:
    if not text or not text.strip():
        return False

    must_contain = []

    # Check both key names
    duration_sec = (
        result.get("total_duration_seconds") or
        result.get("duration_seconds") or
        result.get("duration")
    )
    if duration_sec is not None:
        minutes = int(float(duration_sec) // 60)
        must_contain.append(str(minutes))   # "29" must appear in output

    value = result.get("value")
    if value is not None:
        must_contain.append(_format_value(value))

    phases = result.get("phases")
    if phases:
        must_contain.append(str(len(phases)))

    # Check total_segments too
    segments = result.get("total_segments") or result.get("segment_count")
    if segments and isinstance(segments, int) and segments > 1:
        must_contain.append(str(segments))

    for val in must_contain:
        if val not in text:
            return False

    return True


def _extract_rephrased(raw_output: str, prompt: str) -> str:
    """
    Extract just the rephrased sentence from the LLM output.
    TinyLlama tends to echo the prompt back, so we strip it.
    """

    if not raw_output:
        return ""

    # Remove the prompt prefix if the model echoed it
    if prompt in raw_output:
        raw_output = raw_output.replace(prompt, "").strip()

    # Take only the first sentence
    sentences = re.split(r'(?<=[.!?])\s+', raw_output.strip())
    for sentence in sentences:
        sentence = sentence.strip()
        # Skip very short fragments or prompt artifacts
        if len(sentence) > 20 and not sentence.startswith("FACTS"):
            return sentence

    # If we can't find a clean sentence, return everything trimmed
    return raw_output.strip()


# ─────────────────────────────────────────────
# SHARED HELPERS
# ─────────────────────────────────────────────

def _phase_name(phase: str) -> str:
    if not phase:
        return "unknown"
    return phase.strip().capitalize()


def _format_time(seconds) -> str:
    try:
        seconds = int(float(seconds))
    except (TypeError, ValueError):
        return "an unknown duration"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    parts = []
    if hours:
        parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
    if minutes:
        parts.append(f"{minutes} minute{'s' if minutes > 1 else ''}")
    if secs or not parts:
        parts.append(f"{secs} second{'s' if secs != 1 else ''}")

    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return f"{parts[0]}, {parts[1]}, and {parts[2]}"


def _format_value(value) -> str:
    try:
        f = float(value)
        return str(int(f)) if f == int(f) else f"{f:.1f}"
    except (TypeError, ValueError):
        return str(value)


def _infer_intent(result: Dict) -> str:
    keys = set(result.keys())

    duration_keys = {
        "duration_seconds", "duration",
        "total_duration_seconds",    # ← add this
        "total_seconds", "duration_sec"
    }
    if duration_keys & keys and "phases" not in keys:
        return "phase_duration"

    if "phases" in keys or "phase_list" in keys:
        return "list_phases"

    if "value" in keys and ("metric" in keys or "agg" in keys):
        return "metric"

    overview_keys = {"avg_IAS", "avg_AltMSL", "avg_VSpd", "avg_Pitch"}
    if overview_keys & keys:
        return "phase_overview"

    if "total_duration_seconds" in keys and "phase_count" in keys:
        return "flight_overview"

    return "unknown"
