@echo off
chcp 65001 >nul

echo ========================================
echo   风机-雷达干扰评估系统
echo   Wind Turbine - Radar Interference
echo   Assessment System
echo ========================================
echo.

REM 检查Python版本
echo 检查Python版本...
python --version

REM 检查虚拟环境
if not exist "venv" (
    echo 创建虚拟环境...
    python -m venv venv
)

REM 激活虚拟环境
echo 激活虚拟环境...
call venv\Scripts\activate.bat

REM 安装依赖
echo 检查依赖...
pip install -q -r requirements.txt

REM 启动应用
echo.
echo 启动应用...
echo 请在浏览器中访问: http://localhost:8501
echo.
cd src && streamlit run app.py

pause
