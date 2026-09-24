import streamlit as st
import pandas as pd
from datetime import datetime
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    import openai
except ImportError:
    openai = None

# =========================================================
# 1. CONFIGURATION DE LA PAGE & STYLES PRO CI
# =========================================================
st.set_page_config(
    page_title="SYDAM Pro Transit CI - Automation & IA",
    page_icon="🇨🇮",
    layout="wide",
    initial_sidebar_state="expanded"
)
