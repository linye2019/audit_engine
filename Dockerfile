# ============================================================================
# 医保智能审核引擎 — Dockerfile
# 多阶段构建：stage1 安装依赖 → stage2 运行
# ============================================================================

# ---- Stage 1: 依赖安装 ----
FROM python:3.11-slim AS builder

WORKDIR /app

# 先复制依赖声明，利用 Docker 缓存层（不改依赖就不重装）
COPY pyproject.toml README.md ./
COPY audit_engine/ audit_engine/

# 安装生产依赖（不含 dev 组）
RUN pip install --no-cache-dir -e .

# ---- Stage 2: 运行 ----
FROM python:3.11-slim

WORKDIR /app

# 从 builder 阶段复制已安装的依赖和代码
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /app/audit_engine /app/audit_engine
COPY api/ api/
COPY api_server.py .
COPY web/ web/

# 数据库文件通过 volume 挂载，不打包进镜像
# 例如: -v /host/path/medicare_engine.db:/app/medicare_engine.db

EXPOSE 8000

# 环境变量（可通过 -e 覆盖）
ENV MEDICARE_DB_PATH=medicare_engine.db

# 启动命令（使用 uvicorn，worker 数可调）
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
