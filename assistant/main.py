import time
import logging
from assistant import PersonalAssistant
from config import POLL_INTERVAL_SECONDS

logger = logging.getLogger(__name__)


def main():
    assistant = PersonalAssistant()
    logger.info(f"Started. Polling every {POLL_INTERVAL_SECONDS}s...")

    while True:
        try:
            assistant.run_once()
        except KeyboardInterrupt:
            logger.info("Stopped by user.")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
