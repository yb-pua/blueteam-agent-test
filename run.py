#!/usr/bin/env python3
"""
蓝队威胁情报辅助平台 - 一键启动脚本
Blue Team Threat Intel Agent

启动方式: python run.py

运行前请先构建前端:
  cd frontend && npm install && npm run build
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PORT = 8020

def print_banner():
    print("=" * 54)
    print("  蓝队威胁情报辅助平台 v1.0")
    print("  Blue Team Threat Intel Agent")
    print("=" * 54)
    print()
    print(f"  Web UI:  http://localhost:{PORT}")
    print(f"  API:     http://localhost:{PORT}/api/v1")
    print(f"  Health:  http://localhost:{PORT}/health")
    print(f"  Docs:    http://localhost:{PORT}/docs")
    print()

def main():
    print_banner()

    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT, reload=False)

if __name__ == "__main__":
    main()
