import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO
import time

warnings.filterwarnings('ignore')

# ==================== 페이지 설정 ====================
st.set_page_config(
    page_title="MAG 7+2 Dark Pool & Short Analysis",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== 로그인 시스템 ====================
def check_password():
    """비밀번호 확인 및 로그인 상태 관리"""
    if st.session_state.get('password_correct', False):
        return True
    
    st.title("DarkPool")
    st.markdown("### Magnificent Seven + Bitcoin Exposure 종합 분석")
    
    with st.form("credentials"):
        username = st.text_input("아이디 (ID)", key="username")
        password = st.text_input("비밀번호 (Password)", type="password", key="password")
        submit_btn = st.form_submit_button("로그인", type="primary")
    
    if submit_btn:
        if username in st.secrets["passwords"] and password == st.secrets["passwords"][username]:
            st.session_state['password_correct'] = True
            st.rerun()
        else:
            st.error("😕 아이디 또는 비밀번호가 올바르지 않습니다.")
    
    return False

if not check_password():
    st.stop()

# ==================== 로그아웃 버튼 ====================
with st.sidebar:
    st.success(f"✅ 로그인 성공!")
    if st.button("🚪 로그아웃"):
        st.session_state['password_correct'] = False
        st.rerun()

# ==================== 설정 및 종목 리스트 ====================
MAG7_STOCKS = {
    'AAPL': 'Apple', 'MSFT': 'Microsoft', 'GOOGL': 'Alphabet',
    'AMZN': 'Amazon', 'NVDA': 'NVIDIA', 'META': 'Meta',
    'TSLA': 'Tesla', 'COIN': 'Coinbase', 'IBIT': 'Bitcoin ETF'
}

# ==================== 데이터 수집 함수 ====================

@st.cache_data(ttl=3600)
def get_market_volume(ticker, days_back=65):
    """Yahoo Finance에서 전체 시장 거래량 가져오기"""
    try:
        stock = yf.Ticker(ticker)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back + 10)
        df = stock.history(start=start_date, end=end_date)
        return df['Volume']
    except:
        return None

