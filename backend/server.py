"""
FastAPI 应用
============
提供 REST API + 静态文件服务。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from utils.logger import log
from utils.version import AppVersion


@asynccontextmanager
async def lifespan(application: FastAPI):
    log.info("FastAPI 应用启动")
    yield
    log.info("FastAPI 应用关闭")


app = FastAPI(
    title="GenshinDogFoodSweeper",
    description="原神狗粮清扫器 — 后端 API",
    version=AppVersion.semver(),
    lifespan=lifespan,
)

# CORS（开发阶段允许前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===================== 基础路由 =====================


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/stats")
async def get_stats():
    """统计概览（占位）"""
    return {
        "total_artifacts": 0,
        "five_star_count": 0,
        "four_star_count": 0,
        "avg_score": 0.0,
    }


# ===================== 子路由（后续接入） =====================
# from api.artifacts import router as artifacts_router
# from api.scan import router as scan_router
# from api.settings import router as settings_router
# app.include_router(artifacts_router, prefix="/api")
# app.include_router(scan_router, prefix="/api")
# app.include_router(settings_router, prefix="/api")