from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys
import os
from typing import Any

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(ROOT_DIR)

from lib.engine_executor import execute_query, engine

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    query: str


@app.get("/")
def health():
    return {"status": "healthy"}


@app.post("/query")
def query_engine(payload: QueryRequest):
    if not payload.query or not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query text must not be empty.")

    try:
        intent_json = infer_intent(payload.query)
        result = execute_query(intent_json, engine)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error processing query: {exc}") from exc

    had_error = isinstance(result, dict) and bool(result.get("error"))
    return {
        "success": not had_error,
        "intent": intent_json["intent"],
        "parameters": {k: v for k, v in intent_json.items() if k != "intent" and v is not None},
        "result": result,
        "reply": format_engine_response(result),
        "validation_passed": not had_error,
    }


@app.post("/dialogflow/webhook")
async def dialogflow_webhook(request: Request):
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc

    intent_json = extract_dialogflow_intent(body)
    result = execute_query(intent_json, engine)
    reply = format_engine_response(result)
    had_error = isinstance(result, dict) and bool(result.get("error"))

    # Keep session parameters small and flat - Dialogflow CX session parameters
    # are meant for lightweight state, not the full nested engine payload.
    return {
        "fulfillment_response": {
            "messages": [
                {
                    "text": {
                        "text": [reply]
                    }
                }
            ]
        },
        "sessionInfo": {
            "parameters": {
                "intent": intent_json.get("intent"),
                "phase": intent_json.get("phase"),
                "success": not had_error,
            }
        }
    }


@app.get("/test")
def test_engine():

    result = execute_query(
        {
            "intent": "phase_duration",
            "phase": "CRUISE"
        },
        engine
    )

    return result


def extract_dialogflow_intent(body: dict[str, Any]) -> dict[str, Any]:
    fulfillment = body.get("fulfillmentInfo") or {}
    intent_info = body.get("intentInfo") or {}
    session_info = body.get("sessionInfo") or {}
    parameters = session_info.get("parameters") or {}

    display_name = (
        fulfillment.get("tag")
        or intent_info.get("displayName")
        or intent_info.get("lastMatchedIntent")
        or ""
    )

    text = (
        body.get("text")
        or body.get("transcript")
        or body.get("queryResult", {}).get("queryText")
        or ""
    )

    intent_json = infer_intent(text, display_name)

    for key in ("phase", "metric", "agg", "segment"):
        if parameters.get(key) is not None:
            value = parameters[key]
            intent_json[key] = value.get("resolvedValue", value) if isinstance(value, dict) else value

    return intent_json


def infer_intent(query: str, display_name: str = "") -> dict[str, Any]:
    text = f"{display_name} {query}".lower()

    phases = {
        "taxi": "TAXI",
        "takeoff": "TAKEOFF",
        "climb": "CLIMB",
        "cruise": "CRUISE",
        "descent": "DESCENT",
        "approach": "APPROACH",
        "landing": "LANDING",
    }
    phase = next((value for key, value in phases.items() if key in text), None)

    if "safety" in text or "anomaly" in text or "abnormal" in text or "unsafe" in text:
        return {"intent": "safety_analysis", "phase": phase}
    if "trend" in text:
        return {"intent": "trend_analysis", "phase": phase}
    if "executive" in text:
        return {"intent": "executive_summary", "phase": phase}
    if "overview" in text or "summary" in text:
        return {"intent": "phase_overview" if phase else "flight_overview", "phase": phase}
    if "duration" in text or "how long" in text or "time" in text:
        return {"intent": "phase_duration", "phase": phase or "CRUISE"}

    metrics = {
        "altitude": "altitude",
        "height": "altitude",
        "ias": "ias",
        "airspeed": "ias",
        "speed": "ias",
        "ground": "gnd",
        "pitch": "pitch",
        "vertical": "vspd",
    }
    metric = next((value for key, value in metrics.items() if key in text), None)
    if metric:
        agg = "avg"
        if "max" in text or "highest" in text or "peak" in text:
            agg = "max"
        elif "min" in text or "lowest" in text:
            agg = "min"
        elif "start" in text:
            agg = "start"
        elif "end" in text:
            agg = "end"
        return {"intent": "metric", "phase": phase, "metric": metric, "agg": agg}

    return {"intent": "flight_overview", "phase": phase}


def _fmt_metric_block(name: str, block: dict) -> str:
    unit = block.get("unit", "")
    return (
        f"{name} ranged from {block.get('min'):.1f} to {block.get('max'):.1f} {unit} "
        f"(avg {block.get('avg'):.1f} {unit})"
    )


