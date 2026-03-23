import asyncio
import logging

from app.bot import create_bot, create_dispatcher
from app.config import settings
from app.logging_setup import setup_logging


async def main() -> None:
    setup_logging(settings.log_level)
    logger = logging.getLogger(__name__)

    bot = create_bot(settings.bot_token)
    dp = create_dispatcher()

    logger.info("Starting bot")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
