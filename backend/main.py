from fastapi import FastAPI, Request
import sys
import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(ROOT_DIR)

from lib.engine_executor import execute_query, engine

app = FastAPI()


@app.get("/")
def health():
    return {"status": "healthy"}


@app.post("/dialogflow/webhook")
async def dialogflow_webhook(request: Request):

    body = await request.json()

    print("==== DIALOGFLOW REQUEST ====")
    print(body)

    return {
        "fulfillment_response": {
            "messages": [
                {
                    "text": {
                        "text": [
                            "Webhook connected."
                        ]
                    }
                }
            ]
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