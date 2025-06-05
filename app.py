import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from dateutil.relativedelta import relativedelta
import calendar
from functools import lru_cache
from io import BytesIO
import streamlit.components.v1 as components
import socket
import yfinance as yf
from yfinance import shared
shared._USE_THREADS = False
# yf.pdr_override() removed due to AttributeError

st.set_page_config(page_title="ETF Income Planner", layout="centered")
st.markdown("""
    <style>
    .main {background-color: #f5f5f5; color: #111;}
    .stApp {max-width: 900px; margin: auto;}
    h1, h2, h3, h4 {color: #0a3d62;}
    </style>
""", unsafe_allow_html=True)

# --- Developer Toggle ---
dev_code = st.sidebar.text_input("🔐 Developer Access Code", type="password")
is_developer = dev_code == "letmein123"

# --- IP Address Tracking ---
@st.cache_data(show_spinner=False)
def get_client_ip():
    try:
        return socket.gethostbyname(socket.gethostname())
    except:
        return "unknown"

client_ip = get_client_ip()

# --- Trial Usage State ---
if "used_ips" not in st.session_state:
    st.session_state.used_ips = set()

has_used_trial = client_ip in st.session_state.used_ips
if not is_developer and not has_used_trial:
    st.session_state.used_ips.add(client_ip)

# --- Static ETF Data ---
etf_yields = {
    'JEPI': 0.0838, 'SPYD': 0.045, 'SCHD': 0.035, 'VYM': 0.032,
    'QYLD': 0.115, 'RYLD': 0.12, 'BND': 0.04, 'PFF': 0.065
}

etf_distribution_schedules = {
    'JEPI': {'frequency': 'monthly', 'next_pay_date': '2024-06-30'},
    'SPYD': {'frequency': 'quarterly', 'next_pay_date': '2024-06-30'},
    'SCHD': {'frequency': 'quarterly', 'next_pay_date': '2024-06-30'},
    'VYM': {'frequency': 'quarterly', 'next_pay_date': '2024-06-30'},
    'QYLD': {'frequency': 'monthly', 'next_pay_date': '2024-06-30'},
    'RYLD': {'frequency': 'monthly', 'next_pay_date': '2024-06-30'},
    'BND': {'frequency': 'monthly', 'next_pay_date': '2024-06-30'},
    'PFF': {'frequency': 'monthly', 'next_pay_date': '2024-06-30'}
}

state_tax_rates = {
    'Massachusetts': 0.05, 'California': 0.093, 'New York': 0.064, 'Texas': 0.0, 'Florida': 0.0,
    'Illinois': 0.0495, 'Washington': 0.0, 'New Jersey': 0.0637, 'Pennsylvania': 0.0307, 'Ohio': 0.0399
}

# --- Tax Calculation ---
@lru_cache(maxsize=None)
def get_federal_tax_rate(income):
    brackets = [(11600, 0.10), (47150, 0.12), (100525, 0.22),
                (191950, 0.24), (243725, 0.32), (609350, 0.35)]
    for limit, rate in brackets:
        if income <= limit:
            return rate
    return 0.37

# --- Distribution Schedule ---
def generate_distribution_schedule(investment, etf_weights):
    if not etf_weights:
        return pd.DataFrame()

    rows = []
    for etf, weight in etf_weights.items():
        rate = etf_yields[etf]
        amount = investment * weight * rate
        sched = etf_distribution_schedules[etf]
        freq, next_date = sched['frequency'], datetime.strptime(sched['next_pay_date'], "%Y-%m-%d")

        periods = 12 if freq == 'monthly' else 4
        step = 1 if freq == 'monthly' else 3
        dist = amount / periods

        for i in range(periods):
            date = next_date + relativedelta(months=step * i)
            final_date = datetime(date.year, date.month, calendar.monthrange(date.year, date.month)[1])
            rows.append({'ETF': etf, 'Pay Date': final_date, 'Estimated Distribution ($)': round(dist, 2)})

    return pd.DataFrame(rows).sort_values('Pay Date')

