"""Backend FastAPI: webhook Telegram + endpoint /api/order per la mini app.

Avvio locale:
    uvicorn bot.main:app --host 0.0.0.0 --port 8080
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field
from telegram import (
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from .auth import verify_init_data
from .handlers import build_order_message, build_owner_keyboard

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("haze-bot")

BOT_TOKEN = os.environ["8838108627:AAFSyinh4PNPgRbR-r0euv69pqeUARrfgAs"]
WEBHOOK_SECRET = os.environ.get("01908107d7d4beb214eeb423f774a536850268ec4589999616cd3c398ad753ac", "")
WEBAPP_URL = os.environ["https://thunderous-lily-fc8fd7.netlify.app/"].rstrip("/")
OWNER_CHAT_ID = int(os.environ["5849051243"])

# ======================================================================
# Costruzione PTB Application (gestisce webhook + bot in un unico processo)
# ======================================================================
application = Application.builder().token(BOT_TOKEN).build()


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Risponde a /start con un messaggio che apre la mini app."""
    user = update.effective_user
    url = WEBAPP_URL or "https://thunderous-lily-fc8fd7.netlify.app/"
    await update.message.reply_text(
        f"Ciao {user.first_name}! 👋\n"
        "Tocca il bottone qui sotto per aprire il negozio HAZÉ.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton(text="🛒 Apri negozio HAZÉ", url=url)]]
        ),
    )


async def on_owner_decision(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Owner preme ✅ / ❌ sui bottoni inline."""
    query = update.callback_query
    await query.answer()
    decision, order_id = query.data.split(":", 1)
    if decision == "accept":
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"✅ Ordine #{order_id} accettato. Inoltro in corso…",
        )
    else:
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"❌ Ordine #{order_id} rifiutato. Il cliente non ha ancora "
            "ricevuto la notifica — modifica la spedizione e usa /forward "
            f"{order_id} per inoltrare manualmente se necessario.",
        )


application.add_handler(CommandHandler("start", cmd_start))
application.add_handler(CallbackQueryHandler(on_owner_decision, pattern=r"^(accept|reject):"))

# ======================================================================
# FastAPI
# ======================================================================
app = FastAPI(title="HAZÉ Smoke Club Bot")


class OrderPayload(BaseModel):
    init_data: str = Field(..., description="Telegram.WebApp.initData non firmato")
    service_mode: str = Field(..., pattern="^(delivery|meetup)$")
    items: list[dict]
    location: Optional[str] = None
    meeting_place: Optional[str] = None
    meeting_time: Optional[str] = None
    notes: Optional[str] = None


@app.on_event("startup")
async def _startup() -> None:
    await application.initialize()
    await application.start()
    log.info("Bot avviato (webhook).")


@app.on_event("shutdown")
async def _shutdown() -> None:
    await application.stop()
    await application.shutdown()


@app.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(default=None),
) -> dict:
    """Endpoint webhook Telegram (imposta con setWebhook)."""
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="bad secret token")

    payload = await request.json()
    update = Update.de_json(payload, application.bot)
    await application.process_update(update)
    return {"ok": True}


@app.post("/api/order")
async def api_order(payload: OrderPayload) -> dict:
    """
    1. Verifica firma initData con HMAC-SHA256 del BOT_TOKEN.
    2. Genera order_id.
    3. Invia riepilogo al proprietario (OWNER_CHAT_ID) con bottoni ✅/❌.
    4. Restituisce order_id al client mini app.
    """
    try:
        init = verify_init_data(payload.init_data, BOT_TOKEN)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    user_info = json.loads(init.get("user", "{}"))
    user_id = user_info.get("id")
    username = user_info.get("username") or user_info.get("first_name", "Anon")

    text = build_order_message(
        user=user_info,
        service_mode=payload.service_mode,
        items=payload.items,
        location=payload.location,
        meeting_place=payload.meeting_place,
        meeting_time=payload.meeting_time,
        notes=payload.notes,
    )
    # L'order_id è inserito nel testo dal builder.

    import uuid
    order_id = uuid.uuid4().hex[:8].upper()

    chat = await application.bot.send_message(
        chat_id=OWNER_CHAT_ID,
        text=text + f"\n\n🧾 Ordine: `{order_id}`\n👤 Cliente: @{username} (id {user_id})",
        parse_mode="Markdown",
        reply_markup=build_owner_keyboard(order_id),
    )

    # Conferma immediata al cliente via Telegram (se il bot conosce il chat_id)
    try:
        await application.bot.send_message(
            chat_id=user_id,
            text=(
                f"✅ Ordine `{order_id}` ricevuto!\n"
                f"Modalità: {'🚚 Delivery' if payload.service_mode == 'delivery' else '🤝 Meet-Up'}\n"
                "Stato: in attesa di conferma del negozio."
            ),
            parse_mode="Markdown",
        )
    except Exception as exc:  # utente non ha mai avviato il bot -> ok
        log.warning("Impossibile notificare utente %s: %s", user_id, exc)

    return {"ok": True, "order_id": order_id, "owner_chat_id": chat.chat_id}


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "bot": "haze-smoke-club"}
