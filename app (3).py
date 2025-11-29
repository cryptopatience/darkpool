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
    page_title="MAG 7+2 Dark Pool 분석",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== 설정 및 종목 리스트 ====================
MAG7_STOCKS = {
    'AAPL': 'Apple', 'MSFT': 'Microsoft', 'GOOGL': 'Alphabet',
    'AMZN': 'Amazon', 'NVDA': 'NVIDIA', 'META': 'Meta',
    'TSLA': 'Tesla', 'COIN': 'Coinbase', 'IBIT': 'Bitcoin ETF'
}

# ==================== 데이터 수집 함수 ====================

@st.cache_data(ttl=3600)  # 1시간 캐시
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

@st.cache_data(ttl=3600)  # 1시간 캐시
def get_finra_data_full(ticker, days_back=60):
    """
    FINRA 데이터 수집 및 핵심 지표 3가지 계산 (60일 history 포함)
    """
    try:
        today = datetime.now()
        data_list = []

        # Yahoo 전체 거래량 (분모용)
        market_volumes = get_market_volume(ticker, days_back)
        if market_volumes is None or market_volumes.empty: 
            return None

        # FINRA 데이터 루프 (최근 N일)
        for days in range(days_back + 5):  # 휴일 고려 여유분
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

                        # Yahoo Volume 매칭
                        market_vol = 0
                        if date_key in market_volumes.index:
                            market_vol = market_volumes.loc[date_key]
                        else:
                            for idx in market_volumes.index:
                                if idx.strftime('%Y-%m-%d') == date_key:
                                    market_vol = market_volumes[idx]
                                    break

                        if market_vol > 0:
                            # 지표 계산
                            dp_ratio = (finra_total / market_vol) * 100
                            dp_short_ratio = (finra_short / finra_total) * 100
                            total_short_ratio = (finra_short / market_vol) * 100

                            # 보정 (데이터 오차)
                            if dp_ratio > 100: 
                                dp_ratio = 100

                            data_list.append({
                                'date': date_key,
                                'dp_ratio': round(dp_ratio, 2),
                                'dp_short_ratio': round(dp_short_ratio, 2),
                                'total_short_ratio': round(total_short_ratio, 2),
                                'market_vol': market_vol
                            })

                if len(data_list) >= days_back: 
                    break
            except:
                continue

        if not data_list: 
            return None

        df_hist = pd.DataFrame(data_list).sort_values('date')

        # 10일 평균 및 변화율 계산
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
            'total_short_ratio': latest['total_short_ratio'],
            'dp_short_10d_avg': latest['dp_short_ratio_10d_avg'],
            'dp_short_change_pct': dp_short_change,
            'history': df_hist
        }

    except Exception as e:
        return None

def create_signal(row):
    """시그널 생성 함수"""
    if row['dp_short_change_pct'] < -5:
        return '🟢 급락 (청산 신호)'
    if row['dp_ratio'] > 50 and row['dp_short_ratio'] > 55:
        return '🔴 기관 강한 약세 포지션'
    if row['dp_ratio'] > 50 and row['dp_short_ratio'] < 45:
        return '💚 기관 매집 가능성'
    if row['dp_vs_total'] > 5:
        return '⚠️ DP에 공매도 집중'
    if row['dp_vs_total'] < -5:
        return '✅ 거래소에 공매도 집중'
    return '⚪ 관망/정상'

# ==================== 메인 앱 ====================

