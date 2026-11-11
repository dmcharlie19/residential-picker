import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from app.api.search import router
from app.schemas.search import SearchValidationError

logger = logging.getLogger("residential_picker")
app = FastAPI(title="Подбор ЖК", docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(router)


def error(status, code, message, fields=None):
    return JSONResponse(status_code=status, content={"error": {
        "code": code, "message": message, "fields": fields or {},
    }})


@app.exception_handler(SearchValidationError)
async def validation_error(request: Request, exc: SearchValidationError):
    return error(422, "VALIDATION_ERROR", "Проверьте параметры поиска", exc.fields)


@app.exception_handler(OperationalError)
async def database_error(request: Request, exc: OperationalError):
    logger.error("Database unavailable (%s)", type(exc).__name__)
    return error(503, "DATABASE_UNAVAILABLE", "Сервис временно недоступен. Попробуйте позже.")


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    logger.error("Request failed (%s)", type(exc).__name__)
    return error(500, "INTERNAL_ERROR", "Не удалось выполнить поиск. Попробуйте позже.")
