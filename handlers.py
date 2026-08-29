"""Helpers per il formato dell'ordine."""
from __future__ import annotations

from typing import Any, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def build_order_message(
    *,
    user: dict[str, Any],
    service_mode: str,
    items: list[dict],
    location: Optional[str],
    meeting_place: Optional[str],
    meeting_time: Optional[str],
    notes: Optional[str],
) -> str:
    label = "🚚 Delivery" if service_mode == "delivery" else "🤝 Meet-Up"
    lines: list[str] = [
        "🔔 *Nuovo ordine ricevuto*",
        f"👤 *Cliente:* @{user.get('username') or user.get('first_name', 'Anon')}",
        f"📞 *Telegram ID:* `{user.get('id')}`",
        f"📦 *Modalità:* {label}",
        "",
        "*Articoli:*",
    ]
    for it in items:
        title = it.get("title", "?")
        qty = it.get("qty", 1)
        price = it.get("price_min", 0)
        lines.append(f"• {title} × {qty} — da €{price}")

    if service_mode == "delivery" and location:
        lines += ["", f"📍 *Indirizzo:* {location}"]
    if service_mode == "meetup":
        if meeting_place:
            lines += ["", f"📍 *Luogo meet-up:* {meeting_place}"]
        if meeting_time:
            lines += [f"⏰ *Quando:* {meeting_time}"]

    if notes:
        lines += ["", f"📝 *Note:* {notes}"]
    return "\n".join(lines)


def build_owner_keyboard(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Accetta", callback_data=f"accept:{order_id}"),
                InlineKeyboardButton("❌ Rifiuta", callback_data=f"reject:{order_id}"),
            ],
            [
                InlineKeyboardButton(
                    "📤 Inoltra al dropship", callback_data=f"forward:{order_id}"
                )
            ],
        ]
    )
