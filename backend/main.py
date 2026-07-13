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
    intent_json = infer_intent(payload.query)
    result = execute_query(intent_json, engine)
    return {
        "success": not (isinstance(result, dict) and result.get("error")),
        "intent": intent_json["intent"],
        "parameters": {k: v for k, v in intent_json.items() if k != "intent" and v is not None},
        "result": result,
        "reply": format_engine_response(result),
        "validation_passed": not (isinstance(result, dict) and result.get("error")),
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
                "result": result,
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


def format_engine_response(result: Any) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        if result.get("error"):
            return str(result["error"])
        if result.get("phase") and result.get("total_duration_formatted"):
            return (
                f"{result['phase']} lasted {result['total_duration_formatted']} "
                f"across {result.get('total_segments', 0)} segment(s)."
            )
        if result.get("phase") and result.get("metrics"):
            return f"{result['phase']} overview: {result.get('duration_formatted', 'duration unavailable')}."
        if result.get("summary"):
            return str(result["summary"])
        return str(result)
    return str(result)
