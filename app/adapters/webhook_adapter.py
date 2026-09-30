import logging
import requests
from typing import Dict, Any

logger = logging.getLogger(__name__)

class WebhookAdapter:
    """
    Adapter for interacting with external webhooks (e.g., Slack, Teams).
    Ensures safe HTTP POST requests with logging and strict timeouts.
    """
    @staticmethod
    def send_post(url: str, payload: Dict[str, Any], timeout: float = 5.0) -> bool:
        """Sends a POST request to the provided webhook URL."""
        # Sanitize URL logging to avoid leaking sensitive tokens in plain logs if necessary
        safe_url = url.split("?")[0] if "?" in url else url
        logger.info(f"WebhookAdapter: Sending POST request to webhook endpoint ({safe_url})")
        
        try:
            resp = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=timeout
            )
            resp.raise_for_status()
            logger.info("WebhookAdapter: Successfully POSTed to webhook.")
            return True
        except requests.RequestException as e:
            logger.error(f"WebhookAdapter: Request failed - {str(e)}")
            raise
