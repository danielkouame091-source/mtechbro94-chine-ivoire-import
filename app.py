import streamlit as st

st.set_page_config(
    page_title="China–Côte d'Ivoire Import & Export",
    page_icon="🌍",
    layout="wide",
)

st.title("China–Côte d'Ivoire Import & Export")
st.write("Welcome to the import and export information platform.")

st.sidebar.header("Navigation")
page = st.sidebar.radio("Go to", ["Home", "Import estimate", "About"])

if page == "Home":
    st.header("Move goods with confidence")
    st.info("Use the sidebar to estimate an import cost or learn more about this platform.")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Origin", "China")
    with col2:
        st.metric("Destination", "Côte d'Ivoire")
    with col3:
        st.metric("Service", "Import & export")

elif page == "Import estimate":
    st.header("Import cost estimate")
    st.caption("This is an estimate only. Confirm duties, taxes, and shipping fees with your customs broker.")

    col1, col2 = st.columns(2)
    with col1:
        product_value = st.number_input("Product value (CNY)", min_value=0.0, step=100.0)
        shipping_cost = st.number_input("Shipping cost (CNY)", min_value=0.0, step=100.0)
    with col2:
        duty_rate = st.number_input("Estimated duty rate (%)", min_value=0.0, max_value=100.0, value=10.0, step=0.5)
        exchange_rate = st.number_input("CNY to XOF exchange rate", min_value=0.0, value=82.0, step=0.1)

    subtotal = product_value + shipping_cost
    duty = subtotal * duty_rate / 100
    total_cny = subtotal + duty
    total_xof = total_cny * exchange_rate

    st.divider()
    result_col1, result_col2, result_col3 = st.columns(3)
    result_col1.metric("Subtotal", f"{subtotal:,.2f} CNY")
    result_col2.metric("Estimated duty", f"{duty:,.2f} CNY")
    result_col3.metric("Estimated total", f"{total_xof:,.0f} XOF")

else:
    st.header("About")
    st.write(
        "This Streamlit application is a starting point for connecting buyers in "
        "Côte d'Ivoire with suppliers in China."
    )
    st.warning("The estimate does not replace an official customs or freight quotation.")
