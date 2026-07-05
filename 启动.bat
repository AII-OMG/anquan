@echo off
chcp 65001 >nul
echo ========================================
echo 湖南省建筑施工企业"安管人员"
echo 安全生产考核刷题系统
echo ========================================
echo.
where python >nul 2>nul
if %errorlevel%==0 (
    echo 正在启动本地服务器 http://localhost:8010
    echo 关闭本窗口即停止服务
    echo.
    start "" "http://localhost:8010"
    python -m http.server 8010 --directory "%~dp0"
) else (
    echo 本机未安装 Python，为您打开在线版...
    start "" "https://st.btt.kdns.fr"
    echo.
    pause
)
