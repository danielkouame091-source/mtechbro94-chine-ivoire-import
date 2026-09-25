import base64
import hashlib
import os
import sqlite3
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st

# Graphiques
try:
    import plotly.express as px
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

# Importation pour la génération PDF
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

try:
    from groq import Groq
except ImportError:
    Groq = None

# =========================================================
# CONFIGURATION ET DESIGN SYSTEM 3D / GLASSMORPHISM
# =========================================================
st.set_page_config(
    page_title="Kelanewin Transit - SYDAM Pro Enterprise 2026",
    page_icon="🇨🇮",
    layout="wide",
)

st.markdown(
    """
<style>
.stApp { 
    background-color: #0B0F19; 
    color: #F8FAFC; 
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
}
.header-banner { 
    background: linear-gradient(135deg, #047857 0%, #10B981 50%, #0284C7 100%); 
    padding: 28px; 
    border-radius: 20px; 
    color: white; 
    margin-bottom: 25px; 
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
    border: 1px solid rgba(255, 255, 255, 0.15);
}
.custom-card-3d { 
    background: #1E293B; 
    border-radius: 18px; 
    padding: 22px; 
    border: 1px solid #334155; 
    margin-bottom: 22px; 
    box-shadow: 8px 8px 16px #070a11, -8px -8px 16px #151a27;
}
.kpi-card {
    background: linear-gradient(145deg, #1e293b, #111827);
    border-radius: 14px;
    padding: 16px;
    border: 1px solid #374151;
    box-shadow: inset 1px 1px 2px rgba(255,255,255,0.05), 0 10px 15px -3px rgba(0,0,0,0.3);
    text-align: center;
}
.kpi-title {
    font-size: 0.8rem;
    color: #9CA3AF;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 5px;
}
.kpi-value {
    font-size: 1.35rem;
    font-weight: 700;
    color: #38BDF8;
}
.profit-box-3d { 
    background: linear-gradient(135deg, #15803D 0%, #166534 100%); 
    color: white; 
    padding: 18px; 
    border-radius: 14px; 
    text-align: center; 
    margin-top: 15px; 
    box-shadow: inset 2px 2px 5px rgba(255,255,255,0.2), 0 10px 20px rgba(21, 128, 61, 0.4);
    font-size: 1.2rem;
    font-weight: 600;
}
.ai-box-3d { 
    background: linear-gradient(135deg, #1E1B4B 0%, #312E81 100%); 
    border: 1px solid #6366F1; 
    padding: 22px; 
    border-radius: 16px; 
    margin-top: 15px; 
    box-shadow: 0 10px 20px rgba(99, 102, 241, 0.25);
}
.badge-sydam {
    background-color: #0284C7;
    color: white;
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 0.78rem;
    font-weight: 600;
}
</style>
""",
    unsafe_allow_html=True,
)

# =========================================================
# FONCTIONS DE HACHAGE ET SÉCURITÉ
# =========================================================
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

