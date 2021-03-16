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


async def test_db():
    async with Connection() as conn:
        db_active = await conn.fetchval("SELECT NOW() AS timestamp;")

    return {"db": f"healthy - {db_active}"}


async def test_storage():
    async with AsyncStorageClient("pipeline", "info/seen") as blob_client:
        blob = await blob_client.download()
        blob_data = await blob.readall()

    return {"storage": f"healthy - {blob_data.decode()}"}


async def run_healthcheck() -> dict[str, str]:
    loop = get_event_loop()

    tasks = [
        loop.create_task(test_db()),
        loop.create_task(test_storage())
    ]

    response = dict()
    done, pending = await wait(tasks)
    for future in done:
        response.update(future.result())

    return response
