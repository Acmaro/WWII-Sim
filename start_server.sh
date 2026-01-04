#!/bin/bash
# ============================================================================
# WWII Simulation v2 - 快速启动脚本 (Linux/Mac)
# ============================================================================

echo "======================================================================"
echo "WWII Simulation v2 Server Launcher"
echo "======================================================================"
echo ""

# 检查虚拟环境是否存在
if [ ! -d "venv" ]; then
    echo "[错误] 未找到虚拟环境！"
    echo "请先运行: python -m venv venv"
    echo ""
    exit 1
fi

# 激活虚拟环境
echo "[1/3] 激活虚拟环境..."
source venv/bin/activate

# 检查.env文件
if [ ! -f ".env" ]; then
    echo ""
    echo "[警告] 未找到.env配置文件！"
    echo "使用默认配置启动..."
    echo "建议: 复制 .env.example 为 .env 并配置"
    echo ""
fi

# 启动服务器
echo "[2/3] 启动FastAPI服务器..."
echo ""
echo "======================================================================"
echo "服务器信息:"
echo "  - API文档: http://localhost:8000/docs"
echo "  - 健康检查: http://localhost:8000/health"
echo "  - 按 Ctrl+C 停止服务器"
echo "======================================================================"
echo ""

# 运行服务器
python -m backend.api.server

# 如果出错
if [ $? -ne 0 ]; then
    echo ""
    echo "[错误] 服务器启动失败！"
    echo "请检查:"
    echo "  1. 是否安装了所有依赖: pip install -r requirements.txt"
    echo "  2. 是否配置了.env文件"
    echo "  3. LLM服务是否运行中（如果使用LM Studio）"
    echo ""
fi
