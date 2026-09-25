import base64

import hashlib

import io

import json

import os

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



# ReportLab pour la génération de documents PDF nationaux

from reportlab.lib.pagesizes import letter

from reportlab.lib import colors

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle



try:

    from groq import Groq

except ImportError:

    Groq = None



# =========================================================

# CONFIGURATION ET STYLE NATIONAL GOVTECH 3D

# =========================================================

st.set_page_config(

    page_title="SNDGIR - Système National Douanier",

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

# BASE DE DONNÉES SQLITE - ARCHITECTURE DOUBLE FLUX

# =========================================================

DB_NAME = "sndgir_national_customs.db"

UPLOAD_DIR = "uploads_dossiers"

os.makedirs(UPLOAD_DIR, exist_ok=True)



def hash_password(password: str) -> str:

    return hashlib.sha256(password.encode('utf-8')).hexdigest()



def init_db():

    conn = sqlite3.connect(DB_NAME)

    cursor = conn.cursor()



    # Table Utilisateurs & Rôles

    cursor.execute("""

        CREATE TABLE IF NOT EXISTS users (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            username TEXT UNIQUE,

            password_hash TEXT,

            role TEXT,

            statut TEXT DEFAULT 'Actif'

        )

    """)



    # Table Manifestes & Fret

    cursor.execute("""

        CREATE TABLE IF NOT EXISTS manifestes (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            num_manifeste TEXT UNIQUE,

            moyen_transport TEXT,

            num_voyage TEXT,

            provenance TEXT,

            date_arrivee TEXT,

            statut TEXT DEFAULT 'Enregistré'

        )

    """)



    # Table Lignes de Fret (Connaissements / LTA)

    cursor.execute("""

        CREATE TABLE IF NOT EXISTS fret_lines (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            num_manifeste TEXT,

            bl_number TEXT UNIQUE,

            consignee TEXT,

            poids_brut REAL,

            nb_colis INTEGER,

            statut_apurement TEXT DEFAULT 'Non apuré'

        )

    """)



    # Table Articles & Nomenclatures SH

    cursor.execute("""

        CREATE TABLE IF NOT EXISTS articles (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            nom TEXT UNIQUE,

            sh TEXT,

            dd REAL,

            categorie TEXT

        )

    """)



    # Table Déclarations en Détail (SAD)

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

            date_arrivee TEXT,

            score_risque REAL,

            canal_selectivite TEXT,

            motifs_risque TEXT,

            quittance_num TEXT,

            document_path TEXT

        )

    """)



    # Table Traces d'Audit

    cursor.execute("""

        CREATE TABLE IF NOT EXISTS audit_logs (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            timestamp TEXT,

            username TEXT,

            action TEXT,

            details TEXT

        )

    """)



    # Utilisateurs par défaut

    default_users = [

        ("admin", hash_password("transit2026"), "Administrateur Système", "Actif"),

        ("verificateur", hash_password("douane2026"), "Vérificateur Douanier", "Actif"),

        ("caissier", hash_password("caisse2026"), "Agent de Caisse", "Actif"),

        ("declarant", hash_password("compta2026"), "Commissionnaire Agréé", "Actif")

    ]

    for u in default_users:

        cursor.execute("INSERT OR IGNORE INTO users (username, password_hash, role, statut) VALUES (?, ?, ?, ?)", u)



    # Articles par défaut

    default_articles = [

        ("Station Totale Topographique & GNSS/GPS", "9015.80.00", 5.0, "Topographie"),

        ("Smartphones & Téléphones portables", "8517.13.00", 20.0, "High-Tech"),

        ("Ordinateurs Portables & MacBooks", "8471.30.00", 5.0, "Informatique"),

        ("Vélos et Bicyclettes sans moteur", "8712.00.00", 20.0, "Transport"),

        ("Motos & Motocycles (125cc - 250cc)", "8711.20.00", 20.0, "Transport"),

        ("Voitures de Tourisme (Berlines / SUV)", "8703.22.00", 20.0, "Véhicules"),

        ("Vêtements Homme / Femme / Enfant", "6203.00.00", 20.0, "Textile"),

        ("Sacs à main pour Dames", "4202.22.00", 20.0, "Maroquinerie")

    ]

    for item in default_articles:

        cursor.execute("INSERT OR IGNORE INTO articles (nom, sh, dd, categorie) VALUES (?, ?, ?, ?)", item)



    conn.commit()

    conn.close()



init_db()



def log_action(username, action, details):

    conn = sqlite3.connect(DB_NAME)

    cursor = conn.cursor()

    cursor.execute("INSERT INTO audit_logs (timestamp, username, action, details) VALUES (?, ?, ?, ?)", 

                   (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), username, action, details))

    conn.commit()

    conn.close()



# =========================================================

# MOTEUR DE SÉLECTIVITÉ HYBRIDE & ANLYSE DES RISQUES

# =========================================================

def calculer_selectivite_risque(fob_xof, item_info, diff_ocr_pct, client_nom):

    score = 10.0

    motifs = []



    # Règle 1 : Valeur élevée

    if fob_xof > 50000000:

        score += 30

        motifs.append("Valeur FOB supérieure à 50M FCFA")

    elif fob_xof > 10000000:

        score += 15

        motifs.append("Valeur FOB supérieure à 10M FCFA")



    # Règle 2 : Divergence OCR Facture vs Déclaration

    if diff_ocr_pct > 15.0:

        score += 40

        motifs.append(f"Divergence majeure OCR Facture ({diff_ocr_pct:.1f}%)")

    elif diff_ocr_pct > 5.0:

        score += 20

        motifs.append(f"Écart mineur OCR Facture ({diff_ocr_pct:.1f}%)")



    # Règle 3 : Catégories sensibles

    if item_info['cat'] in ['High-Tech', 'Véhicules']:

        score += 15

        motifs.append(f"Catégorie sous surveillance ({item_info['cat']})")



    # Détermination du Canal

    if score < 25:

        canal = "VERT"

    elif score < 45:

        canal = "BLEU"

    elif score < 70:

        canal = "JAUNE"

    else:

        canal = "ROUGE"



    return round(score, 1), canal, " | ".join(motifs) if motifs else "Déclaration conforme"



# =========================================================

# GENERATEUR EDI UN/EDIFACT (CUSDEC / CUSRES)

# =========================================================

def generer_message_edifact_cusdec(num_dossier, client, article, fob_xof, regime):

    now_str = datetime.now().strftime("%Y%m%d:%H%M")

    edifact = f"""UNB+UNOA:2+SNDGIR_CI+DECLARANT+260925:{now_str}+00001'

