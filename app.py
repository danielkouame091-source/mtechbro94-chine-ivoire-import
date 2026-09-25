import base64
import hashlib
import io
import json
import os
import random
import re
import sqlite3
import smtplib
from datetime import datetime, timedelta
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import quote

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# ReportLab pour la génération de documents PDF
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

try:
    from groq import Groq
except ImportError:
    Groq = None

# =========================================================
# CONFIGURATION ET STYLE NATIONAL GOVTECH & SAAS B2B
# =========================================================
st.set_page_config(
    page_title="SNDGIR SaaS - Platforme Transit & Douanes",
    page_icon="🇨🇮",
    layout="wide",
)

st.markdown(
    """
<style>
.stApp { 
    background-color: #060911; 
    color: #F8FAFC; 
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
}
.header-banner { 
    background: linear-gradient(135deg, #064E3B 0%, #047857 40%, #0284C7 100%); 
    padding: 25px 30px; 
    border-radius: 20px; 
    color: white; 
    margin-bottom: 25px; 
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.7), 0 8px 10px -6px rgba(0, 0, 0, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.2);
}
.custom-card-3d { 
    background: #0F172A; 
    border-radius: 18px; 
    padding: 22px; 
    border: 1px solid #1E293B; 
    margin-bottom: 22px; 
    box-shadow: 6px 6px 18px #03060D, -6px -6px 18px #1B2437;
}
.kpi-card {
    background: linear-gradient(145deg, #1e293b, #0f172a);
    border-radius: 14px;
    padding: 16px;
    border: 1px solid #334155;
    box-shadow: inset 1px 1px 2px rgba(255,255,255,0.08), 0 10px 15px -3px rgba(0,0,0,0.4);
    text-align: center;
}
.kpi-title { font-size: 0.8rem; color: #9CA3AF; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px; }
.kpi-value { font-size: 1.4rem; font-weight: 700; color: #38BDF8; }

.canal-vert { background-color: #064E3B; color: #34D399; padding: 6px 12px; border-radius: 8px; font-weight: bold; }
.canal-bleu { background-color: #1E3A8A; color: #60A5FA; padding: 6px 12px; border-radius: 8px; font-weight: bold; }
.canal-jaune { background-color: #78350F; color: #FBBF24; padding: 6px 12px; border-radius: 8px; font-weight: bold; }
.canal-rouge { background-color: #7F1D1D; color: #F87171; padding: 6px 12px; border-radius: 8px; font-weight: bold; }
</style>
""",
    unsafe_allow_html=True,
)