# =========================================================
# BDD SQLITE - STRUCTURATION & MIGRATION AUTOMATIQUE
# =========================================================
DB_NAME = "transit_enterprise.db"
UPLOAD_DIR = "uploads_dossiers"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Table des Utilisateurs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT,
            nom_complet TEXT,
            role TEXT,
            statut TEXT
        )
    """)

    # Utilisateurs par défaut si table vide
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        def_users = [
            ("admin", hash_password("transit2026"), "Administrateur Système", "Administrateur", "Actif"),
            ("commercial", hash_password("compta2026"), "Déclarant Commercial", "Commercial / Déclarant", "Actif"),
            ("comptable", hash_password("finance2026"), "Responsable Trésorerie", "Comptable / Trésorerie", "Actif"),
        ]
        cursor.executemany("INSERT INTO users (username, password_hash, nom_complet, role, statut) VALUES (?, ?, ?, ?, ?)", def_users)

    # Table des Articles
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT UNIQUE,
            sh TEXT,
            dd REAL,
            categorie TEXT
        )
    """)

    # Articles d'importation par défaut
    default_data = [
        ("Station Totale Topographique & GNSS/GPS", "9015.80.00", 5.0, "Topographie"),
        ("Théodolites, Niveaux Optiques & Laser", "9015.10.00", 5.0, "Topographie"),
        ("Smartphones, iPhones & Téléphones portables", "8517.13.00", 20.0, "High-Tech"),
        ("Ordinateurs Portables, MacBooks & Tablettes", "8471.30.00", 5.0, "Informatique"),
        ("Panneaux Photovoltaïques / Solaires", "8541.43.00", 5.0, "Énergie"),
        ("Groupes Électrogènes (Générateurs)", "8502.11.00", 5.0, "Machines"),
        ("Vélos et Bicyclettes sans moteur", "8712.00.00", 20.0, "Deux-roues"),
        ("Motos & Motocycles (125cc - 250cc)", "8711.20.00", 20.0, "Deux-roues"),
        ("Voitures de Tourisme (Berlines / SUV)", "8703.22.00", 20.0, "Véhicules"),
        ("Vêtements Homme (Pantalons, Chemises)", "6203.00.00", 20.0, "Textile"),
        ("Vêtements Femme (Robes, Jupes)", "6204.00.00", 20.0, "Textile"),
        ("Vêtements Bébés & Enfants", "6209.00.00", 20.0, "Textile"),
        ("Sacs à main pour Dames", "4202.22.00", 20.0, "Maroquinerie"),
    ]
    for item in default_data:
        cursor.execute("INSERT OR IGNORE INTO articles (nom, sh, dd, categorie) VALUES (?, ?, ?, ?)", item)

    # Table des Dossiers
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dossiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            client TEXT,
            article TEXT,
            devise TEXT,
            fob_devise REAL,
            taux_change REAL,
            fob_xof REAL,
            regime TEXT,
            num_bl TEXT,
            num_conteneur TEXT,
            total_facture REAL,
            marge_nette REAL,
            solde_du REAL,
            statut TEXT,
            document_path TEXT
        )
    """)

    # Migration / Alignement des colonnes existantes si nécessaire
    cursor.execute("PRAGMA table_info(dossiers)")
    cols = [c[1] for c in cursor.fetchall()]
    new_cols = {
        "devise": "TEXT DEFAULT 'CNY'",
        "fob_devise": "REAL DEFAULT 0",
        "taux_change": "REAL DEFAULT 1",
        "regime": "TEXT DEFAULT 'C100'",
        "num_bl": "TEXT DEFAULT ''",
        "num_conteneur": "TEXT DEFAULT ''",
        "marge_nette": "REAL DEFAULT 0"
    }
    for col_name, col_type in new_cols.items():
        if col_name not in cols:
            cursor.execute(f"ALTER TABLE dossiers ADD COLUMN {col_name} {col_type}")

    conn.commit()
    conn.close()

init_db()

# =========================================================
# REQUÊTES SQL & HELPERS
# =========================================================
def get_articles_db():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM articles ORDER BY id DESC", conn)
    conn.close()
    return df

def get_dossiers_db():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM dossiers ORDER BY id DESC", conn)
    conn.close()
    return df

def get_users_db():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT id, username, nom_complet, role, statut FROM users", conn)
    conn.close()
    return df

def ajouter_dossier_db(client, article, devise, fob_devise, taux_change, fob_xof, regime, num_bl, num_conteneur, total_facture, marge_nette, solde_du, statut="En cours", doc_path=""):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    date_jour = datetime.now().strftime("%Y-%m-%d %H:%M")
    cursor.execute(
        """INSERT INTO dossiers 
           (date, client, article, devise, fob_devise, taux_change, fob_xof, regime, num_bl, num_conteneur, total_facture, marge_nette, solde_du, statut, document_path) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (date_jour, client, article, devise, fob_devise, taux_change, fob_xof, regime, num_bl, num_conteneur, total_facture, marge_nette, solde_du, statut, doc_path)
    )
    conn.commit()
    conn.close()

def modifier_statut_dossier(dossier_id, nouveau_statut):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE dossiers SET statut = ? WHERE id = ?", (nouveau_statut, dossier_id))
    conn.commit()
    conn.close()

