#!/bin/bash

echo "======================================"
echo "MAG 7+2 분석 대시보드 설치 스크립트"
echo "======================================"
echo ""

# Python 버전 확인
echo "1️⃣ Python 버전 확인 중..."
python --version

if [ $? -ne 0 ]; then
    echo "❌ Python이 설치되어 있지 않습니다."
    echo "Python 3.8 이상을 설치해주세요."
    exit 1
fi

echo "✅ Python 확인 완료"
echo ""

# 가상환경 생성
echo "2️⃣ 가상환경 생성 중..."
python -m venv venv

if [ $? -ne 0 ]; then
    echo "❌ 가상환경 생성 실패"
    exit 1
fi

echo "✅ 가상환경 생성 완료"
echo ""

# 가상환경 활성화
echo "3️⃣ 가상환경 활성화 중..."
source venv/bin/activate

echo "✅ 가상환경 활성화 완료"
echo ""

# pip 업그레이드
echo "4️⃣ pip 업그레이드 중..."
pip install --upgrade pip

echo ""

# 의존성 설치
echo "5️⃣ 필요한 패키지 설치 중..."
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "❌ 패키지 설치 실패"
    exit 1
fi

echo ""
echo "======================================"
echo "✅ 설치 완료!"
echo "======================================"
echo ""
echo "다음 명령어로 앱을 실행하세요:"
echo "  ./run.sh"
echo ""
echo "또는:"
echo "  streamlit run app.py"
echo ""