# --- Simulation Logic ---
def simulate_income_planner(investment, etf_weights, state, income):
    if not etf_weights:
        return {}

    yield_avg = sum(etf_yields[etf] * w for etf, w in etf_weights.items())
    annual = investment * yield_avg
    monthly = annual / 12

    fed_tax = get_federal_tax_rate(income)
    state_tax = state_tax_rates.get(state, 0.05)
    total_tax = annual * (fed_tax + state_tax)
    net_annual = annual - total_tax

    return {
        'Average Yield (%)': round(yield_avg * 100, 2),
        'Gross Monthly Income ($)': round(monthly, 2),
        'Gross Yearly Income ($)': round(annual, 2),
        'Federal Tax Rate': f"{int(fed_tax * 100)}%",
        'State Tax Rate': f"{int(state_tax * 100)}%",
        'Net Monthly Income ($)': round(net_annual / 12, 2),
        'Net Yearly Income ($)': round(net_annual, 2)
    }

# --- Historical Performance ---
def show_portfolio_performance(etf_weights, start, end, interval):
    prices, returns = pd.DataFrame(), {}
    for etf, w in etf_weights.items():
        data = yf.download(etf, start=start, end=end, interval=interval, progress=False, threads=False)
        if 'Adj Close' not in data:
            st.warning(f"⚠️ No data found for {etf}. Skipping.")
            continue
        data = data['Adj Close']
        prices[etf] = data
    rets = prices.pct_change().dropna()
    matching_weights = {etf: w for etf, w in etf_weights.items() if etf in prices.columns}
    if not matching_weights:
        st.error("❌ No valid ETF data available to calculate performance.")
        return
    weighted = rets[matching_weights.keys()].dot(pd.Series(matching_weights))
    growth = (1 + weighted).cumprod()
    st.markdown("### 📈 Historical Portfolio Performance")
    st.line_chart(growth)
    st.write("Cumulative return: {:.2f}%".format((growth.iloc[-1] - 1) * 100))

# --- UI ---
st.title("📊 Monthly Income Planner for ETF Investors")

investment = st.number_input("💰 Investment Amount ($)", value=250000)
income = st.number_input("💼 Your Current Taxable Income ($)", value=145000)
selected_etfs = st.multiselect("📊 Select ETFs", list(etf_yields), default=['JEPI', 'SPYD'])
state = st.selectbox("🌎 Select Your State", list(state_tax_rates), index=0)

etf_weights, total_weight = {}, 0.0
if selected_etfs:
    st.markdown("### ⚖️ Assign Portfolio Weights (%)")
    for etf in selected_etfs:
        val = st.slider(f"{etf} Weight %", 0, 100, int(100 / len(selected_etfs)))
        etf_weights[etf] = val / 100
    total_weight = sum(etf_weights.values())

# --- Date Range & Frequency ---
st.markdown("### 🕰️ Customize Performance Timeframe")
start_date = st.date_input("Start Date", datetime(2019, 1, 1))
end_date = st.date_input("End Date", datetime.today())
interval = st.selectbox("Frequency", ["1d", "1wk", "1mo"], index=2)

if st.button("📉 Calculate Income"):
    if is_developer or not has_used_trial:
        if selected_etfs and investment > 0 and abs(total_weight - 1.0) <= 0.01:
            summary = simulate_income_planner(investment, etf_weights, state, income)
            st.markdown("### 📋 Income Summary")
            st.dataframe(pd.DataFrame(summary.items(), columns=['Metric', 'Value']))

            st.markdown("### 📆 Projected Distribution Schedule")
            schedule = generate_distribution_schedule(investment, etf_weights)
            if not schedule.empty:
                schedule['Pay Date'] = schedule['Pay Date'].dt.strftime('%Y-%m-%d')
                st.dataframe(schedule)
            else:
                st.info("No distributions available for the selected ETFs.")

            show_portfolio_performance(etf_weights, start_date, end_date, interval)
        else:
            st.warning("Please ensure your weights total 100% and all inputs are valid.")
    else:
        st.warning("🛑 You've used your free simulation. Subscribe for unlimited access.")
        st.markdown("[Click here to subscribe for $5/month](https://buy.stripe.com/test_dR6aEd8KcbkN4fK4gg)")