def supprimer_dossier_db(dossier_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM dossiers WHERE id = ?", (dossier_id,))
    conn.commit()
    conn.close()

def supprimer_article_db(article_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM articles WHERE id = ?", (article_id,))
    conn.commit()
    conn.close()

def modifier_article_db(article_id, nom, sh, dd, cat):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE articles SET nom = ?, sh = ?, dd = ?, categorie = ? WHERE id = ?", (nom, sh, dd, cat, article_id))
    conn.commit()
    conn.close()

def ajouter_utilisateur_db(username, password, nom_complet, role):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    pwd_hash = hash_password(password)
    cursor.execute("INSERT INTO users (username, password_hash, nom_complet, role, statut) VALUES (?, ?, ?, ?, 'Actif')",
                   (username, pwd_hash, nom_complet, role))
    conn.commit()
    conn.close()

def changer_statut_utilisateur_db(user_id, statut):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET statut = ? WHERE id = ?", (statut, user_id))
    conn.commit()
    conn.close()

# =========================================================
# GESTION DES TAUX DE CHANGE (CNY, USD, EUR, AED)
# =========================================================
@st.cache_data(ttl=3600)
def obtenir_taux_change():
    taux = {
        "EUR": 655.957, # Taux fixe BCEAO
        "USD": 610.0,
        "CNY": 85.0,
        "AED": 166.0
    }
    source = "⚠️ Taux fixes Bceao/Secours"
    try:
        url = "https://open.er-api.com/v6/latest/USD"
        res = requests.get(url, timeout=4)
        if res.status_code == 200:
            data = res.json().get("rates", {})
            usd_xof = data.get("XOF", 610.0)
            usd_cny = data.get("CNY", 7.2)
            usd_aed = data.get("AED", 3.67)

            taux["USD"] = round(usd_xof, 2)
            taux["CNY"] = round(usd_xof / usd_cny, 2) if usd_cny else 85.0
            taux["AED"] = round(usd_xof / usd_aed, 2) if usd_aed else 166.0
            source = "🟢 Taux direct API en temps réel"
    except Exception:
        pass
    return taux, source

taux_dict, status_api_devises = obtenir_taux_change()

# =========================================================
# AUTHENTIFICATION BDD AVEC RÔLES (RBAC)
# =========================================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_role = ""
    st.session_state.username = ""
    st.session_state.nom_complet = ""

if not st.session_state.authenticated:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
        st.subheader("🔐 Connexion Sécurisée - Kelanewin Transit")
        st.caption("Authentification BDD & Contrôle d'Accès Avancé (RBAC)")

        user_input = st.text_input("Identifiant utilisateur")
        pass_input = st.text_input("Mot de passe", type="password")

        if st.button("Se connecter", use_container_width=True):
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("SELECT id, password_hash, nom_complet, role, statut FROM users WHERE username = ?", (user_input,))
            res = cursor.fetchone()
            conn.close()

            if res:
                uid, pwd_hash, nom_comp, role, statut = res
                if statut != "Actif":
                    st.error("Ce compte est désactivé. Veuillez contacter l'administrateur.")
                elif verify_password(pass_input, pwd_hash):
                    st.session_state.authenticated = True
                    st.session_state.username = user_input
                    st.session_state.nom_complet = nom_comp
                    st.session_state.user_role = role
                    st.rerun()
                else:
                    st.error("Mot de passe incorrect.")
            else:
                st.error("Utilisateur introuvable.")
        st.markdown('</div>', unsafe_allow_html=True)
        st.stop()

# =========================================================
# GÉNÉRATION PDF PROFESSIONNEL
# =========================================================
def generer_pdf_devis_pro(nom_client, article_nom, item_info, quantite, fob_xof, fret_xof, assurance_xof, caf_xof, total_douane, total_transit, post_acheminement, total_facture, acompte, solde_du, regime, num_bl, num_conteneur):
    pdf_filename = f"Devis_Pro_{nom_client.replace(' ', '_')}.pdf"
    doc = SimpleDocTemplate(pdf_filename, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'TitleStyle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#047857'), spaceAfter=4, alignment=1
    )
    subtitle_style = ParagraphStyle(
        'SubTitleStyle', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor('#64748B'), spaceAfter=12, alignment=1
    )

    elements.append(Paragraph("<b>KELANEWIN TRANSIT S.A. (SYDAM PRO CI)</b>", title_style))
    elements.append(Paragraph("Agrément Douane N° 2026/CI-ABJ | Port d'Abidjan & San-Pédro<br/>Contact : contact@kelanewin-transit.ci | Tél: +225 07 00 00 00 00", subtitle_style))
    elements.append(Spacer(1, 4))

    info_client = f"""<b>Client / Importateur :</b> {nom_client}<br/>
<b>Date d'émission :</b> {datetime.now().strftime('%d/%m/%Y')}<br/>
<b>Régime Douanier :</b> {regime} | <b>N° B/L :</b> {num_bl or 'N/A'} | <b>N° Conteneur :</b> {num_conteneur or 'N/A'}"""
    elements.append(Paragraph(info_client, styles['Normal']))
    elements.append(Spacer(1, 10))

    data = [
        ["Désignation / Prestation", "Code SH", "Qté", "Montant (FCFA)"],
        [article_nom, item_info['sh'], str(quantite), f"{fob_xof:,.0f}"],
        ["Fret International & Assurance", "-", "-", f"{(fret_xof + assurance_xof):,.0f}"],
        ["Valeur CAF (Douane)", "-", "-", f"{caf_xof:,.0f}"],
        [f"Droits & Taxes Douanières ({regime})", "-", "-", f"{total_douane:,.0f}"],
        ["Passage Portuaire, GUCE & Honoraires", "-", "-", f"{total_transit:,.0f}"],
        ["Post-acheminement & Surestaries", "-", "-", f"{post_acheminement:,.0f}"],
        ["<b>TOTAL GÉNÉRAL FACTURÉ</b>", "", "", f"<b>{total_facture:,.0f} FCFA</b>"],
        ["Acompte versé / Provision", "", "", f"{acompte:,.0f} FCFA"],
        ["<b>SOLDE RESTANT À PAYER</b>", "", "", f"<b>{solde_du:,.0f} FCFA</b>"]
    ]

    t = Table(data, colWidths=[220, 80, 40, 140])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0F172A')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 5),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#F8FAFC')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('BACKGROUND', (0,7), (-1,7), colors.HexColor('#E2E8F0')),
        ('BACKGROUND', (0,9), (-1,9), colors.HexColor('#DCFCE7')),
    ]))

    elements.append(t)
    elements.append(Spacer(1, 15))
    elements.append(Paragraph("<b>Conditions de règlement :</b> 50% à la commande, solde avant BAE (Bon à Enlever).<br/><i>Proforma arrêtée à la somme de <b>{:,.0f} FCFA</b>. Cachet & Signature :</i>".format(total_facture), styles['Normal']))

    doc.build(elements)
    return pdf_filename