def main():
    # 타이틀
    st.title("🚀 MAG 7+2: Dark Pool & Short Interest 심층 분석")
    st.markdown("---")
    
    # 사이드바
    with st.sidebar:
        st.header("⚙️ 설정")
        days_back = st.slider("분석 기간 (일)", 30, 90, 60)
        auto_refresh = st.checkbox("자동 새로고침 (1시간)", value=False)
        
        st.markdown("---")
        st.markdown("### 📚 신호 해석 가이드")
        st.markdown("""
        - **🔴 기관 강한 약세**: DP Ratio >50% & DP Short >55%
        - **💚 기관 매집 가능성**: DP Ratio >50% & DP Short <45%
        - **🟢 급락 (청산)**: 10일 대비 -5%p 이상
        - **⚠️ DP 공매도 집중**: DP Short > Total Short +5%p
        - **✅ 거래소 공매도**: Total Short > DP Short +5%p
        """)
    
    # 데이터 로딩
    if st.button("🔄 데이터 새로고침") or auto_refresh:
        st.cache_data.clear()
    
    with st.spinner("데이터 수집 중..."):
        analysis_results = []
        progress_bar = st.progress(0)
        
        for idx, ticker in enumerate(MAG7_STOCKS.keys()):
            res = get_finra_data_full(ticker, days_back=days_back)
            if res:
                analysis_results.append(res)
            progress_bar.progress((idx + 1) / len(MAG7_STOCKS))
        
        progress_bar.empty()
    
    if not analysis_results:
        st.error("데이터를 가져올 수 없습니다. 잠시 후 다시 시도해주세요.")
        return
    
    # 메인 데이터프레임 생성
    df_main = pd.DataFrame([{k:v for k,v in r.items() if k != 'history'} for r in analysis_results])
    df_main['dp_vs_total'] = (df_main['dp_short_ratio'] - df_main['total_short_ratio']).round(2)
    df_main['Signal'] = df_main.apply(create_signal, axis=1)
    df_main = df_main.sort_values('dp_ratio', ascending=False)
    
    # ==================== 요약 통계 ====================
    st.header("📊 전체 시장 개요")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        avg_dp = df_main['dp_ratio'].mean()
        st.metric("평균 Dark Pool Ratio", f"{avg_dp:.1f}%")
    
    with col2:
        avg_short = df_main['dp_short_ratio'].mean()
        st.metric("평균 DP Short Ratio", f"{avg_short:.1f}%")
    
    with col3:
        bullish_count = len(df_main[df_main['Signal'].str.contains('매집|청산')])
        st.metric("강세 신호 종목", f"{bullish_count}개")
    
    with col4:
        bearish_count = len(df_main[df_main['Signal'].str.contains('약세|집중')])
        st.metric("약세 신호 종목", f"{bearish_count}개")
    
    st.markdown("---")
    
    # ==================== 통합 테이블 ====================
    st.header("📋 통합 상세 비교 테이블")
    
    df_display = df_main.copy()
    df_display = df_display.rename(columns={
        'ticker': '티커',
        'name': '종목명',
        'dp_ratio': 'DP Ratio (%)',
        'dp_short_ratio': 'DP Short (%)',
        'dp_short_10d_avg': 'DP 10일 평균',
        'dp_short_change_pct': '1일 vs 10일',
        'total_short_ratio': 'Total Short (%)',
        'dp_vs_total': 'DP vs Total',
        'Signal': '신호'
    })
    
    # 컬럼 포맷팅
    display_cols = ['티커', '종목명', 'DP Ratio (%)', 'DP Short (%)', 
                    'DP 10일 평균', '1일 vs 10일', 'Total Short (%)', 
                    'DP vs Total', '신호']
    
    # 스타일링
    def highlight_signal(row):
        if '🔴' in str(row['신호']):
            return ['background-color: #ffcccc'] * len(row)
        elif '💚' in str(row['신호']) or '🟢' in str(row['신호']):
            return ['background-color: #ccffcc'] * len(row)
        elif '⚠️' in str(row['신호']):
            return ['background-color: #fff3cd'] * len(row)
        return [''] * len(row)
    
    st.dataframe(
        df_display[display_cols].style.apply(highlight_signal, axis=1).format({
            'DP Ratio (%)': '{:.2f}%',
            'DP Short (%)': '{:.2f}%',
            'DP 10일 평균': '{:.2f}%',
            '1일 vs 10일': '{:+.2f}%p',
            'Total Short (%)': '{:.2f}%',
            'DP vs Total': '{:+.2f}%p'
        }),
        use_container_width=True,
        height=400
    )
    
    st.markdown("---")
    
    # ==================== 차트 섹션 ====================
    st.header("📈 시각화 분석")
    
    # 탭으로 구성
    tab1, tab2, tab3, tab4 = st.tabs([
        "Dark Pool Ratio", 
        "Short 비교", 
        "4분면 분석", 
        "시계열 분석"
    ])
    
    # Tab 1: Dark Pool Ratio
    with tab1:
        st.subheader("Dark Pool Ratio (기관의 장외 거래 장악력)")
        
        colors_dp = ['green' if x < 40 else 'orange' if x < 50 else 'red' 
                     for x in df_main['dp_ratio']]
        
        fig1 = go.Figure()
        fig1.add_trace(go.Bar(
            x=df_main['ticker'], 
            y=df_main['dp_ratio'],
            text=[f"{x:.1f}%" for x in df_main['dp_ratio']], 
            textposition='auto',
            marker_color=colors_dp, 
            name='Dark Pool %'
        ))
        
        fig1.add_hline(y=50, line_dash="dash", line_color="red", 
                      annotation_text="기관 과열 (50%)")
        fig1.add_hline(y=40, line_dash="dash", line_color="green", 
                      annotation_text="정상 범위 (40%)")
        
        fig1.update_layout(
            title='Dark Pool Ratio (FINRA Vol / Total Vol)', 
            height=500, 
            template='plotly_white',
            xaxis_title='종목',
            yaxis_title='Dark Pool Ratio (%)'
        )
        
        st.plotly_chart(fig1, use_container_width=True)
    
    # Tab 2: Short 비교
    with tab2:
        st.subheader("은밀한 공매도(장외) vs 공개된 공매도 비교")
        
        # Short 비교 해석 가이드
        with st.expander("📚 Short 비교 해석 가이드 (클릭하여 보기)", expanded=False):
            st.markdown("""
            ### 📊 Dark Pool Short vs Total Short 분석
            
            이 차트는 **장외(Dark Pool) 공매도**와 **전체 시장 공매도**를 비교하여 
            기관들이 어디서 공매도를 실행하는지 파악합니다.
            
            #### 📈 지표 설명
            
            | 지표 | 의미 | 계산 방식 |
            |:---|:---|:---|
            | **Dark Pool Short %** (파란색) | 장외 거래 중 공매도 비율 | (Dark Pool 공매도량 / Dark Pool 전체 거래량) × 100 |
            | **Total Short %** (회색) | 전체 시장 대비 공매도 비율 | (Dark Pool 공매도량 / 전체 시장 거래량) × 100 |
            
            #### 🔍 해석 방법
            
            **1. Dark Pool Short > Total Short (파란색 > 회색)**
            - **의미**: 장외 거래에서 공매도가 집중되고 있음
            - **시사점**: 기관들이 **비공개적으로** 공매도 포지션 구축 중
            - **신호**: ⚠️ 은밀한 약세 베팅 (주의 필요)
            
            **2. Total Short > Dark Pool Short (회색 > 파란색)**
            - **의미**: 거래소에서 공매도가 더 많이 발생
            - **시사점**: 공매도가 **투명하게** 공개 시장에서 이루어짐
            - **신호**: ✅ 투명한 거래 (상대적으로 건전)
            
            **3. 두 지표 모두 높음 (>50%)**
            - **의미**: 장외/거래소 모두에서 강한 공매도 압력
            - **시사점**: 시장 전반적인 약세 심리
            - **신호**: 🔴 강한 하락 베팅
            
            **4. 두 지표 모두 낮음 (<45%)**
            - **의미**: 공매도 압력이 약함
            - **시사점**: 매수세가 우위이거나 균형 상태
            - **신호**: 💚 건전한 매수 심리
            
            #### 💡 실전 활용 팁
            
            - **DP Short - Total Short 차이**가 클수록 장외에서 은밀한 공매도가 진행 중
            - **DP Short Ratio > 55%**: 기관의 강한 약세 포지션 의심
            - **Total Short Ratio > DP Short + 5%p**: 투명한 공개 시장 공매도
            """)
        
        # 데이터 계산
        df_main['dp_vs_total_diff'] = df_main['dp_short_ratio'] - df_main['total_short_ratio']
        
        fig2 = go.Figure()
        
        # 호버 텍스트 생성
        hover_text_dp = []
        hover_text_total = []
        
        for idx, row in df_main.iterrows():
            diff = row['dp_vs_total_diff']
            if diff > 5:
                signal = "⚠️ 장외에 공매도 집중 (비밀 포지션)"
            elif diff < -5:
                signal = "✅ 거래소에 공매도 집중 (투명)"
            else:
                signal = "⚪ 균형적 분포"
            
            hover_dp = (
                f"<b>{row['ticker']} - Dark Pool Short</b><br>"
                f"DP Short Ratio: {row['dp_short_ratio']:.2f}%<br>"
                f"Total Short Ratio: {row['total_short_ratio']:.2f}%<br>"
                f"차이: {diff:+.2f}%p<br>"
                f"<br>{signal}"
            )
            hover_total = (
                f"<b>{row['ticker']} - Total Market Short</b><br>"
                f"Total Short Ratio: {row['total_short_ratio']:.2f}%<br>"
                f"DP Short Ratio: {row['dp_short_ratio']:.2f}%<br>"
                f"차이: {-diff:+.2f}%p<br>"
                f"<br>{signal}"
            )
            
            hover_text_dp.append(hover_dp)
            hover_text_total.append(hover_total)
        
        fig2.add_trace(go.Bar(
            x=df_main['ticker'], 
            y=df_main['dp_short_ratio'],
            name='Dark Pool Short % (장외 내부)',
            marker_color='darkblue',
            hovertext=hover_text_dp,
            hoverinfo='text'
        ))
        
        fig2.add_trace(go.Bar(
            x=df_main['ticker'], 
            y=df_main['total_short_ratio'],
            name='Total Short % (전체 시장)',
            marker_color='gray',
            hovertext=hover_text_total,
            hoverinfo='text'
        ))
        
        # 기준선 추가
        fig2.add_hline(y=50, line_dash="dash", line_color="red", 
                      annotation_text="공매도 우위 기준 (50%)", 
                      annotation_position="right")
        
        fig2.update_layout(
            title='Dark Pool Short Ratio vs Total Market Short Ratio',
            barmode='group', 
            height=500, 
            template='plotly_white',
            xaxis_title='종목',
            yaxis_title='Short Ratio (%)',
            hovermode='closest'
        )
        
        st.plotly_chart(fig2, use_container_width=True)
        
        # Short 패턴 분석 요약
        st.markdown("### 📊 Short 패턴 분석")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            hidden_short = df_main[df_main['dp_vs_total_diff'] > 5]
            st.warning(f"**⚠️ 장외 공매도 집중**\n\n{', '.join(hidden_short['ticker'].tolist()) if not hidden_short.empty else '없음'}")
        
        with col2:
            transparent_short = df_main[df_main['dp_vs_total_diff'] < -5]
            st.success(f"**✅ 투명한 공매도**\n\n{', '.join(transparent_short['ticker'].tolist()) if not transparent_short.empty else '없음'}")
        
        with col3:
            high_short = df_main[df_main['dp_short_ratio'] > 55]
            st.error(f"**🔴 강한 공매도 압력**\n\n{', '.join(high_short['ticker'].tolist()) if not high_short.empty else '없음'}")
    
    # Tab 3: 4분면 분석
    with tab3:
        st.subheader("Market Sentiment Map (4분면 분석)")
        
        # 4분면 해석 가이드
        with st.expander("📚 4분면 해석 가이드 (클릭하여 보기)", expanded=False):
            st.markdown("""
            ### 📈 Dark Pool Sentiment Map 분석
            
            이 4분면 차트는 **Dark Pool Ratio (DP Ratio)**와 **Dark Pool Short Ratio (DP Short Ratio)** 
            두 가지 주요 지표를 사용하여 기관 투자자들의 현재 포지션과 심리를 시각화합니다.
            
            #### 📊 차트 축 및 분면 해석
            
            | 분면 | X축 (DP Ratio) | Y축 (DP Short Ratio) | 시장 심리 (해석) |
            |:---|:---|:---|:---|
            | **우상단 (Distribution)** | **높음** (기관 개입 강함) | **높음** (공매도 심리 강함) | **기관의 매도/공매도 집중** (가장 부정적 신호) |
            | **좌상단** | **낮음** (기관 개입 약함) | **높음** (공매도 심리 강함) | **개인 주도 공매도 또는 관망 속 공매도** |
            | **우하단 (Accumulation)** | **높음** (기관 개입 강함) | **낮음** (공매도 심리 약함) | **기관의 매집/매수 집중** (가장 긍정적 신호) |
            | **좌하단 (개인/관망)** | **낮음** (기관 개입 약함) | **낮음** (공매도 심리 약함) | **기관의 관심 부족** (개인 주도 거래) |
            
            #### 💡 투자 시사점
            
            - **우하단 (매집 영역)**: 기관들이 장외에서 적극적으로 매수 포지션 구축 → **긍정적 신호**
            - **우상단 (분배 영역)**: 기관들이 장외에서 강력한 공매도 포지션 구축 → **부정적 신호**
            - **좌하단 (관망 영역)**: 기관 활동이 과열되지 않고 안정적인 범위 → **중립적 신호**
            
            ⚠️ **주의**: 이 분석은 장외(Dark Pool) 거래에 국한된 기관의 움직임만을 나타내므로, 
            최종 투자 결정은 전체 거래소의 가격, 기술적 지표, 뉴스 등을 종합하여 판단해야 합니다.
            """)
        
        # 분면별 설명을 위한 호버 텍스트 생성
        def get_quadrant_info(dp_ratio, dp_short_ratio):
            """각 분면에 대한 상세 설명 반환"""
            if dp_ratio >= 45 and dp_short_ratio >= 50:
                return "🔴 Distribution (분배): 기관의 매도/공매도 집중 - 부정적 신호"
            elif dp_ratio >= 45 and dp_short_ratio < 50:
                return "💚 Accumulation (매집): 기관의 매수 집중 - 긍정적 신호"
            elif dp_ratio < 45 and dp_short_ratio >= 50:
                return "⚠️ 개인 주도 공매도: 기관 개입 약함, 공매도 심리 강함"
            else:
                return "⚪ 개인/관망: 기관 개입 약함, 정상 범위"
        
        # 각 종목에 대한 호버 텍스트 생성
        hover_texts = []
        for idx, row in df_main.iterrows():
            quadrant = get_quadrant_info(row['dp_ratio'], row['dp_short_ratio'])
            hover_text = (
                f"<b>{row['ticker']} ({row['name']})</b><br>"
                f"DP Ratio: {row['dp_ratio']:.2f}%<br>"
                f"DP Short Ratio: {row['dp_short_ratio']:.2f}%<br>"
                f"<br>{quadrant}"
            )
            hover_texts.append(hover_text)
        
        fig3 = go.Figure()
        
        fig3.add_trace(go.Scatter(
            x=df_main['dp_ratio'],
            y=df_main['dp_short_ratio'],
            mode='markers+text',
            text=df_main['ticker'],
            textposition='top center',
            marker=dict(
                size=df_main['dp_ratio'] * 0.8,
                color=df_main['dp_short_ratio'],
                colorscale='RdYlGn_r',
                showscale=True,
                colorbar=dict(title="Short Ratio")
            ),
            hovertext=hover_texts,
            hoverinfo='text'
        ))
        
        # 분면 구분선
        fig3.add_vline(x=45, line_dash="dot", line_color="gray", line_width=2)
        fig3.add_hline(y=50, line_dash="dot", line_color="gray", line_width=2)
        
        # 분면 라벨 (배경색 추가)
        fig3.add_annotation(
            x=55, y=70, 
            text="<b>매도/공매도</b><br>(Distribution)<br>🔴 부정적", 
            showarrow=False, 
            font=dict(color="darkred", size=12),
            bgcolor="rgba(255,200,200,0.3)",
            bordercolor="red",
            borderwidth=1,
            borderpad=4
        )
        fig3.add_annotation(
            x=55, y=30, 
            text="<b>매집</b><br>(Accumulation)<br>💚 긍정적", 
            showarrow=False, 
            font=dict(color="darkgreen", size=12),
            bgcolor="rgba(200,255,200,0.3)",
            bordercolor="green",
            borderwidth=1,
            borderpad=4
        )
        fig3.add_annotation(
            x=35, y=30, 
            text="<b>개인/관망</b><br>⚪ 중립", 
            showarrow=False, 
            font=dict(color="gray", size=12),
            bgcolor="rgba(220,220,220,0.3)",
            bordercolor="gray",
            borderwidth=1,
            borderpad=4
        )
        fig3.add_annotation(
            x=35, y=70, 
            text="<b>개인 공매도</b><br>⚠️ 주의", 
            showarrow=False, 
            font=dict(color="orange", size=12),
            bgcolor="rgba(255,240,200,0.3)",
            bordercolor="orange",
            borderwidth=1,
            borderpad=4
        )
        
        fig3.update_layout(
            title='X축: 기관 관심도 (DP Ratio) vs Y축: 공매도 심리 (DP Short Ratio)',
            xaxis_title='Dark Pool Ratio (%) - 높을수록 기관 개입 강함',
            yaxis_title='Dark Pool Short Ratio (%) - 높을수록 하락 베팅',
            height=600, 
            template='plotly_white',
            hovermode='closest'
        )
        
        st.plotly_chart(fig3, use_container_width=True)
        
        # 현재 포지션 요약
        st.markdown("### 📊 현재 포지션 요약")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            accumulation = df_main[(df_main['dp_ratio'] >= 45) & (df_main['dp_short_ratio'] < 50)]
            st.success(f"**💚 매집 (Accumulation)**\n\n{', '.join(accumulation['ticker'].tolist()) if not accumulation.empty else '없음'}")
        
        with col2:
            distribution = df_main[(df_main['dp_ratio'] >= 45) & (df_main['dp_short_ratio'] >= 50)]
            st.error(f"**🔴 분배 (Distribution)**\n\n{', '.join(distribution['ticker'].tolist()) if not distribution.empty else '없음'}")
        
        with col3:
            neutral = df_main[df_main['dp_ratio'] < 45]
            st.info(f"**⚪ 개인/관망**\n\n{', '.join(neutral['ticker'].tolist()) if not neutral.empty else '없음'}")
    
    # Tab 4: 시계열 분석
    with tab4:
        st.subheader("전체 종목 상세 시계열 분석")
        
        # 시계열 해석 가이드
        with st.expander("📚 시계열 분석 해석 가이드 (클릭하여 보기)", expanded=False):
            st.markdown("""
            ### 📈 시계열 차트 분석 방법
            
            이 차트는 선택한 종목의 **Dark Pool 활동**과 **공매도 심리**를 시간에 따라 추적합니다.
            
            ---
            
            #### 📊 차트 1: Dark Pool Ratio Trend (상단)
            
            **의미**: 전체 거래량 중 장외 거래가 차지하는 비율의 변화
            
            | 상황 | 해석 | 시그널 |
            |:---|:---|:---|
            | **상승 추세** | 기관의 장외 거래 참여 증가 | 🔵 기관 관심도 증가 |
            | **하락 추세** | 공개 거래소 거래 비중 증가 | ⚪ 개인 투자자 주도 |
            | **50% 돌파** (빨간선) | 장외 거래가 전체의 절반 초과 | 🔴 기관 과열 (주의) |
            | **40% 이하** (초록선) | 정상적인 시장 거래 구조 | 💚 건전한 시장 |
            
            **트렌드 분석**:
            - 급격한 상승: 대형 기관의 긴급 포지션 조정 가능성
            - 급격한 하락: 기관 이탈 또는 소매 투자자 유입
            - 횡보: 안정적인 기관-개인 거래 균형
            
            ---
            
            #### 📊 차트 2: Dark Pool Short Ratio Trend (하단)
            
            **의미**: 장외 거래 중 공매도가 차지하는 비율의 변화
            
            | 상황 | 해석 | 시그널 |
            |:---|:---|:---|
            | **50% 이상** | 장외 거래의 절반 이상이 공매도 | 🔴 강한 약세 심리 |
            | **50% 미만** | 장외 거래의 절반 이상이 매수 | 💚 강한 강세 심리 |
            | **급락** (10일 평균 대비 -5%p 이상) | 공매도 청산 시작 | 🟢 **상승 전환 신호!** |
            | **급등** (10일 평균 대비 +5%p 이상) | 공매도 공격 시작 | 🔴 **하락 압력 증가** |
            
            **10일 평균선 (회색 점선)**:
            - 현재값이 평균선 위: 단기적으로 공매도 증가 중
            - 현재값이 평균선 아래: 단기적으로 공매도 감소 중
            - 평균선과의 격차: 변화 강도 (격차가 클수록 급격한 변화)
            
            ---
            
            #### 🎯 핵심 패턴 인식
            
            **1. 공매도 청산 패턴 (매수 기회)**
            - DP Short Ratio가 높은 수준(>55%)에서 급락
            - 10일 평균 대비 -5%p 이상 하락
            - → 💡 공매도 세력의 청산, 주가 상승 전환점 가능
            
            **2. 공매도 공격 패턴 (매도 주의)**
            - DP Short Ratio가 급등하며 50% 돌파
            - DP Ratio도 동시에 상승 (기관 참여 증가)
            - → ⚠️ 기관의 대규모 공매도 공격 시작
            
            **3. 매집 패턴 (긍정적)**
            - DP Ratio 상승 + DP Short Ratio 하락
            - DP Short Ratio가 지속적으로 50% 이하 유지
            - → 💚 기관이 장외에서 조용히 매수 중
            
            **4. 분산 패턴 (부정적)**
            - DP Ratio 상승 + DP Short Ratio 상승
            - DP Short Ratio가 50% 이상으로 상승
            - → 🔴 기관이 장외에서 공매도 및 매도 증가
            
            ---
            
            #### 💡 실전 활용 예시
            
            **시나리오 1**: TSLA의 DP Ratio 50% → 58% 상승, DP Short 55% → 48% 하락
            - **해석**: 기관 개입은 증가했으나 공매도는 감소 = **매집 신호**
            - **전략**: 분할 매수 또는 포지션 유지
            
            **시나리오 2**: COIN의 DP Short 45% → 58% 급등, 10일 평균 대비 +8%p
            - **해석**: 급격한 공매도 공격 시작 = **약세 신호**
            - **전략**: 관망 또는 손절 검토
            
            **시나리오 3**: NVDA의 DP Short 60% → 52% 급락, 10일 평균 대비 -7%p
            - **해석**: 공매도 청산 시작 = **반등 신호**
            - **전략**: 진입 기회 포착
            """)
        
        selected_ticker = st.selectbox(
            "종목 선택",
            options=[f"{r['ticker']} ({r['name']})" for r in analysis_results],
            index=0
        )
        
        ticker_code = selected_ticker.split()[0]
        item = next(r for r in analysis_results if r['ticker'] == ticker_code)
        
        df_hist = item['history']
        
        # 현재 상태 분석
        latest = df_hist.iloc[-1]
        prev_10d = df_hist.iloc[-10] if len(df_hist) >= 10 else df_hist.iloc[0]
        
        dp_ratio_change = latest['dp_ratio'] - prev_10d['dp_ratio']
        dp_short_change = latest['dp_short_ratio'] - prev_10d['dp_short_ratio']
        
        # 패턴 인식
        pattern = ""
        pattern_color = "blue"
        
        if dp_ratio_change > 5 and dp_short_change < -5:
            pattern = "💚 매집 패턴 (Accumulation)"
            pattern_color = "green"
        elif dp_ratio_change > 5 and dp_short_change > 5:
            pattern = "🔴 분산 패턴 (Distribution)"
            pattern_color = "red"
        elif dp_short_change < -5:
            pattern = "🟢 공매도 청산 (Short Squeeze 가능)"
            pattern_color = "lightgreen"
        elif dp_short_change > 5:
            pattern = "⚠️ 공매도 공격 (Short Attack)"
            pattern_color = "orange"
        else:
            pattern = "⚪ 안정적 추세 (Stable)"
            pattern_color = "lightblue"
        
        # 현재 상태 요약 카드
        st.markdown(f"### 📊 {ticker_code} 현재 상태 분석")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Dark Pool Ratio", 
                f"{latest['dp_ratio']:.2f}%",
                f"{dp_ratio_change:+.2f}%p (10일)",
                delta_color="normal"
            )
        
        with col2:
            st.metric(
                "DP Short Ratio", 
                f"{latest['dp_short_ratio']:.2f}%",
                f"{dp_short_change:+.2f}%p (10일)",
                delta_color="inverse"
            )
        
        with col3:
            st.metric(
                "10일 평균", 
                f"{latest['dp_short_ratio_10d_avg']:.2f}%",
                f"{latest['dp_short_ratio'] - latest['dp_short_ratio_10d_avg']:+.2f}%p"
            )
        
        with col4:
            st.markdown(f"**패턴 인식**")
            st.markdown(f"<h3 style='color: {pattern_color};'>{pattern}</h3>", unsafe_allow_html=True)
        
        # 시계열 차트
        fig_ts = make_subplots(
            rows=2, cols=1, 
            shared_xaxes=True,
            subplot_titles=(
                f"{ticker_code} - Dark Pool Ratio Trend (기관 개입 강도)",
                f"{ticker_code} - Dark Pool Short Ratio Trend (공매도 심리)"
            ),
            vertical_spacing=0.15
        )
        
        # 차트 1: Dark Pool Ratio (호버 텍스트 추가)
        hover_text_dp_ratio = [
            f"날짜: {row['date']}<br>"
            f"DP Ratio: {row['dp_ratio']:.2f}%<br>"
            f"거래량: {row['market_vol']:,.0f}"
            for idx, row in df_hist.iterrows()
        ]
        
        fig_ts.add_trace(go.Scatter(
            x=df_hist['date'], 
            y=df_hist['dp_ratio'],
            mode='lines+markers', 
            name='DP Ratio', 
            line=dict(color='blue', width=2),
            showlegend=True,
            hovertext=hover_text_dp_ratio,
            hoverinfo='text'
        ), row=1, col=1)
        
        fig_ts.add_hline(y=50, line_dash="dot", line_color="red", 
                        annotation_text="과열 (50%)", row=1, col=1)
        fig_ts.add_hline(y=40, line_dash="dot", line_color="green", 
                        annotation_text="안정 (40%)", row=1, col=1)
        
        # 차트 2: Dark Pool Short Ratio (호버 텍스트 추가)
        hover_text_dp_short = [
            f"날짜: {row['date']}<br>"
            f"DP Short: {row['dp_short_ratio']:.2f}%<br>"
            f"10일 평균: {row['dp_short_ratio_10d_avg']:.2f}%<br>"
            f"차이: {row['dp_short_ratio'] - row['dp_short_ratio_10d_avg']:+.2f}%p"
            for idx, row in df_hist.iterrows()
        ]
        
        fig_ts.add_trace(go.Scatter(
            x=df_hist['date'], 
            y=df_hist['dp_short_ratio'],
            mode='lines+markers', 
            name='DP Short Ratio', 
            line=dict(color='orange', width=2),
            showlegend=True,
            hovertext=hover_text_dp_short,
            hoverinfo='text'
        ), row=2, col=1)
        
        # 10일 평균선
        fig_ts.add_trace(go.Scatter(
            x=df_hist['date'], 
            y=df_hist['dp_short_ratio_10d_avg'],
            mode='lines', 
            name='10일 평균', 
            line=dict(color='gray', dash='dot'),
            showlegend=True
        ), row=2, col=1)
        
        fig_ts.add_hline(y=50, line_dash="dot", line_color="gray", 
                        annotation_text="매수/매도 분기점 (50%)", row=2, col=1)
        
        # 급락/급등 구간 하이라이트
        for i in range(1, len(df_hist)):
            prev = df_hist.iloc[i-1]
            curr = df_hist.iloc[i]
            change = curr['dp_short_ratio'] - prev['dp_short_ratio']
            
            # 급락 (녹색 배경)
            if change < -5:
                fig_ts.add_vrect(
                    x0=prev['date'], x1=curr['date'],
                    fillcolor="green", opacity=0.1,
                    layer="below", line_width=0,
                    row=2, col=1
                )
            # 급등 (빨간 배경)
            elif change > 5:
                fig_ts.add_vrect(
                    x0=prev['date'], x1=curr['date'],
                    fillcolor="red", opacity=0.1,
                    layer="below", line_width=0,
                    row=2, col=1
                )
        
        fig_ts.update_layout(
            height=700, 
            title_text=f"📊 {ticker_code} ({item['name']}) {days_back}일 상세 타임라인", 
            template='plotly_white',
            hovermode='x unified'
        )
        
        fig_ts.update_xaxes(title_text="날짜", row=2, col=1)
        fig_ts.update_yaxes(title_text="DP Ratio (%)", row=1, col=1)
        fig_ts.update_yaxes(title_text="DP Short Ratio (%)", row=2, col=1)
        
        st.plotly_chart(fig_ts, use_container_width=True)
        
        # 주요 이벤트 탐지
        st.markdown("### 🔍 주요 이벤트 탐지")
        
        # 공매도 청산 이벤트
        squeeze_events = []
        attack_events = []
        
        for i in range(10, len(df_hist)):
            curr = df_hist.iloc[i]
            avg_10d = df_hist.iloc[i-10:i]['dp_short_ratio'].mean()
            change = curr['dp_short_ratio'] - avg_10d
            
            if change < -5:
                squeeze_events.append({
                    'date': curr['date'],
                    'dp_short': curr['dp_short_ratio'],
                    'change': change
                })
            elif change > 5:
                attack_events.append({
                    'date': curr['date'],
                    'dp_short': curr['dp_short_ratio'],
                    'change': change
                })
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.success("**🟢 공매도 청산 이벤트**")
            if squeeze_events:
                for event in squeeze_events[-3:]:  # 최근 3개만
                    st.write(f"- {event['date']}: {event['change']:+.2f}%p (Short: {event['dp_short']:.2f}%)")
            else:
                st.write("최근 이벤트 없음")
        
        with col2:
            st.warning("**⚠️ 공매도 공격 이벤트**")
            if attack_events:
                for event in attack_events[-3:]:  # 최근 3개만
                    st.write(f"- {event['date']}: {event['change']:+.2f}%p (Short: {event['dp_short']:.2f}%)")
            else:
                st.write("최근 이벤트 없음")
        
        # 상세 데이터 테이블
        with st.expander("📊 상세 데이터 보기"):
            st.dataframe(
                df_hist[['date', 'dp_ratio', 'dp_short_ratio', 
                        'dp_short_ratio_10d_avg', 'total_short_ratio']].sort_values('date', ascending=False),
                use_container_width=True
            )
    
    # 푸터
    st.markdown("---")
    st.markdown(f"**최종 업데이트**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.caption("데이터 출처: Yahoo Finance & FINRA | 1시간마다 캐시 갱신")

if __name__ == "__main__":
    main()