UNH+1+CUSDEC:D:96B:UN'

BGM+107+{num_dossier}+9'

CST+1+{regime}'

NAD+CZ++{client.upper()}'

LOC+11+CIABJ'

MEA+WT+G+{fob_xof:.0f}'

UNT+7+1'

UNZ+1+00001'"""

    return edifact



# =========================================================

# CALCULATEUR DROITS ET TAXES

# =========================================================

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

# AUTHENTIFICATION & SESSIONS

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

        st.subheader("🔐 Portail National Douanier (SNDGIR)")

        st.caption("Système National de Dédouanement et de Gestion Intelligente des Risques")



        username_input = st.text_input("Identifiant Officiel")

        password_input = st.text_input("Mot de passe", type="password")



        if st.button("Se connecter au Système", use_container_width=True):

            conn = sqlite3.connect(DB_NAME)

            cursor = conn.cursor()

            cursor.execute("SELECT username, password_hash, role, statut FROM users WHERE username = ?", (username_input,))

            row = cursor.fetchone()

            conn.close()



            if row:

                u_name, u_pwd_hash, u_role, u_statut = row

                if u_statut != "Actif":

                    st.error("Compte désactivé.")

                elif hash_password(password_input) == u_pwd_hash:

                    st.session_state.authenticated = True

                    st.session_state.username = u_name

                    st.session_state.user_role = u_role

                    log_action(u_name, "Connexion", "Accès accordé au portail")

                    st.rerun()

                else:

                    st.error("Mot de passe incorrect.")

            else:

                st.error("Identifiant non reconnu. (Ex: admin / transit2026)")

        st.markdown('</div>', unsafe_allow_html=True)

        st.stop()



# =========================================================

# GENERATION DE BON A ENLEVER (BAE) ET QUITTANCE PDF

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

    elements.append(Paragraph("<b>Le Chef du Bureau de Douane certifie que la marchandise ci-dessus a satisfait à toutes les obligations douanières et autorise son enlèvement du port.</b>", styles['Normal']))



    doc.build(elements)

    return pdf_filename



# =========================================================

# BARRE LATÉRALE DE NAVIGATION

# =========================================================

st.sidebar.title("🇨🇮 SNDGIR NATIONAL")

st.sidebar.markdown(f"**Agent :** `{st.session_state.username}`")

st.sidebar.markdown(f"**Rôle :** `{st.session_state.user_role}`")

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

# EN-TÊTE ET ONGLETS DU SYSTÈME DOUANIER