# =========================================================
# BARRE LATÉRALE - UTILISATEUR & DEVISES & SMTP
# =========================================================
st.sidebar.title("🇨🇮 KELANEWIN TRANSIT")
st.sidebar.markdown(f"**Utilisateur :** `{st.session_state.nom_complet}`")
st.sidebar.markdown(f"**Rôle :** `{st.session_state.user_role}`")
st.sidebar.markdown("---")

default_key = st.secrets.get("GROQ_API_KEY", "") if hasattr(st, "secrets") else ""
groq_api_key = st.sidebar.text_input("🔑 Clé API Groq", value=default_key, type="password")

st.sidebar.subheader("💱 Taux de Change (BCEAO / Live)")
st.sidebar.caption(status_api_devises)

taux_cny = st.sidebar.number_input("1 CNY -> FCFA", value=taux_dict["CNY"], step=0.1)
taux_usd = st.sidebar.number_input("1 USD -> FCFA", value=taux_dict["USD"], step=1.0)
taux_eur = st.sidebar.number_input("1 EUR -> FCFA", value=taux_dict["EUR"], step=0.1)
taux_aed = st.sidebar.number_input("1 AED -> FCFA", value=taux_dict["AED"], step=0.5)

st.sidebar.subheader("⚙️ Configuration SMTP (Email)")
smtp_server = st.sidebar.text_input("Serveur SMTP", value="smtp.gmail.com")
smtp_port = st.sidebar.number_input("Port SMTP", value=587)
sender_email = st.sidebar.text_input("Email Expéditeur", value="")
smtp_password = st.sidebar.text_input("Mot de passe application", type="password")

st.sidebar.markdown("---")
if st.sidebar.button("🚪 Déconnexion"):
    st.session_state.authenticated = False
    st.rerun()

# =========================================================
# BANNIÈRE PRINCIPALE
# =========================================================
st.markdown("""
<div class="header-banner">
    <h1>📦 KELANEWIN TRANSIT : ENTERPRISE SUITE 2026</h1>
    <p>Plateforme Intégrée : Analytics, Suivi B/L Armateurs, Régimes SYDAM & CRM Multicouche</p>
</div>
""", unsafe_allow_html=True)

# Définition des onglets principaux
tab_analytics, tab_cotation, tab_crm, tab_tracking, tab_ai, tab_base_sh, tab_admin = st.tabs([
    "📈 Dashboard & Analytics",
    "📊 Cotation & Régimes SYDAM",
    "📂 CRM & Pièces Jointes",
    "🚢 Suivi Armateurs & B/L",
    "🤖 Assistant IA SYDAM",
    "📚 Base SH & CRUD Articles",
    "⚙️ User Management (RBAC)"
])

df_articles_db = get_articles_db()
liste_articles_noms = df_articles_db["nom"].tolist()

