"""
医保智能审核引擎 — RESTful API 服务

启动方式:
  uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
  或: python3 api_server.py
"""

import os
import uvicorn

from api import app
from api.deps import DB_PATH

if __name__ == "__main__":
    print(f"[INFO] 医保智能审核引擎 API 服务启动中...")
    print(f"[INFO] 数据库: {os.path.abspath(DB_PATH)}")
    print(f"[INFO] API文档: http://localhost:8000/docs")
    print(f"[INFO] ReDoc:  http://localhost:8000/redoc")
    uvicorn.run(app, host="0.0.0.0", port=8000)
