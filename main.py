from __future__ import annotations
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.v1.router import api_router
from config.settings import get_settings

settings = get_settings()
logging.basicConfig(level=logging.DEBUG if settings.debug else logging.INFO)

app = FastAPI(
    title="M-QoL Assessment API",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# CORS（按需放开）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 生产环境请改白名单
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 健康检查
@app.get("/healthz")
def healthz():
    return {"ok": True, "env": settings.env}

# v1 路由
app.include_router(api_router, prefix="/api/v1")

# 便捷启动命令：
# uvicorn main:app --reload --port 8000