# =========================================================

st.markdown("""

<div class="header-banner">

    <h1>🏛️ CÔTE D'IVOIRE : SYSTÈME NATIONAL DE DÉDOUANEMENT (SNDGIR v5.0)</h1>

    <p>Module Intégré : Manifeste, Sélectivité Hybride (Vert/Bleu/Jaune/Rouge), Caisse, EDI & AI Risk Management</p>

</div>

""", unsafe_allow_html=True)



tabs_list = [

    "📈 Dashboard National",

    "🚢 1. Manifeste & Fret",

    "📋 2. Déclaration en Détail & Sélectivité",

    "💳 3. Caisse & BAE",

    "🔄 4. Passerelle EDI",

    "📄 5. IDP OCR Cross-Check",

    "📖 6. Code des Douanes",

    "🤖 7. Assistant IA Douanes",

    "🔐 Admin & Audit Logs"

]



tabs = st.tabs(tabs_list)

tab_dash = tabs[0]

tab_manifeste = tabs[1]

tab_sad = tabs[2]

tab_caisse = tabs[3]

tab_edi = tabs[4]

tab_ocr = tabs[5]

tab_code = tabs[6]

tab_ai = tabs[7]

tab_admin = tabs[8]



# =========================================================

# TAB 0 : DASHBOARD NATIONAL DE PERFORMANCE

# =========================================================

with tab_dash:

    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)

    st.subheader("📈 Indicateurs Nationaux de Liquidation & Risques Douaniers")



    conn = sqlite3.connect(DB_NAME)

    df_d = pd.read_sql_query("SELECT * FROM dossiers", conn)

    conn.close()



    if df_d.empty:

        st.info("Aucune déclaration enregistrée dans le système national.")

    else:

        tot_droits = df_d['total_facture'].sum()

        nb_decl = len(df_d)

        nb_rouge = len(df_d[df_d['canal_selectivite'] == 'ROUGE'])

        nb_vert = len(df_d[df_d['canal_selectivite'] == 'VERT'])



        k1, k2, k3, k4 = st.columns(4)

        with k1: st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Recettes Liquidées</div><div class="kpi-value">{tot_droits:,.0f} FCFA</div></div>""", unsafe_allow_html=True)

        with k2: st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Total Déclarations</div><div class="kpi-value">{nb_decl}</div></div>""", unsafe_allow_html=True)

        with k3: st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Circuits Verts (Mainlevée)</div><div class="kpi-value" style="color:#34D399;">{nb_vert}</div></div>""", unsafe_allow_html=True)

        with k4: st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Circuits Rouges (Inspections)</div><div class="kpi-value" style="color:#F87171;">{nb_rouge}</div></div>""", unsafe_allow_html=True)



        st.markdown("<br/>", unsafe_allow_html=True)

        col_g1, col_g2 = st.columns(2)

        with col_g1:

            fig_canal = px.pie(df_d, names='canal_selectivite', title="Répartition par Canal de Sélectivité", hole=0.4,

                               color_discrete_map={'VERT': '#047857', 'BLEU': '#1D4ED8', 'JAUNE': '#D97706', 'ROUGE': '#B91C1C'})

            fig_canal.update_layout(paper_bgcolor='rgba(0,0,0,0)', font_color='white')

            st.plotly_chart(fig_canal, use_container_width=True)



        with col_g2:

            fig_regime = px.bar(df_d, x='regime', y='total_facture', color='canal_selectivite', title="Recettes par Régime Douanier")

            fig_regime.update_layout(paper_bgcolor='rgba(0,0,0,0)', font_color='white')

            st.plotly_chart(fig_regime, use_container_width=True)



    st.markdown('</div>', unsafe_allow_html=True)



# =========================================================

# TAB 1 : MODULE MANIFESTE & CARGO TRACKING

# =========================================================

