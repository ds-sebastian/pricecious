import asyncio
import logging

import apprise

logger = logging.getLogger(__name__)

def _send_sync(urls: list, title: str, body: str):
    """
    Synchronous notification sending.
    """
    if not urls:
        return

    apobj = apprise.Apprise()

    for url in urls:
        apobj.add(url)

    try:
        apobj.notify(
            body=body,
            title=title,
        )
        logger.info(f"Notification sent: {title}")
    except Exception as e:
        logger.error(f"Error sending notification: {e}")

async def send_notification(urls: list, title: str, body: str):
    """
    Async wrapper for sending notifications.
    """
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _send_sync, urls, title, body)
