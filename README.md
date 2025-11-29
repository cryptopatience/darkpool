# MAG 7+2 Dark Pool & Short Interest 분석 대시보드

## 📊 프로젝트 소개

MAG 7 주요 기술주와 비트코인 관련 종목의 Dark Pool 거래 및 공매도 데이터를 실시간으로 분석하는 Streamlit 대시보드입니다.

### 분석 대상 종목
- **MAG 7**: AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA
- **Bitcoin 관련**: COIN (Coinbase), IBIT (Bitcoin ETF)

### 주요 기능

1. **Dark Pool Ratio 분석**
   - 전체 거래량 대비 장외 거래 비율 측정
   - 기관 투자자의 시장 개입 강도 파악

2. **Short Interest 분석**
   - Dark Pool 내부 공매도 비율
   - 전체 시장 공매도 비율
   - 10일 이동평균 및 변화율 추적

3. **4분면 분석**
   - 기관 관심도 vs 공매도 심리 매핑
   - 매집/분산 구간 시각화

4. **시계열 추적**
   - 60일 히스토리 차트
   - 트렌드 및 패턴 분석

## 🚀 설치 및 실행

### 1. 환경 설정

```bash
# 저장소 클론 또는 다운로드
git clone <repository-url>
cd mag7_darkpool_app

# 가상환경 생성 (선택사항)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 2. 앱 실행

```bash
streamlit run app.py
```

브라우저에서 자동으로 `http://localhost:8501` 열림

## 📈 사용 방법

### 사이드바 설정
- **분석 기간**: 30~90일 선택 가능 (기본값: 60일)
- **자동 새로고침**: 1시간 주기로 데이터 자동 갱신

### 메인 대시보드
1. **전체 시장 개요**: 평균 지표 및 신호 카운트
2. **통합 테이블**: 전체 종목 핵심 지표 비교
3. **시각화 분석**: 4가지 차트 탭
   - Dark Pool Ratio
   - Short 비교
   - 4분면 분석
   - 시계열 분석

## 🔍 신호 해석 가이드

| 신호 | 조건 | 의미 |
|------|------|------|
| 🔴 기관 강한 약세 포지션 | DP Ratio >50% & DP Short >55% | 기관의 비공개 공매도 집중 |
| 💚 기관 매집 가능성 | DP Ratio >50% & DP Short <45% | 장외 매수 거래 증가 |
| 🟢 급락 (청산 신호) | 10일 대비 -5%p 이상 | 공매도 청산, 상승 전환 가능 |
| ⚠️ DP에 공매도 집중 | DP Short > Total Short +5%p | 비밀 공매도 포지션 |
| ✅ 거래소에 공매도 집중 | Total Short > DP Short +5%p | 투명한 공매도 거래 |

## 📊 데이터 출처

- **Yahoo Finance**: 전체 시장 거래량 데이터
- **FINRA**: Dark Pool 및 공매도 데이터
- **업데이트 주기**: 1시간 캐시 (매일 갱신)

## ⚙️ 기술 스택

- **Frontend**: Streamlit
- **Data**: yfinance, requests
- **Visualization**: Plotly
- **Analysis**: pandas, numpy

## 📝 라이선스

MIT License

## 🤝 기여

이슈 및 PR은 언제나 환영합니다!

## 📧 문의

질문이나 제안사항이 있으시면 이슈를 등록해주세요.
