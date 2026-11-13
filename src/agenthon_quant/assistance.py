"""Mock-only assistance boundary. No HTTP client or generated code executor.

Reservations remain charged at their upper bound even when a request fails.
A live adapter requires provider-specific token/cost bounds and cancellation;
this mock interface is not evidence that real model behavior has been tested.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from decimal import Decimal


class BudgetExceeded(ValueError):
    pass


@dataclass(frozen=True)
class Limits:
    calls: int = 0
    tokens: int = 0
    dollars: Decimal = Decimal("0")
    seconds: float = 0

    def __post_init__(self):
        if any(type(v) is not int or v < 0 for v in (self.calls, self.tokens)):
            raise ValueError("Call and token limits must be nonnegative integers")
        if not isinstance(self.dollars, Decimal) or not self.dollars.is_finite() or self.dollars < 0:
            raise ValueError("Dollar limit must be a nonnegative finite Decimal")
        if isinstance(self.seconds, bool) or not math.isfinite(self.seconds) or self.seconds < 0:
            raise ValueError("Deadline seconds must be finite and nonnegative")


class Budget:
    def __init__(self, limits: Limits = Limits(), *, clock=time.monotonic):
        self.limits, self.clock = limits, clock
        self.deadline = clock() + limits.seconds
        self.calls = self.tokens = 0
        self.dollars = Decimal("0")

    def reserve(self, *, input_tokens: int, max_output_tokens: int,
                input_dollars_per_token: Decimal, output_dollars_per_token: Decimal):
        if any(type(v) is not int or v < 0 for v in (input_tokens, max_output_tokens)):
            raise ValueError("Token bounds must be nonnegative integers")
        for price in (input_dollars_per_token, output_dollars_per_token):
            if not isinstance(price, Decimal) or not price.is_finite() or price < 0:
                raise ValueError("Token prices must be nonnegative finite Decimals")
        tokens = input_tokens + max_output_tokens
        dollars = input_tokens * input_dollars_per_token + max_output_tokens * output_dollars_per_token
        if self.clock() >= self.deadline:
            raise BudgetExceeded("Deadline reached before dispatch")
        if self.calls + 1 > self.limits.calls or self.tokens + tokens > self.limits.tokens or self.dollars + dollars > self.limits.dollars:
            raise BudgetExceeded("Request upper bound exceeds the remaining allocation")
        self.calls += 1
        self.tokens += tokens
        self.dollars += dollars
        return {"reserved_calls": self.calls, "reserved_tokens": self.tokens,
                "reserved_cost_usd": str(self.dollars)}


class MockAssistant:
    """Canned responses for adapter tests; never used to calculate or verify."""
    def __init__(self, budget: Budget, responses: list[str]):
        self.budget, self.responses = budget, iter(responses)

    def explain(self, text: str, *, max_output_tokens: int = 128) -> dict:
        if not isinstance(text, str):
            raise ValueError("Mock input must be text")
        # Mock defines one token as one UTF-8 byte; not a production tokenizer.
        accounting = self.budget.reserve(input_tokens=len(text.encode()), max_output_tokens=max_output_tokens,
                                         input_dollars_per_token=Decimal("0"), output_dollars_per_token=Decimal("0"))
        response = next(self.responses)
        if len(response.encode()) > max_output_tokens:
            raise ValueError("Mock response exceeds its reserved output bound")
        if self.budget.clock() >= self.budget.deadline:
            raise BudgetExceeded("Deadline reached; response is not accepted")
        return {"text": response, "mode": "mock", "accounting": accounting}
