"""Pydantic schema for stream messages."""

from datetime import datetime
from math import isfinite

from pydantic import BaseModel, Field, field_validator, model_validator


class OHLCVBar(BaseModel):
    timestamp: datetime
    ticker: str = Field(min_length=1, max_length=16)
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)
    ingested_at: datetime | None = None
    source: str = Field(default="unknown", pattern="^(live|sample|local|unknown)$")

    @field_validator("ticker")
    @classmethod
    def ticker_upper(cls, value: str) -> str:
        ticker = value.strip().upper()
        if not ticker:
            raise ValueError("ticker cannot be empty")
        return ticker

    @model_validator(mode="after")
    def prices_are_valid(self):
        prices = (self.open, self.high, self.low, self.close)

        if not all(isfinite(price) for price in prices):
            raise ValueError("prices must be finite")

        if self.low > min(self.open, self.close):
            raise ValueError("low must be <= open and close")

        if self.high < max(self.open, self.close):
            raise ValueError("high must be >= open and close")

        if self.low > self.high:
            raise ValueError("low must be <= high")

        return self