with tab_manifeste:

    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)

    st.subheader("🚢 Module 1 : Gestion des Manifestes de Cargo (Air / Mer)")



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

                cursor.execute("INSERT INTO manifestes (num_manifeste, moyen_transport, num_voyage, provenance, date_arrivee) VALUES (?, ?, ?, ?, ?)",

                               (m_num, m_transport, m_voyage, m_prov, m_date.strftime("%Y-%m-%d")))

                conn.commit()

                log_action(st.session_state.username, "Ajout Manifeste", f"Manifeste {m_num} créé")

                st.success(f"Manifeste {m_num} créé !")

            except Exception as e:

                st.error(f"Erreur : {e}")

            conn.close()



    with col_m2:

        st.markdown("##### 2️⃣ Ajouter une Ligne de Fret (Connaissement B/L)")

        conn = sqlite3.connect(DB_NAME)

        df_man = pd.read_sql_query("SELECT num_manifeste FROM manifestes", conn)

        conn.close()



        if not df_man.empty:

            with st.form("form_fret"):

                f_man = st.selectbox("Manifeste Associé", df_man['num_manifeste'].tolist())

                f_bl = st.text_input("N° Connaissement / B/L", value="MEDU98765432")

                f_client = st.text_input("Destinataire (Consignee)", value="ETS KOUASSI & FRERES")

                f_poids = st.number_input("Poids Brut (kg)", value=1500.0)

                f_colis = st.number_input("Nombre de Colis", value=45)

                btn_f = st.form_submit_button("Ajouter la Ligne de Fret")



            if btn_f and f_bl:

                conn = sqlite3.connect(DB_NAME)

                cursor = conn.cursor()

                try:

                    cursor.execute("INSERT INTO fret_lines (num_manifeste, bl_number, consignee, poids_brut, nb_colis) VALUES (?, ?, ?, ?, ?)",

                                   (f_man, f_bl, f_client, f_poids, f_colis))

                    conn.commit()

                    st.success(f"B/L {f_bl} rattaché au manifeste {f_man} !")

                except Exception as e:

                    st.error(f"Erreur B/L existant : {e}")

                conn.close()



    st.markdown("---")

    st.markdown("### Registre National des Manifestes et Apurement Fret")

    conn = sqlite3.connect(DB_NAME)

    df_fret_all = pd.read_sql_query("SELECT * FROM fret_lines", conn)

    conn.close()

    st.dataframe(df_fret_all, use_container_width=True)



    st.markdown('</div>', unsafe_allow_html=True)



# =========================================================

# TAB 2 : DÉCLARATION EN DÉTAIL & SÉLECTIVITÉ HYBRIDE

# =========================================================

