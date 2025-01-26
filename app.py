import streamlit as st
import pandas as pd
import yfinance as yf
import talib
from datetime import datetime, timedelta, timezone
from backtesting import Backtest, Strategy
import warnings
from urllib3.exceptions import NotOpenSSLWarning

# Suppress warnings
warnings.filterwarnings("ignore", category=NotOpenSSLWarning)


class RobustStrategy(Strategy):
    rsi_period = 14
    rsi_ob = 70
    rsi_os = 30
    sma_fast = 50
    sma_slow = 200

    def init(self):
        self.rsi = self.I(talib.RSI, self.data.Close, self.rsi_period)
        self.sma_fast_line = self.I(talib.SMA, self.data.Close, self.sma_fast)
        self.sma_slow_line = self.I(talib.SMA, self.data.Close, self.sma_slow)

    def next(self):
        if not self.position:
            if (self.rsi < self.rsi_os) and (self.sma_fast_line > self.sma_slow_line):
                self.buy(size=0.95)
        else:
            if self.rsi > self.rsi_ob:
                self.position.close()

@st.cache_data()
def fetch_financial_data(symbol, start, end, interval):
    """Bulletproof data fetcher with column normalization"""
    try:
        data = yf.download(
            symbol,
            start=start,
            end=end,
            interval=interval,
            auto_adjust=True,
            threads=False,
            progress=False
        )

        # Flatten MultiIndex columns
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [f'{col[0]}_{col[1]}' for col in data.columns]

        # Normalize column names
        column_map = {
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume',
            'adj close': 'Close'
        }

        # Case-insensitive normalization
        data.columns = data.columns.str.lower()
        data = data.rename(columns=lambda x: column_map.get(x.split('_')[0], x))

        # Create missing OHLC columns from Close if needed
        if 'Close' not in data.columns:
            raise ValueError("No price data available")

        if 'Open' not in data.columns:
            data['Open'] = data['Close'].shift(1).ffill()
        if 'High' not in data.columns:
            data['High'] = data[['Open', 'Close']].max(axis=1)
        if 'Low' not in data.columns:
            data['Low'] = data[['Open', 'Close']].min(axis=1)

        # Handle volume
        if 'Volume' not in data.columns:
            data['Volume'] = 1e6  # Default volume

        data['Volume'] = pd.to_numeric(data['Volume'], errors='coerce').fillna(1e6)

        # Final column validation
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        data = data[required_cols].copy()
        data.columns = pd.Index(required_cols)

        # Clean index
        data.index = pd.to_datetime(data.index)
        data.index = data.index.tz_localize(None)

        return data.dropna()

    except Exception as e:
        st.error(f"Data Error: {str(e)}")
        return pd.DataFrame()


# Streamlit UI
st.title("💹 Professional Trading Backtester")
st.write("Institutional-grade backtesting platform")

with st.sidebar:
    st.header("Configuration")
    symbol = st.text_input("Ticker Symbol", "BTC-USD").strip().upper()
    timeframe = st.selectbox("Timeframe", ['1h', '4h', '1d', '1wk'], index=2)

    # Date handling
    today = datetime.now(timezone.utc).date()
    start_date = st.date_input("Start Date", today - timedelta(days=365))
    end_date = st.date_input("End Date", today)

    st.header("Strategy Parameters")
    rsi_period = st.slider("RSI Period", 5, 30, 14)
    rsi_ob = st.slider("RSI Overbought", 50, 100, 70)
    rsi_os = st.slider("RSI Oversold", 0, 50, 30)
    sma_fast = st.slider("Fast SMA", 20, 100, 50)
    sma_slow = st.slider("Slow SMA", 100, 300, 200)

# Main execution flow
data = fetch_financial_data(
    symbol=symbol,
    start=datetime.combine(start_date, datetime.min.time()),
    end=datetime.combine(end_date, datetime.max.time()),
    interval={'1h': '60m', '4h': '60m', '1d': '1d', '1wk': '1wk'}[timeframe]
)

if not data.empty:
    st.subheader(f"📊 Market Data: {symbol} ({timeframe})")
    st.write(f"Data from {data.index[0].date()} to {data.index[-1].date()}")
    st.dataframe(data.tail(5), use_container_width=True)

    if st.button("🚀 Execute Backtest", type="primary"):
        try:
            bt = Backtest(
                data,
                RobustStrategy,
                cash=1_000_000,
                commission=0.002,
                exclusive_orders=True
            )

            results = bt.run(
                rsi_period=rsi_period,
                rsi_ob=rsi_ob,
                rsi_os=rsi_os,
                sma_fast=sma_fast,
                sma_slow=sma_slow
            )

            st.success("✅ Backtest Completed Successfully")

            # Performance Metrics
            col1, col2, col3 = st.columns(3)
            col1.metric("Return (%)", f"{results['Return [%]']:.2f}")
            col2.metric("Max DD (%)", f"{results['Max. Drawdown [%]']:.2f}")
            col3.metric("Sharpe Ratio", f"{results['Sharpe Ratio']:.2f}")

            col4, col5, col6 = st.columns(3)
            col4.metric("Trades", results['# Trades'])
            col5.metric("Win Rate (%)", f"{results['Win Rate [%]']:.2f}")
            col6.metric("Profit Factor", f"{results['Profit Factor']:.2f}")

            # Visualization
            fig = bt.plot(resample=False)
            st.bokeh_chart(fig, use_container_width=True)

            # Detailed Analysis
            with st.expander("🔍 Trade Analysis"):
                trades = results._trades
                trades['Duration'] = trades.ExitTime - trades.EntryTime
                st.dataframe(
                    trades.style.format({
                        'Duration': lambda x: f"{x.days}d {x.seconds // 3600}h",
                        'ReturnPct': '{:.2f}%',
                        'PnL': '${:,.2f}'
                    }),
                    use_container_width=True
                )

        except Exception as e:
            st.error(f"Backtest Error: {str(e)}")
else:
    st.warning("No valid data available for backtesting")

st.markdown("---")
st.caption("""
**Disclaimer:** Backtest results are hypothetical and for educational purposes only.
Past performance does not guarantee future results. Trading involves risk.
""")