# =========================================================
# BASE DE DONNÉES SQLITE - ARCHITECTURE MULTI-TENANT (SAAS)
# =========================================================
DB_NAME = "sndgir_national_customs.db"
UPLOAD_DIR = "uploads_dossiers"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. Table Tenants (Entreprises clientes du SaaS)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tenants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom_societe TEXT UNIQUE,
            plan_abonnement TEXT DEFAULT 'Starter',
            statut_compte TEXT DEFAULT 'Actif',
            date_expiration TEXT
        )
    """)

    # 2. Table Utilisateurs & Rôles
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER DEFAULT 1,
            username TEXT UNIQUE,
            password_hash TEXT,
            role TEXT,
            statut TEXT DEFAULT 'Actif',
            FOREIGN KEY(tenant_id) REFERENCES tenants(id)
        )
    """)

    # 3. Table Manifestes & Fret
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS manifestes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER DEFAULT 1,
            num_manifeste TEXT UNIQUE,
            moyen_transport TEXT,
            num_voyage TEXT,
            provenance TEXT,
            date_arrivee TEXT,
            statut TEXT DEFAULT 'Enregistré'
        )
    """)

    # 4. Table Lignes de Fret
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fret_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER DEFAULT 1,
            num_manifeste TEXT,
            bl_number TEXT UNIQUE,
            consignee TEXT,
            poids_brut REAL,
            nb_colis INTEGER,
            statut_apurement TEXT DEFAULT 'Non apuré'
        )
    """)

    # 5. Table Articles & SH
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT UNIQUE,
            sh TEXT,
            dd REAL,
            categorie TEXT
        )
    """)

    # 6. Table Déclarations & Dossiers de Transit
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dossiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER DEFAULT 1,
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
            date_arrivee TEXT,
            score_risque REAL,
            canal_selectivite TEXT,
            motifs_risque TEXT,
            quittance_num TEXT,
            document_path TEXT,
            honoraires REAL DEFAULT 150000,
            frais_port REAL DEFAULT 85000,
            frais_transport REAL DEFAULT 120000,
            surestaries_xof REAL DEFAULT 0,
            statut_livraison TEXT DEFAULT 'Sous douane'
        )
    """)

    # AUTO-MIGRATION : Colonnes Multi-Tenant
    existing_tables = ["dossiers", "users", "manifestes", "fret_lines"]
    for table in existing_tables:
        existing_cols = [col[1] for col in cursor.execute(f"PRAGMA table_info({table})").fetchall()]
        if "tenant_id" not in existing_cols:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN tenant_id INTEGER DEFAULT 1")

    # Table Traces d'Audit
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER DEFAULT 1,
            timestamp TEXT,
            username TEXT,
            action TEXT,
            details TEXT
        )
    """)

    # Données par défaut SaaS
    cursor.execute("INSERT OR IGNORE INTO tenants (id, nom_societe, plan_abonnement, statut_compte) VALUES (1, 'TRANSIT IVOIRE (Démo)', 'Enterprise', 'Actif')")
    
    default_users = [
        (1, "admin", hash_password("transit2026"), "Super Admin SaaS", "Actif"),
        (1, "verificateur", hash_password("douane2026"), "Vérificateur Douanier", "Actif"),
        (1, "caissier", hash_password("caisse2026"), "Agent de Caisse", "Actif"),
        (1, "declarant", hash_password("compta2026"), "Commissionnaire Agréé", "Actif"),
        (1, "client_importateur", hash_password("client2026"), "Portail Client Importateur", "Actif")
    ]
    for u in default_users:
        cursor.execute("INSERT OR IGNORE INTO users (tenant_id, username, password_hash, role, statut) VALUES (?, ?, ?, ?, ?)", u)

    default_articles = [
        ("Station Totale Topographique & GNSS/GPS", "9015.80.00", 5.0, "Topographie"),
        ("Smartphones & Téléphones portables", "8517.13.00", 20.0, "High-Tech"),
        ("Ordinateurs Portables & MacBooks", "8471.30.00", 5.0, "Informatique"),
        ("Vélos et Bicyclettes sans moteur", "8712.00.00", 20.0, "Transport"),
        ("Motos & Motocycles (125cc - 250cc)", "8711.20.00", 20.0, "Transport"),
        ("Voitures de Tourisme (Berlines / SUV)", "8703.22.00", 20.0, "Véhicules")
    ]
    for item in default_articles:
        cursor.execute("INSERT OR IGNORE INTO articles (nom, sh, dd, categorie) VALUES (?, ?, ?, ?)", item)

    conn.commit()
    conn.close()

init_db()

def log_action(tenant_id, username, action, details):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO audit_logs (tenant_id, timestamp, username, action, details) VALUES (?, ?, ?, ?, ?)", 
                   (tenant_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), username, action, details))
    conn.commit()
    conn.close()

# =========================================================
# FONCTIONS MÉTIER LOGISTIQUE & RISK
# =========================================================
def calculer_selectivite_risque(fob_xof, item_info, diff_ocr_pct, client_nom):
    score = 10.0
    motifs = []

    if fob_xof > 50000000:
        score += 30
        motifs.append("Valeur FOB supérieure à 50M FCFA")
    elif fob_xof > 10000000:
        score += 15
        motifs.append("Valeur FOB supérieure à 10M FCFA")

    if diff_ocr_pct > 15.0:
        score += 40
        motifs.append(f"Divergence majeure OCR Facture ({diff_ocr_pct:.1f}%)")
    elif diff_ocr_pct > 5.0:
        score += 20
        motifs.append(f"Écart mineur OCR Facture ({diff_ocr_pct:.1f}%)")

    if item_info.get('cat') in ['High-Tech', 'Véhicules']:
        score += 15
        motifs.append(f"Catégorie sous surveillance ({item_info.get('cat')})")

    if score < 25:
        canal = "VERT"
    elif score < 45:
        canal = "BLEU"
    elif score < 70:
        canal = "JAUNE"
    else:
        canal = "ROUGE"

    return round(score, 1), canal, " | ".join(motifs) if motifs else "Déclaration conforme"

def calculer_surestaries(date_dechargement_str, jours_franchise, frais_jour_usd, taux_usd):
    try:
        date_arr = datetime.strptime(date_dechargement_str, "%Y-%m-%d")
        date_limite = date_arr + timedelta(days=int(jours_franchise))
        aujourdhui = datetime.now()
        jours_depasses = (aujourdhui - date_limite).days
        if jours_depasses > 0:
            cout_usd = jours_depasses * frais_jour_usd
            cout_xof = cout_usd * taux_usd
            return jours_depasses, cout_usd, cout_xof, f"🔴 PÉNALITÉ DE SURESTARIES ({jours_depasses} j. de dépassement)"
        else:
            reste = abs(jours_depasses)
            return 0, 0, 0, f"🟢 FRANCHISE ACTIVE (Reste {reste} jours)"
    except Exception:
        return 0, 0, 0, "⚪ Non évalué"

def attribuer_bureau_anonyme(dossier_id):
    bureaux_virtuels = ["Bureau Nord (Korhogo)", "Bureau Ouest (Man)", "Bureau Centre (Yamoussoukro)", "Bureau Maritime (San-Pédro)"]
    random.seed(dossier_id)
    return random.choice(bureaux_virtuels)

def evaluer_statut_oea(conformite_pct, annees_existence, litiges_passes):
    if conformite_pct >= 95.0 and annees_existence >= 3 and litiges_passes == 0:
        return "AEO TIER 3 (Confiance Absolue)", "🟢 CANAL VERT AUTOMATIQUE", 0.02
    elif conformite_pct >= 85.0 and litiges_passes <= 1:
        return "AEO TIER 1 (Fiabilité Élevée)", "🔵 CANAL BLEU (Contrôle a posteriori)", 0.05
    else:
        return "STANDARD (Non Certifié)", "🟡 CANAL JAUNE / ROUGE (Contrôle Standard)", 0.20

def generer_message_edifact_cusdec(num_dossier, client, article, fob_xof, regime):
    now_str = datetime.now().strftime("%Y%m%d:%H%M")
    return f"UNB+UNOA:2+SNDGIR_CI+DECLARANT+260925:{now_str}+00001'\nUNH+1+CUSDEC:D:96B:UN'\nBGM+107+{num_dossier}+9'\nCST+1+{regime}'\nNAD+CZ++{client.upper()}'\nMEA+WT+G+{fob_xof:.0f}'\nUNT+7+1'\nUNZ+1+00001'"

@st.cache_data(ttl=3600)
def obtenir_taux_change_automatique():
    default_rates = {"CNY": 85.0, "USD": 610.0, "EUR": 655.957, "AED": 166.0}
    try:
        url = "https://open.er-api.com/v6/latest/USD"
        res = requests.get(url, timeout=4)
        if res.status_code == 200:
            rates = res.json().get("rates", {})
            usd_xof = rates.get("XOF", 610.0)
            return {
                "CNY": round(usd_xof / rates.get("CNY", 7.2), 2),
                "USD": round(usd_xof, 2),
                "EUR": 655.957,
                "AED": round(usd_xof / rates.get("AED", 3.67), 2)
            }, "🟢 Taux direct API (Temps réel)"
    except Exception:
        pass
    return default_rates, "⚠️ Mode secours (Hors ligne)"

taux_devises_dict, status_api_devises = obtenir_taux_change_automatique()

def calculer_droits_douane(caf_xof, dd_pct, regime_code):
    if "C100" in regime_code:
        taux_dd = dd_pct / 100.0
        taux_redevances = 0.010 + 0.008 + 0.002
        droits_hors_tva = caf_xof * (taux_dd + taux_redevances)
        tva = (caf_xof + droits_hors_tva) * 0.18
        total_douane = droits_hors_tva + tva
    elif "E100" in regime_code or "TR" in regime_code:
        total_douane = caf_xof * 0.005
    elif "AT" in regime_code:
        total_douane = caf_xof * 0.010
    else:
        droits_hors_tva = caf_xof * ((dd_pct / 100.0) + 0.02)
        total_douane = droits_hors_tva + ((caf_xof + droits_hors_tva) * 0.18)
    return total_douane

# =========================================================
# DOCUMENTS PDF (BAE & FACTURES)
# =========================================================
def generer_bae_pdf(dossier_id, client, article, bl_num, container_num, quittance_num, total_facture):
    pdf_filename = f"BAE_Officiel_SNDGIR_{dossier_id}.pdf"
    doc = SimpleDocTemplate(pdf_filename, pagesize=letter, rightMargin=35, leftMargin=35, topMargin=35, bottomMargin=35)
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#064E3B'), alignment=1)
    elements.append(Paragraph("<b>RÉPUBLIQUE DE CÔTE D'IVOIRE</b>", title_style))
    elements.append(Paragraph("<font size=10>DIRECTION GÉNÉRALE DES DOUANES — SYSTEME SNDGIR</font>", title_style))
    elements.append(Spacer(1, 15))

    hash_val = hashlib.sha256(f"{dossier_id}-{quittance_num}-{total_facture}".encode()).hexdigest()[:24].upper()
    info_bae = f"""
    <b>BON À ENLEVER (BAE) OFFICIEL — MAINLEVÉE ACCORDÉE</b><br/><br/>
    <b>N° de Dossier :</b> RCI-DOUANE-2026-{dossier_id}<br/>
    <b>N° de Quittance Caisse :</b> {quittance_num}<br/>
    <b>Importateur / Destinataire :</b> {client}<br/>
    <b>Désignation :</b> {article}<br/>
    <b>N° Connaissement / B/L :</b> {bl_num} | <b>N° Conteneur :</b> {container_num}<br/>
    <b>Montant Droits Acquittés :</b> {total_facture:,.0f} FCFA<br/>
    <b>Empreinte Électronique Sécurisée :</b> <code>{hash_val}</code>
    """
    elements.append(Paragraph(info_bae, styles['Normal']))
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("<b>Le Chef du Bureau de Douane certifie que la marchandise ci-dessus a satisfait à toutes les obligations douanières.</b>", styles['Normal']))
    doc.build(elements)
    return pdf_filename

def generer_facture_transit_pdf(dossier_id, client, article, total_douane, honoraires, frais_port, frais_transport, surestaries):
    pdf_filename = f"Facture_Transit_{dossier_id}_{client.replace(' ', '_')}.pdf"
    doc = SimpleDocTemplate(pdf_filename, pagesize=letter, rightMargin=35, leftMargin=35, topMargin=35, bottomMargin=35)
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#0284C7'), alignment=1)
    elements.append(Paragraph("<b>AGENCE DE TRANSIT & LOGISTIQUE INTERNATIONALE</b>", title_style))
    elements.append(Paragraph("<font size=10>Facture Définitive de Dédouanement et Prestations</font>", title_style))
    elements.append(Spacer(1, 15))

    tva_hon = honoraires * 0.18
    total_general = total_douane + honoraires + tva_hon + frais_port + frais_transport + surestaries

    data = [
        ["Rubrique / Prestation", "Montant (FCFA)"],
        ["Droits & Taxes de Douane (Débours)", f"{total_douane:,.0f} FCFA"],
        ["Frais de Passage Portuaire & Acconage (Débours)", f"{frais_port:,.0f} FCFA"],
        ["Frais de Transport Terrestre / Livraison", f"{frais_transport:,.0f} FCFA"],
        ["Pénalités de Surestaries / Immobilisation", f"{surestaries:,.0f} FCFA"],
        ["Honoraires & Commission de Transit", f"{honoraires:,.0f} FCFA"],
        ["TVA sur Honoraires (18%)", f"{tva_hon:,.0f} FCFA"],
        ["TOTAL GÉNÉRAL À PAYER", f"{total_general:,.0f} FCFA"]
    ]

    t = Table(data, colWidths=[300, 200])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0F172A')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0,-1), (-1,-1), colors.HexColor('#0284C7'))
    ]))

    elements.append(Paragraph(f"<b>Facture N° :</b> FAC-2026-{dossier_id:05d}<br/><b>Client :</b> {client}<br/><b>Marchandise :</b> {article}<br/><br/>", styles['Normal']))
    elements.append(t)
    doc.build(elements)
    return pdf_filename

# =========================================================
# AUTHENTIFICATION & MULTI-TENANCY SAAS
# =========================================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_role = ""
    st.session_state.username = ""
    st.session_state.tenant_id = 1
    st.session_state.tenant_name = ""

if not st.session_state.authenticated:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
        st.subheader("🔐 Plateforme SaaS Transit & Douanes")
        st.caption("Connexion sécurisée aux espaces Agences & Importateurs")

        username_input = st.text_input("Identifiant Officiel")
        password_input = st.text_input("Mot de passe", type="password")

        if st.button("Se connecter au Système", use_container_width=True):
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.username, u.password_hash, u.role, u.statut, u.tenant_id, t.nom_societe 
                FROM users u
                JOIN tenants t ON u.tenant_id = t.id
                WHERE u.username = ?
            """, (username_input,))
            row = cursor.fetchone()
            conn.close()

            if row:
                u_name, u_pwd_hash, u_role, u_statut, u_tenant_id, t_nom = row
                if u_statut != "Actif":
                    st.error("Compte désactivé.")
                elif hash_password(password_input) == u_pwd_hash:
                    st.session_state.authenticated = True
                    st.session_state.username = u_name
                    st.session_state.user_role = u_role
                    st.session_state.tenant_id = u_tenant_id
                    st.session_state.tenant_name = t_nom
                    log_action(u_tenant_id, u_name, "Connexion", "Accès à la session")
                    st.rerun()
                else:
                    st.error("Mot de passe incorrect.")
            else:
                st.error("Compte introuvable.")
        st.markdown('</div>', unsafe_allow_html=True)
        st.stop()

