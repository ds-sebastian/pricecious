import apprise
import logging

logger = logging.getLogger(__name__)

def send_notification(urls: list, title: str, body: str):
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
