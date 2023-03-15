__version__ = "0.1.0"

import random
import time
import traceback
from functools import reduce
from typing import Dict

import sys
import uuid
import watchtower

from fastapi import Depends, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse
from fastapi import FastAPI
from loguru import logger


logger.remove()

logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{"
    "function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level> {extra}",
    diagnose=True,
)

logger.add(watchtower.CloudWatchLogHandler("/experiment/cw-log-demo"), serialize=True)

app = FastAPI(debug=True)


@app.on_event("shutdown")
def shutdown_event():
    logger.info("Server shutting down")


async def handle_request(request, call_next):
    start_time = time.time()
    logger.debug(
        "Request: {method} {url} {query}",
        method=request.method.upper(),
        url=request.url.path,
        query=dict(request.query_params),
    )
    try:
        response = await call_next(request)
    except Exception as exc:
        response = await handle_generic_exception(request, exc)

    process_time = time.time() - start_time
    logger.debug("Took {time}", time=process_time)
    return response


@app.middleware("http")
async def log_request_response(request: Request, call_next):
    if "request_id" in request.query_params:
        with logger.contextualize(request_id=request.query_params["request_id"]):
            return await handle_request(request, call_next)
    else:
        return await handle_request(request, call_next)


@app.exception_handler(Exception)
async def handle_generic_exception(request: Request, error: Exception) -> JSONResponse:
    error_id = str(uuid.uuid4())
    if len(error.args) > 1:
        _logger = logger.bind(**error.args[1], error_id=error_id)
    else:
        _logger = logger.bind(error_id=error_id)

    _logger.error(
        f"{type(error).__name__} in {request.url}: {error.args[0]}",
        exc_info=traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"error": "Ooops! Server encountered an error", "error_id": error_id},
    )


@app.get("/", response_model=Dict[str, str])
async def root() -> Dict[str, str]:
    time.sleep(random.randint(1, 5))
    resp = {"message": "Hello World"}
    logger.debug("Response: {response}", response=resp)
    return resp


@app.get("/health")
async def health() -> dict[str, str]:
    time.sleep(random.randint(1, 5))
    resp = {"health": "ok"}
    logger.debug("Response: {response}", response=resp)
    return resp


@app.get("/exception")
async def health() -> dict[str, str]:
    time.sleep(random.randint(1, 5))
    raise Exception("Item not found", {"item_id": 1})
