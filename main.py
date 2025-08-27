from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta

from db import SessionLocal
import models

app = FastAPI()

# ✅ Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # during local dev you can leave *
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic model for request body
class OddsCreate(BaseModel):
    sportsbook: str
    league: str
    event: str
    market: str
    outcome: str
    odds_decimal: float

@app.post("/odds/")
def add_odds(odds: OddsCreate, db: Session = Depends(get_db)):
    new_odds = models.Odds(
        sportsbook=odds.sportsbook,
        league=odds.league,
        event=odds.event,
        market=odds.market,
        outcome=odds.outcome,
        odds_decimal=odds.odds_decimal,
    )
    db.add(new_odds)
    db.commit()
    db.refresh(new_odds)
    return new_odds

@app.get("/odds/")
def get_odds(db: Session = Depends(get_db)):
    return db.query(models.Odds).all()

@app.get("/arbitrage/")
def get_arbitrage(db: Session = Depends(get_db)):
    """
    Find arbitrage opportunities by comparing odds across sportsbooks,
    but only for games that start at least 24h from now
    and only if the line matches (e.g. both are Over 2.5).
    """
    odds = db.query(models.Odds).all()
    opportunities = []

    # ✅ filter out live or soon games
    cutoff = datetime.utcnow() + timedelta(hours=24)
    odds = [o for o in odds if o.commence_time and o.commence_time > cutoff]

    # Group by event + market + line
    from collections import defaultdict
    grouped = defaultdict(list)
    for o in odds:
        key = (o.event, o.market, o.line)  # ✅ include line
        grouped[key].append(o)

    # Check for arbitrage
    for (event, market, line), group in grouped.items():
        outcomes = {}
        for o in group:
            if o.outcome not in outcomes or o.odds_decimal > outcomes[o.outcome].odds_decimal:
                outcomes[o.outcome] = o

        if len(outcomes) >= 2:
            inv_sum = sum(1 / o.odds_decimal for o in outcomes.values())
            if inv_sum < 1:
                profit_margin = (1 - inv_sum) * 100
                opportunities.append({
                    "event": event,
                    "market": market,
                    "line": line,  # ✅ now included in response
                    "profit_margin": round(profit_margin, 2),
                    "best_odds": [
                        {
                            "sportsbook": o.sportsbook,
                            "outcome": o.outcome,
                            "odds": o.odds_decimal,
                            "odds_american": o.odds_american,   # ✅ send American odds
                            "date": getattr(o, "event_date", None)  # ✅ send event date if stored
                        } for o in outcomes.values()
                    ],
                    "commence_time": o.commence_time.isoformat() if o.commence_time else None

                })

    return opportunities

