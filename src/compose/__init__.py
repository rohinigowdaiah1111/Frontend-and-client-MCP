"""Compose package: fact pack, Groq final copy, delivery gate."""

from src.compose.delivery_gate import (
    DeliveryBlocked,
    check_delivery_gate,
    fill_doc_link,
    require_delivery_ready,
)
from src.compose.facts import extract_quotes, load_fact_pack, write_fact_pack
from src.compose.groq_writer import GroqWriteError, persist_final_copy, write_final_copy
from src.compose.render import iso_week_label, load_week_of, render_pattern

__all__ = [
    "DeliveryBlocked",
    "GroqWriteError",
    "check_delivery_gate",
    "extract_quotes",
    "fill_doc_link",
    "iso_week_label",
    "load_fact_pack",
    "load_week_of",
    "persist_final_copy",
    "render_pattern",
    "require_delivery_ready",
    "write_fact_pack",
    "write_final_copy",
]