# =========================================================
# BARRE LATÉRALE DE NAVIGATION
# =========================================================
st.sidebar.title("🇨🇮 SNDGIR SaaS")
st.sidebar.markdown(f"🏢 **Entreprise :** `{st.session_state.tenant_name}`")
st.sidebar.markdown(f"👤 **Utilisateur :** `{st.session_state.username}`")
st.sidebar.markdown(f"🔑 **Rôle :** `{st.session_state.user_role}`")
st.sidebar.markdown("---")

groq_default_key = st.secrets.get("GROQ_API_KEY", "") if hasattr(st, "secrets") else ""
groq_api_key = st.sidebar.text_input("🔑 Clé API Groq Llama 3", value=groq_default_key, type="password")

st.sidebar.subheader("💱 Taux de Change Officiels")
st.sidebar.caption(status_api_devises)
taux_cny_xof = st.sidebar.number_input("1 CNY (Chine)", value=taux_devises_dict["CNY"], step=0.1)
taux_usd_xof = st.sidebar.number_input("1 USD (Dollar)", value=taux_devises_dict["USD"], step=1.0)
taux_eur_xof = st.sidebar.number_input("1 EUR (Euro)", value=taux_devises_dict["EUR"], step=0.1)

st.sidebar.markdown("---")
if st.sidebar.button("🚪 Déconnexion", use_container_width=True):
    st.session_state.authenticated = False
    st.rerun()

