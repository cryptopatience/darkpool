@echo off
echo 🚀 MAG 7+2 Dark Pool 분석 대시보드 시작...
echo.

REM 가상환경 활성화 (존재하는 경우)
if exist venv\Scripts\activate.bat (
    echo 가상환경 활성화 중...
    call venv\Scripts\activate.bat
)

REM Streamlit 실행
echo Streamlit 앱 실행 중...
streamlit run app.py

pause
