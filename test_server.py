# Use lifespan to run startup background thread (on_event startup is deprecated)
import threading
import time
import random
import os
from typing import Dict, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=_toggle_loop, daemon=True).start()
    yield


app = FastAPI(lifespan=lifespan)

# Interval (seconds) for toggling the sale_status. Can be overridden via env for faster tests.
TOGGLE_INTERVAL = float(os.environ.get("TEST_TOGGLE_INTERVAL", "5"))

_state_lock = threading.Lock()
_state: Dict[str, List[int]] = {"fixed_list": [1]}


def _toggle_loop() -> None:
    while True:
        time.sleep(TOGGLE_INTERVAL)
        with _state_lock:
            current = _state["fixed_list"]
            _state["fixed_list"] = [2] if current == [1] else [1]


# startup handled by lifespan


@app.get("/apiw/v2/uni-loan/earn/market/list")
def list_market(
    search_coin: str = "",
    page: int = 1,
    limit: int = 7,
    available: str = "false",
    have_balance: int = 2,
    have_award: int = 0,
    is_subscribed: int = 0,
    sort_business: int = 1,
    search_type: int = 0,
):
    # Simulate intermittent connection failures: 1 in 3 requests will return an error
    if random.randint(1, 3) == 1:
        raise HTTPException(status_code=502, detail="Simulated connection error")

    coin = (search_coin or "algo").lower()
    if coin != "algo":
        return {"code": 0, "message": "ok", "data": []}

    with _state_lock:
        fixed = _state["fixed_list"]

    item = {
        "id": 1,
        "asset": "ALGO",
        "name": "Algorand",
        "sort_apr": "2.50",
        "fixed_list": [{"sale_status": fixed[0]}],
        "fixable_list": [],
    }
    return {"code": 0, "message": "ok", "data": [item]}
