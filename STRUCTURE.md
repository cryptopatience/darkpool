# 프로젝트 구조

```
mag7_darkpool_app/
│
├── app.py                      # 메인 Streamlit 애플리케이션
├── requirements.txt            # Python 의존성 패키지 목록
├── README.md                   # 프로젝트 설명서
├── .gitignore                  # Git 무시 파일 목록
│
├── .streamlit/
│   └── config.toml            # Streamlit 설정 파일
│
├── run.sh                     # Unix/Mac 실행 스크립트
├── run.bat                    # Windows 실행 스크립트
├── install.sh                 # 설치 스크립트
│
└── STRUCTURE.md              # 이 파일
```

## 파일 설명

### 핵심 파일

- **app.py**: Streamlit 기반 웹 애플리케이션 메인 코드
  - 데이터 수집 (Yahoo Finance, FINRA)
  - 분석 로직 (Dark Pool, Short Interest)
  - UI 및 차트 구성

- **requirements.txt**: 필요한 Python 패키지
  - streamlit: 웹 대시보드 프레임워크
  - yfinance: Yahoo Finance 데이터
  - plotly: 인터랙티브 차트
  - pandas, numpy: 데이터 분석

### 설정 파일

- **.streamlit/config.toml**: Streamlit 앱 설정
  - 테마 색상
  - 서버 포트 및 옵션
  - 브라우저 설정

- **.gitignore**: 버전 관리 제외 파일
  - Python 캐시 파일
  - 가상환경
  - IDE 설정 파일

### 실행 스크립트

- **run.sh**: Unix/Mac용 실행 스크립트
  - 가상환경 자동 활성화
  - Streamlit 앱 시작

- **run.bat**: Windows용 실행 스크립트
  - 동일한 기능 (Windows 환경)

- **install.sh**: 자동 설치 스크립트
  - 가상환경 생성
  - 패키지 설치
  - 환경 설정

## 사용 흐름

1. **설치**: `./install.sh` 또는 수동 설치
2. **실행**: `./run.sh` 또는 `streamlit run app.py`
3. **접속**: 브라우저에서 `http://localhost:8501`

## 데이터 흐름

```
Yahoo Finance API → 시장 거래량 데이터
        ↓
FINRA API → Dark Pool 데이터
        ↓
데이터 병합 및 계산 (app.py)
        ↓
Streamlit 대시보드 렌더링
        ↓
사용자 브라우저
```

## 캐싱 전략

- `@st.cache_data(ttl=3600)`: 1시간 동안 데이터 캐시
- 자동 새로고침 옵션으로 주기적 갱신 가능
- 수동 새로고침 버튼 제공
