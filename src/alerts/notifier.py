"""SendGrid email alerts for SMA crossovers and RSI extremes."""

from __future__ import annotations

from src.config import get_settings
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def send_alert(subject: str, body: str) -> bool:
    settings = get_settings()
    if not settings.enable_email_alerts or not settings.sendgrid_api_key:
        logger.info("Alert (email disabled)", extra={"subject": subject, "body": body})
        return False

    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail

    message = Mail(
        from_email=settings.alert_from_email,
        to_emails=settings.alert_to_email,
        subject=subject,
        plain_text_content=body,
    )
    client = SendGridAPIClient(settings.sendgrid_api_key)
    response = client.send(message)
    logger.info("Email sent", extra={"status": response.status_code, "subject": subject})
    return response.status_code < 300


def maybe_alert(row: dict) -> None:
    settings = get_settings()
    ticker = row.get("ticker")
    close = row.get("close")
    rsi = row.get("rsi_14")
    cross = row.get("sma_cross") or 0

    if cross == 1:
        send_alert(
            f"[BULLISH] {ticker} SMA crossover",
            f"{ticker} 20 SMA crossed above 50 SMA. Close={close}",
        )
    elif cross == -1:
        send_alert(
            f"[BEARISH] {ticker} SMA crossover",
            f"{ticker} 20 SMA crossed below 50 SMA. Close={close}",
        )

    if rsi is not None and rsi >= settings.rsi_overbought:
        send_alert(f"[RSI] {ticker} overbought", f"{ticker} RSI={rsi:.1f} close={close}")
    elif rsi is not None and rsi <= settings.rsi_oversold:
        send_alert(f"[RSI] {ticker} oversold", f"{ticker} RSI={rsi:.1f} close={close}")