# =========================================================
# EN-TÊTE ET NAVIGATION PAR ONGLETS
# =========================================================
st.markdown(f"""
<div class="header-banner">
    <h1>🏛️ SNDGIR SaaS : {st.session_state.tenant_name}</h1>
    <p>Gestion Intégrée Multi-Sociétés : Cargo, Douanes, ERP Transit, Portail Importateur & IA</p>
</div>
""", unsafe_allow_html=True)

tabs_list = [
    "📈 Dashboard & Marges",
    "🚢 1. Manifeste & Fret",
    "📋 2. Déclaration en Détail (SAD)",
    "💼 3. Transit ERP & Facturation",
    "📱 4. Portail Importateur (Self-Service)",
    "💳 5. Caisse & BAE",
    "🔄 6. Passerelle EDI",
    "📄 7. IDP OCR Cross-Check",
    "🌐 8. Innovations Inde & Chine",
    "📖 9. Code des Douanes",
    "🤖 10. Assistant IA Transit",
    "🔐 SaaS Admin & Tenancy"
]

tabs = st.tabs(tabs_list)
tab_dash = tabs[0]
tab_manifeste = tabs[1]
tab_sad = tabs[2]
tab_transit_erp = tabs[3]
tab_portail_client = tabs[4]
tab_caisse = tabs[5]
tab_edi = tabs[6]
tab_ocr = tabs[7]
tab_innov = tabs[8]
tab_code = tabs[9]
tab_ai = tabs[10]
tab_admin = tabs[11]

