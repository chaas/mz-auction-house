import logging
import asyncio
import psycopg
from sse_starlette.sse import EventSourceResponse
from fastapi import FastAPI, Request
from fastapi.logger import logger
import uvicorn

from config import DSN

_logger = logging.getLogger('uvicorn.error')
logger.handlers = _logger.handlers
def log_db_diagnosis_callback(diagnosis: psycopg.Error.diag):
    _logger.info(f"The database says: {diagnosis.severity} - {diagnosis.message_primary}")

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello World"}


async def event_generator(request: Request, conn: psycopg.AsyncConnection):
    try:
        while True:
            if await request.is_disconnected():
                break
            yield "wait a moment..."
            async with conn:
                async with conn.cursor() as cur:
                    _logger.info("made it here!")
                    await cur.execute(
                    """SET CLUSTER = auction_house;
                        SUBSCRIBE (
                            SELECT auction_id, bid_id, item, amount
                            FROM winning_bids
                        );
                    """)
                    conn.commit()
                    _logger.info("hello")
                    data_exists = await cur.fetchone()
                    if data_exists:
                        async for row in cur:
                            yield row   
                    else:
                        _logger.info("no data yet")
                        yield "no data yet"
                        asyncio.sleep(1)
                        continue
                
    except Exception as err:
        _logger.error(err)

@app.get("/subscribe")
async def message_stream(request: Request):

    try:
        conn = await psycopg.AsyncConnection.connect(DSN)
        conn.add_notice_handler(log_db_diagnosis_callback)        
        return EventSourceResponse(event_generator(request, conn))
    finally:
        conn.close()



if __name__ == "__main__":
    logger.setLevel(_logger.level)
    uvicorn.run(app, host="127.0.0.1", port=8000)
