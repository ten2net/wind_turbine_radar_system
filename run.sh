#!/bin/bash

# 风机-雷达干扰评估系统启动脚本

echo "========================================"
echo "  风机-雷达干扰评估系统"
echo "  Wind Turbine - Radar Interference"
echo "  Assessment System"
echo "========================================"
echo ""

# 检查Python版本
echo "检查Python版本..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python版本: $python_version"

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
echo "激活虚拟环境..."
source venv/bin/activate

# 安装依赖
echo "检查依赖..."
pip install -q -r requirements.txt

# 启动应用
echo ""
echo "启动应用..."
echo "请在浏览器中访问: http://localhost:8501"
echo "提示: 热加载已启用，修改代码后浏览器会自动刷新"
echo ""
cd src && streamlit run app.py --server.runOnSave true --server.fileWatcherType poll