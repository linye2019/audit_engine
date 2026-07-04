"""医保智能审核引擎 — FastAPI 应用入口"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .deps import API_VERSION
from .routes import api_router


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用实例"""
    app = FastAPI(
        title="医保智能审核引擎 API",
        description="""
## 医保智能审核引擎 RESTful API

基于四柱审核框架（药品目录限制 → 耗材使用合规 → 项目收费合规 → 支付合规性），
支持三阶段审核（向下级联）：

- **事前医嘱审核** (pre_check)：医生开立医嘱时实时检查，返回拦截/提醒
- **事中出科审核** (end_check)：患者出科/出院时全量审核，含跨行互斥判断
- **事后结算监管** (post_audit)：结算后深度分析，含DRG支付合规

### 快速开始

1. 事前医嘱审核：`POST /api/v1/audit/precheck`
2. 事中出科审核：`POST /api/v1/audit/end_check`
3. 查看规则：`GET /api/v1/rules`
4. AI 智能体界面：`/ai-assistant.html`

### 字段编码标准

所有枚举值对齐国家医保局《医疗保障信息平台定点医药机构接口规范》V1.1.85
        """,
        version=API_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")

    return app


app = create_app()
