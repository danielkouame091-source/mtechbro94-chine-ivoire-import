import base64
import hashlib
import io
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
import plotly.express as px
import plotly.graph_objects as go

# ReportLab pour la génération de PDF professionnels
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

try:
    from groq import Groq
except ImportError:
    Groq = None

# =========================================================
# CONFIGURATION & STYLE DESIGN 3D / GLASSMORPHISM
# =========================================================
st.set_page_config(
    page_title="Kelanewin Transit - SYDAM Pro Enterprise",
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
    padding: 25px 30px; 
    border-radius: 20px; 
    color: white; 
    margin-bottom: 25px; 
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
    border: 1px solid rgba(255, 255, 255, 0.15);
}
.custom-card-3d { 
    background: #1E293B; 
    border-radius: 18px; 
    padding: 25px; 
    border: 1px solid #334155; 
    margin-bottom: 25px; 
    box-shadow: 8px 8px 16px #070a11, -8px -8px 16px #151a27;
}
.kpi-card {
    background: linear-gradient(145deg, #1e293b, #111827);
    border-radius: 14px;
    padding: 18px;
    border: 1px solid #374151;
    box-shadow: inset 1px 1px 2px rgba(255,255,255,0.05), 0 10px 15px -3px rgba(0,0,0,0.3);
    text-align: center;
}
.kpi-title {
    font-size: 0.85rem;
    color: #9CA3AF;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 5px;
}
.kpi-value {
    font-size: 1.4rem;
    font-weight: 700;
    color: #38BDF8;
}
.profit-box-3d { 
    background: linear-gradient(135deg, #15803D 0%, #166534 100%); 
    color: white; 
    padding: 20px; 
    border-radius: 16px; 
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
    font-size: 0.8rem;
    font-weight: 600;
}
</style>
""",
    unsafe_allow_html=True,
)

# =========================================================
# GESTION SÉCURISÉE DES MOTS DE PASSE & BASE DE DONNÉES SQLITE
# =========================================================
DB_NAME = "transit_enterprise.db"
UPLOAD_DIR = "uploads_dossiers"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Table Articles & SH
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT UNIQUE,
            sh TEXT,
            dd REAL,
            categorie TEXT
        )
    """)

    # Table Dossiers CRM enrichie
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dossiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            client TEXT,
            article TEXT,
            regime TEXT,
            fob_xof REAL,
            total_facture REAL,
            solde_du REAL,
            statut TEXT,
            bl_number TEXT,
            container_number TEXT,
            document_path TEXT
        )
    """)

    # Table Utilisateurs RBAC BDD
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT,
            role TEXT,
            statut TEXT DEFAULT 'Actif'
        )
    """)

    # Utilisateurs par défaut
    default_users = [
        ("admin", hash_password("transit2026"), "Administrateur", "Actif"),
        ("comptable", hash_password("finance2026"), "Comptable / Trésorerie", "Actif"),
        ("commercial", hash_password("compta2026"), "Commercial / Déclarant", "Actif")
    ]
    for u in default_users:
        cursor.execute("INSERT OR IGNORE INTO users (username, password_hash, role, statut) VALUES (?, ?, ?, ?)", u)

    # Articles d'importation Chine / CI par défaut
    default_data = [
        ("Station Totale Topographique & GNSS/GPS", "9015.80.00", 5.0, "Topographie"),
        ("Théodolites, Niveaux Optiques & Laser", "9015.10.00", 5.0, "Topographie"),
        ("Smartphones, iPhones & Téléphones portables", "8517.13.00", 20.0, "High-Tech"),
        ("Ordinateurs Portables, MacBooks & Tablettes", "8471.30.00", 5.0, "Informatique"),
        ("Panneaux Photovoltaïques / Solaires", "8541.43.00", 5.0, "Énergie"),
        ("Groupes Électrogènes (Générateurs)", "8502.11.00", 5.0, "Machines"),
        ("Vélos et Bicyclettes sans moteur", "8712.00.00", 20.0, "Matériel de transport (Deux-roues)"),
        ("Motos & Motocycles (125cc - 250cc)", "8711.20.00", 20.0, "Matériel de transport (Deux-roues)"),
        ("Voitures de Tourisme (Berlines / SUV)", "8703.22.00", 20.0, "Matériel de transport (Véhicules)"),
        ("Vêtements Homme (Pantalons, Chemises)", "6203.00.00", 20.0, "Textile et Habillement"),
        ("Vêtements Femme (Robes, Jupes)", "6204.00.00", 20.0, "Textile et Habillement"),
        ("Vêtements Bébés & Enfants", "6209.00.00", 20.0, "Textile et Habillement"),
        ("Sacs à main pour Dames", "4202.22.00", 20.0, "Maroquinerie et Accessoires")
    ]
    for item in default_data:
        cursor.execute("INSERT OR IGNORE INTO articles (nom, sh, dd, categorie) VALUES (?, ?, ?, ?)", item)

    conn.commit()
    conn.close()

init_db()

