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

st.set_page_config(page_title="ETF Income Planner", layout="centered")
st.markdown("""
    <style>
    .main {background-color: #f5f5f5; color: #111;}
    .stApp {max-width: 900px; margin: auto;}
    h1, h2, h3, h4 {color: #0a3d62;}
    </style>
""", unsafe_allow_html=True)

# --- Developer Toggle via Secret Code ---
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

# --- Trial Usage Tracking ---
if "used_ips" not in st.session_state:
    st.session_state.used_ips = set()

has_used_trial = client_ip in st.session_state.used_ips
if not is_developer and not has_used_trial:
    st.session_state.used_ips.add(client_ip)

# --- ETF Data ---
etf_yields = {
    'JEPI': 0.0838,
    'SPYD': 0.045,
    'SCHD': 0.035,
    'VYM': 0.032,
    'QYLD': 0.115,
    'RYLD': 0.12,
    'BND': 0.04,
    'PFF': 0.065
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

@lru_cache(maxsize=None)
def get_federal_tax_rate(income):
    if income <= 11600:
        return 0.10
    elif income <= 47150:
        return 0.12
    elif income <= 100525:
        return 0.22
    elif income <= 191950:
        return 0.24
    elif income <= 243725:
        return 0.32
    elif income <= 609350:
        return 0.35
    else:
        return 0.37

def generate_distribution_schedule(investment, selected_etfs):
    if not selected_etfs:
        return pd.DataFrame()

    distribution_rows = []
    for etf in selected_etfs:
        yield_rate = etf_yields[etf]
        annual_amount = investment * (yield_rate / len(selected_etfs))
        frequency = etf_distribution_schedules[etf]['frequency']
        next_pay_date = datetime.strptime(etf_distribution_schedules[etf]['next_pay_date'], "%Y-%m-%d")

        payments = 12 if frequency == 'monthly' else 4
        interval = 1 if frequency == 'monthly' else 3
        monthly_dist = annual_amount / payments

        for i in range(payments):
            pay_date = next_pay_date + relativedelta(months=interval * i)
            pay_date = datetime(pay_date.year, pay_date.month, calendar.monthrange(pay_date.year, pay_date.month)[1])
            distribution_rows.append({
                'ETF': etf,
                'Pay Date': pay_date,
                'Estimated Distribution ($)': round(monthly_dist, 2)
            })

    return pd.DataFrame(distribution_rows).sort_values(by='Pay Date')

def simulate_income_planner(investment_amount, selected_etfs, state, income):
    if not selected_etfs:
        return {}

    avg_yield = sum([etf_yields[etf] for etf in selected_etfs]) / len(selected_etfs)
    annual_income = investment_amount * avg_yield
    monthly_income = annual_income / 12

    fed_tax_rate = get_federal_tax_rate(income)
    state_tax_rate = state_tax_rates.get(state, 0.05)

    total_tax = annual_income * (fed_tax_rate + state_tax_rate)
    after_tax_income_annual = annual_income - total_tax
    after_tax_income_monthly = after_tax_income_annual / 12

    return {
        'Average Yield (%)': round(avg_yield * 100, 2),
        'Gross Monthly Income ($)': round(monthly_income, 2),
        'Federal Tax Rate': f"{int(fed_tax_rate * 100)}%",
        'State Tax Rate': f"{int(state_tax_rate * 100)}%",
        'Net Monthly Income ($)': round(after_tax_income_monthly, 2)
    }

def plot_distribution_schedule(df):
    fig, ax = plt.subplots(figsize=(8, 4))
    pivot = df.pivot_table(index='Pay Date', values='Estimated Distribution ($)', aggfunc='sum')
    pivot.plot(kind='bar', legend=False, ax=ax)
    ax.set_title('Monthly Distribution Schedule')
    ax.set_xlabel('Pay Date')
    ax.set_ylabel('Distribution ($)')
    plt.xticks(rotation=45, ha='right')
    st.pyplot(fig)

def create_pdf(summary_df, schedule_df):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        summary_df.to_excel(writer, sheet_name='Income Summary', index=False)
        schedule_df.to_excel(writer, sheet_name='Distribution Schedule', index=False)
    st.download_button("📅 Download Summary as Excel", data=buffer.getvalue(), file_name="income_summary.xlsx")

# --- UI ---
st.title("📊 Monthly Income Planner for ETF Investors")

investment = st.number_input("💰 Investment Amount ($)", value=250000)
income = st.number_input("💼 Your Current Taxable Income ($)", value=145000)
selected_etfs = st.multiselect("📊 Select ETFs", list(etf_yields.keys()), default=['JEPI', 'SPYD'])
state = st.selectbox("🌎 Select Your State", list(state_tax_rates.keys()), index=0, help="If your state isn't listed, default tax rate of 5% will apply")

if st.button("📉 Calculate Income"):
    if is_developer or not has_used_trial:
        if selected_etfs and investment > 0:
            summary = simulate_income_planner(investment, selected_etfs, state, income)
            st.markdown("### 📋 Income Summary")
            summary_df = pd.DataFrame(summary.items(), columns=['Metric', 'Value'])
            st.dataframe(summary_df)

            st.markdown("### 📆 Projected Distribution Schedule")
            schedule = generate_distribution_schedule(investment, selected_etfs)
            if not schedule.empty:
                schedule['Pay Date'] = schedule['Pay Date'].apply(lambda d: d.strftime('%Y-%m-%d'))
                st.dataframe(schedule)
                plot_distribution_schedule(schedule)
                create_pdf(summary_df, schedule)
            else:
                st.info("No distributions available for the selected ETFs.")
        else:
            st.warning("Please enter an investment amount and select at least one ETF.")
    else:
        st.warning("🛑 You've used your free simulation. Subscribe for unlimited access.")
        st.markdown("[Click here to subscribe for $5/month](https://buy.stripe.com/test_dR6aEd8KcbkN4fK4gg)")
