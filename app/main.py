from fastapi import FastAPI

from app.routes.prosthesis import router as prosthesis_router

app = FastAPI(title="BBM API")

app.include_router(
    prosthesis_router,
    prefix="/prosthesis",
    tags=["prosthesis"],
)
