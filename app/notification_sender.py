import asyncio
import concurrent.futures
import logging

import apprise

logger = logging.getLogger(__name__)

# Dedicated thread pool for notifications — prevents competing with
# image encoding and other I/O in the default executor.
_notification_executor = concurrent.futures.ThreadPoolExecutor(max_workers=3, thread_name_prefix="notif")


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
    Async wrapper for sending notifications via dedicated thread pool.
    """
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(_notification_executor, _send_sync, urls, title, body)
