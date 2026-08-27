import os

import fastapi
from fastapi import HTTPException
from pydantic import BaseModel
from typing import List

from challenge.model import DelayModel

app = fastapi.FastAPI()
model = DelayModel()

# Load pre-trained model or train from data automatically
if os.path.exists(DelayModel._MODEL_PATH):
    model._load()
else:
    _data_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "data", "data.csv"
    )
    if os.path.exists(_data_path):
        model.train_from_csv(_data_path)


class FlightInput(BaseModel):
    OPERA: str
    TIPOVUELO: str
    MES: int


class PredictInput(BaseModel):
    flights: List[FlightInput]


@app.get("/health", status_code=200)
async def get_health() -> dict:
    return {
        "status": "OK"
    }


@app.post("/predict", status_code=200)
async def post_predict(data: PredictInput) -> dict:
    for flight in data.flights:
        if flight.MES < 1 or flight.MES > 12:
            raise HTTPException(status_code=400, detail="Invalid MES value")
        if flight.TIPOVUELO not in ("I", "N"):
            raise HTTPException(status_code=400, detail="Invalid TIPOVUELO value")

    flights_list = [f.dict() for f in data.flights]
    features = model.preprocess_api(flights_list)
    predictions = model.predict(features)
    return {"predict": predictions}