def format_engine_response(result: Any) -> str:
    """Convert any engine result into a concise, human-readable sentence or
    short paragraph suitable for a chat/Dialogflow reply. This function must
    NEVER return a raw dict/JSON repr - every known result shape is handled
    explicitly, and the fallback summarizes rather than dumping structures.
    """
    if isinstance(result, str):
        return result.strip()

    if not isinstance(result, dict):
        return str(result)

    if result.get("error"):
        return str(result["error"])

    if result.get("flight_start") and "phase_breakdown" in result:
        parts = [
            f"The flight ran {result.get('total_duration_formatted', 'an unknown duration')}, "
            f"from {result.get('flight_start')} to {result.get('flight_end')}."
        ]
        if result.get("altitude"):
            parts.append(_fmt_metric_block("Altitude", result["altitude"]) + ".")
        if result.get("ias"):
            parts.append(_fmt_metric_block("Airspeed", result["ias"]) + ".")
        if result.get("gnd_speed"):
            parts.append(_fmt_metric_block("Ground speed", result["gnd_speed"]) + ".")

        phase_breakdown = result.get("phase_breakdown") or []
        totals: dict[str, float] = {}
        order: list[str] = []
        for seg in phase_breakdown:
            phase = seg.get("phase") or "UNKNOWN"
            totals[phase] = totals.get(phase, 0.0) + (seg.get("duration_seconds") or 0)
            if phase not in order:
                order.append(phase)
        if totals:
            phase_bits = [f"{p} ({int(totals[p] // 60)}m {int(totals[p] % 60)}s)" for p in order]
            parts.append("Phase breakdown: " + ", ".join(phase_bits) + ".")
        return " ".join(parts)

    if result.get("phase") and result.get("total_duration_formatted") and "segments" in result:
        return (
            f"{result['phase']} lasted {result['total_duration_formatted']} "
            f"across {result.get('total_segments', 0)} segment(s)."
        )

    if result.get("phase") and "metrics" in result:
        parts = [
            f"{result['phase']} overview: {result.get('duration_formatted', 'duration unavailable')} "
            f"across {result.get('total_segments', 0)} segment(s)."
        ]
        metrics = result.get("metrics") or {}
        label_map = {
            "altitude": "Altitude",
            "ias": "Airspeed",
            "vspd": "Vertical speed",
            "pitch": "Pitch",
            "gnd_speed": "Ground speed",
        }
        for key, label in label_map.items():
            if key in metrics:
                parts.append(_fmt_metric_block(label, metrics[key]) + ".")
        if result.get("detailed_summary"):
            parts.append(str(result["detailed_summary"]).strip())
        return " ".join(parts)

    if "value" in result and result.get("metric"):
        unit = result.get("unit", "")
        value = result["value"]
        phase_txt = f" during {result['phase']}" if result.get("phase") else ""
        segment_txt = f" (segment {result['segment']})" if result.get("segment") else ""
        if result.get("position"):
            return (
                f"The {result['metric']} at the {result['position']} of "
                f"{result.get('phase', 'the flight')}{segment_txt} was {value:.1f} {unit}."
            )
        agg = result.get("aggregation", "avg")
        agg_word = {"avg": "average", "min": "minimum", "max": "maximum"}.get(agg, agg)
        return f"The {agg_word} {result['metric']}{phase_txt}{segment_txt} was {value:.1f} {unit}."

    if "phases" in result and "count" in result:
        return f"The flight includes {result['count']} phase(s): {', '.join(result['phases'])}."

    if result.get("summary"):
        parts = [str(result["summary"])]
        if result.get("issues"):
            issue_names = [i.get("check", "issue") for i in result["issues"] if isinstance(i, dict)]
            if issue_names:
                parts.append("Flagged checks: " + ", ".join(issue_names) + ".")
        if result.get("total_duration_formatted"):
            parts.append(f"Total duration: {result['total_duration_formatted']}.")
        return " ".join(parts)

    scalar_bits = []
    other_keys = []
    for key, value in result.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            label = key.replace("_", " ")
            scalar_bits.append(f"{label}: {value}")
        else:
            other_keys.append(key)
    sentence = "; ".join(scalar_bits) if scalar_bits else "Here is what I found"
    if other_keys:
        sentence += f" (additional detail available for: {', '.join(other_keys)})"
    return sentence + "."