# =========================================================
# TAB 1 : DASHBOARD & ANALYTICS (KPIs & PLOTLY)
# =========================================================
with tab_analytics:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📊 Tableau de Bord Exécutif & Indicateurs Clés")

    df_dossiers_all = get_dossiers_db()

    if df_dossiers_all.empty:
        st.info("Aucune donnée enregistrée dans l'ERP pour alimenter le Tableau de Bord.")
    else:
        ca_total = df_dossiers_all["total_facture"].sum()
        marge_totale = df_dossiers_all["marge_nette"].sum()
        nb_dossiers = len(df_dossiers_all)
        solde_en_attente = df_dossiers_all["solde_du"].sum()

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Chiffre d'Affaires Cumulé</div><div class="kpi-value">{ca_total:,.0f} FCFA</div></div>""", unsafe_allow_html=True)
        with k2:
            st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Bénéfice Net Transitaire</div><div class="kpi-value" style="color:#10B981;">{marge_totale:,.0f} FCFA</div></div>""", unsafe_allow_html=True)
        with k3:
            st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Nombre de Dossiers</div><div class="kpi-value">{nb_dossiers}</div></div>""", unsafe_allow_html=True)
        with k4:
            st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Soldes à Recouvrer</div><div class="kpi-value" style="color:#F59E0B;">{solde_en_attente:,.0f} FCFA</div></div>""", unsafe_allow_html=True)

        st.markdown("<br/>", unsafe_allow_html=True)

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.markdown("##### 📌 Répartition des Dossiers par Statut")
            statut_counts = df_dossiers_all["statut"].value_counts().reset_index()
            statut_counts.columns = ["Statut", "Nombre"]
            if HAS_PLOTLY:
                fig_pie = px.pie(statut_counts, values="Nombre", names="Statut", hole=0.4, color_discrete_sequence=px.colors.qualitative.Set2)
                fig_pie.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#FFFFFF")
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.bar_chart(statut_counts.set_index("Statut"))

        with col_g2:
            st.markdown("##### 💰 Chiffre d'Affaires par Client")
            ca_client = df_dossiers_all.groupby("client")["total_facture"].sum().reset_index()
            if HAS_PLOTLY:
                fig_bar = px.bar(ca_client, x="client", y="total_facture", labels={"total_facture": "CA (FCFA)", "client": "Client"}, color_discrete_sequence=["#38BDF8"])
                fig_bar.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#FFFFFF")
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.bar_chart(ca_client.set_index("client"))

    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 2 : COTATION & RÉGIMES DOUANIERS SYDAM
# =========================================================
with tab_cotation:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("👤 1. Coordonnées & Suivi Logistique (B/L & Conteneur)")
    c1, c2, c3 = st.columns(3)
    with c1:
        nom_client = st.text_input("Nom / Entreprise Client", value="ETS KOUASSI & FRERES")
        email_client = st.text_input("Email Client", value="client@example.com")
    with c2:
        num_bl = st.text_input("Numéro de B/L (Connaissement)", value="MEDUST123456")
        num_conteneur = st.text_input("Numéro de Conteneur", value="MSCU9876543")
    with c3:
        tel_client = st.text_input("Téléphone / WhatsApp", value="+2250700000000")
        uploaded_file = st.file_uploader("📎 Pièce jointe (PDF, Image)", type=["pdf", "png", "jpg", "jpeg"])

    saved_doc_path = ""
    if uploaded_file is not None:
        saved_doc_path = os.path.join(UPLOAD_DIR, f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uploaded_file.name}")
        with open(saved_doc_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"Fichier sauvegardé : {uploaded_file.name}")

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📋 2. Devises, Régimes Douaniers SYDAM & Marchandise")

    col_a, col_b = st.columns([2, 1])

    with col_a:
        article_nom = st.selectbox("Sélectionner l'article", liste_articles_noms)
        item_row = df_articles_db[df_articles_db["nom"] == article_nom].iloc[0]
        item_info = {"sh": item_row["sh"], "dd": item_row["dd"], "cat": item_row["categorie"]}

        ca1, ca2 = st.columns(2)
        with ca1:
            devise_facture = st.selectbox("Devise de la Facture", ["CNY (Yuan Chinois)", "USD (Dollar)", "EUR (Euro)", "AED (Dirham E.A.U)"])
            regime_douanier = st.selectbox("Régime Douanier SYDAM", [
                "C100 - Mise à la Consommation Directe",
                "E100 - Entrepôt de Douane (Suspensif)",
                "AT - Admission Temporaire",
                "TR - Transit Réexportation"
            ])
        with ca2:
            quantite = st.number_input("Quantité d'unités", min_value=1, value=50)
            prix_unitaire = st.number_input(f"Prix Unitaire ({devise_facture.split()[0]})", min_value=0.01, value=300.0)

        fret_devise = st.number_input(f"Fret Total ({devise_facture.split()[0]})", min_value=0.0, value=1500.0)

        fob_devise = quantite * prix_unitaire
        code_devise = devise_facture.split()[0]
        taux_actuel = taux_cny if code_devise == "CNY" else (taux_usd if code_devise == "USD" else (taux_eur if code_devise == "EUR" else taux_aed))

        fob_xof = fob_devise * taux_actuel
        st.markdown(f"👉 **FOB Total :** `{fob_devise:,.2f} {code_devise}` = `{(fob_xof):,.0f} FCFA` (Taux: {taux_actuel} FCFA)")

    with col_b:
        st.markdown(f"""
        <div style="background:#0F172A; padding:16px; border-radius:12px; border:1px solid #334155;">
            <span class="badge-sydam">RÉGIME SYDAM</span><br/><br/>
            <b>Code SH :</b> <code>{item_info['sh']}</code><br/>
            <b>Catégorie :</b> {item_info['cat']}<br/>
            <b>Droit Douane (DD) :</b> {item_info['dd']}%<br/>
            <b>Régime Saisi :</b> {regime_douanier.split('-')[0]}<br/>
            <hr style="border-color:#334155">
            <small style="color:#38BDF8;">{"⚠️ FDI/RFC Obligatoires" if fob_xof >= 1000000 else "✅ FDI non requise (< 1M FCFA)"}</small>
        </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Calculs Financiers Douaniers selon le Régime
    fret_xof = fret_devise * taux_actuel
    assurance_xof = max((fob_xof + fret_xof) * 0.005, 5000.0)
    caf_xof = fob_xof + fret_xof + assurance_xof

    taux_dd = item_info["dd"] / 100.0
    taux_redevances = 0.010 + 0.008 + 0.002 # RS + PCS + PUA

    if "E100" in regime_douanier or "TR" in regime_douanier:
        # Régimes suspensifs: DD & TVA suspendus
        total_droits_hors_tva = caf_xof * 0.01 # Redevance minimale de transit
        tva_xof = 0.0
    elif "AT" in regime_douanier:
        # Admission temporaire: TVA suspendue, DD partiel
        total_droits_hors_tva = caf_xof * (taux_dd * 0.3 + taux_redevances)
        tva_xof = 0.0
    else:
        # C100 - Consommation Directe
        total_droits_hors_tva = caf_xof * (taux_dd + taux_redevances)
        tva_xof = (caf_xof + total_droits_hors_tva) * 0.18

    total_douane = total_droits_hors_tva + tva_xof

    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("🚚 3. Prestations, Honoraires & Post-Acheminement")
    h1, h2, h3 = st.columns(3)
    with h1:
        frais_port = st.number_input("Passage Portuaire (FCFA)", value=150000)
        frais_guce = st.number_input("Frais GUCE (FCFA)", value=35000)
    with h2:
        honoraires = st.number_input("Honoraires Transit (FCFA)", value=250000)
        charges_ops = st.number_input("Charges Réelles / Débours (FCFA)", value=50000)
    with h3:
        transport_interieur = st.number_input("Post-Acheminement (FCFA)", value=120000)
        surestaries = st.number_input("Provisions Surestaries (FCFA)", value=75000)
        acompte = st.number_input("Acompte Reçu (FCFA)", value=1000000)

    post_acheminement_total = transport_interieur + surestaries
    marge_nette = honoraires - charges_ops
    total_transit = frais_port + frais_guce + honoraires
    total_facture = fob_xof + fret_xof + assurance_xof + total_douane + total_transit + post_acheminement_total
    solde_du = total_facture - acompte

    st.markdown(f'<div class="profit-box-3d">💰 MARGE NETTE DU TRANSITAIRE : <b>{marge_nette:,.0f} FCFA</b></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📊 4. Validation & Génération de la Proforma")

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Valeur CAF</div><div class="kpi-value">{caf_xof:,.0f} FCFA</div></div>""", unsafe_allow_html=True)
    with k2:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Taxes Douane ({regime_douanier.split()[0]})</div><div class="kpi-value">{total_douane:,.0f} FCFA</div></div>""", unsafe_allow_html=True)
    with k3:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Frais Transit & Post-Ach.</div><div class="kpi-value">{(total_transit + post_acheminement_total):,.0f} FCFA</div></div>""", unsafe_allow_html=True)
    with k4:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title" style="color:#10B981;">Total Facturé</div><div class="kpi-value" style="color:#10B981;">{total_facture:,.0f} FCFA</div></div>""", unsafe_allow_html=True)

    st.markdown("<br/>", unsafe_allow_html=True)

    if st.button("💾 Enregistrer le Dossier dans la Base CRM", use_container_width=True):
        ajouter_dossier_db(nom_client, article_nom, code_devise, fob_devise, taux_actuel, fob_xof, regime_douanier, num_bl, num_conteneur, total_facture, marge_nette, solde_du, "En cours", saved_doc_path)
        st.success("Dossier enregistré dans le CRM avec succès !")

    pdf_path = generer_pdf_devis_pro(nom_client, article_nom, item_info, quantite, fob_xof, fret_xof, assurance_xof, caf_xof, total_douane, total_transit, post_acheminement_total, total_facture, acompte, solde_du, regime_douanier, num_bl, num_conteneur)

    with open(pdf_path, "rb") as f:
        PDFbyte = f.read()

    st.download_button("📥 Télécharger la Facture Proforma & Devis Officiel (PDF)", data=PDFbyte, file_name=pdf_path, mime="application/octet-stream", use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 3 : CRM, PIÈCES JOINTES & ACTIONS CRUD DOSSIERS
# =========================================================
with tab_crm:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📂 Suivi Opérationnel, Pièces Jointes & Exportation CRM")

    df_crm = get_dossiers_db()

    if df_crm.empty:
        st.info("Aucun dossier enregistré.")
    else:
        # Exportation Excel / CSV
        c_exp1, c_exp2 = st.columns(2)
        with c_exp1:
            csv_data = df_crm.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Exporter le CRM en CSV", data=csv_data, file_name="crm_dossiers_transit.csv", mime="text/csv", use_container_width=True)
        with c_exp2:
            # Recherche
            filtre_client = st.text_input("🔍 Filtrer par nom de client ou B/L")

        if filtre_client:
            df_crm = df_crm[df_crm['client'].str.contains(filtre_client, case=False, na=False) | df_crm['num_bl'].str.contains(filtre_client, case=False, na=False)]

        st.dataframe(df_crm[['id', 'date', 'client', 'article', 'regime', 'num_bl', 'total_facture', 'solde_du', 'statut']], use_container_width=True)

        st.markdown("---")
        st.subheader("🛠️ Consultation des Documents & Actions sur le Dossier")

        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            dossier_id_sel = st.selectbox("Sélectionner l'ID du Dossier", df_crm['id'].tolist())
            row_sel = df_crm[df_crm['id'] == dossier_id_sel].iloc[0]

        with col_c2:
            st.markdown(f"**Client :** {row_sel['client']}")
            st.markdown(f"**B/L :** `{row_sel['num_bl'] or 'N/A'}`")
            doc_p = row_sel['document_path']
            if doc_p and os.path.exists(str(doc_p)):
                with open(doc_p, "rb") as file_doc:
                    st.download_button("👁️ Télécharger/Voir la Pièce Jointe", data=file_doc, file_name=os.path.basename(doc_p), use_container_width=True)
            else:
                st.caption("Aucune pièce jointe stockée.")

        with col_c3:
            statut_nouveau = st.selectbox("Modifier le Statut", ["En cours", "FDI & RFC Validées", "Visite Douanière", "BAE Émis", "Livré Client"], index=0)
            if st.button("Mettre à jour le Statut", use_container_width=True):
                modifier_statut_dossier(dossier_id_sel, statut_nouveau)
                st.success("Statut mis à jour !")
                st.rerun()

            if st.session_state.user_role == "Administrateur":
                if st.button("🗑️ Supprimer ce Dossier", use_container_width=True):
                    supprimer_dossier_db(dossier_id_sel)
                    st.warning("Dossier supprimé.")
                    st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 4 : SUIVI DES NAVIRES & TRACKING ARMATEURS
# =========================================================
with tab_tracking:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("🚢 Suivi en Direct des Navires & Conteneurs Armateurs")
    st.caption("Accès direct aux portails de tracking des principales compagnies maritimes servant le Port d'Abidjan")

    num_tracking_input = st.text_input("Saisir un N° de Connaissement (B/L) ou N° de Conteneur", value="MSCU1234567")

    st.markdown("<br/>", unsafe_allow_html=True)

    t1, t2, t3, t4 = st.columns(4)
    with t1:
        st.markdown("### 🟦 MSC")
        st.link_button("Track MSC 🔗", "https://www.msc.com/en/track-a-shipment", use_container_width=True)
    with t2:
        st.markdown("### 🟦 CMA CGM")
        st.link_button("Track CMA CGM 🔗", "https://www.cma-cgm.com/ebusiness/tracking", use_container_width=True)
    with t3:
        st.markdown("### 🟦 MAERSK")
        st.link_button("Track Maersk 🔗", f"https://www.maersk.com/tracking/{num_tracking_input}", use_container_width=True)
    with t4:
        st.markdown("### 🟦 GRIMALDI")
        st.link_button("Track Grimaldi 🔗", "https://www.grimaldi.napoli.it/gws/pu/search_cargo.aspx", use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 5 : ASSISTANT IA SYDAM (GROQ LLAMA3)
# =========================================================
with tab_ai:
    st.markdown('<div class="ai-box-3d">', unsafe_allow_html=True)
    st.subheader("🤖 Assistant Expert Douane & Transit (Groq LLM)")
    user_query = st.text_area("Posez votre question réglementaire (ex: procédures d'exonération, admission temporaire, règles d'origine CEDEAO...)")

    if st.button("🔍 Interroger l'Expert IA"):
        if groq_api_key and Groq:
            try:
                client_ai = Groq(api_key=groq_api_key)
                prompt_expert = f"Vous êtes un expert déclarant en douane et transitaire agréé en Côte d'Ivoire. Répondez avec précision : {user_query}"

                modeles = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"]
                res_ai = None
                for m in modeles:
                    try:
                        res_ai = client_ai.chat.completions.create(
                            model=m, messages=[{"role": "user", "content": prompt_expert}], temperature=0.2
                        )
                        break
                    except Exception:
                        continue

                if res_ai:
                    st.info(res_ai.choices[0].message.content)
                else:
                    st.error("Impossible d'interroger Groq. Vérifiez vos clés et crédits.")
            except Exception as e:
                st.error(f"Erreur : {e}")
        else:
            st.warning("Veuillez renseigner votre clé API Groq dans le panneau latéral.")
    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 6 : BASE SH & ACTIONS CRUD ARTICLES
# =========================================================
with tab_base_sh:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📚 Répertoire Tarifaire & Modifications CRUD des Articles")

    if st.session_state.user_role in ["Administrateur", "Commercial / Déclarant"]:
        c_art1, c_art2 = st.columns(2)

        with c_art1:
            st.markdown("##### ➕ Ajouter un Article")
            with st.form("form_add_art"):
                art_nom = st.text_input("Nom de l'article")
                art_sh = st.text_input("Code SH (ex: 8703.22.00)")
                art_dd = st.number_input("Droit de Douane (%)", value=20.0)
                art_cat = st.text_input("Catégorie", value="Divers")
                btn_add_art = st.form_submit_button("Enregistrer Article")

            if btn_add_art and art_nom and art_sh:
                try:
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO articles (nom, sh, dd, categorie) VALUES (?, ?, ?, ?)", (art_nom, art_sh, art_dd, art_cat))
                    conn.commit()
                    conn.close()
                    st.success("Article ajouté !")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur d'enregistrement : {e}")

        with c_art2:
            st.markdown("##### 🛠️ Modifier ou Supprimer un Article")
            df_curr_art = get_articles_db()
            art_sel_id = st.selectbox("Sélectionner l'article à gérer", df_curr_art['id'].tolist() if not df_curr_art.empty else [0])

            if not df_curr_art.empty and art_sel_id != 0:
                row_art = df_curr_art[df_curr_art['id'] == art_sel_id].iloc[0]
                edit_nom = st.text_input("Nom", value=row_art['nom'])
                edit_sh = st.text_input("SH", value=row_art['sh'])
                edit_dd = st.number_input("DD (%)", value=float(row_art['dd']))
                edit_cat = st.text_input("Catégorie", value=row_art['categorie'])

                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("✏️ Appliquer Modifications"):
                        modifier_article_db(art_sel_id, edit_nom, edit_sh, edit_dd, edit_cat)
                        st.success("Modifications enregistrées.")
                        st.rerun()
                with col_btn2:
                    if st.button("🗑️ Supprimer Article"):
                        supprimer_article_db(art_sel_id)
                        st.warning("Article supprimé.")
                        st.rerun()

    st.markdown("---")
    st.markdown("### Liste Générale des Articles")
    st.dataframe(get_articles_db(), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 7 : GESTION DES UTILISATEURS (RBAC ADMIN)
# =========================================================
with tab_admin:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("⚙️ Administration & Gestion des Comptes Utilisateurs")

    if st.session_state.user_role != "Administrateur":
        st.warning("Accès réservé exclusivement aux Administrateurs du système.")
    else:
        st.dataframe(get_users_db(), use_container_width=True)

        st.markdown("---")
        u_col1, u_col2 = st.columns(2)

        with u_col1:
            st.markdown("##### ➕ Créer un Nouvel Utilisateur")
            with st.form("form_add_user"):
                new_username = st.text_input("Identifiant (Username)")
                new_password = st.text_input("Mot de passe", type="password")
                new_nom_complet = st.text_input("Nom Complet")
                new_role = st.selectbox("Rôle", ["Administrateur", "Commercial / Déclarant", "Comptable / Trésorerie"])
                btn_create_u = st.form_submit_button("Créer l'utilisateur")

            if btn_create_u and new_username and new_password:
                try:
                    ajouter_utilisateur_db(new_username, new_password, new_nom_complet, new_role)
                    st.success("Utilisateur créé avec succès en BDD !")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur (Identifiant déjà utilisé) : {e}")

        with u_col2:
            st.markdown("##### 🔒 Activer / Désactiver un Compte")
            df_u = get_users_db()
            user_sel_id = st.selectbox("Sélectionner l'utilisateur", df_u['id'].tolist())
            user_row = df_u[df_u['id'] == user_sel_id].iloc[0]

            st.write(f"**Utilisateur :** {user_row['username']} ({user_row['nom_complet']})")
            st.write(f"**Statut Actuel :** `{user_row['statut']}`")

            col_s1, col_s2 = st.columns(2)
            with col_s1:
                if st.button("✅ Activer le compte"):
                    changer_statut_utilisateur_db(user_sel_id, "Actif")
                    st.success("Compte activé.")
                    st.rerun()
            with col_s2:
                if st.button("🚫 Désactiver le compte"):
                    changer_statut_utilisateur_db(user_sel_id, "Inactif")
                    st.warning("Compte désactivé.")
                    st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