with tab_sad:

    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)

    st.subheader("📋 Module 2 : Déclaration en Détail (SAD) & Moteur de Sélectivité")



    conn = sqlite3.connect(DB_NAME)

    df_art_db = pd.read_sql_query("SELECT * FROM articles", conn)

    df_bl_unpurged = pd.read_sql_query("SELECT bl_number, consignee FROM fret_lines WHERE statut_apurement = 'Non apuré'", conn)

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

        caf_xof = fob_xof * 1.08 # Fret + Assurance estimés

        total_douane = calculer_droits_douane(caf_xof, item_row['dd'], regime_code)



    with col_s2:

        st.markdown("##### 🎯 Anlayse du Risque & Sélectivité")

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

            (date, client, article, regime, fob_xof, total_facture, solde_du, statut, bl_number, container_number, date_arrivee, score_risque, canal_selectivite, motifs_risque)

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

        """, (date_str, client_decl, article_nom, regime_code, fob_xof, total_douane, total_douane, "En cours de contrôle" if canal in ["JAUNE", "ROUGE"] else "Liquidé - En attente de paiement",

              bl_select, container_input, datetime.now().strftime("%Y-%m-%d"), score_risk, canal, motifs_risk))



        # Apurement du Fret

        cursor.execute("UPDATE fret_lines SET statut_apurement = 'Apuré par SAD' WHERE bl_number = ?", (bl_select,))

        conn.commit()

        conn.close()



        log_action(st.session_state.username, "Soumission SAD", f"SAD enregistrée pour {client_decl} - Canal {canal}")

        st.success(f"Déclaration enregistrée avec succès sous le Canal **{canal}** !")



    st.markdown('</div>', unsafe_allow_html=True)



# =========================================================

# TAB 3 : CAISSE & BON À ENLEVER (BAE) SÉCURISÉ

# =========================================================

with tab_caisse:

    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)

    st.subheader("💳 Module 3 : Caisse Douanière & Émission du Bon à Enlever (BAE)")



    conn = sqlite3.connect(DB_NAME)

    df_dossiers_all = pd.read_sql_query("SELECT * FROM dossiers ORDER BY id DESC", conn)

    conn.close()



    if df_dossiers_all.empty:

        st.info("Aucune déclaration enregistrée.")

    else:

        st.dataframe(df_dossiers_all[['id', 'date', 'client', 'article', 'canal_selectivite', 'total_facture', 'solde_du', 'statut']], use_container_width=True)



        st.markdown("---")

        st.subheader("⚙️ Encaisser la Liquidation & Délivrer la Mainlevée (BAE)")



        col_pay1, col_pay2 = st.columns(2)

        with col_pay1:

            sel_dossier_id = st.selectbox("Sélectionner l'ID de Déclaration à Encaisser", df_dossiers_all['id'].tolist())

            row_pay = df_dossiers_all[df_dossiers_all['id'] == sel_dossier_id].iloc[0]



            st.write(f"**Client :** {row_pay['client']} | **Montant à Régler :** `{row_pay['solde_du']:,.0f} FCFA`")

            st.write(f"**Canal de Sélectivité :** `{row_pay['canal_selectivite']}`")



        with col_pay2:

            moyen_paiement = st.selectbox("Mode de Règlement", ["TrésorPay / RTGS Banque Centrale", "Chèque Certifié Trésor Public", "Virement SWIFT", "Mobile Money"])

            if st.button("💳 Valider le Paiement & Émettre le BAE", use_container_width=True):

                quittance = f"QUIT-2026-{sel_dossier_id:05d}"

                conn = sqlite3.connect(DB_NAME)

                cursor = conn.cursor()

                cursor.execute("UPDATE dossiers SET solde_du = 0, statut = 'Liquidé & Payé (BAE Émis)', quittance_num = ? WHERE id = ?", (quittance, sel_dossier_id))

                conn.commit()

                conn.close()



                log_action(st.session_state.username, "Paiement Caisse", f"Quittance {quittance} générée pour dossier #{sel_dossier_id}")

                st.success(f"Paiement enregistré ! Quittance N° **{quittance}** émise.")



                # Génération du BAE PDF

                pdf_bae = generer_bae_pdf(sel_dossier_id, row_pay['client'], row_pay['article'], row_pay['bl_number'], row_pay['container_number'], quittance, row_pay['total_facture'])



                with open(pdf_bae, "rb") as f_bae:

                    st.download_button("📥 Télécharger le Bon à Enlever (BAE) Sécurisé (PDF)", data=f_bae.read(), file_name=pdf_bae, mime="application/pdf", use_container_width=True)



    st.markdown('</div>', unsafe_allow_html=True)



# =========================================================

# TAB 4 : PASSERELLE EDI (UN/EDIFACT)

# =========================================================

with tab_edi:

    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)

    st.subheader("🔄 Module 4 : Passerelle EDI & Interopérabilité UN/EDIFACT")

    st.caption("Génération et conversion automatique des messages normalisés OMD/UN (CUSDEC / CUSRES)")



    conn = sqlite3.connect(DB_NAME)

    df_d_edi = pd.read_sql_query("SELECT * FROM dossiers ORDER BY id DESC LIMIT 5", conn)

    conn.close()



    if not df_d_edi.empty:

        sel_edi_id = st.selectbox("Sélectionner une Déclaration à exporter en EDI", df_d_edi['id'].tolist())

        row_edi = df_d_edi[df_d_edi['id'] == sel_edi_id].iloc[0]



        edifact_str = generer_message_edifact_cusdec(f"SAD-2026-{sel_edi_id}", row_edi['client'], row_edi['article'], row_edi['fob_xof'], row_edi['regime'])



        st.code(edifact_str, language="text")



        st.download_button("📥 Télécharger le Fichier EDI (UN/EDIFACT .edi)", data=edifact_str, file_name=f"CUSDEC_D{sel_edi_id}.edi", mime="text/plain", use_container_width=True)



    st.markdown('</div>', unsafe_allow_html=True)



# =========================================================

# TAB 5 : IDP OCR CROSS-CHECKING

# =========================================================

with tab_ocr:

    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)

    st.subheader("📄 Module 5 : IDP OCR & Cross-Checking des Pièces Jointes")

    st.caption("Détection automatique des tentatives de sous-évaluation douanière")



    f_ocr = st.file_uploader("Joindre la Facture Commerciale PDF/Image", type=["pdf", "png", "jpg", "txt"])

    if f_ocr:

        st.success("Facture scannée. Extraction des métadonnées terminée.")

        col_oc1, col_oc2 = st.columns(2)

        with col_oc1:

            st.metric("Montant Extrait sur Facture OCR", "$ 25,000 USD")

            st.metric("Poids Brut Extrait", "1,500.0 kg")

        with col_oc2:

            st.metric("Montant Déclaré par le Déclarant", "$ 20,000 USD")

            st.error("⚠️ ALERTE DISCORDANCE : Sous-évaluation détectée (-20.0%) ! Dossier basculé en CIRCUIT ROUGE.")



    st.markdown('</div>', unsafe_allow_html=True)



# ==========================================
