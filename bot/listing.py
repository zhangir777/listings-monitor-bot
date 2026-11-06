"""Shared types for all site adapters."""

from dataclasses import dataclass


class FetchError(Exception):
    pass


@dataclass(frozen=True)
class Listing:
    id: str
    title: str
    price: int | None
    address: str
    url: str
    currency: str = "₸"
