from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.prosthesis import router as prosthesis_router
from app.config import ALLOWED_ORIGINS

app = FastAPI(
    title="Hunda",
    summary="Tecnología 3D para prótesis caninas personalizadas",
    description="Generación y gestión de prótesis adaptadas a cada perro.",
    version="1.0.0",
    contact={
        "name": "BBM Team",
        "email": "betterbm26@gmail.com",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    # Previews de Vercel del front (hunda-<hash>.vercel.app) y artifacts de Claude
    # (front de prueba), que se sirven desde subdominios dinámicos.
    allow_origin_regex=r"https://(hunda[a-z0-9-]*\.vercel\.app|[a-z0-9-]+(\.[a-z0-9-]+)*\.(claudeusercontent\.com|claude\.site))",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "BBM API funcionando"}


@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(prosthesis_router, prefix="/prosthesis", tags=["prosthesis"])