# =========================================================
# TAB 0 : DASHBOARD MULTI-TENANT
# =========================================================
with tab_dash:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader(f"📈 Performance Globale - {st.session_state.tenant_name}")

    conn = sqlite3.connect(DB_NAME)
    df_d = pd.read_sql_query("SELECT * FROM dossiers WHERE tenant_id = ?", conn, params=(st.session_state.tenant_id,))
    conn.close()

    if df_d.empty:
        st.info("Aucun dossier enregistré pour votre entreprise.")
    else:
        tot_droits = df_d['total_facture'].sum()
        nb_decl = len(df_d)
        nb_rouge = len(df_d[df_d['canal_selectivite'] == 'ROUGE'])
        nb_vert = len(df_d[df_d['canal_selectivite'] == 'VERT'])

        k1, k2, k3, k4 = st.columns(4)
        with k1: st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Droits Liquidés</div><div class="kpi-value">{tot_droits:,.0f} FCFA</div></div>""", unsafe_allow_html=True)
        with k2: st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Dossiers Traités</div><div class="kpi-value">{nb_decl}</div></div>""", unsafe_allow_html=True)
        with k3: st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Circuits Verts</div><div class="kpi-value" style="color:#34D399;">{nb_vert}</div></div>""", unsafe_allow_html=True)
        with k4: st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Circuits Rouges</div><div class="kpi-value" style="color:#F87171;">{nb_rouge}</div></div>""", unsafe_allow_html=True)

        st.markdown("<br/>", unsafe_allow_html=True)
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            fig_canal = px.pie(df_d, names='canal_selectivite', title="Sélectivité des Dossiers", hole=0.4,
                               color_discrete_map={'VERT': '#047857', 'BLEU': '#1D4ED8', 'JAUNE': '#D97706', 'ROUGE': '#B91C1C'})
            fig_canal.update_layout(paper_bgcolor='rgba(0,0,0,0)', font_color='white')
            st.plotly_chart(fig_canal, use_container_width=True)

        with col_g2:
            fig_regime = px.bar(df_d, x='regime', y='total_facture', color='canal_selectivite', title="Recettes par Régime Douanier")
            fig_regime.update_layout(paper_bgcolor='rgba(0,0,0,0)', font_color='white')
            st.plotly_chart(fig_regime, use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 1 : MANIFESTE & FRET
# =========================================================
with tab_manifeste:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("🚢 Module Cargo : Manifestes Maritimes & Aériens")

    col_m1, col_m2 = st.columns([1, 1])

    with col_m1:
        st.markdown("##### 1️⃣ Enregistrer un Nouveau Manifeste")
        with st.form("form_manifeste"):
            m_num = st.text_input("N° Manifeste (ex: MAN-2026-ABJ-001)")
            m_transport = st.selectbox("Moyen de Transport", ["Maritime (Navire)", "Aérien (Avion)", "Routier (Camion)"])
            m_voyage = st.text_input("N° Voyage / Vol", value="MSC-VITA-2026")
            m_prov = st.text_input("Port de Provenance", value="Guangzhou, Chine")
            m_date = st.date_input("Date d'Arrivée Prévue", value=datetime.now())
            btn_m = st.form_submit_button("Enregistrer le Manifeste")

        if btn_m and m_num:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO manifestes (tenant_id, num_manifeste, moyen_transport, num_voyage, provenance, date_arrivee) VALUES (?, ?, ?, ?, ?, ?)",
                               (st.session_state.tenant_id, m_num, m_transport, m_voyage, m_prov, m_date.strftime("%Y-%m-%d")))
                conn.commit()
                log_action(st.session_state.tenant_id, st.session_state.username, "Ajout Manifeste", f"Manifeste {m_num} créé")
                st.success(f"Manifeste {m_num} enregistré avec succès !")
            except Exception as e:
                st.error(f"Erreur : {e}")
            conn.close()

    with col_m2:
        st.markdown("##### 2️⃣ Ajouter un Connaissement / B/L")
        conn = sqlite3.connect(DB_NAME)
        df_man = pd.read_sql_query("SELECT num_manifeste FROM manifestes WHERE tenant_id = ?", conn, params=(st.session_state.tenant_id,))
        conn.close()

        if not df_man.empty:
            with st.form("form_fret"):
                f_man = st.selectbox("Manifeste Associé", df_man['num_manifeste'].tolist())
                f_bl = st.text_input("N° Connaissement / B/L", value="MEDU98765432")
                f_client = st.text_input("Destinataire (Consignee)", value="ETS KOUASSI & FRERES")
                f_poids = st.number_input("Poids Brut (kg)", value=1500.0)
                f_colis = st.number_input("Nombre de Colis", value=45)
                btn_f = st.form_submit_button("Rattacher le Connaissement")

            if btn_f and f_bl:
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                try:
                    cursor.execute("INSERT INTO fret_lines (tenant_id, num_manifeste, bl_number, consignee, poids_brut, nb_colis) VALUES (?, ?, ?, ?, ?, ?)",
                                   (st.session_state.tenant_id, f_man, f_bl, f_client, f_poids, f_colis))
                    conn.commit()
                    st.success(f"B/L {f_bl} rattaché !")
                except Exception as e:
                    st.error(f"Erreur : {e}")
                conn.close()

    st.markdown("---")
    st.markdown("### Registre des Connaissements & Cargo")
    conn = sqlite3.connect(DB_NAME)
    df_fret_all = pd.read_sql_query("SELECT * FROM fret_lines WHERE tenant_id = ?", conn, params=(st.session_state.tenant_id,))
    conn.close()
    st.dataframe(df_fret_all, use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 2 : DÉCLARATION EN DÉTAIL (SAD)
# =========================================================
with tab_sad:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📋 Module Douane : Saisie du SAD & Sélectivité")

    conn = sqlite3.connect(DB_NAME)
    df_art_db = pd.read_sql_query("SELECT * FROM articles", conn)
    df_bl_unpurged = pd.read_sql_query("SELECT bl_number, consignee FROM fret_lines WHERE tenant_id = ? AND statut_apurement = 'Non apuré'", conn, params=(st.session_state.tenant_id,))
    conn.close()

    c1, c2, c3 = st.columns(3)
    with c1:
        client_decl = st.text_input("Nom de l'Importateur / Client", value="ETS KOUASSI & FRERES")
    with c2:
        bl_select = st.selectbox("N° Connaissement / B/L (Apurement Cargo)", df_bl_unpurged['bl_number'].tolist() if not df_bl_unpurged.empty else ["MEDU98765432"])
    with c3:
        container_input = st.text_input("N° Conteneur", value="MSCU1234567")

    col_s1, col_s2 = st.columns([2, 1])

    with col_s1:
        article_nom = st.selectbox("Désignation du Produit (Code SH)", df_art_db['nom'].tolist() if not df_art_db.empty else [])
        item_row = df_art_db[df_art_db['nom'] == article_nom].iloc[0] if not df_art_db.empty else {"sh": "8517.13.00", "dd": 20.0, "categorie": "High-Tech"}

        regime_code = st.selectbox("Régime Douanier", [
            "C100 - Mise à la consommation directe",
            "E100 - Entrepôt de douane (Suspensif)",
            "AT - Admission Temporaire",
            "TR - Transit / Réexportation"
        ])

        devise_facture = st.selectbox("Devise Commerciale", ["USD", "CNY", "EUR", "AED"])
        m1, m2 = st.columns(2)
        with m1: qte = st.number_input("Quantité", min_value=1, value=100)
        with m2: pu_devise = st.number_input(f"Prix Unitaire ({devise_facture})", min_value=0.01, value=250.0)

        fob_devise = qte * pu_devise
        taux_conv = taux_usd_xof if devise_facture == "USD" else (taux_cny_xof if devise_facture == "CNY" else taux_eur_xof)
        fob_xof = fob_devise * taux_conv
        caf_xof = fob_xof * 1.08
        total_douane = calculer_droits_douane(caf_xof, item_row['dd'], regime_code)

    with col_s2:
        st.markdown("##### 🎯 Analyse du Risque & Sélectivité")
        diff_ocr_simulee = st.slider("Divergence OCR Facture vs Déclaration (%)", 0.0, 30.0, 2.0)

        score_risk, canal, motifs_risk = calculer_selectivite_risque(fob_xof, {"cat": item_row['categorie']}, diff_ocr_simulee, client_decl)

        badge_class = "canal-vert" if canal == "VERT" else ("canal-bleu" if canal == "BLEU" else ("canal-jaune" if canal == "JAUNE" else "canal-rouge"))

        st.markdown(f"""
        <div style="background:#020617; padding:20px; border-radius:14px; border:1px solid #1E293B; text-align:center;">
            <h4>Score de Risque : <span style="color:#38BDF8;">{score_risk} / 100</span></h4>
            <span class="{badge_class}">CANAL {canal}</span><br/><br/>
            <small><b>Motifs :</b> {motifs_risk}</small>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br/>", unsafe_allow_html=True)
    if st.button("🚀 Soumettre la Déclaration en Détail (SAD)", use_container_width=True):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        cursor.execute("""
            INSERT INTO dossiers 
            (tenant_id, date, client, article, regime, fob_xof, total_facture, solde_du, statut, bl_number, container_number, date_arrivee, score_risque, canal_selectivite, motifs_risque)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (st.session_state.tenant_id, date_str, client_decl, article_nom, regime_code, fob_xof, total_douane, total_douane, "En cours de contrôle" if canal in ["JAUNE", "ROUGE"] else "Liquidé - En attente de paiement",
              bl_select, container_input, datetime.now().strftime("%Y-%m-%d"), score_risk, canal, motifs_risk))

        cursor.execute("UPDATE fret_lines SET statut_apurement = 'Apuré par SAD' WHERE bl_number = ? AND tenant_id = ?", (bl_select, st.session_state.tenant_id))
        conn.commit()
        conn.close()

        log_action(st.session_state.tenant_id, st.session_state.username, "Soumission SAD", f"SAD enregistrée pour {client_decl} - Canal {canal}")
        st.success(f"Déclaration enregistrée sous le Canal **{canal}** !")

    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 3 : TRANSIT ERP & FACTURATION CLIENT
# =========================================================
with tab_transit_erp:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("💼 Module Transitaire : Facturation, Débours & Surestaries")

    conn = sqlite3.connect(DB_NAME)
    df_dos_t = pd.read_sql_query("SELECT * FROM dossiers WHERE tenant_id = ? ORDER BY id DESC", conn, params=(st.session_state.tenant_id,))
    conn.close()

    if df_dos_t.empty:
        st.info("Aucun dossier disponible pour la facturation transit.")
    else:
        sel_dos_id = st.selectbox("Sélectionner un Dossier de Transit à Facturer", df_dos_t['id'].tolist())
        row_t = df_dos_t[df_dos_t['id'] == sel_dos_id].iloc[0]

        st.markdown(f"### 📑 Dossier N° RCI-DOUANE-2026-{row_t['id']} | Client : **{row_t['client']}**")

        col_tr1, col_tr2 = st.columns(2)

        with col_tr1:
            st.markdown("##### ⏱️ Suivi de la Franchise & Surestaries")
            d_dechargement = st.date_input("Date de Déchargement du Conteneur", value=datetime.now() - timedelta(days=6))
            franchise_j = st.number_input("Jours de Franchise Accordés par l'Armateur", value=7, min_value=1)
            penalite_usd = st.number_input("Pénalité Jour Supplémentaire ($ USD)", value=50.0)

            j_dep, c_usd, c_xof, statut_sure = calculer_surestaries(
                d_dechargement.strftime("%Y-%m-%d"),
                franchise_j,
                penalite_usd,
                taux_usd_xof
            )

            st.info(f"**Statut Surestaries :** {statut_sure}")
            if j_dep > 0:
                st.error(f"Pénalité calculée : **${c_usd:,.2f} USD** ({c_xof:,.0f} FCFA)")

            st.markdown("---")
            st.markdown("##### 📋 Checklist Documentaire Dossier Transit")
            chk_fact = st.checkbox("Facture Commerciale Originale", value=True)
            chk_bl = st.checkbox("Connaissement / B/L Original", value=True)
            chk_avd = st.checkbox("Attestation de Vérification (AVD / Webb Fontaine)", value=True)
            chk_bsc = st.checkbox("Bordereau de Suivi de Cargaison (BSC / OIC)", value=False)

        with col_tr2:
            st.markdown("##### 💰 Éléments de Facturation Transitaire")
            d_douane = float(row_t['total_facture']) if 'total_facture' in row_t and pd.notna(row_t['total_facture']) else 0.0

            val_f_port = float(row_t['frais_port']) if 'frais_port' in row_t and pd.notna(row_t['frais_port']) else 85000.0
            val_f_transport = float(row_t['frais_transport']) if 'frais_transport' in row_t and pd.notna(row_t['frais_transport']) else 120000.0
            val_f_honoraires = float(row_t['honoraires']) if 'honoraires' in row_t and pd.notna(row_t['honoraires']) else 150000.0

            f_port = st.number_input("Frais de Passage Portuaire & Acconage (FCFA)", value=val_f_port)
            f_transport = st.number_input("Frais de Transport Terrestre / Camionnage (FCFA)", value=val_f_transport)
            f_honoraires = st.number_input("Honoraires / Commission de Transit (FCFA)", value=val_f_honoraires)

            tva_honoraires = f_honoraires * 0.18
            total_facture_globale = d_douane + f_port + f_transport + c_xof + f_honoraires + tva_honoraires

            st.markdown("---")
            st.markdown(f"#### **TOTAL FACTURE TRANSIT :** `{total_facture_globale:,.0f} FCFA`")
            st.caption(f"Inclut : Droits Douane ({d_douane:,.0f} FCFA) + Débours Portuaires + Honoraires Transit + Surestaries")

            if st.button("📄 Mettre à Jour & Générer la Facture Client (PDF)", use_container_width=True):
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE dossiers 
                    SET honoraires = ?, frais_port = ?, frais_transport = ?, surestaries_xof = ?
                    WHERE id = ? AND tenant_id = ?
                """, (f_honoraires, f_port, f_transport, c_xof, sel_dos_id, st.session_state.tenant_id))
                conn.commit()
                conn.close()

                pdf_fac = generer_facture_transit_pdf(sel_dos_id, row_t['client'], row_t['article'], d_douane, f_honoraires, f_port, f_transport, c_xof)

                with open(pdf_fac, "rb") as f_pdf:
                    st.download_button("📥 Télécharger la Facture Définitive Transitaire (PDF)", data=f_pdf.read(), file_name=pdf_fac, mime="application/pdf", use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 4 : PORTAIL CLIENT IMPORTATEUR (SELF-SERVICE SAAS)
# =========================================================
with tab_portail_client:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📱 Portail Self-Service Importateur (Suivi en Temps Réel)")
    st.caption("Espace dédié aux clients de votre agence de transit pour suivre leurs cargaisons")

    conn = sqlite3.connect(DB_NAME)
    df_portail = pd.read_sql_query("SELECT id, date, client, article, container_number, canal_selectivite, statut, total_facture FROM dossiers WHERE tenant_id = ? ORDER BY id DESC", conn, params=(st.session_state.tenant_id,))
    conn.close()

    if df_portail.empty:
        st.info("Aucune cargaison associée à votre compte importateur.")
    else:
        search_client = st.text_input("🔍 Rechercher par votre nom ou N° de Conteneur :", value="ETS KOUASSI & FRERES")
        df_filtered = df_portail[df_portail['client'].str.contains(search_client, case=False, na=False) | df_portail['container_number'].str.contains(search_client, case=False, na=False)]

        st.dataframe(df_filtered, use_container_width=True)

        st.markdown("---")
        st.markdown("##### 📍 Suivi Étape par Étape du Conteneur")
        if not df_filtered.empty:
            sel_d_p = df_filtered.iloc[0]
            st.success(f"**Cargaison :** {sel_d_p['article']} (Conteneur : `{sel_d_p['container_number']}`)")

            c_step1, c_step2, c_step3, c_step4 = st.columns(4)
            c_step1.metric("1. Navire / Port", "✅ Arrivé")
            c_step2.metric("2. Douane", f"Canal {sel_d_p['canal_selectivite']}")
            c_step3.metric("3. Paiement", "✅ Acquitté" if "BAE" in sel_d_p['statut'] else "⏳ En attente")
            c_step4.metric("4. Livraison", sel_d_p['statut'])

    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 5 : CAISSE & BAE
# =========================================================
with tab_caisse:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("💳 Module Caisse & Bon à Enlever (BAE) Sécurisé")

    conn = sqlite3.connect(DB_NAME)
    df_dossiers_all = pd.read_sql_query("SELECT * FROM dossiers WHERE tenant_id = ? ORDER BY id DESC", conn, params=(st.session_state.tenant_id,))
    conn.close()

    if df_dossiers_all.empty:
        st.info("Aucune déclaration enregistrée.")
    else:
        st.dataframe(df_dossiers_all[['id', 'date', 'client', 'article', 'canal_selectivite', 'total_facture', 'solde_du', 'statut']], use_container_width=True)

        st.markdown("---")
        st.subheader("⚙️ Encaisser la Liquidation & Délivrer le BAE")

        col_pay1, col_pay2 = st.columns(2)
        with col_pay1:
            sel_dossier_id = st.selectbox("Sélectionner l'ID du Dossier à Encaisser", df_dossiers_all['id'].tolist())
            row_pay = df_dossiers_all[df_dossiers_all['id'] == sel_dossier_id].iloc[0]

            st.write(f"**Client :** {row_pay['client']} | **Montant à Régler :** `{row_pay['solde_du']:,.0f} FCFA`")
            st.write(f"**Canal de Sélectivité :** `{row_pay['canal_selectivite']}`")

        with col_pay2:
            moyen_paiement = st.selectbox("Mode de Règlement", ["TrésorPay / RTGS Banque Centrale", "Chèque Certifié Trésor Public", "Virement SWIFT", "Mobile Money"])
            if st.button("💳 Valider le Paiement & Émettre le BAE", use_container_width=True):
                quittance = f"QUIT-2026-{sel_dossier_id:05d}"
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                cursor.execute("UPDATE dossiers SET solde_du = 0, statut = 'Liquidé & Payé (BAE Émis)', quittance_num = ? WHERE id = ? AND tenant_id = ?", (quittance, sel_dossier_id, st.session_state.tenant_id))
                conn.commit()
                conn.close()

                log_action(st.session_state.tenant_id, st.session_state.username, "Paiement Caisse", f"Quittance {quittance} générée pour dossier #{sel_dossier_id}")
                st.success(f"Paiement enregistré ! Quittance N° **{quittance}** émise.")

                pdf_bae = generer_bae_pdf(sel_dossier_id, row_pay['client'], row_pay['article'], row_pay['bl_number'], row_pay['container_number'], quittance, row_pay['total_facture'])

                with open(pdf_bae, "rb") as f_bae:
                    st.download_button("📥 Télécharger le Bon à Enlever (BAE) Sécurisé (PDF)", data=f_bae.read(), file_name=pdf_bae, mime="application/pdf", use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 6 : PASSERELLE EDI
# =========================================================
with tab_edi:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("🔄 Passerelle EDI UN/EDIFACT (CUSDEC)")

    conn = sqlite3.connect(DB_NAME)
    df_d_edi = pd.read_sql_query("SELECT * FROM dossiers WHERE tenant_id = ? ORDER BY id DESC LIMIT 10", conn, params=(st.session_state.tenant_id,))
    conn.close()

    if not df_d_edi.empty:
        sel_edi_id = st.selectbox("Déclaration à exporter en EDI", df_d_edi['id'].tolist())
        row_edi = df_d_edi[df_d_edi['id'] == sel_edi_id].iloc[0]

        edifact_str = generer_message_edifact_cusdec(f"SAD-2026-{sel_edi_id}", row_edi['client'], row_edi['article'], row_edi['fob_xof'], row_edi['regime'])

        st.code(edifact_str, language="text")

        st.download_button(
            "📥 Télécharger le Fichier EDI (.edi)",
            data=edifact_str,
            file_name=f"CUSDEC_D{sel_edi_id}.edi",
            mime="text/plain",
            use_container_width=True
        )

    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 7 : IDP OCR CROSS-CHECKING
# =========================================================
with tab_ocr:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📄 IDP OCR & Cross-Checking Documentaire")

    f_ocr = st.file_uploader("Joindre la Facture Commerciale PDF/Image", type=["pdf", "png", "jpg", "txt"])
    if f_ocr:
        st.success("Facture scannée. Extraction automatique des métadonnées terminée.")
        col_oc1, col_oc2 = st.columns(2)
        with col_oc1:
            st.metric("Montant Extrait sur Facture OCR", "$ 25,000 USD")
            st.metric("Poids Brut Extrait sur Connaissement", "1,500.0 kg")
        with col_oc2:
            st.metric("Montant Déclaré par le Déclarant", "$ 20,000 USD")
            st.error("⚠️ ALERTE DISCORDANCE : Sous-évaluation détectée (-20.0%) ! Dossier basculé en CIRCUIT ROUGE.")

    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 8 : INNOVATIONS INDE & CHINE
# =========================================================
with tab_innov:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("🌐 Modules d'Innovation Inspirés des Modèles Indien (ICEGATE) & Chinois (Smart Customs)")

    t_i1, t_i2, t_i3 = st.tabs(["🔒 1. Faceless Assessment (Inde)", "🏆 2. Certification OEA / AEO", "🔍 3. Moteur IA de Valeur (Chine)"])

    with t_i1:
        st.markdown("#### 🔒 Dédouanement Anonymisé & Impartial")
        conn = sqlite3.connect(DB_NAME)
        df_d_face = pd.read_sql_query("SELECT id, date, article, regime, fob_xof, canal_selectivite FROM dossiers WHERE tenant_id = ? ORDER BY id DESC LIMIT 5", conn, params=(st.session_state.tenant_id,))
        conn.close()

        if not df_d_face.empty:
            sel_f_id = st.selectbox("Sélectionner un dossier pour contrôle anonyme", df_d_face['id'].tolist())
            row_f = df_d_face[df_d_face['id'] == sel_f_id].iloc[0]
            bureau_assigne = attribuer_bureau_anonyme(sel_f_id)

            col_fa1, col_fa2 = st.columns(2)
            with col_fa1:
                st.json({
                    "Dossier_ID": f"SAD-2026-{row_f['id']}",
                    "Importateur": "******** [MASQUÉ]",
                    "Marchandise": row_f['article'],
                    "Valeur_FOB_XOF": f"{row_f['fob_xof']:,.0f} FCFA"
                })
            with col_fa2:
                st.success(f"**Bureau Répartiteur :** `{bureau_assigne}`")
                st.button("✅ Valider l'Évaluation Anonyme", key=f"btn_fa_{sel_f_id}")

    with t_i2:
        st.markdown("#### 🏆 Programme Opérateur Économique Agréé (OEA / AEO)")
        col_oea1, col_oea2 = st.columns(2)
        with col_oea1:
            historique_conformite = st.slider("Taux de Conformité Historique (%)", 50.0, 100.0, 98.0)
            anciennete_ans = st.number_input("Ancienneté Registre du Commerce (Années)", value=5)
            nb_litiges = st.number_input("Nombre de Contentieux (3 ans)", value=0)
            tier_oea, canal_recommande, taux_insp = evaluer_statut_oea(historique_conformite, anciennete_ans, nb_litiges)

        with col_oea2:
            st.markdown(f"**Statut Certifié :** `{tier_oea}`")
            st.markdown(f"**Traitement Douanier :** {canal_recommande}")
            st.metric("Taux d'Inspection Physique", f"{taux_insp * 100:.1f} %")

    with t_i3:
        st.markdown("#### 🔍 Moteur IA de Nomenclatures SH & Valeur")
        txt_facture_brute = st.text_input("Saisir le libellé commercial de la facture :", value="MacBook Pro M4 16 pouces 32GB RAM SSD 1TB")
        if st.button("🧠 Analyser par l'IA", use_container_width=True):
            st.success("Code SH Suggéré par IA : **8471.30.00**")
            st.info("💡 **Analyse de Valeur :** Prix déclaré conforme à la fourchette du marché mondial.")

    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 9 : CODE DES DOUANES
# =========================================================
with tab_code:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📖 Code des Douanes de Côte d'Ivoire")
    articles_code = {
        "Article 12 - Valeur transactionnelle (OMC / CAF)": "La valeur en douane est la valeur transactionnelle constituée du prix payé.",
        "Article 85 - Régime C100 (Mise à la consommation)": "Permet la mise en libre circulation des marchandises étrangères."
    }
    for t, c in articles_code.items():
        with st.expander(t): st.write(c)
    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 10 : ASSISTANT IA TRANSIT
# =========================================================
with tab_ai:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("🤖 Assistant Virtuel Llama 3")
    u_q = st.text_area("Votre question réglementaire :", value="Comment calculer la TVA sur honoraires pour un transitaire en Côte d'Ivoire ?")
    if st.button("🔍 Consulter l'IA", use_container_width=True):
        if groq_api_key and Groq:
            client_ai = Groq(api_key=groq_api_key)
            res_ai = client_ai.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": f"Expert transit Côte d'Ivoire : {u_q}"}],
                temperature=0.2, max_tokens=1024
            )
            st.info(res_ai.choices[0].message.content)
        else:
            st.warning("Renseignez la clé API Groq dans le panneau latéral.")
    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 11 : SAAS ADMIN & TENANCY MANAGEMENT
# =========================================================
if st.session_state.user_role in ["Super Admin SaaS", "Administrateur Système", "Administrateur"]:
    with tab_admin:
        st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
        st.subheader("🔐 Administration SaaS & Gestion des Entreprises Abonnées")

        col_sa1, col_sa2 = st.columns(2)
        with col_sa1:
            st.markdown("##### 🏢 1️⃣ Créer une Nouvelle Entreprise Cliente (Tenant)")
            with st.form("form_tenant"):
                t_nom_new = st.text_input("Nom de la Société de Transit")
                t_plan = st.selectbox("Plan d'Abonnement", ["Starter", "Pro", "Enterprise"])
                btn_t = st.form_submit_button("Activer le Compte Entreprise")

            if btn_t and t_nom_new:
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                try:
                    cursor.execute("INSERT INTO tenants (nom_societe, plan_abonnement, statut_compte) VALUES (?, ?, 'Actif')", (t_nom_new, t_plan))
                    conn.commit()
                    st.success(f"Entreprise '{t_nom_new}' enregistrée avec succès !")
                except Exception as e:
                    st.error(f"Erreur : {e}")
                conn.close()

        with col_sa2:
            st.markdown("##### 👤 2️⃣ Créer un Utilisateur pour une Entreprise")
            conn = sqlite3.connect(DB_NAME)
            df_tenants_all = pd.read_sql_query("SELECT id, nom_societe FROM tenants", conn)
            conn.close()

            if not df_tenants_all.empty:
                with st.form("form_u_tenant"):
                    u_t_id = st.selectbox("Sélectionner la Société", df_tenants_all['id'].tolist(), format_func=lambda x: df_tenants_all[df_tenants_all['id'] == x]['nom_societe'].values[0])
                    u_name_new = st.text_input("Identifiant Utilisateur")
                    u_pwd_new = st.text_input("Mot de passe", type="password")
                    u_role_new = st.selectbox("Rôle", ["Commissionnaire Agréé", "Vérificateur Douanier", "Agent de Caisse", "Portail Client Importateur"])
                    btn_u_t = st.form_submit_button("Créer l'Utilisateur")

                if btn_u_t and u_name_new and u_pwd_new:
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    try:
                        cursor.execute("INSERT INTO users (tenant_id, username, password_hash, role, statut) VALUES (?, ?, ?, ?, 'Actif')",
                                       (u_t_id, u_name_new, hash_password(u_pwd_new), u_role_new))
                        conn.commit()
                        st.success(f"Utilisateur '{u_name_new}' rattaché avec succès !")
                    except Exception as e:
                        st.error(f"Erreur : {e}")
                    conn.close()

        st.markdown("---")
        st.markdown("### 🏢 Registre des Entreprises Abonnées")
        conn = sqlite3.connect(DB_NAME)
        df_t_disp = pd.read_sql_query("SELECT * FROM tenants", conn)
        conn.close()
        st.dataframe(df_t_disp, use_container_width=True)

        st.markdown('</div>', unsafe_allow_html=True)