@st.cache_data(ttl=3600)
def get_yf_short_info(ticker):
    """Yahoo Finance에서 공매도 정보 가져오기 (표준 지표)"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        return {
            'shares_short': info.get('sharesShort', 0),
            'short_percent_float': info.get('shortPercentOfFloat', 0) * 100,
            'short_ratio_days': info.get('shortRatio', 0),
            'shares_outstanding': info.get('sharesOutstanding', 0)
        }
    except:
        return {
            'shares_short': 0,
            'short_percent_float': 0,
            'short_ratio_days': 0,
            'shares_outstanding': 0
        }

@st.cache_data(ttl=3600)
def get_finra_data_full(ticker, days_back=60):
    """FINRA 데이터 수집 및 핵심 지표 계산"""
    try:
        today = datetime.now()
        data_list = []

        yf_short_info = get_yf_short_info(ticker)
        yf_shares_short = yf_short_info['shares_short']

        market_volumes = get_market_volume(ticker, days_back)
        if market_volumes is None or market_volumes.empty:
            return None

        for days in range(days_back + 5):
            check_date = today - timedelta(days=days)
            if check_date.weekday() >= 5:
                continue

            date_str = check_date.strftime('%Y%m%d')
            date_key = check_date.strftime('%Y-%m-%d')

            url = f"https://cdn.finra.org/equity/regsho/daily/CNMSshvol{date_str}.txt"

            try:
                response = requests.get(url, timeout=3)
                if response.status_code == 200:
                    df = pd.read_csv(StringIO(response.text), sep='|')
                    if 'Symbol' in df.columns:
                        df.rename(columns={'Symbol': 'symbol'}, inplace=True)
                    if 'ShortVolume' in df.columns:
                        df.rename(columns={'ShortVolume': 'shortVolume'}, inplace=True)
                    if 'TotalVolume' in df.columns:
                        df.rename(columns={'TotalVolume': 'totalVolume'}, inplace=True)

                    row = df[df['symbol'] == ticker.upper()]

                    if not row.empty:
                        finra_total = int(row.iloc[0]['totalVolume'])
                        finra_short = int(row.iloc[0]['shortVolume'])

                        market_vol = 0
                        if date_key in market_volumes.index:
                            market_vol = market_volumes.loc[date_key]
                        else:
                            for idx in market_volumes.index:
                                if idx.strftime('%Y-%m-%d') == date_key:
                                    market_vol = market_volumes[idx]
                                    break

                        if market_vol > 0:
                            dp_ratio = (finra_total / market_vol) * 100
                            dp_short_ratio = (finra_short / finra_total) * 100
                            dp_short_market_impact = (finra_short / market_vol) * 100

                            if dp_ratio > 100:
                                dp_ratio = 100

                            data_list.append({
                                'date': date_key,
                                'dp_ratio': round(dp_ratio, 2),
                                'dp_short_ratio': round(dp_short_ratio, 2),
                                'dp_short_market_impact': round(dp_short_market_impact, 2),
                                'market_vol': market_vol,
                                'yf_shares_short': yf_shares_short
                            })

                if len(data_list) >= days_back:
                    break
            except:
                continue

        if not data_list:
            return None

        df_hist = pd.DataFrame(data_list).sort_values('date')
        df_hist['dp_short_ratio_10d_avg'] = df_hist['dp_short_ratio'].rolling(window=10, min_periods=1).mean()
        latest = df_hist.iloc[-1]
        recent_10d_avg = df_hist.iloc[-10:]['dp_short_ratio'].mean()
        dp_short_change = latest['dp_short_ratio'] - recent_10d_avg

        return {
            'ticker': ticker,
            'name': MAG7_STOCKS[ticker],
            'latest_date': latest['date'],
            'dp_ratio': latest['dp_ratio'],
            'dp_short_ratio': latest['dp_short_ratio'],
            'dp_short_market_impact': latest['dp_short_market_impact'],
            'dp_short_10d_avg': latest['dp_short_ratio_10d_avg'],
            'dp_short_change_pct': dp_short_change,
            'yf_shares_short': latest['yf_shares_short'],
            'yf_short_percent_float': yf_short_info['short_percent_float'],
            'yf_short_ratio_days': yf_short_info['short_ratio_days'],
            'history': df_hist
        }

    except Exception as e:
        return None

def create_signal(row):
    """시그널 생성 함수"""
    if row['yf_short_ratio_days'] > 5 and row['dp_short_change_pct'] < -5:
        return '🔥 Short Squeeze 임박!'
    if row['dp_short_change_pct'] < -5:
        return '🟢 급락 (청산 신호)'
    if row['yf_short_ratio_days'] > 7:
        return '🔴🔴 극심한 공매도 (7일+)'
    if row['dp_ratio'] > 50 and row['dp_short_ratio'] > 55:
        return '🔴 기관 강한 약세'
    if row['dp_ratio'] > 50 and row['dp_short_ratio'] < 45:
        return '💚 기관 매집 가능성'
    if row['yf_short_ratio_days'] < 3:
        return '✅ 건강 (DTC <3일)'
    return '⚪ 관망/정상'

# ==================== 메인 앱 ====================

st.title("🚀 MAG 7+2: Dark Pool & Short Interest 심층 분석")
st.markdown("### Magnificent Seven + Bitcoin Exposure 종합 분석")

# 사이드바 설정
with st.sidebar:
    st.header("⚙️ 분석 설정")
    days_back = st.slider("분석 기간 (일)", 30, 90, 60)
    
    st.markdown("---")
    st.info(f"📅 분석 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if st.button("🔄 데이터 새로고침", type="primary"):
        st.cache_data.clear()
        st.rerun()

# 데이터 수집
with st.spinner("📊 데이터 수집 중..."):
    analysis_results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, ticker in enumerate(MAG7_STOCKS.keys()):
        status_text.text(f"수집 중: {ticker}")
        res = get_finra_data_full(ticker, days_back=days_back)
        if res:
            analysis_results.append(res)
        progress_bar.progress((i + 1) / len(MAG7_STOCKS))
    
    status_text.empty()
    progress_bar.empty()

if not analysis_results:
    st.error("❌ 데이터를 가져올 수 없습니다.")
    st.stop()

# FINRA/YF 비율 계산
for item in analysis_results:
    yf_shares_short = item['yf_shares_short']
    if yf_shares_short > 0 and not item['history'].empty:
        latest_market_vol = item['history'].iloc[-1]['market_vol']
        daily_finra_short_vol = (item['dp_short_market_impact'] * latest_market_vol) / 100
        finra_yf_short_ratio = (daily_finra_short_vol / yf_shares_short) * 100
        item['finra_yf_short_ratio'] = finra_yf_short_ratio
    else:
        item['finra_yf_short_ratio'] = 0.0

df_main = pd.DataFrame([{k:v for k,v in r.items() if k != 'history'} for r in analysis_results])
df_main['Signal'] = df_main.apply(create_signal, axis=1)
df_main = df_main.sort_values('yf_short_ratio_days', ascending=False)

st.success(f"✅ {len(analysis_results)}개 종목 분석 완료!")

# ==================== 핵심 지표 해석 가이드 ====================

with st.expander("📚 핵심 지표 체계 및 상세 해석 가이드", expanded=False):
    st.markdown("""
    ### 📊 표준 공매도 지표 (Yahoo Finance 제공) - 가장 중요!
    
    #### 1️⃣ Short Ratio (Days to Cover) ⭐⭐⭐ 최우선 핵심 지표!
    
    **📐 계산식:** 공매도 잔고 / 평균 일일 거래량
    
    **💡 의미:**
    - 현재 쌓여있는 모든 공매도 포지션을 청산하는데 며칠 걸리는가?
    - 공매도 세력이 "탈출"하는데 필요한 시간
    - Short Squeeze 위험도의 직접적 측정치
    
    **📊 해석 기준:**
    - **<3일 (초록)**: 정상 - 공매도 청산 용이, 위험 낮음
    - **3-5일 (주황)**: 주의 - 공매도 압력 존재, 변동성 가능
    - **5-7일 (빨강)**: 높음 - Short Squeeze 가능성, 급등 잠재력
    - **>7일 (적색)**: 매우 높음 - Short Squeeze 고위험, 폭발적 상승 가능
    
    **🎯 실전 활용:**
    - Days to Cover >5일 + 호재 발생 = 🔥 Short Squeeze 폭발!
    - Days to Cover >7일 + DP Short 급락(-5%p) = 🚀 청산 시작, 강력 매수 신호
    - Days to Cover <3일 = 공매도 압력 적음, 안정적 거래 가능
    
    ---
    
    #### 2️⃣ Short % of Float (Short Float) ⭐⭐
    
    **📐 계산식:** (공매도 잔고 / 유통주식수) × 100
    
    **💡 의미:**
    - 시장에서 거래 가능한 주식(Float) 중 몇 %가 공매도되었는가?
    - 시장 참여자들의 약세 심리 강도
    
    **📊 해석 기준:**
    - **<2%**: 매우 낮음 - 시장의 강한 신뢰
    - **2-5%**: 정상 - 일반적인 수준
    - **5-10%**: 주의 - 공매도 세력의 관심 증가
    - **>10%**: 높음 - 강한 약세 베팅 + Short Squeeze 잠재력
    
    ---
    
    ### 📊 FINRA 장외 거래 지표 (Dark Pool Analysis)
    
    #### 3️⃣ DP Ratio (Dark Pool 비중) ⭐
    
    **📐 계산식:** (FINRA 전체 거래량 / 전체 시장 거래량) × 100
    
    **💡 의미:** 전체 시장에서 장외(비공개) 거래가 차지하는 비중
    
    **📊 해석:** >50% = 기관 과열, 40-50% = 기관 관심, <40% = 정상
    
    ---
    
    #### 4️⃣ DP Internal Short Ratio (DP 내부 공매도) ⭐
    
    **📐 계산식:** (FINRA 공매도량 / FINRA 전체 거래량) × 100
    
    **💡 의미:** 장외 거래 중 공매도가 차지하는 비율 (기관의 숨겨진 심리)
    
    **📊 해석:** >55% = 강한 약세, 45-55% = 중립, <45% = 강세
    
    ---
    
    #### 5️⃣ DP Short Market Impact (DP 공매도 시장 영향)
    
    **📐 계산식:** (FINRA 공매도량 / 전체 시장 거래량) × 100
    
    **💡 의미:** 전체 시장 거래량 대비 장외 공매도의 실제 영향력
    
    ---
    
    #### 6️⃣ FINRA/YF Short Ratio (공매도 신선도) - 우리의 독자 지표
    
    **📐 계산식:** (FINRA 일일 공매도량 / YF 전체 공매도 잔고) × 100
    
    **💡 의미:** 전체 공매도 중 오늘 장외에서 발생한 비율 (신규 vs 기존)
    
    **📊 해석:** >50% = 활발한 신규 공매도, 10-50% = 정상, <10% = 청산 진행 중
    """)

# ==================== 종합 시나리오 분석 ====================

with st.expander("🎯 종합 시나리오 분석 - 지표 조합으로 상황 파악하기", expanded=False):
    st.markdown("""
    ### 🔥 시나리오 1: Short Squeeze 임박! (최고 기회 or 최고 위험)
    
    **조건:**
    - Days to Cover > 5일 (공매도 청산 어려움)
    - Short % Float > 10% (높은 공매도 비율)
    - DP Short 급락 (10일 대비 -5%p 이상)
    - FINRA/YF < 10% (신규 공매도 없음, 청산 시작)
    
    **📊 해석:**
    공매도 세력이 쌓아놓은 포지션은 많은데(Float >10%, DTC >5일),
    청산하기 시작했고(DP Short 급락, FINRA/YF 낮음),
    청산에 시간도 오래 걸림(DTC >5일)
    → 💥 연쇄 청산으로 폭등 가능성!
    
    **🎯 전략:** 적극적 매수 진입 (단, 리스크 높음!)
    
    ---
    
    ### 🔴 시나리오 2: 공매도 공격 진행 중
    
    **조건:**
    - Days to Cover 증가 추세
    - DP Short > 55% (장외에서 강한 공매도)
    - DP Short 급등 (10일 대비 +5%p 이상)
    - FINRA/YF > 50% (활발한 신규 공매도)
    
    **📊 해석:**
    공매도 세력이 적극적으로 포지션을 늘리고 있음
    → 하락 압력 증가 예상
    
    **🎯 전략:** 관망 또는 단기 숏 포지션 (역추세 매수는 위험)
    
    ---
    
    ### 💚 시나리오 3: 기관 매집 (장외 매수)
    
    **조건:**
    - DP Ratio > 50% (기관 개입 강함)
    - DP Short < 45% (장외에서 매수 우위)
    - Days to Cover < 3일 (공매도 압력 낮음)
    - Short % Float < 5% (건강한 수준)
    
    **📊 해석:**
    기관들이 장외에서 조용히 매수 중, 공매도 압력도 낮음
    → 안정적 상승 가능성
    
    **🎯 전략:** 안정적 매수 또는 홀딩
    
    ---
    
    ### ✅ 시나리오 4: 건강한 종목 (이상적)
    
    **조건:**
    - Days to Cover < 3일
    - Short % Float < 5%
    - DP Short 40-50% (중립)
    - FINRA/YF 10-50% (정상 회전)
    
    **📊 해석:**
    공매도 압력 낮고, 기관 활동도 정상 범위
    → 안정적 거래 가능, 변동성 낮음
    
    **🎯 전략:** 펀더멘털 분석 기반 투자
    """)

# ==================== 통합 상세 비교 테이블 ====================

st.markdown("---")
st.subheader("📋 통합 상세 비교 테이블: 표준 지표 중심 분석")

with st.expander("💡 테이블 읽는 법", expanded=False):
    st.markdown("""
    - **Days_to_Cover >5일** = Short Squeeze 위험 구간
    - **Short_%_Float >10%** = 높은 공매도 비율
    - **DP내부공매도 >55%** = 장외에서 강한 약세
    - **1일vs10일 <-5%p** = 청산 시작 신호
    - **FINRA/YF >50%** = 활발한 신규 공매도, <10% = 청산 진행
    """)

df_display = df_main.copy()
df_display = df_display.rename(columns={
    'ticker': '티커',
    'name': '종목명',
    'yf_short_ratio_days': 'Days_to_Cover',
    'yf_short_percent_float': 'Short_%_Float',
    'dp_ratio': 'DP비중_%',
    'dp_short_ratio': 'DP내부공매도_%',
    'dp_short_10d_avg': 'DP_10일평균',
    'dp_short_change_pct': '1일vs10일',
    'dp_short_market_impact': 'DP→시장_%',
    'finra_yf_short_ratio': 'FINRA/YF_%',
    'Signal': '신호'
})

table_cols = ['티커', '종목명', 'Days_to_Cover', 'Short_%_Float',
              'DP비중_%', 'DP내부공매도_%', 'DP_10일평균', '1일vs10일',
              'DP→시장_%', 'FINRA/YF_%', '신호']

df_display['Days_to_Cover'] = df_display['Days_to_Cover'].apply(lambda x: f"{x:.2f}일")
df_display['Short_%_Float'] = df_display['Short_%_Float'].apply(lambda x: f"{x:.2f}%")
df_display['DP비중_%'] = df_display['DP비중_%'].apply(lambda x: f"{x:.2f}%")
df_display['DP내부공매도_%'] = df_display['DP내부공매도_%'].apply(lambda x: f"{x:.2f}%")
df_display['DP_10일평균'] = df_display['DP_10일평균'].apply(lambda x: f"{x:.2f}%")
df_display['1일vs10일'] = df_display['1일vs10일'].apply(lambda x: f"{x:+.2f}%p")
df_display['DP→시장_%'] = df_display['DP→시장_%'].apply(lambda x: f"{x:.2f}%")
df_display['FINRA/YF_%'] = df_display['FINRA/YF_%'].apply(lambda x: f"{x:.1f}%")

st.dataframe(df_display[table_cols], use_container_width=True, hide_index=True)

# ==================== 요약 통계 ====================

st.markdown("---")
st.subheader("📊 전체 시장 개요")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("평균 Days to Cover", f"{df_main['yf_short_ratio_days'].mean():.2f}일")
with col2:
    st.metric("평균 Short % Float", f"{df_main['yf_short_percent_float'].mean():.2f}%")
with col3:
    st.metric("평균 DP 비중", f"{df_main['dp_ratio'].mean():.2f}%")
with col4:
    st.metric("평균 DP 내부 공매도", f"{df_main['dp_short_ratio'].mean():.2f}%")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Short Squeeze 위험 (DTC >5일)", 
              f"{len(df_main[df_main['yf_short_ratio_days'] > 5])}개")
with col2:
    st.metric("높은 공매도 비율 (Float >10%)", 
              f"{len(df_main[df_main['yf_short_percent_float'] > 10])}개")
with col3:
    st.metric("청산 신호 (1일vs10일 <-5%p)", 
              f"{len(df_main[df_main['dp_short_change_pct'] < -5])}개")
with col4:
    st.metric("활발한 신규 공매도 (FINRA/YF >50%)", 
              f"{len(df_main[df_main['finra_yf_short_ratio'] > 50])}개")

# ==================== 차트 섹션 ====================

st.markdown("---")
st.header("📈 차트 분석")

# 차트 1: Days to Cover
st.subheader("📊 Chart 1: Days to Cover - Short Squeeze 위험도 측정")

with st.expander("💡 Days to Cover 상세 해석", expanded=False):
    st.markdown("""
    ### 🔍 이 지표가 가장 중요한 이유:
    - Short Squeeze 가능성을 직접적으로 측정
    - 공매도 세력의 "탈출 난이도" 표시
    - 변동성 및 급등 가능성 예측
    
    ### 📊 해석 기준:
    - **<3일 (초록)**: 정상 - 공매도 세력이 빠르게 청산 가능, 변동성 낮음
    - **3-5일 (노랑)**: 주의 - 공매도 청산에 시간 소요, 호재 발생 시 변동성 증가 가능
    - **5-7일 (주황)**: 위험 - Short Squeeze 가능성 있음, 공매도 세력 탈출 어려움
    - **>7일 (빨강)**: 극도 위험! - Short Squeeze 고위험 구간, 폭등 가능
    
    ### 🎯 실전 활용 전략:
    1. DTC >7일 + 호재 발생 = 🚀 폭발적 상승 가능
    2. DTC >5일 + DP Short 급락 = 🔥 청산 시작, 매수 기회
    3. DTC <3일 = 안정적 종목, 펀더멘털 위주 투자
    """)

fig1 = go.Figure()

colors_dtc = []
for x in df_main['yf_short_ratio_days']:
    if x < 3:
        colors_dtc.append('green')
    elif x < 5:
        colors_dtc.append('yellow')
    elif x < 7:
        colors_dtc.append('orange')
    else:
        colors_dtc.append('red')

fig1.add_trace(go.Bar(
    x=df_main['ticker'],
    y=df_main['yf_short_ratio_days'],
    text=[f"{x:.2f}일" for x in df_main['yf_short_ratio_days']],
    textposition='auto',
    marker_color=colors_dtc,
    hovertemplate='<b>%{x}</b><br>Days to Cover: %{y:.2f}일<br>청산 소요 기간<extra></extra>'
))

fig1.add_hline(y=3, line_dash="dash", line_color="green", annotation_text="정상 (3일)")
fig1.add_hline(y=5, line_dash="dash", line_color="orange", annotation_text="주의 (5일)")
fig1.add_hline(y=7, line_dash="dash", line_color="red", annotation_text="위험 (7일)")

fig1.update_layout(
    title='Days to Cover (Short Ratio): 공매도 청산 소요 일수 - Short Squeeze 핵심 지표',
    height=550,
    template='plotly_white',
    xaxis_title='종목',
    yaxis_title='Days to Cover (일)'
)

st.plotly_chart(fig1, use_container_width=True)

# 차트 2: Short % of Float
st.markdown("---")
st.subheader("📊 Chart 2: Short % of Float - 유통주식 대비 공매도 비율")

with st.expander("💡 Short % of Float 해석", expanded=False):
    st.markdown("""
    ### 🔍 의미:
    - 시장에서 거래 가능한 주식 중 몇 %가 공매도되었는가?
    - 시장 참여자들의 약세 심리 강도 측정
    
    ### 📊 해석 기준:
    - **<2%**: 매우 낮음 (시장의 강한 신뢰)
    - **2-5%**: 정상 범위 (건강한 시장)
    - **5-10%**: 주의 (공매도 세력 관심 증가)
    - **>10%**: 높음 (강한 약세 베팅, Squeeze 잠재력도 높음)
    
    ### 🎯 Days to Cover와 함께 보기:
    - Float >10% + DTC >5일 = 💥 극도로 위험(또는 기회!)
    - Float <5% + DTC <3일 = ✅ 안정적 종목
    """)

fig2 = go.Figure()

colors_float = ['green' if x < 2 else 'yellowgreen' if x < 5 else 'orange' if x < 10 else 'red'
               for x in df_main['yf_short_percent_float']]

fig2.add_trace(go.Bar(
    x=df_main['ticker'],
    y=df_main['yf_short_percent_float'],
    text=[f"{x:.2f}%" for x in df_main['yf_short_percent_float']],
    textposition='auto',
    marker_color=colors_float,
    hovertemplate='<b>%{x}</b><br>Short % Float: %{y:.2f}%<extra></extra>'
))

fig2.add_hline(y=2, line_dash="dash", line_color="green", annotation_text="매우 낮음 (2%)")
fig2.add_hline(y=5, line_dash="dash", line_color="yellowgreen", annotation_text="정상 (5%)")
fig2.add_hline(y=10, line_dash="dash", line_color="red", annotation_text="높음 (10%)")

fig2.update_layout(
    title='Short % of Float: 유통주식 대비 공매도 비율',
    xaxis_title='종목',
    yaxis_title='Short % of Float (%)',
    height=550,
    template='plotly_white'
)

st.plotly_chart(fig2, use_container_width=True)

# 차트 2-1: DP Ratio
st.markdown("---")
st.subheader("📊 Chart 2-1: DP Ratio - Dark Pool 거래 비중")

with st.expander("💡 DP Ratio (Dark Pool 비중) 해석", expanded=False):
    st.markdown("""
    ### 🔍 의미:
    - 전체 시장 거래량 중 장외(Dark Pool)에서 거래된 비중
    - 기관 투자자들의 시장 개입 강도 측정
    - 높을수록 기관들이 '은밀하게' 거래 중
    
    ### 📊 해석 기준:
    - **<40%**: 정상 범위 (일반적인 시장 거래)
    - **40-50%**: 기관 관심 증가 (모니터링 필요)
    - **>50%**: 기관 과열 (강한 기관 개입)
    - **>60%**: 극도 과열 (비정상적 수준)
    
    ### 🎯 실전 활용:
    - DP Ratio >50% + DP Short >55% = 기관 강한 약세
    - DP Ratio >50% + DP Short <45% = 기관 매집 가능성
    - DP Ratio <40% = 정상 시장, 기관 개입 낮음
    """)

fig2_1 = go.Figure()

colors_dp = []
for x in df_main['dp_ratio']:
    if x < 40:
        colors_dp.append('green')
    elif x < 50:
        colors_dp.append('yellowgreen')
    elif x < 60:
        colors_dp.append('orange')
    else:
        colors_dp.append('red')

fig2_1.add_trace(go.Bar(
    x=df_main['ticker'],
    y=df_main['dp_ratio'],
    text=[f"{x:.1f}%" for x in df_main['dp_ratio']],
    textposition='auto',
    marker_color=colors_dp,
    hovertemplate='<b>%{x}</b><br>DP Ratio: %{y:.2f}%<br>장외 거래 비중<extra></extra>'
))

fig2_1.add_hline(y=40, line_dash="dash", line_color="green", annotation_text="정상 (40%)")
fig2_1.add_hline(y=50, line_dash="dash", line_color="orange", annotation_text="과열 (50%)")
fig2_1.add_hline(y=60, line_dash="dash", line_color="red", annotation_text="극도과열 (60%)")

fig2_1.update_layout(
    title='DP Ratio (Dark Pool 비중): 전체 시장 대비 장외 거래 비중',
    height=550,
    template='plotly_white',
    xaxis_title='종목',
    yaxis_title='DP Ratio (%)'
)

st.plotly_chart(fig2_1, use_container_width=True)

# 차트 3: 공매도 종합 비교
st.markdown("---")
st.subheader("📊 Chart 3: 공매도 종합 비교 - Dark Pool vs 전체 시장")

with st.expander("💡 4가지 지표 종합 비교", expanded=False):
    st.markdown("""
    ### 1️⃣ DP Internal Short (파란색)
    - 장외 거래 중 공매도 비율
    - 기관의 은밀한 심리
    
    ### 2️⃣ DP Market Impact (회색)
    - 전체 시장 대비 장외 공매도 영향
    - 절대적 규모
    
    ### 3️⃣ FINRA/YF Ratio (보라색) ⭐
    - 오늘 발생한 공매도 / 전체 잔고
    - 공매도 "신선도" 측정
    - >50% = 신규 공매도 활발
    - <10% = 청산 진행
    
    ### 📈 종합 해석:
    - DP Internal 높음 + FINRA/YF 높음 = 신규 공매도 공격
    - DP Internal 높음 + FINRA/YF 낮음 = 청산 시작 (기회!)
    """)

fig3 = go.Figure()

fig3.add_trace(go.Bar(
    x=df_main['ticker'],
    y=df_main['dp_short_ratio'],
    name='DP Internal Short',
    marker_color='darkblue',
    text=df_main['dp_short_ratio'].round(1),
    textposition='auto'
))

fig3.add_trace(go.Bar(
    x=df_main['ticker'],
    y=df_main['dp_short_market_impact'],
    name='DP Market Impact',
    marker_color='gray',
    text=df_main['dp_short_market_impact'].round(1),
    textposition='auto'
))

fig3.add_trace(go.Bar(
    x=df_main['ticker'],
    y=df_main['finra_yf_short_ratio'],
    name='FINRA/YF Ratio (신선도)',
    marker_color='purple',
    text=df_main['finra_yf_short_ratio'].round(1),
    textposition='auto'
))

fig3.add_hline(y=50, line_dash="dash", line_color="orange", annotation_text="50% 기준")

fig3.update_layout(
    title='공매도 종합 비교: DP Internal vs Market Impact vs 신선도',
    barmode='group',
    height=550,
    template='plotly_white',
    xaxis_title='종목',
    yaxis_title='비율 (%)',
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)

st.plotly_chart(fig3, use_container_width=True)

# 차트 4: Days to Cover vs Short % Float
st.markdown("---")
st.subheader("📊 Chart 4: Days to Cover vs Short % Float - 위험도 매트릭스")

with st.expander("💡 2D 위험도 분석", expanded=False):
    st.markdown("""
    ### X축: Short % of Float (공매도 비율)
    ### Y축: Days to Cover (청산 소요 일수)
    
    ### 🔥 우상단 (빨강): 극도 위험!
    - Float 높음 + DTC 높음
    - Short Squeeze 폭발 가능 구간
    - 가장 변동성 높은 영역
    
    ### 💚 좌하단 (초록): 안정적
    - Float 낮음 + DTC 낮음
    - 공매도 압력 거의 없음
    - 펀더멘털 투자 적합
    
    **버블 크기** = DP 내부 공매도 비율  
    **버블 색상** = Days to Cover (빨간색일수록 위험)
    """)

fig4 = go.Figure()

fig4.add_trace(go.Scatter(
    x=df_main['yf_short_percent_float'],
    y=df_main['yf_short_ratio_days'],
    mode='markers+text',
    text=df_main['ticker'],
    textposition='top center',
    marker=dict(
        size=df_main['dp_short_ratio'] * 1.2,
        color=df_main['yf_short_ratio_days'],
        colorscale='RdYlGn_r',
        showscale=True,
        colorbar=dict(title="Days to Cover"),
        line=dict(width=1, color='black')
    ),
    hovertemplate='<b>%{text}</b><br>Float: %{x:.2f}%<br>DTC: %{y:.2f}일<extra></extra>'
))

fig4.add_vline(x=10, line_dash="dot", line_color="gray", line_width=2)
fig4.add_hline(y=5, line_dash="dot", line_color="gray", line_width=2)

fig4.add_annotation(x=15, y=8, text="<b>🔥 극도 위험<br>Squeeze Zone</b>",
                  showarrow=False, font=dict(color="darkred", size=12),
                  bgcolor="rgba(255,200,200,0.3)", bordercolor="red", borderwidth=2, borderpad=4)
fig4.add_annotation(x=3, y=2, text="<b>💚 안정적<br>Safe Zone</b>",
                  showarrow=False, font=dict(color="darkgreen", size=12),
                  bgcolor="rgba(200,255,200,0.3)", bordercolor="green", borderwidth=2, borderpad=4)

fig4.update_layout(
    title='Short Squeeze Risk Matrix: Float % vs Days to Cover',
    xaxis_title='Short % of Float (%)',
    yaxis_title='Days to Cover (일)',
    height=600,
    template='plotly_white'
)

st.plotly_chart(fig4, use_container_width=True)

# 차트 4-1: DP Ratio vs DP Short Ratio
st.markdown("---")
st.subheader("📊 Chart 4-1: DP Ratio vs DP Short Ratio - 기관 포지션 매트릭스")

with st.expander("💡 기관 투자자 포지션 4분면 분석", expanded=False):
    st.markdown("""
    ### X축: DP Ratio (장외 거래 비중) - 기관 개입 강도
    ### Y축: DP Short Ratio (장외 내부 공매도 비율) - 기관 심리
    
    ### 🔴 우상단 (빨강): 기관 강한 약세
    - DP Ratio >50% (강한 기관 개입)
    - DP Short >55% (장외에서 공매도 우위)
    - **해석**: 기관들이 적극적으로 공매도 중
    - **전략**: 하락 압력 주의, 역추세 매수 위험
    
    ### 💚 우하단 (초록): 기관 매집 가능성
    - DP Ratio >50% (강한 기관 개입)
    - DP Short <45% (장외에서 매수 우위)
    - **해석**: 기관들이 조용히 매수 중
    - **전략**: 상승 잠재력, 안정적 매수 기회
    
    ### ⚪ 좌측 (회색): 정상 범위
    - DP Ratio <50% (기관 개입 낮음)
    - **해석**: 일반 시장 거래 우세
    - **전략**: 펀더멘털 중심 투자
    
    **버블 크기** = Days to Cover (클수록 Short Squeeze 위험)  
    **버블 색상** = DP Short Ratio (빨간색일수록 약세)
    """)

fig4_1 = go.Figure()

fig4_1.add_trace(go.Scatter(
    x=df_main['dp_ratio'],
    y=df_main['dp_short_ratio'],
    mode='markers+text',
    text=df_main['ticker'],
    textposition='top center',
    marker=dict(
        size=df_main['yf_short_ratio_days'] * 8,
        color=df_main['dp_short_ratio'],
        colorscale='RdYlGn_r',
        showscale=True,
        colorbar=dict(title="DP Short<br>Ratio (%)"),
        line=dict(width=1, color='black'),
        cmin=40,
        cmax=60
    ),
    hovertemplate='<b>%{text}</b><br>DP Ratio: %{x:.1f}%<br>DP Short: %{y:.1f}%<br>DTC: ' + 
                  df_main['yf_short_ratio_days'].round(2).astype(str) + '일<extra></extra>'
))

fig4_1.add_vline(x=50, line_dash="dot", line_color="gray", line_width=2)
fig4_1.add_hline(y=50, line_dash="dot", line_color="gray", line_width=2)
fig4_1.add_vline(x=40, line_dash="dash", line_color="lightgray", line_width=1)
fig4_1.add_hline(y=45, line_dash="dash", line_color="lightgray", line_width=1)
fig4_1.add_hline(y=55, line_dash="dash", line_color="lightgray", line_width=1)

fig4_1.add_annotation(
    x=60, y=60,
    text="<b>🔴 기관 강한 약세<br>Active Short</b>",
    showarrow=False,
    font=dict(color="darkred", size=12),
    bgcolor="rgba(255,200,200,0.3)",
    bordercolor="red",
    borderwidth=2,
    borderpad=4
)

fig4_1.add_annotation(
    x=60, y=40,
    text="<b>💚 기관 매집<br>Accumulation</b>",
    showarrow=False,
    font=dict(color="darkgreen", size=12),
    bgcolor="rgba(200,255,200,0.3)",
    bordercolor="green",
    borderwidth=2,
    borderpad=4
)

fig4_1.add_annotation(
    x=35, y=50,
    text="<b>⚪ 정상 범위<br>Normal Market</b>",
    showarrow=False,
    font=dict(color="gray", size=11),
    bgcolor="rgba(240,240,240,0.3)",
    bordercolor="gray",
    borderwidth=1,
    borderpad=4
)

fig4_1.update_layout(
    title='기관 포지션 매트릭스: DP Ratio vs DP Short Ratio<br><sub>버블 크기 = Days to Cover (Short Squeeze 위험도)</sub>',
    xaxis_title='DP Ratio (%) - 장외 거래 비중',
    yaxis_title='DP Short Ratio (%) - 장외 내부 공매도 비율',
    height=650,
    template='plotly_white',
    xaxis=dict(range=[30, 70]),
    yaxis=dict(range=[25, 65])
)

st.plotly_chart(fig4_1, use_container_width=True)

# ==================== 차트 5-6: 시계열 분석 + 종목별 해석 ====================

st.markdown("---")
st.subheader("📊 Chart 5-6: 전체 종목 시계열 분석 - 60일 트렌드")

with st.expander("💡 시계열 차트 해석", expanded=False):
    st.markdown("""
    ### 1️⃣ 상단: DP 비중 Trend
    - 기관 개입 강도 변화
    - 상승 = 기관 활동 증가
    
    ### 2️⃣ 중단: DP 내부 공매도 Trend + 10일 평균
    - 장외 공매도 심리 변화
    - 10일 평균 대비 ±5%p = 중요한 변곡점
    - 급락(-5%p) = 🟢 청산 신호
    - 급등(+5%p) = 🔴 공매도 공격
    
    ### 📈 패턴 인식:
    - 중단 급락 = 공매도 청산 시작 (매수 기회)
    - 중단 급등 = 공매도 공격 시작 (주의)
    - 상단↑ + 중단↓ = 기관 매집
    - 상단↑ + 중단↑ = 기관 분산
    """)

# 종목 선택
selected_ticker = st.selectbox(
    "종목을 선택하세요:",
    options=[item['ticker'] for item in analysis_results],
    format_func=lambda x: f"{x} ({MAG7_STOCKS[x]})"
)

# 선택된 종목의 데이터 찾기
selected_item = next((item for item in analysis_results if item['ticker'] == selected_ticker), None)

if selected_item:
    ticker = selected_item['ticker']
    name = selected_item['name']
    df_hist = selected_item['history']
    
    st.info(f"🔍 {ticker} ({name}) - DTC: {selected_item['yf_short_ratio_days']:.2f}일, Float: {selected_item['yf_short_percent_float']:.2f}%")
    
    fig_ts = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        subplot_titles=(
            f"{ticker} - Dark Pool 비중 Trend",
            f"{ticker} - DP 내부 공매도 Trend + 10일 평균"
        ),
        vertical_spacing=0.12
    )
    
    # 차트 1: DP 비중
    fig_ts.add_trace(go.Scatter(
        x=df_hist['date'],
        y=df_hist['dp_ratio'],
        mode='lines+markers',
        name='DP 비중',
        line=dict(color='blue', width=2),
        showlegend=False,
        hovertemplate='날짜: %{x}<br>DP비중: %{y:.2f}%<extra></extra>'
    ), row=1, col=1)
    
    fig_ts.add_hline(y=50, line_dash="dot", line_color="red",
                    annotation_text="과열 (50%)", row=1, col=1)
    
    # 차트 2: DP 내부 공매도 + 10일 평균
    fig_ts.add_trace(go.Scatter(
        x=df_hist['date'],
        y=df_hist['dp_short_ratio'],
        mode='lines+markers',
        name='DP 내부 공매도',
        line=dict(color='orange', width=2),
        showlegend=False,
        hovertemplate='DP Short: %{y:.2f}%<extra></extra>'
    ), row=2, col=1)
    
    fig_ts.add_trace(go.Scatter(
        x=df_hist['date'],
        y=df_hist['dp_short_ratio_10d_avg'],
        mode='lines',
        name='10일 평균',
        line=dict(color='gray', dash='dot', width=1.5),
        showlegend=False,
        hovertemplate='10일평균: %{y:.2f}%<extra></extra>'
    ), row=2, col=1)
    
    fig_ts.add_hline(y=50, line_dash="dot", line_color="gray",
                    annotation_text="분기점", row=2, col=1)
    
    # 급락/급등 구간 하이라이트
    for i in range(1, len(df_hist)):
        prev = df_hist.iloc[i-1]
        curr = df_hist.iloc[i]
        change = curr['dp_short_ratio'] - prev['dp_short_ratio']
        
        if change < -5:
            fig_ts.add_vrect(
                x0=prev['date'], x1=curr['date'],
                fillcolor="green", opacity=0.15,
                layer="below", line_width=0,
                row=2, col=1
            )
        elif change > 5:
            fig_ts.add_vrect(
                x0=prev['date'], x1=curr['date'],
                fillcolor="red", opacity=0.15,
                layer="below", line_width=0,
                row=2, col=1
            )
    
    fig_ts.update_layout(
        height=700,
        title_text=f"📊 {ticker} ({name}) - 60일 트렌드 | DTC: {selected_item['yf_short_ratio_days']:.2f}일",
        template='plotly_white',
        hovermode='x unified'
    )
    
    fig_ts.update_xaxes(title_text="날짜", row=2, col=1)
    fig_ts.update_yaxes(title_text="DP 비중 (%)", row=1, col=1)
    fig_ts.update_yaxes(title_text="DP 내부 공매도 (%)", row=2, col=1)
    
    st.plotly_chart(fig_ts, use_container_width=True)
    
    # ==================== 60일 트렌드 종목별 해석 ====================
    
    st.markdown("---")
    st.subheader(f"📝 {ticker} ({name}) - 60일 트렌드 상세 분석")
    
    # 데이터 분석
    latest = df_hist.iloc[-1]
    oldest = df_hist.iloc[0]
    
    dp_ratio_change = latest['dp_ratio'] - oldest['dp_ratio']
    dp_short_change = latest['dp_short_ratio'] - oldest['dp_short_ratio']
    avg_dp_ratio = df_hist['dp_ratio'].mean()
    avg_dp_short = df_hist['dp_short_ratio'].mean()
    
    # 급락/급등 구간 카운트
    sharp_drop_count = 0
    sharp_rise_count = 0
    for i in range(1, len(df_hist)):
        change = df_hist.iloc[i]['dp_short_ratio'] - df_hist.iloc[i-1]['dp_short_ratio']
        if change < -5:
            sharp_drop_count += 1
        elif change > 5:
            sharp_rise_count += 1
    
    # 최근 추세 (최근 10일)
    recent_10d = df_hist.iloc[-10:]
    recent_trend = recent_10d['dp_short_ratio'].iloc[-1] - recent_10d['dp_short_ratio'].iloc[0]
    
    # 분석 결과 표시
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "60일 DP 비중 변화", 
            f"{latest['dp_ratio']:.1f}%",
            f"{dp_ratio_change:+.1f}%p"
        )
    
    with col2:
        st.metric(
            "60일 DP Short 변화", 
            f"{latest['dp_short_ratio']:.1f}%",
            f"{dp_short_change:+.1f}%p"
        )
    
    with col3:
        st.metric(
            "평균 DP 비중 (60일)", 
            f"{avg_dp_ratio:.1f}%"
        )
    
    with col4:
        st.metric(
            "평균 DP Short (60일)", 
            f"{avg_dp_short:.1f}%"
        )
    
    # 상세 해석
    st.markdown("### 📊 트렌드 해석")
    
    # DP 비중 트렌드 해석
    if dp_ratio_change > 10:
        dp_ratio_trend = "🔴 **급격히 상승** - 기관 개입이 크게 증가했습니다. 대형 거래가 장외에서 활발히 진행되고 있음을 의미합니다."
    elif dp_ratio_change > 5:
        dp_ratio_trend = "🟠 **상승** - 기관 개입이 증가 추세입니다."
    elif dp_ratio_change > -5:
        dp_ratio_trend = "⚪ **안정적** - 기관 개입 수준이 일정하게 유지되고 있습니다."
    elif dp_ratio_change > -10:
        dp_ratio_trend = "🟢 **하락** - 기관 개입이 감소 추세입니다."
    else:
        dp_ratio_trend = "💚 **급격히 하락** - 기관 개입이 크게 줄어들었습니다. 일반 시장 거래로 회귀하는 중입니다."
    
    st.write(f"**1️⃣ DP 비중 (기관 개입) 트렌드:**")
    st.write(dp_ratio_trend)
    
    # DP Short 트렌드 해석
    if dp_short_change > 10:
        dp_short_trend = "🔴 **급격히 상승** - 장외에서 공매도가 크게 증가했습니다. 기관들의 강한 약세 베팅이 진행 중입니다."
        strategy = "⚠️ **전략**: 하락 압력 강화 예상. 신중한 접근 필요."
    elif dp_short_change > 5:
        dp_short_trend = "🟠 **상승** - 공매도가 증가 추세입니다."
        strategy = "⚠️ **전략**: 공매도 증가 모니터링 필요."
    elif dp_short_change > -5:
        dp_short_trend = "⚪ **안정적** - 공매도 수준이 일정하게 유지되고 있습니다."
        strategy = "📊 **전략**: 중립적 관점 유지."
    elif dp_short_change > -10:
        dp_short_trend = "🟢 **하락** - 공매도가 감소 추세입니다. 청산 움직임이 보입니다."
        strategy = "💡 **전략**: 공매도 청산 가능성. 반등 기회 주시."
    else:
        dp_short_trend = "💚 **급격히 하락** - 공매도가 대폭 감소했습니다. 강력한 청산 신호입니다."
        strategy = "🚀 **전략**: 공매도 청산 진행 중. 상승 모멘텀 기대 가능."
    
    st.write(f"\n**2️⃣ DP 내부 공매도 트렌드:**")
    st.write(dp_short_trend)
    st.write(strategy)
    
    # 최근 추세
    st.write(f"\n**3️⃣ 최근 10일 동향:**")
    if recent_trend > 5:
        st.write("🔴 **최근 급등** - 지난 10일간 공매도가 급증했습니다. 단기 약세 압력 강화.")
    elif recent_trend > 2:
        st.write("🟠 **최근 상승** - 지난 10일간 공매도가 증가 중입니다.")
    elif recent_trend > -2:
        st.write("⚪ **최근 보합** - 지난 10일간 큰 변화 없이 안정적입니다.")
    elif recent_trend > -5:
        st.write("🟢 **최근 하락** - 지난 10일간 공매도가 감소 중입니다.")
    else:
        st.write("💚 **최근 급락** - 지난 10일간 공매도가 급감했습니다. 청산 진행 중.")
    
    # 급등/급락 이벤트
    st.write(f"\n**4️⃣ 60일간 주요 이벤트:**")
    st.write(f"- 🟢 공매도 급락 구간 (청산): **{sharp_drop_count}회**")
    st.write(f"- 🔴 공매도 급등 구간 (공격): **{sharp_rise_count}회**")
    
    if sharp_drop_count > sharp_rise_count:
        event_summary = "전반적으로 청산 움직임이 우세했습니다. 공매도 세력의 철수 신호로 해석 가능합니다."
    elif sharp_rise_count > sharp_drop_count:
        event_summary = "전반적으로 공매도 공격이 우세했습니다. 약세 베팅이 강화되었습니다."
    else:
        event_summary = "청산과 공격이 균형을 이루고 있습니다. 교착 상태입니다."
    
    st.write(f"   **→ {event_summary}**")
    
    # 종합 평가
    st.markdown("### 🎯 종합 평가 및 투자 전략")
    
    # 현재 상태 평가
    current_dtc = selected_item['yf_short_ratio_days']
    current_float = selected_item['yf_short_percent_float']
    current_dp_ratio = latest['dp_ratio']
    current_dp_short = latest['dp_short_ratio']
    
    # 시나리오 판단
    if current_dtc > 5 and dp_short_change < -5:
        scenario = "🔥 **Short Squeeze 가능성**"
        evaluation = f"""
        DTC {current_dtc:.2f}일로 높은 상태에서 60일간 공매도가 {abs(dp_short_change):.1f}%p 감소했습니다.
        공매도 세력이 청산하기 시작했으나 아직 높은 잔고가 남아있어 연쇄 청산 가능성이 있습니다.
        
        **투자 전략**: 
        - 공격적 투자자: 반등 초기 진입 고려
        - 보수적 투자자: 추가 청산 신호 확인 후 진입
        - 리스크: 높음 (변동성 큼)
        """
    elif current_dp_ratio > 50 and current_dp_short < 45 and dp_short_change < 0:
        scenario = "💚 **기관 매집 시나리오**"
        evaluation = f"""
        DP 비중 {current_dp_ratio:.1f}%로 기관 개입이 높지만, DP Short {current_dp_short:.1f}%로 매수가 우세합니다.
        60일간 공매도가 감소 추세로, 기관들이 조용히 매집 중일 가능성이 있습니다.
        
        **투자 전략**:
        - 중장기 관점에서 안정적 매수 기회
        - 분할 매수 전략 권장
        - 리스크: 중간
        """
    elif current_dp_short > 55 and dp_short_change > 5:
        scenario = "🔴 **공매도 공격 진행**"
        evaluation = f"""
        DP Short {current_dp_short:.1f}%로 높고, 60일간 {dp_short_change:.1f}%p 증가했습니다.
        기관들이 적극적으로 공매도 포지션을 늘리고 있어 하락 압력이 강화될 수 있습니다.
        
        **투자 전략**:
        - 신규 매수 보류 권장
        - 기존 보유자는 손절 라인 설정
        - 역추세 매수는 고위험
        - 리스크: 높음
        """
    elif current_dtc < 3 and current_float < 5:
        scenario = "✅ **건강한 종목**"
        evaluation = f"""
        DTC {current_dtc:.2f}일, Float {current_float:.2f}%로 공매도 압력이 낮습니다.
        60일 트렌드도 안정적이어서 건전한 거래 환경입니다.
        
        **투자 전략**:
        - 펀더멘털 분석 기반 투자 적합
        - 안정적 장기 투자 가능
        - 리스크: 낮음
        """
    else:
        scenario = "⚪ **관망 필요**"
        evaluation = f"""
        현재 명확한 방향성이 보이지 않는 중립적 상황입니다.
        추가적인 촉매(호재/악재)를 기다리는 것이 좋습니다.
        
        **투자 전략**:
        - 관망 또는 소량 분할 매수
        - 시장 상황 모니터링
        - 리스크: 중간
        """
    
    st.info(f"**{scenario}**\n\n{evaluation}")
    
    # 주의사항
    st.warning("""
    ⚠️ **투자 주의사항**
    
    이 분석은 기술적 지표 기반이며, 다음 사항을 반드시 고려하세요:
    - 기업의 펀더멘털 (실적, 재무상태)
    - 산업 동향 및 경쟁 환경
    - 거시경제 상황
    - 개별 이슈 및 뉴스
    
    투자 결정은 본인의 책임이며, 이 분석은 참고 자료일 뿐입니다.
    """)

# ==================== 최종 요약 및 인사이트 ====================

st.markdown("---")
st.header("✨ 최종 분석 요약 - 핵심 인사이트")

# 1. Short Squeeze 고위험 종목
squeeze_risk = df_main[(df_main['yf_short_ratio_days'] > 5) & (df_main['yf_short_percent_float'] > 10)]
if not squeeze_risk.empty:
    st.subheader("🔥 Short Squeeze 고위험 종목 (DTC >5일 & Float >10%)")
    for _, row in squeeze_risk.iterrows():
        dtc_change = "청산 중" if row['dp_short_change_pct'] < -5 else "유지" if abs(row['dp_short_change_pct']) < 5 else "증가 중"
        st.write(f"**{row['ticker']}**: DTC {row['yf_short_ratio_days']:.2f}일, Float {row['yf_short_percent_float']:.2f}% - {dtc_change}")

# 2. 청산 진행 중
squeeze_starting = df_main[(df_main['yf_short_ratio_days'] > 5) & (df_main['dp_short_change_pct'] < -5)]
if not squeeze_starting.empty:
    st.subheader("🟢 청산 시작 종목 (DTC >5일 & DP Short 급락)")
    for _, row in squeeze_starting.iterrows():
        finra_status = "청산 진행" if row['finra_yf_short_ratio'] < 10 else "정상"
        st.write(f"**{row['ticker']}**: {row['dp_short_change_pct']:+.2f}%p 급락, FINRA/YF {row['finra_yf_short_ratio']:.1f}% ({finra_status})")

# 3. 신규 공매도 공격
new_short_attack = df_main[(df_main['dp_short_change_pct'] > 5) & (df_main['finra_yf_short_ratio'] > 50)]
if not new_short_attack.empty:
    st.subheader("🔴 신규 공매도 공격 진행 (DP Short 급등 & FINRA/YF >50%)")
    for _, row in new_short_attack.iterrows():
        st.write(f"**{row['ticker']}**: {row['dp_short_change_pct']:+.2f}%p 급등, FINRA/YF {row['finra_yf_short_ratio']:.1f}%")

# 4. 건강한 종목
healthy = df_main[(df_main['yf_short_ratio_days'] < 3) & (df_main['yf_short_percent_float'] < 5)]
if not healthy.empty:
    st.subheader("✅ 건강한 종목 (DTC <3일 & Float <5%)")
    for _, row in healthy.iterrows():
        st.write(f"**{row['ticker']}**: DTC {row['yf_short_ratio_days']:.2f}일, Float {row['yf_short_percent_float']:.2f}%")

# 5. 기관 매집 의심
accumulation = df_main[(df_main['dp_ratio'] > 50) & (df_main['dp_short_ratio'] < 45)]
if not accumulation.empty:
    st.subheader("💚 기관 매집 가능성 (DP >50% & DP Short <45%)")
    for _, row in accumulation.iterrows():
        st.write(f"**{row['ticker']}**: DP {row['dp_ratio']:.1f}%, DP Short {row['dp_short_ratio']:.1f}%")

# ==================== 하단 정보 ====================

st.markdown("---")
st.info("""
📊 **데이터 출처:**
- Yahoo Finance: Days to Cover, Short % of Float (표준 지표)
- FINRA: Dark Pool 거래 데이터 (장외 거래 분석)

🕐 **분석 완료:** """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

with st.expander("💡 투자 시 주의사항", expanded=False):
    st.warning("""
    1. Days to Cover가 높다고 무조건 오르는 것은 아닙니다.
    2. 공매도 세력이 맞을 수도 있으며, 주가는 계속 하락할 수 있습니다.
    3. 하지만 일단 반등이 시작되면, DTC가 높을수록 Short Squeeze로 폭등할 가능성이 큽니다.
    4. 이 분석은 기술적 지표일 뿐, 펀더멘털 분석과 병행해야 합니다.
    5. 투자 결정은 본인의 책임이며, 이 분석은 참고 자료일 뿁입니다.
    """)
