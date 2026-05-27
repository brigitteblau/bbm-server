from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.prosthesis import router as prosthesis_router

app = FastAPI(title="BBM API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://bbm-server-hfq1.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "BBM API funcionando"}

app.include_router(
    prosthesis_router,
    prefix="/prosthesis",
    tags=["prosthesis"],
)
