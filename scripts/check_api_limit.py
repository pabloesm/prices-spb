import asyncio
import logging
import os

import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_URL_TEMPLATE = os.environ.get("API_URL_TEMPLATE", "default")
if not API_URL_TEMPLATE or API_URL_TEMPLATE == "default":
    raise ValueError("API_URL_TEMPLATE environment variable must be provided")

API_URL = API_URL_TEMPLATE.format(id=80320)

MAX_REQUESTS = 150


async def make_request(session, request_number):
    response = await session.get(API_URL)
    logger.info("Request %s: Status Code - %s", request_number, response.status_code)


async def test_rate_limit():
    async with httpx.AsyncClient() as session:
        tasks = []
        request_number = 1

        try:
            while True:
                task = asyncio.create_task(make_request(session, request_number))
                tasks.append(task)
                request_number += 1
                await asyncio.sleep(0.1)  # To avoid sending requests too quickly
                if request_number == MAX_REQUESTS:
                    request_number = 1
                    logger.info("Waiting for 1 minute...")
                    await asyncio.sleep(60)
        except KeyboardInterrupt:
            logger.info("Test interrupted.")
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(test_rate_limit())
