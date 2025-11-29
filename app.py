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
        
        fig2 = go.Figure()
        
        fig2.add_trace(go.Bar(
            x=df_main['ticker'], 
            y=df_main['dp_short_ratio'],
            name='Dark Pool Short % (장외 내부)',
            marker_color='darkblue'
        ))
        
        fig2.add_trace(go.Bar(
            x=df_main['ticker'], 
            y=df_main['total_short_ratio'],
            name='Total Short % (전체 시장)',
            marker_color='gray'
        ))
        
        fig2.update_layout(
            title='Dark Pool Short Ratio vs Total Market Short Ratio',
            barmode='group', 
            height=500, 
            template='plotly_white',
            xaxis_title='종목',
            yaxis_title='Short Ratio (%)'
        )
        
        st.plotly_chart(fig2, use_container_width=True)
    
    # Tab 3: 4분면 분석
    with tab3:
        st.subheader("Market Sentiment Map (4분면 분석)")
        
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
            hovertemplate='<b>%{text}</b><br>DP Ratio: %{x:.2f}%<br>DP Short Ratio: %{y:.2f}%<extra></extra>'
        ))
        
        fig3.add_vline(x=45, line_dash="dot", line_color="gray")
        fig3.add_hline(y=50, line_dash="dot", line_color="gray")
        
        fig3.add_annotation(x=55, y=30, text="매집 (Accumulation)", 
                           showarrow=False, font=dict(color="green", size=14))
        fig3.add_annotation(x=55, y=70, text="매도/공매도 (Distribution)", 
                           showarrow=False, font=dict(color="red", size=14))
        fig3.add_annotation(x=35, y=30, text="개인/관망", 
                           showarrow=False, font=dict(color="gray", size=14))
        
        fig3.update_layout(
            title='X축: 기관 관심도 (DP Ratio) vs Y축: 공매도 심리 (DP Short Ratio)',
            xaxis_title='Dark Pool Ratio (%) - 높을수록 기관 개입 강함',
            yaxis_title='Dark Pool Short Ratio (%) - 높을수록 하락 베팅',
            height=600, 
            template='plotly_white'
        )
        
        st.plotly_chart(fig3, use_container_width=True)
    
    # Tab 4: 시계열 분석
    with tab4:
        st.subheader("전체 종목 상세 시계열 분석")
        
        selected_ticker = st.selectbox(
            "종목 선택",
            options=[f"{r['ticker']} ({r['name']})" for r in analysis_results],
            index=0
        )
        
        ticker_code = selected_ticker.split()[0]
        item = next(r for r in analysis_results if r['ticker'] == ticker_code)
        
        df_hist = item['history']
        
        fig_ts = make_subplots(
            rows=2, cols=1, 
            shared_xaxes=True,
            subplot_titles=(
                f"{ticker_code} - Dark Pool Ratio Trend (기관 개입 강도)",
                f"{ticker_code} - Dark Pool Short Ratio Trend (공매도 심리)"
            ),
            vertical_spacing=0.15
        )
        
        # Dark Pool Ratio
        fig_ts.add_trace(go.Scatter(
            x=df_hist['date'], 
            y=df_hist['dp_ratio'],
            mode='lines+markers', 
            name='DP Ratio', 
            line=dict(color='blue', width=2),
            showlegend=True
        ), row=1, col=1)
        
        fig_ts.add_hline(y=50, line_dash="dot", line_color="red", 
                        annotation_text="과열 (50%)", row=1, col=1)
        fig_ts.add_hline(y=40, line_dash="dot", line_color="green", 
                        annotation_text="안정 (40%)", row=1, col=1)
        
        # Dark Pool Short Ratio
        fig_ts.add_trace(go.Scatter(
            x=df_hist['date'], 
            y=df_hist['dp_short_ratio'],
            mode='lines+markers', 
            name='DP Short Ratio', 
            line=dict(color='orange', width=2),
            showlegend=True
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
                        annotation_text="매수/매도 분기점", row=2, col=1)
        
        fig_ts.update_layout(
            height=700, 
            title_text=f"📊 {ticker_code} ({item['name']}) {days_back}일 상세 타임라인", 
            template='plotly_white'
        )
        
        fig_ts.update_xaxes(title_text="날짜", row=2, col=1)
        fig_ts.update_yaxes(title_text="DP Ratio (%)", row=1, col=1)
        fig_ts.update_yaxes(title_text="DP Short Ratio (%)", row=2, col=1)
        
        st.plotly_chart(fig_ts, use_container_width=True)
        
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
