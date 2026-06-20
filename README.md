# PrintCode Guard

印刷厂喷码二维码质检 Demo（v1 RTSP 验证版）。

## 快速启动

1. 创建虚拟环境并安装依赖：
   ```bash
   python3.11 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```
2. 确保本地 PostgreSQL 已启动，并创建数据库：
   ```bash
   bash scripts/init_db.sh
   ```
   或手动：
   ```sql
   CREATE DATABASE printcode_guard;
   ```
3. 启动服务：
   ```bash
   .venv/bin/uvicorn src.printcode_guard.main:app --reload --host 0.0.0.0 --port 8090
   ```
4. 打开 http://localhost:8000/ 开始验证。

## 数据目录

- 异常截图保存在 `private-data/screenshots/`。

## 版本规划

- v1：萤石云 RTSP 单摄像头验证版（当前）
- v2：三把枪版本（多固定摄像头）
- v3：正规高速工业相机版本
- v4（可能）：线扫相机版本