# =========================================================
# FONCTIONS DE GESTION DE BASE DE DONNÉES (CRUD)
# =========================================================
def get_user_db(username):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password_hash, role, statut FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    return row

def get_all_users_db():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT id, username, role, statut FROM users", conn)
    conn.close()
    return df

def create_user_db(username, password, role):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    pwd_hash = hash_password(password)
    cursor.execute("INSERT INTO users (username, password_hash, role, statut) VALUES (?, ?, ?, 'Actif')", (username, pwd_hash, role))
    conn.commit()
    conn.close()

def toggle_user_statut_db(user_id, current_statut):
    new_statut = "Inactif" if current_statut == "Actif" else "Actif"
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET statut = ? WHERE id = ?", (new_statut, user_id))
    conn.commit()
    conn.close()

def get_articles_db():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM articles", conn)
    conn.close()
    return df

def update_article_db(article_id, nom, sh, dd, categorie):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE articles SET nom=?, sh=?, dd=?, categorie=? WHERE id=?", (nom, sh, dd, categorie, article_id))
    conn.commit()
    conn.close()

def delete_article_db(article_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM articles WHERE id=?", (article_id,))
    conn.commit()
    conn.close()

def ajouter_dossier_db(client, article, regime, fob, total, solde, statut="En cours", bl="", container="", doc_path=""):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    date_jour = datetime.now().strftime("%Y-%m-%d %H:%M")
    cursor.execute(
        "INSERT INTO dossiers (date, client, article, regime, fob_xof, total_facture, solde_du, statut, bl_number, container_number, document_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (date_jour, client, article, regime, fob, total, solde, statut, bl, container, doc_path)
    )
    conn.commit()
    conn.close()

def get_dossiers_db():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM dossiers ORDER BY id DESC", conn)
    conn.close()
    return df

def mettre_a_jour_statut_db(dossier_id, nouveau_statut):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE dossiers SET statut = ? WHERE id = ?", (nouveau_statut, dossier_id))
    conn.commit()
    conn.close()

def update_dossier_db(dossier_id, client, article, regime, solde_du, statut, bl, container):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE dossiers 
        SET client=?, article=?, regime=?, solde_du=?, statut=?, bl_number=?, container_number=? 
        WHERE id=?
    """, (client, article, regime, solde_du, statut, bl, container, dossier_id))
    conn.commit()
    conn.close()

def delete_dossier_db(dossier_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM dossiers WHERE id=?", (dossier_id,))
    conn.commit()
    conn.close()

# =========================================================
# CALCULATEUR MULTI-DEVISES & RÉGIMES DOUANIERS
# =========================================================
@st.cache_data(ttl=3600)
def obtenir_taux_change_automatique():
    default_rates = {"CNY": 85.0, "USD": 610.0, "EUR": 655.957, "AED": 166.0}
    try:
        url = "https://open.er-api.com/v6/latest/USD"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            rates = response.json().get("rates", {})
            usd_xof = rates.get("XOF", 610.0)
            usd_cny = rates.get("CNY", 7.2)
            usd_aed = rates.get("AED", 3.67)
            return {
                "CNY": round(usd_xof / usd_cny, 2) if usd_cny else 85.0,
                "USD": round(usd_xof, 2),
                "EUR": 655.957,
                "AED": round(usd_xof / usd_aed, 2) if usd_aed else 166.0
            }, "🟢 Taux direct API (Temps réel)"
    except Exception:
        pass
    return default_rates, "⚠️ Mode secours (Hors ligne)"

taux_devises_dict, status_api_devises = obtenir_taux_change_automatique()

def calculer_droits_douane(caf_xof, dd_pct, regime_code):
    if regime_code == "C100 - Mise à la consommation":
        taux_dd = dd_pct / 100.0
        taux_redevances = 0.010 + 0.008 + 0.002 # RS (1%) + PCS (0.8%) + PUA (0.2%)
        droits_hors_tva = caf_xof * (taux_dd + taux_redevances)
        tva = (caf_xof + droits_hors_tva) * 0.18
        total_douane = droits_hors_tva + tva
        details = f"DD ({dd_pct}%): {caf_xof*taux_dd:,.0f} FCFA | Redevances: {caf_xof*taux_redevances:,.0f} FCFA | TVA (18%): {tva:,.0f} FCFA"
    elif regime_code == "E100 - Entrepôt de douane (Suspensif)":
        taux_redevances = 0.005 # Redevance d'entrepôt
        droits_hors_tva = caf_xof * taux_redevances
        total_douane = droits_hors_tva
        details = f"Régime Suspensif E100 : Droits & TVA suspendus | Redevance Entrepôt: {droits_hors_tva:,.0f} FCFA"
    elif regime_code == "AT - Admission Temporaire":
        taux_redevances = 0.010 # Taxe AT
        droits_hors_tva = caf_xof * taux_redevances
        total_douane = droits_hors_tva
        details = f"Régime Suspensif AT : Droits & TVA suspendus | Taxe AT: {droits_hors_tva:,.0f} FCFA"
    elif regime_code == "TR - Transit / Réexportation":
        taux_redevances = 0.005 # Taxe de transit
        droits_hors_tva = caf_xof * taux_redevances
        total_douane = droits_hors_tva
        details = f"Régime Transit TR : Exonération TVA | Redevance Transit: {droits_hors_tva:,.0f} FCFA"
    else:
        taux_dd = dd_pct / 100.0
        droits_hors_tva = caf_xof * (taux_dd + 0.02)
        tva = (caf_xof + droits_hors_tva) * 0.18
        total_douane = droits_hors_tva + tva
        details = f"Régime standard | Total: {total_douane:,.0f} FCFA"
        
    return total_douane, details

# =========================================================
# AUTHENTIFICATION & GESTION DES SESSIONS
# =========================================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_role = ""
    st.session_state.username = ""

if not st.session_state.authenticated:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
        st.subheader("🔐 Connexion Entreprise - Kelanewin Transit")
        st.caption("Sécurité Hachée SHA256 & Contrôle d'Accès BDD (RBAC)")

        username_input = st.text_input("Identifiant utilisateur")
        password_input = st.text_input("Mot de passe", type="password")

        if st.button("Se connecter", use_container_width=True):
            user_data = get_user_db(username_input)
            if user_data:
                u_id, u_name, u_pwd_hash, u_role, u_statut = user_data
                if u_statut != "Actif":
                    st.error("Ce compte a été désactivé par l'administrateur.")
                elif hash_password(password_input) == u_pwd_hash:
                    st.session_state.authenticated = True
                    st.session_state.username = u_name
                    st.session_state.user_role = u_role
                    st.rerun()
                else:
                    st.error("Mot de passe incorrect.")
            else:
                st.error("Utilisateur introuvable. (Ex: admin / transit2026)")
        st.markdown('</div>', unsafe_allow_html=True)
        st.stop()

# =========================================================
# GÉNÉRATION DE PDF PROFORMA AMÉLIORÉ
# =========================================================
def generer_pdf_devis_pro(nom_client, article_nom, item_info, regime_code, quantite, fob_xof, fret_xof, assurance_xof, caf_xof, total_douane, total_transit, post_acheminement, total_facture, acompte, solde_du, bl_num="", container_num=""):
    pdf_filename = f"Devis_Pro_{nom_client.replace(' ', '_')}.pdf"
    doc = SimpleDocTemplate(pdf_filename, pagesize=letter, rightMargin=35, leftMargin=35, topMargin=35, bottomMargin=35)
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#047857'),
        spaceAfter=4,
        alignment=1
    )
    subtitle_style = ParagraphStyle(
        'SubTitleStyle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#64748B'),
        spaceAfter=15,
        alignment=1
    )

    elements.append(Paragraph("<b>KELANEWIN TRANSIT S.A. (SYDAM PRO CI)</b>", title_style))
    elements.append(Paragraph("Agrément Douane N° 2026/CI-ABJ | Abidjan Port & San-Pédro<br/>Contact : contact@kelanewin-transit.ci | Tél: +225 07 00 00 00 00", subtitle_style))
    elements.append(Spacer(1, 5))

    info_client_text = f"""<b>Client / Importateur :</b> {nom_client}<br/>
<b>Date d'émission :</b> {datetime.now().strftime('%d/%m/%Y')}<br/>
<b>Régime Douanier :</b> {regime_code}<br/>
<b>N° Connaissement (B/L) :</b> {bl_num if bl_num else 'En attente'} | <b>N° Conteneur :</b> {container_num if container_num else 'En attente'}<br/>
<b>Objet :</b> Facture Proforma & Cotation Logistique Douanière
"""
    elements.append(Paragraph(info_client_text, styles['Normal']))
    elements.append(Spacer(1, 10))

    data = [
        ["Désignation / Prestation", "Code SH", "Qté", "Montant (FCFA)"],
        [article_nom, item_info['sh'], str(quantite), f"{fob_xof:,.0f}"],
        ["Fret International & Assurance", "-", "-", f"{(fret_xof + assurance_xof):,.0f}"],
        ["Valeur CAF (Douane)", "-", "-", f"{caf_xof:,.0f}"],
        [f"Droits & Taxes Douane ({regime_code.split('-')[0].strip()})", "-", "-", f"{total_douane:,.0f}"],
        ["Passage Portuaire, GUCE & Honoraires", "-", "-", f"{total_transit:,.0f}"],
        ["Post-acheminement & Surestaries", "-", "-", f"{post_acheminement:,.0f}"],
        ["<b>TOTAL GÉNÉRAL FACTURÉ</b>", "", "", f"<b>{total_facture:,.0f} FCFA</b>"],
        ["Acompte versé / Provision", "", "", f"{acompte:,.0f} FCFA"],
        ["<b>SOLDE RESTANT À PAYER</b>", "", "", f"<b>{solde_du:,.0f} FCFA</b>"]
    ]

    t = Table(data, colWidths=[230, 80, 45, 145])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0F172A')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#F8FAFC')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('BACKGROUND', (0,7), (-1,7), colors.HexColor('#E2E8F0')),
        ('BACKGROUND', (0,9), (-1,9), colors.HexColor('#DCFCE7')),
    ]))

    elements.append(t)
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("<b>Conditions de règlement :</b> 50% à la commande, solde avant BAE (Bon à Enlever).<br/><i>Arrêtée la présente proforma à la somme de <b>{:,.0f} FCFA</b>. Cachet & Signature autorisés :</i>".format(total_facture), styles['Normal']))

    doc.build(elements)
    return pdf_filename

# =========================================================
# BARRE LATÉRALE DE NAVIGATION
# =========================================================
st.sidebar.title("🇨🇮 KELANEWIN TRANSIT")
st.sidebar.markdown(f"**Utilisateur :** `{st.session_state.username}`")
st.sidebar.markdown(f"**Rôle :** `{st.session_state.user_role}`")
st.sidebar.markdown("---")

groq_default_key = st.secrets.get("GROQ_API_KEY", "") if hasattr(st, "secrets") else ""
groq_api_key = st.sidebar.text_input("🔑 Clé API Groq", value=groq_default_key, type="password")

st.sidebar.subheader("💱 Taux de Devises (FCFA)")
st.sidebar.caption(status_api_devises)
taux_cny_xof = st.sidebar.number_input("1 CNY (Chine)", value=taux_devises_dict["CNY"], step=0.1)
taux_usd_xof = st.sidebar.number_input("1 USD (Dollar)", value=taux_devises_dict["USD"], step=1.0)
taux_eur_xof = st.sidebar.number_input("1 EUR (Euro)", value=taux_devises_dict["EUR"], step=0.1)
taux_aed_xof = st.sidebar.number_input("1 AED (Dubaï)", value=taux_devises_dict["AED"], step=0.5)

st.sidebar.subheader("⚙️ Configuration SMTP Email")
smtp_server = st.sidebar.text_input("Serveur SMTP", value="smtp.gmail.com")
smtp_port = st.sidebar.number_input("Port SMTP", value=587)
sender_email = st.sidebar.text_input("Email Expéditeur", value="")
smtp_password = st.sidebar.text_input("Mot de passe application", type="password")

st.sidebar.markdown("---")
if st.sidebar.button("🚪 Se déconnecter", use_container_width=True):
    st.session_state.authenticated = False
    st.rerun()

# =========================================================
# EN-TÊTE ET TABS PRINCIPAUX
# =========================================================
st.markdown("""
<div class="header-banner">
    <h1>📦 KELANEWIN TRANSIT : ENTERPRISE SUITE 2026</h1>
    <p>Système de Cotation, Tracking Armateurs, Analytics CRM & Intelligence Artificielle SYDAM</p>
</div>
""", unsafe_allow_html=True)

tabs_list = [
    "📈 Dashboard & Analytics",
    "📊 Cotation & Devis Pro",
    "📂 CRM, Workflow & Tracking",
    "🤖 Assistant IA SYDAM",
    "📚 Base SH & Articles",
]

if st.session_state.user_role == "Administrateur":
    tabs_list.append("🔐 Admin & Utilisateurs BDD")

tabs = st.tabs(tabs_list)
tab_dash = tabs[0]
tab_cotation = tabs[1]
tab_crm = tabs[2]
tab_ai = tabs[3]
tab_sh = tabs[4]
tab_admin = tabs[5] if st.session_state.user_role == "Administrateur" else None

df_articles_db = get_articles_db()
liste_articles_noms = df_articles_db["nom"].tolist()

# =========================================================
# TAB 1 : DASHBOARD EXECUTIVE & ANALYTICS
# =========================================================
with tab_dash:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📈 Tableau de Bord Analytique - Performance Transit")
    
    df_d = get_dossiers_db()
    
    if df_d.empty:
        st.info("Aucune donnée enregistrée dans la base CRM pour générer le tableau de bord.")
    else:
        tot_ca = df_d['total_facture'].sum()
        tot_solde = df_d['solde_du'].sum()
        nb_dossiers = len(df_d)
        nb_livres = len(df_d[df_d['statut'] == 'Livré au Client'])

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Facturation Cumulée</div><div class="kpi-value">{tot_ca:,.0f} FCFA</div></div>""", unsafe_allow_html=True)
        with k2:
            st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Soldes à Recouvrer</div><div class="kpi-value" style="color:#F59E0B;">{tot_solde:,.0f} FCFA</div></div>""", unsafe_allow_html=True)
        with k3:
            st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Total Dossiers</div><div class="kpi-value">{nb_dossiers}</div></div>""", unsafe_allow_html=True)
        with k4:
            st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Dossiers Livrés</div><div class="kpi-value" style="color:#10B981;">{nb_livres}</div></div>""", unsafe_allow_html=True)

        st.markdown("<br/>", unsafe_allow_html=True)
        col_g1, col_g2 = st.columns(2)

        with col_g1:
            fig_statut = px.pie(df_d, names='statut', title="Répartition des Dossiers par Statut", hole=0.4, color_discrete_sequence=px.colors.qualitative.Set2)
            fig_statut.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='white')
            st.plotly_chart(fig_statut, use_container_width=True)

        with col_g2:
            fig_article = px.bar(df_d, x='article', y='total_facture', color='regime', title="Facturation par Article & Régime Douanier", barmode='group')
            fig_article.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='white')
            st.plotly_chart(fig_article, use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 2 : COTATION, DEVIS PRO & EXPÉDITION
# =========================================================
with tab_cotation:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("👤 1. Importateur & Références Transport")
    c1, c2, c3 = st.columns(3)
    with c1:
        nom_client = st.text_input("Nom / Enterprise Importatrice", value="ETS KOUASSI & FRERES")
    with c2:
        email_client = st.text_input("Email Client", value="client@example.com")
    with c3:
        tel_client = st.text_input("Téléphone / WhatsApp", value="+2250700000000")

    c4, c5 = st.columns(2)
    with c4:
        bl_num = st.text_input("N° de Connaissement (B/L) / LTA", value="MEDU12345678")
    with c5:
        container_num = st.text_input("N° de Conteneur", value="MSCU9876543")

    uploaded_file = st.file_uploader("📎 Pièces justificatives (Facture, B/L, Packing List)", type=["pdf", "png", "jpg", "jpeg"])
    saved_doc_path = ""
    if uploaded_file is not None:
        saved_doc_path = os.path.join(UPLOAD_DIR, f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uploaded_file.name}")
        with open(saved_doc_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"Document joint : {uploaded_file.name}")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📋 2. Marchandise, Régime Douanier & Devises")
    col_a, col_b = st.columns([2, 1])

    with col_a:
        article_nom = st.selectbox("Sélectionner l'article", liste_articles_noms)
        item_row = df_articles_db[df_articles_db["nom"] == article_nom].iloc[0]
        item_info = {"sh": item_row["sh"], "dd": item_row["dd"], "cat": item_row["categorie"]}

        regime_code = st.selectbox("Régime Douanier SYDAM", [
            "C100 - Mise à la consommation",
            "E100 - Entrepôt de douane (Suspensif)",
            "AT - Admission Temporaire",
            "TR - Transit / Réexportation"
        ])

        devise_choisie = st.selectbox("Devise Facture Fournisseur", ["CNY (Yuan Chinois)", "USD (Dollar)", "EUR (Euro)", "AED (Dirham EAU)"])

        m1, m2, m3 = st.columns(3)
        with m1:
            quantite = st.number_input("Quantité", min_value=1, value=50)
        with m2:
            prix_unitaire_devise = st.number_input("Prix Unitaire (Devise)", min_value=0.01, value=300.0)
        with m3:
            fret_devise = st.number_input("Fret Maritime/Aérien (Devise)", min_value=0.0, value=1500.0)

        fob_devise = quantite * prix_unitaire_devise

    with col_b:
        taux_moyen = taux_cny_xof if "CNY" in devise_choisie else (taux_usd_xof if "USD" in devise_choisie else (taux_eur_xof if "EUR" in devise_choisie else taux_aed_xof))
        fob_xof_estim = fob_devise * taux_moyen
        alerte_fdi = "✅ FDI non requise (< 1M FCFA)" if fob_xof_estim < 1000000 else "⚠️ FDI & RFC Obligatoires (GUCE)"

        st.markdown(f"""
        <div style="background:#0F172A; padding:18px; border-radius:12px; border:1px solid #334155;">
            <span class="badge-sydam">RÉGIME : {regime_code.split('-')[0].strip()}</span><br/><br/>
            <b>Code SH :</b> <code>{item_info['sh']}</code><br/>
            <b>Catégorie :</b> {item_info['cat']}<br/>
            <b>Droit de Douane Standard :</b> {item_info['dd']}%<br/>
            <hr style="border-color:#334155">
            <small style="color:#38BDF8;">{alerte_fdi}</small>
        </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("🚚 3. Transit, Post-Acheminement & Prestations")
    h1, h2, h3 = st.columns(3)
    with h1:
        frais_port = st.number_input("Passage Portuaire / Aéroport (FCFA)", value=150000, step=5000)
        frais_guce = st.number_input("Frais GUCE & Webb Fontaine (FCFA)", value=35000, step=2500)
    with h2:
        honoraires = st.number_input("Honoraires Transit (FCFA)", value=250000, step=10000)
        charges_ops = st.number_input("Débours & Charges Réelles (FCFA)", value=50000, step=5000)
    with h3:
        transport_interieur = st.number_input("Transport / Post-Acheminement (FCFA)", value=120000, step=10000)
        surestaries = st.number_input("Provision Surestaries (FCFA)", value=75000, step=5000)
        acompte = st.number_input("Acompte Reçu du Client (FCFA)", value=1000000, step=50000)

    post_acheminement_total = transport_interieur + surestaries
    benefice_net = honoraires - charges_ops
    st.markdown(f'<div class="profit-box-3d">💰 BÉNÉFICE NET DU TRANSITAIRE : <b>{benefice_net:,.0f} FCFA</b></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Calculs Financiers Finaux
    fob_xof = fob_devise * taux_moyen
    fret_xof = fret_devise * taux_moyen
    assurance_xof = max((fob_xof + fret_xof) * 0.005, 5000.0)
    caf_xof = fob_xof + fret_xof + assurance_xof

    total_douane, details_douane = calculer_droits_douane(caf_xof, item_info["dd"], regime_code)
    total_transit = frais_port + frais_guce + honoraires
    total_facture = fob_xof + fret_xof + assurance_xof + total_douane + total_transit + post_acheminement_total
    solde_du = total_facture - acompte

    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📊 4. Synthèse Financière & Validation Proforma")
    st.caption(f"ℹ️ Détails Douane SYDAM : {details_douane}")

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Valeur CAF Total</div><div class="kpi-value">{caf_xof:,.0f} FCFA</div></div>""", unsafe_allow_html=True)
    with k2:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Droits & Taxes Douane</div><div class="kpi-value">{total_douane:,.0f} FCFA</div></div>""", unsafe_allow_html=True)
    with k3:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Frais Port & Logistics</div><div class="kpi-value">{(total_transit + post_acheminement_total):,.0f} FCFA</div></div>""", unsafe_allow_html=True)
    with k4:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title" style="color:#10B981;">Total Facturé</div><div class="kpi-value" style="color:#10B981;">{total_facture:,.0f} FCFA</div></div>""", unsafe_allow_html=True)

    st.markdown("<br/>", unsafe_allow_html=True)

    if st.button("💾 Enregistrer le Dossier dans la Base CRM", use_container_width=True):
        ajouter_dossier_db(nom_client, article_nom, regime_code, fob_xof, total_facture, solde_du, "En cours", bl_num, container_num, saved_doc_path)
        st.success("Dossier enregistré avec succès dans l'ERP CRM !")

    pdf_path = generer_pdf_devis_pro(nom_client, article_nom, item_info, regime_code, quantite, fob_xof, fret_xof, assurance_xof, caf_xof, total_douane, total_transit, post_acheminement_total, total_facture, acompte, solde_du, bl_num, container_num)

    with open(pdf_path, "rb") as pdf_file:
        PDFbyte = pdf_file.read()

    st.download_button(
        label="📥 Télécharger la Facture Proforma Officielle (PDF)",
        data=PDFbyte,
        file_name=pdf_path,
        mime="application/pdf",
        use_container_width=True
    )

    st.markdown('</div>', unsafe_allow_html=True)

    # Envoi Mail & WhatsApp
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📧 Transmettre la Cotation au Client")

    msg_texte = f"""Bonjour {nom_client},
Veuillez trouver ci-joint la cotation proforma de Kelanewin Transit pour l'importation de {article_nom}.
N° B/L: {bl_num} | Régime: {regime_code}
Montant Total : {total_facture:,.0f} FCFA | Solde dû : {solde_du:,.0f} FCFA.
Cordialement, L'équipe Kelanewin Transit."""

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        if st.button("🚀 Envoyer par Email (SMTP)", use_container_width=True):
            if not sender_email or not smtp_password:
                st.error("Veuillez renseigner vos identifiants SMTP dans la barre latérale.")
            else:
                try:
                    msg = MIMEMultipart()
                    msg['From'] = sender_email
                    msg['To'] = email_client
                    msg['Subject'] = f"Facture Proforma & Cotation - Kelanewin Transit ({article_nom})"
                    msg.attach(MIMEText(msg_texte, 'plain'))

                    with open(pdf_path, "rb") as f:
                        attach = MIMEApplication(f.read(), Name=pdf_path)
                        attach['Content-Disposition'] = f'attachment; filename="{pdf_path}"'
                        msg.attach(attach)

                    server = smtplib.SMTP(smtp_server, smtp_port)
                    server.starttls()
                    server.login(sender_email, smtp_password)
                    server.sendmail(sender_email, email_client, msg.as_string())
                    server.quit()
                    st.success("E-mail envoyé avec succès !")
                except Exception as e:
                    st.error(f"Erreur SMTP : {e}")

    with col_s2:
        whatsapp_url = f"https://wa.me/{tel_client.strip().replace('+', '')}?text={quote(msg_texte)}"
        st.link_button("💬 Envoyer par WhatsApp", whatsapp_url, use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 3 : WORKFLOW CRM, PIÈCES JOINTES & TRACKING ARMATEURS
# =========================================================
with tab_crm:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("🚢 Suivi du Tracking Armateurs & Conteneurs")
    st.caption("Accès direct aux portails de suivi des compagnies maritimes principales")

    col_tr1, col_tr2, col_tr3, col_tr4 = st.columns(4)
    with col_tr1:
        st.link_button("🌐 MSC Tracking", "https://www.msc.com/en/track-a-shipment", use_container_width=True)
    with col_tr2:
        st.link_button("🌐 CMA CGM Tracking", "https://www.cma-cgm.com/ebusiness/tracking", use_container_width=True)
    with col_tr3:
        st.link_button("🌐 Maersk Tracking", "https://www.maersk.com/tracking/", use_container_width=True)
    with col_tr4:
        st.link_button("🌐 Grimaldi Lines", "https://www.grimaldi.napoli.it/en/tracking.html", use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📂 Liste & Gestion des Dossiers CRM")
    df_dossiers = get_dossiers_db()

    if df_dossiers.empty:
        st.info("Aucun dossier enregistré.")
    else:
        st.dataframe(df_dossiers, use_container_width=True)

        # Export BDD
        col_ex1, col_ex2 = st.columns(2)
        with col_ex1:
            csv = df_dossiers.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Exporter le CRM en CSV", data=csv, file_name="dossiers_crm_transit.csv", mime="text/csv", use_container_width=True)
        with col_ex2:
            buffer_excel = io.BytesIO()
            with pd.ExcelWriter(buffer_excel, engine='openpyxl') as writer:
                df_dossiers.to_excel(writer, index=False, sheet_name='Dossiers')
            st.download_button("📥 Exporter le CRM en Excel", data=buffer_excel.getvalue(), file_name="dossiers_crm_transit.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

    st.markdown("---")
    st.subheader("👁️ Consultation des Pièces Jointes & Édition d'un Dossier")

    if not df_dossiers.empty:
        col_c1, col_c2 = st.columns([1, 2])
        with col_c1:
            selected_id = st.selectbox("Sélectionner l'ID du Dossier", df_dossiers['id'].tolist())
            row_dos = df_dossiers[df_dossiers['id'] == selected_id].iloc[0]

            if row_dos['document_path'] and os.path.exists(row_dos['document_path']):
                with open(row_dos['document_path'], "rb") as f_doc:
                    st.download_button("📥 Télécharger la Pièce Jointe du Dossier", data=f_doc.read(), file_name=os.path.basename(row_dos['document_path']), use_container_width=True)
            else:
                st.caption("Aucune pièce jointe associée.")

        with col_c2:
            st.markdown("##### ✏️ Modifier ou Supprimer le Dossier")
            with st.form("form_edit_dossier"):
                e_client = st.text_input("Client", value=row_dos['client'])
                e_article = st.selectbox("Article", liste_articles_noms, index=liste_articles_noms.index(row_dos['article']) if row_dos['article'] in liste_articles_noms else 0)
                e_regime = st.text_input("Régime", value=row_dos['regime'] if row_dos['regime'] else "C100")
                e_solde = st.number_input("Solde Dû (FCFA)", value=float(row_dos['solde_du']))
                e_statut = st.selectbox("Statut Opérationnel", [
                    "En cours", 
                    "FDI & RFC Validées", 
                    "Visite Douanière en Cours", 
                    "Bon à Enlever (BAE) Émis", 
                    "Livré au Client"
                ], index=0)
                e_bl = st.text_input("N° B/L", value=row_dos['bl_number'] if row_dos['bl_number'] else "")
                e_container = st.text_input("N° Conteneur", value=row_dos['container_number'] if row_dos['container_number'] else "")

                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    sub_update = st.form_submit_button("Enregistrer les Modifications", use_container_width=True)
                with col_btn2:
                    sub_delete = st.form_submit_button("🗑️ Supprimer le Dossier", use_container_width=True)

            if sub_update:
                update_dossier_db(selected_id, e_client, e_article, e_regime, e_solde, e_statut, e_bl, e_container)
                st.success(f"Dossier #{selected_id} mis à jour !")
                st.rerun()

            if sub_delete:
                delete_dossier_db(selected_id)
                st.warning(f"Dossier #{selected_id} supprimé !")
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 4 : ASSISTANT IA SYDAM (GROQ LLAMA 3)
# =========================================================
with tab_ai:
    st.markdown('<div class="ai-box-3d">', unsafe_allow_html=True)
    st.subheader("🤖 Assistant Expert Kelanewin Transit (Groq Llama 3)")
    user_query = st.text_area("Posez votre question sur les procédures douanières ivoiriennes (SYDAM, GUCE, régimes suspensifs...)")

    if st.button("🔍 Interroger l'Expert"):
        if groq_api_key and Groq:
            try:
                client_ai = Groq(api_key=groq_api_key)
                prompt_expert = f"Vous êtes un expert transitaire en Côte d'Ivoire. Répondez précisément : {user_query}"

                modeles = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"]
                res_ai = None
                for mod in modeles:
                    try:
                        res_ai = client_ai.chat.completions.create(
                            model=mod,
                            messages=[{"role": "user", "content": prompt_expert}],
                            temperature=0.2,
                            max_tokens=1024,
                        )
                        break
                    except Exception:
                        continue

                if res_ai:
                    st.info(res_ai.choices[0].message.content)
                else:
                    st.error("Impossible d'obtenir une réponse d'IA.")
            except Exception as e:
                st.error(f"Erreur d'initialisation Groq : {e}")
        else:
            st.warning("Veuillez renseigner votre clé API Groq dans la barre latérale.")
    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 5 : BASE SH & CRUD ARTICLES
# =========================================================
with tab_sh:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📚 Gestion de la Base Tarifaire SH & Articles")

    if st.session_state.user_role in ["Administrateur", "Commercial / Déclarant"]:
        col_form1, col_form2 = st.columns([1, 1])

        with col_form1:
            st.markdown("##### 1️⃣ Ajouter un nouvel article")
            with st.form("form_ajout_art"):
                n_nom = st.text_input("Désignation")
                n_sh = st.text_input("Code SH")
                n_dd = st.number_input("Droits de Douane - DD (%)", value=20.0)
                n_cat = st.text_input("Catégorie")
                sub_art = st.form_submit_button("Ajouter à la Base")

            if sub_art and n_nom and n_sh:
                try:
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO articles (nom, sh, dd, categorie) VALUES (?, ?, ?, ?)", (n_nom, n_sh, n_dd, n_cat))
                    conn.commit()
                    conn.close()
                    st.success("Article ajouté avec succès !")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur : {e}")

        with col_form2:
            st.markdown("##### 2️⃣ Importation Massive (Excel / CSV)")
            file_bulk = st.file_uploader("Fichier d'importation (nom, sh, dd, categorie)", type=["csv", "xlsx"])
            if file_bulk is not None:
                try:
                    df_bulk = pd.read_csv(file_bulk) if file_bulk.name.endswith('.csv') else pd.read_excel(file_bulk)
                    if {"nom", "sh", "dd", "categorie"}.issubset(set(df_bulk.columns)):
                        if st.button("🚀 Lancer l'importation massive"):
                            conn = sqlite3.connect(DB_NAME)
                            cursor = conn.cursor()
                            c = 0
                            for _, r in df_bulk.iterrows():
                                cursor.execute("INSERT OR IGNORE INTO articles (nom, sh, dd, categorie) VALUES (?, ?, ?, ?)", (str(r['nom']), str(r['sh']), float(r['dd']), str(r['categorie'])))
                                c += 1
                            conn.commit()
                            conn.close()
                            st.success(f"{c} articles importés !")
                            st.rerun()
                except Exception as e:
                    st.error(f"Erreur d'import : {e}")

    st.markdown("---")
    st.markdown("### Liste & Modification / Suppression d'Articles")
    df_art = get_articles_db()
    st.dataframe(df_art, use_container_width=True)

    if not df_art.empty and st.session_state.user_role == "Administrateur":
        st.markdown("##### ✏️ Éditer ou Supprimer un Article existant")
        art_id_sel = st.selectbox("ID Article", df_art['id'].tolist())
        art_row = df_art[df_art['id'] == art_id_sel].iloc[0]

        with st.form("form_edit_art"):
            u_nom = st.text_input("Nom", value=art_row['nom'])
            u_sh = st.text_input("Code SH", value=art_row['sh'])
            u_dd = st.number_input("DD (%)", value=float(art_row['dd']))
            u_cat = st.text_input("Catégorie", value=art_row['categorie'])

            btn_u1, btn_u2 = st.columns(2)
            with btn_u1:
                sub_art_u = st.form_submit_button("Enregistrer", use_container_width=True)
            with btn_u2:
                sub_art_d = st.form_submit_button("🗑️ Supprimer", use_container_width=True)

        if sub_art_u:
            update_article_db(art_id_sel, u_nom, u_sh, u_dd, u_cat)
            st.success("Article mis à jour !")
            st.rerun()

        if sub_art_d:
            delete_article_db(art_id_sel)
            st.warning("Article supprimé !")
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 6 : ADMINISTRATION & UTILISATEURS BDD (ADMIN SEULEMENT)
# =========================================================
if tab_admin and st.session_state.user_role == "Administrateur":
    with tab_admin:
        st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
        st.subheader("🔐 Administration des Comptes Utilisateurs (RBAC BDD)")

        col_u1, col_u2 = st.columns([1, 1])

        with col_u1:
            st.markdown("##### 1️⃣ Créer un nouvel utilisateur")
            with st.form("form_new_user"):
                new_username = st.text_input("Identifiant")
                new_password = st.text_input("Mot de passe", type="password")
                new_role = st.selectbox("Rôle RBA", ["Administrateur", "Commercial / Déclarant", "Comptable / Trésorerie"])
                sub_user = st.form_submit_button("Créer l'Utilisateur", use_container_width=True)

            if sub_user and new_username and new_password:
                try:
                    create_user_db(new_username, new_password, new_role)
                    st.success(f"Utilisateur '{new_username}' créé avec succès !")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur : {e}")

        with col_u2:
            st.markdown("##### 2️⃣ Gestion des comptes existants")
            df_users = get_all_users_db()
            st.dataframe(df_users, use_container_width=True)

            sel_u_id = st.selectbox("ID Utilisateur à basculer (Actif/Inactif)", df_users['id'].tolist())
            u_statut_curr = df_users[df_users['id'] == sel_u_id]['statut'].values[0]

            if st.button("Changer le statut (Activer / Désactiver)", use_container_width=True):
                toggle_user_statut_db(sel_u_id, u_statut_curr)
                st.success("Statut mis à jour !")
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)
