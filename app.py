import io
import os
import re
import smtplib
import sqlite3
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

try:
    from groq import Groq
except ImportError:
    Groq = None

BASE_DIR = Path(__file__).resolve().parent
DB_NAME = BASE_DIR / "transit_enterprise.db"
UPLOAD_DIR = BASE_DIR / "uploads_dossiers"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
STATUTS = ["En cours", "FDI & RFC Validées", "Visite Douanière en Cours", "Bon à Enlever (BAE) Émis", "Livré au Client"]

st.set_page_config(page_title="Kelanewin Transit - SYDAM Pro", page_icon="🇨🇮", layout="wide")


def setting(name, default=""):
    try:
        value = st.secrets.get(name, default)
        if value not in (None, ""):
            return str(value)
    except Exception:
        pass
    return os.getenv(name, default)


def db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with db_connection() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS articles (id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT UNIQUE NOT NULL, sh TEXT NOT NULL, dd REAL NOT NULL, categorie TEXT NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS dossiers (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, client TEXT NOT NULL, article TEXT NOT NULL, fob_xof REAL NOT NULL, total_facture REAL NOT NULL, solde_du REAL NOT NULL, statut TEXT NOT NULL, document_path TEXT)")
        count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        if not count:
            conn.executemany("INSERT OR IGNORE INTO articles (nom, sh, dd, categorie) VALUES (?, ?, ?, ?)", [
                ("Station Totale Topographique & GNSS/GPS", "9015.80.00", 5.0, "Topographie"),
                ("Théodolites, Niveaux Optiques & Laser", "9015.10.00", 5.0, "Topographie"),
                ("Smartphones, iPhones & Téléphones portables", "8517.13.00", 20.0, "High-Tech"),
                ("Ordinateurs Portables, MacBooks & Tablettes", "8471.30.00", 5.0, "Informatique"),
                ("Panneaux Photovoltaïques / Solaires", "8541.43.00", 5.0, "Énergie"),
                ("Groupes Électrogènes (Générateurs)", "8502.11.00", 5.0, "Machines"),
            ])


def read_table(query, params=()):
    with db_connection() as conn:
        return pd.read_sql_query(query, conn, params=params)


def add_case(client, article, fob, total, balance, document_path):
    with db_connection() as conn:
        conn.execute("INSERT INTO dossiers (date, client, article, fob_xof, total_facture, solde_du, statut, document_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (datetime.now().strftime("%Y-%m-%d %H:%M"), client, article, fob, total, balance, "En cours", document_path))


def update_status(case_id, status):
    with db_connection() as conn:
        conn.execute("UPDATE dossiers SET statut = ? WHERE id = ?", (status, case_id))


def safe_filename(value):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or "document"


def get_rates():
    try:
        response = requests.get("https://open.er-api.com/v6/latest/USD", timeout=5)
        rates = response.json().get("rates", {}) if response.ok else {}
        usd = float(rates.get("XOF", 610.0))
        cny = usd / float(rates.get("CNY", 7.2))
        return round(cny, 2), round(usd, 2), "🟢 API"
    except Exception:
        return 82.0, 610.0, "⚠️ Secours hors ligne"


def build_pdf(client, article, info, qty, fob, freight, insurance, caf, customs, transit, inland, total, deposit, balance):
    path = BASE_DIR / f"Devis_Pro_{safe_filename(client)}.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=letter, rightMargin=35, leftMargin=35, topMargin=35, bottomMargin=35)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("title", parent=styles["Heading1"], fontSize=16, textColor=colors.HexColor("#047857"), alignment=1)
    elements = [Paragraph("<b>KELANEWIN TRANSIT S.A. (SYDAM PRO CI)</b>", title), Paragraph("Facture Proforma & Cotation Logistique Douanière", styles["Normal"]), Spacer(1, 12)]
    elements.append(Paragraph(f"<b>Client :</b> {client}<br/><b>Date :</b> {datetime.now():%d/%m/%Y}<br/><b>Article :</b> {article}", styles["Normal"]))
    data = [["Désignation", "Code SH", "Qté", "Montant FCFA"], [article, info["sh"], str(qty), f"{fob:,.0f}"], ["Fret & assurance", "-", "-", f"{freight + insurance:,.0f}"], ["Valeur CAF", "-", "-", f"{caf:,.0f}"], ["Droits & taxes", "-", "-", f"{customs:,.0f}"], ["Transit", "-", "-", f"{transit:,.0f}"], ["Post-acheminement", "-", "-", f"{inland:,.0f}"], ["<b>TOTAL</b>", "", "", f"<b>{total:,.0f} FCFA</b>"], ["Acompte", "", "", f"{deposit:,.0f} FCFA"], ["<b>SOLDE</b>", "", "", f"<b>{balance:,.0f} FCFA</b>"]]
    table = Table(data, colWidths=[230, 80, 45, 145])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")), ("BACKGROUND", (0, 7), (-1, 7), colors.HexColor("#E2E8F0")), ("BACKGROUND", (0, 9), (-1, 9), colors.HexColor("#DCFCE7"))]))
    elements += [table, Spacer(1, 20), Paragraph("Conditions : 50% à la commande, solde avant BAE.", styles["Normal"])]
    doc.build(elements)
    return path


def dataframe_xlsx(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Dossiers")
    return output.getvalue()


def ask_ai(api_key, question, context):
    if not Groq or not api_key:
        return None, ["Bibliothèque Groq absente ou clé API manquante."]
    client = Groq(api_key=api_key)
    system = ("Tu es l'assistant expert de Kelanewin Transit en Côte d'Ivoire. "
              "Réponds en français, structure la réponse en étapes concrètes, distingue les informations certaines "
              "des points à vérifier auprès de la Douane/GUCE, et ne présente jamais une estimation comme une règle officielle.")
    errors = []
    for model in [setting("GROQ_MODEL", "llama-3.3-70b-versatile"), "llama-3.1-8b-instant"]:
        try:
            result = client.chat.completions.create(model=model, messages=[{"role": "system", "content": system}, {"role": "user", "content": f"Contexte dossier : {context}\n\nQuestion : {question}"}], temperature=0.2, max_tokens=1200)
            return result.choices[0].message.content, errors
        except Exception as exc:
            errors.append(f"{model}: {exc}")
    return None, errors


init_db()
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.session_state.user_role = ""

users = {"admin": (setting("APP_ADMIN_PASSWORD", "transit2026"), "Administrateur"), "commercial": (setting("APP_COMMERCIAL_PASSWORD", "compta2026"), "Commercial / Déclarant"), "comptable": (setting("APP_COMPTABLE_PASSWORD", "finance2026"), "Comptable / Trésorerie")}

if not st.session_state.authenticated:
    st.title("🔐 Kelanewin Transit")
    user = st.text_input("Identifiant")
    password = st.text_input("Mot de passe", type="password")
    if st.button("Se connecter", type="primary"):
        if user in users and password == users[user][0]:
            st.session_state.authenticated, st.session_state.username, st.session_state.user_role = True, user, users[user][1]
            st.rerun()
        st.error("Identifiants invalides. Configurez les secrets de production.")
    st.stop()

cny_rate, usd_rate, rate_status = get_rates()
st.sidebar.title("🇨🇮 KELANEWIN TRANSIT")
st.sidebar.caption(f"{st.session_state.username} · {st.session_state.user_role}")
groq_key = setting("GROQ_API_KEY") or st.sidebar.text_input("Clé API Groq", type="password")
st.sidebar.subheader("💱 Taux")
st.sidebar.caption(rate_status)
cny_rate = st.sidebar.number_input("1 CNY → FCFA", value=cny_rate, step=0.1)
usd_rate = st.sidebar.number_input("1 USD → FCFA", value=usd_rate, step=1.0)
if st.sidebar.button("🚪 Déconnexion"):
    st.session_state.authenticated = False
    st.rerun()

st.markdown("<div class='header'><h1>📦 KELANEWIN TRANSIT · PRO</h1><p>Cotation, CRM, documents, export et assistant douanier</p></div>", unsafe_allow_html=True)
st.markdown("<style>.header{padding:25px;border-radius:18px;background:linear-gradient(135deg,#047857,#0284c7);color:white;margin-bottom:20px}.metric{padding:14px;border:1px solid #334155;border-radius:12px;background:#111827}</style>", unsafe_allow_html=True)

df_articles = read_table("SELECT * FROM articles ORDER BY nom")
dossiers = read_table("SELECT * FROM dossiers ORDER BY id DESC")
tab_quote, tab_crm, tab_ai, tab_tariff = st.tabs(["📊 Cotation premium", "📂 CRM & exports", "🤖 IA douanière", "📚 Tarif SH"])

with tab_quote:
    client, email, phone = st.columns(3)
    with client: client_name = st.text_input("Client", "ETS KOUASSI & FRERES")
    with email: client_email = st.text_input("Email", "client@example.com")
    with phone: client_phone = st.text_input("WhatsApp", "+2250700000000")
    upload = st.file_uploader("Pièce justificative", type=["pdf", "png", "jpg", "jpeg"])
    document_path = ""
    if upload:
        document_path = str(UPLOAD_DIR / f"{datetime.now():%Y%m%d%H%M%S}_{safe_filename(upload.name)}")
        Path(document_path).write_bytes(upload.getbuffer())
        st.success("Document enregistré.")
    if df_articles.empty:
        st.warning("Ajoutez d'abord un article dans Tarif SH.")
        st.stop()
    article = st.selectbox("Article", df_articles["nom"].tolist())
    row = df_articles.loc[df_articles["nom"] == article].iloc[0]
    info = {"sh": row.sh, "dd": float(row.dd), "cat": row.categorie}
    currency = st.selectbox("Devise", ["CNY", "USD"])
    q1, q2, q3 = st.columns(3)
    with q1: quantity = st.number_input("Quantité", min_value=1, value=50)
    with q2: unit_price = st.number_input("Prix unitaire", min_value=0.01, value=300.0)
    with q3: freight_currency = st.number_input("Fret total", min_value=0.0, value=1500.0)
    p1, p2, p3 = st.columns(3)
    with p1: port = st.number_input("Port / aéroport", min_value=0, value=150000, step=5000)
    with p2: fees = st.number_input("GUCE + honoraires", min_value=0, value=285000, step=5000)
    with p3: inland = st.number_input("Transport + surestaries", min_value=0, value=195000, step=5000)
    deposit = st.number_input("Acompte reçu", min_value=0, value=1000000, step=50000)
    rate = cny_rate if currency == "CNY" else usd_rate
    fob = quantity * unit_price * rate
    freight = freight_currency * rate
    insurance = max((fob + freight) * 0.005, 5000.0)
    caf = fob + freight + insurance
    customs = caf * (info["dd"] / 100 + 0.033) * 1.18
    transit = port + fees
    total = fob + freight + insurance + customs + transit + inland
    balance = total - deposit
    metrics = st.columns(4)
    for col, label, value in zip(metrics, ["CAF", "Douane", "Total", "Solde"], [caf, customs, total, balance]):
        col.markdown(f"<div class='metric'><small>{label}</small><h3>{value:,.0f} FCFA</h3></div>", unsafe_allow_html=True)
    if st.button("💾 Enregistrer le dossier", type="primary"):
        add_case(client_name, article, fob, total, balance, document_path)
        st.success("Dossier enregistré dans le CRM.")
    pdf = build_pdf(client_name, article, info, quantity, fob, freight, insurance, caf, customs, transit, inland, total, deposit, balance)
    st.download_button("📥 Télécharger le PDF", pdf.read_bytes(), file_name=pdf.name, mime="application/pdf")
    message = f"Bonjour {client_name}, votre cotation Kelanewin Transit est de {total:,.0f} FCFA. Solde : {balance:,.0f} FCFA."
    st.link_button("💬 WhatsApp", f"https://wa.me/{client_phone.replace('+','')}?text={quote(message)}")

with tab_crm:
    st.subheader("📂 CRM premium")
    if dossiers.empty:
        st.info("Aucun dossier.")
    else:
        status_filter = st.multiselect("Filtrer par statut", STATUTS, default=STATUTS)
        filtered = dossiers[dossiers["statut"].isin(status_filter)]
        m = st.columns(4)
        m[0].metric("Dossiers", len(filtered))
        m[1].metric("Facturé", f"{filtered.total_facture.sum():,.0f} FCFA")
        m[2].metric("Soldes", f"{filtered.solde_du.sum():,.0f} FCFA")
        m[3].metric("Livrés", int((filtered.statut == "Livré au Client").sum()))
        st.dataframe(filtered, use_container_width=True)
        st.download_button("📗 Exporter Excel", dataframe_xlsx(filtered), "dossiers_transit.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.download_button("📄 Exporter CSV", filtered.to_csv(index=False).encode("utf-8-sig"), "dossiers_transit.csv", "text/csv")
        case_id = st.selectbox("Dossier à modifier", filtered.id.tolist())
        new_status = st.selectbox("Nouveau statut", STATUTS)
        if st.button("Mettre à jour"):
            update_status(case_id, new_status)
            st.success("Statut mis à jour.")
            st.rerun()

with tab_ai:
    st.subheader("🤖 Assistant IA douanière")
    question = st.text_area("Votre question", placeholder="Quelles pièces préparer pour une importation ?")
    context = f"Nombre de dossiers: {len(dossiers)}; articles tarifaires: {len(df_articles)}"
    if st.button("🔍 Obtenir une réponse", type="primary"):
        if not question.strip():
            st.warning("Saisissez une question.")
        else:
            with st.spinner("Analyse en cours..."):
                answer, errors = ask_ai(groq_key, question, context)
            if answer:
                st.markdown(answer)
            else:
                st.error("L'assistant n'a pas pu répondre.")
                with st.expander("Détails"):
                    st.code("\n".join(errors))

with tab_tariff:
    st.subheader("📚 Base tarifaire SH")
    if st.session_state.user_role in ["Administrateur", "Commercial / Déclarant"]:
        with st.form("add_article"):
            name = st.text_input("Désignation")
            sh = st.text_input("Code SH")
            dd = st.number_input("DD (%)", min_value=0.0, max_value=100.0, value=20.0)
            category = st.text_input("Catégorie")
            if st.form_submit_button("Ajouter"):
                if name.strip() and sh.strip():
                    try:
                        with db_connection() as conn:
                            conn.execute("INSERT INTO articles (nom, sh, dd, categorie) VALUES (?, ?, ?, ?)", (name.strip(), sh.strip(), dd, category.strip() or "Autre"))
                        st.success("Article ajouté.")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Cet article existe déjà.")
    st.dataframe(read_table("SELECT * FROM articles ORDER BY nom"), use_container_width=True)
