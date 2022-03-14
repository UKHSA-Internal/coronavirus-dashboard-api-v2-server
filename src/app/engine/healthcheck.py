#!/usr/bin python3

"""
<Description of the programme>

Author:        Pouria Hadjibagheri <pouria.hadjibagheri@phe.gov.uk>
Created:       15 Mar 2021
License:       MIT
Contributors:  Pouria Hadjibagheri
"""

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
from asyncio import get_event_loop, wait
from logging import getLogger

# 3rd party:

# Internal: 
from app.database import Connection
from app.storage import AsyncStorageClient

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Header
__author__ = "Pouria Hadjibagheri"
__copyright__ = "Copyright (c) 2021, Public Health England"
__license__ = "MIT"
__version__ = "0.0.1"
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'run_healthcheck'
]


logger = getLogger("app")


async def test_db():
    try:
        async with Connection() as conn:
            db_active = await conn.fetchval("SELECT NOW() AS timestamp;")
    except Exception as err:
        logger.exception(err, exc_info=True)
        raise err

    return {"db": f"healthy - {db_active}"}


async def test_storage():
    try:
        async with AsyncStorageClient("pipeline", "info/seen") as blob_client:
            blob = await blob_client.download()
            blob_data = await blob.readall()
    except Exception as err:
        logger.exception(err, exc_info=True)
        raise err

    return {"storage": f"healthy - {blob_data.decode()}"}


async def run_healthcheck() -> dict[str, str]:
    return {"status": "ALIVE"}
