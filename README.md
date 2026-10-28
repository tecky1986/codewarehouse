# 集装箱装箱工具

Web 应用：按可配置规则将批量货物排入集装箱，输出可导出的装箱方案与 3D 示意。

- 后端：FastAPI + SQLite（`backend/`）
- 前端：Vite + Vue 3 + Three.js（`frontend/`）
- 算法引擎：`backend/packing_engine/`（DBLF、极端点、墙面、Guillotine、自由组合）

## 功能

- 17 列样表导入（cm→mm 自动换算），N 列导入忽略、导出覆盖为 `{箱型}-{序号}`
- 固定箱型（多箱型数量表）与自由组合（箱型勾选 + 数量锁定 + 数量上限）两种用箱模式
- 5 种装箱算法并行对比，KPI 单箱 + 整体对照（体积/载重利用率、完成率、约束满足率）
- 导出 3-sheet xlsx（装箱回写 + 未分配明细 + 用箱摘要）或 CSV；导出模板可自定义列
- Three.js 3D 查看器：每箱页签、包围盒居中、0.5/1/2/4 倍速回放、点选高亮
- 全链路 xlsx 编码，中文文件名 RFC 5987；回写除 N 列与新增列外逐格一致

## 目录结构

```
backend/
  app/            FastAPI 应用（路由、仓储、作业调度、导出）
  packing_engine/ 几何模型、规则校验器、算法、KPI
  requirements.txt
frontend/
  src/            Vue 3 页面与组件
  vite.config.ts
start.py          启动脚本（源码模式 / PyInstaller 冻结模式）
container_packing.spec  PyInstaller onedir 打包配置
```

## 开发运行

### 后端

```bash
cd backend
pip install -r requirements.txt
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

前端开发服务器代理 `/api` 到 `http://127.0.0.1:8000`，预览地址
`https://5173-af91813fdcb62cb4.monkeycode-ai.online`。

### 测试

```bash
cd backend && python3 -m pytest -q
cd frontend && npm test -- --run && npm run build
```

### 源码模式一键启动

```bash
python3 start.py
```

自动探测 8000 起空闲端口，拉起 uvicorn，打开默认浏览器，数据目录
`~/.container-packing/`，Ctrl+C 停止。

## 测试与规格

- 需求与设计：`.monkeycode/specs/container-packing/`（requirements / design / tasklist）
- 回归基线样表：`.monkeycode-tmp-files/d340e47a-Step3Output-1.xlsx`

## 桌面端打包

> PyInstaller 不支持跨平台打包：Linux 环境产出 Linux 可执行文件，Windows 版必须在 Windows 机器上执行同样的流程。

### Linux（已验证）

前置依赖：

```bash
apt-get install -y python3-venv libpython3.11
```

构建步骤：

```bash
# 1. 创建 venv 并安装依赖
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt pyinstaller

# 2. 构建前端并复制到后端静态目录（后端以 StaticFiles 托管）
cd frontend && npm run build && cd ..
rm -rf backend/static
cp -r frontend/dist backend/static

# 3. 打包 onedir（产出 dist/container_packing/，约 30 MB）
rm -rf dist build
.venv/bin/python -m PyInstaller container_packing.spec --clean -y
```

产物与验证：

```bash
./dist/container_packing/container_packing
# 监听 127.0.0.1:8000（占用时自增），自动打开浏览器
# 数据持久化于 ~/.container-packing/data.db
curl -s http://127.0.0.1:8000/api/health
```

分发时把整个 `dist/container_packing/` 目录（可执行文件 + `_internal/`）压缩给用户，
对方解压后直接运行 `container_packing`，无需安装 Python。

### Windows

在 Windows 开发机（Python 3.11 + 同版本 venv）上执行同样的 1–3 步，
`pyinstaller container_packing.spec --clean -y` 产出
`dist/container_packing/container_packing.exe`。冻结模式下启动脚本在进程内运行
uvicorn（`sys.frozen` 检测），资源经 `sys._MEIPASS/_internal` 解析，与源码模式行为一致。

### GitHub Release 下载

推送 `v*` 版本 tag 会自动构建 Linux x64 和 Windows x64 分发压缩包，并附加到 GitHub Release。
用户可在仓库 Releases 页面下载对应平台的 zip，解压后运行目录中的 `container_packing` 或
`container_packing.exe`；请保留同目录的 `_internal/` 资源目录。
