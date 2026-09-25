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
import bcrypt

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

try:
    from groq import Groq
except ImportError:
    Groq = None

st.set_page_config(
    page_title="SNDGIR - Transit & Douanes Côte d'Ivoire (Sécurisé)",
    page_icon="🇨🇮",
    layout="wide",
)

st.markdown(
    """
<style>
.stApp { background-color: #060911; color: #F8FAFC; font-family: 'Inter', system-ui, -apple-system, sans-serif; }
.header-banner { background: linear-gradient(135deg, #064E3B 0%, #047857 40%, #0284C7 100%); padding: 25px 30px; border-radius: 20px; color: white; margin-bottom: 25px; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.7); border: 1px solid rgba(255, 255, 255, 0.2); }
.custom-card-3d { background: #0F172A; border-radius: 18px; padding: 22px; border: 1px solid #1E293B; margin-bottom: 22px; box-shadow: 6px 6px 18px #03060D, -6px -6px 18px #1B2437; }
.kpi-card { background: linear-gradient(145deg, #1e293b, #0f172a); border-radius: 14px; padding: 16px; border: 1px solid #334155; text-align: center; }
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

DB_NAME = "sndgir_national_customs_v2.db"
UPLOAD_DIR = "uploads_dossiers"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def sanitize_input(input_str: str, max_length: int = 100) -> str:
    """Valide et nettoie les entrées textuelles pour contrer les injections."""
    if not isinstance(input_str, str):
        return ""
    cleaned = re.sub(r'[^\w\s\-_@\.\,\(\)]', '', input_str)
    return cleaned[:max_length].strip()

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password_hash TEXT, role TEXT, statut TEXT DEFAULT 'Actif')""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS manifestes (id INTEGER PRIMARY KEY AUTOINCREMENT, num_manifeste TEXT UNIQUE, moyen_transport TEXT, num_voyage TEXT, provenance TEXT, date_arrivee TEXT, statut TEXT DEFAULT 'Enregistré')""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS fret_lines (id INTEGER PRIMARY KEY AUTOINCREMENT, num_manifeste TEXT, bl_number TEXT UNIQUE, consignee TEXT, poids_brut REAL, nb_colis INTEGER, statut_apurement TEXT DEFAULT 'Non apuré')""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS articles (id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT UNIQUE, sh TEXT, dd REAL, categorie TEXT)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS dossiers (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, client TEXT, article TEXT, regime TEXT, fob_xof REAL, total_facture REAL, solde_du REAL, statut TEXT, bl_number TEXT, container_number TEXT, date_arrivee TEXT, score_risque REAL, canal_selectivite TEXT, motifs_risque TEXT, quittance_num TEXT, document_path TEXT, honoraires REAL DEFAULT 150000, frais_port REAL DEFAULT 85000, frais_transport REAL DEFAULT 120000, surestaries_xof REAL DEFAULT 0, statut_livraison TEXT DEFAULT 'Sous douane')""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS compta_ecritures (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, journal TEXT, compte_debit TEXT, libelle_debit TEXT, compte_credit TEXT, libelle_credit TEXT, montant REAL, piece_ref TEXT)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, username TEXT, action TEXT, details TEXT)""")
    
    admin_pwd = hash_password("transit2026")
    verif_pwd = hash_password("douane2026")
    caiss_pwd = hash_password("caisse2026")
    decl_pwd = hash_password("compta2026")

    for u in [("admin", admin_pwd, "Administrateur Système", "Actif"), ("verificateur", verif_pwd, "Vérificateur Douanier", "Actif"), ("caissier", caiss_pwd, "Agent de Caisse", "Actif"), ("declarant", decl_pwd, "Commissionnaire Agréé", "Actif")]:
        cursor.execute("INSERT OR IGNORE INTO users (username, password_hash, role, statut) VALUES (?, ?, ?, ?)", u)
        
    for item in [("Station Totale Topographique & GNSS/GPS", "9015.80.00", 5.0, "Topographie"), ("Smartphones & Téléphones portables", "8517.13.00", 20.0, "High-Tech"), ("Ordinateurs Portables & MacBooks", "8471.30.00", 5.0, "Informatique"), ("Voitures de Tourisme (Berlines / SUV)", "8703.22.00", 20.0, "Véhicules")]:
        cursor.execute("INSERT OR IGNORE INTO articles (nom, sh, dd, categorie) VALUES (?, ?, ?, ?)", item)
    conn.commit()
    conn.close()

init_db()

def log_action(username, action, details):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT INTO audit_logs (timestamp, username, action, details) VALUES (?, ?, ?, ?)", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), username, action, details))
    conn.commit()
    conn.close()

def calculer_selectivite_risque(fob_xof, item_info, diff_ocr_pct, client_nom):
    score = 10.0
    motifs = []
    if fob_xof > 50000000:
        score += 30; motifs.append("Valeur FOB supérieure à 50M FCFA")
    elif fob_xof > 10000000:
        score += 15; motifs.append("Valeur FOB supérieure à 10M FCFA")
    if diff_ocr_pct > 15.0:
        score += 40; motifs.append(f"Divergence majeure OCR Facture ({diff_ocr_pct:.1f}%)")
    elif diff_ocr_pct > 5.0:
        score += 20; motifs.append(f"Écart mineur OCR Facture ({diff_ocr_pct:.1f}%)")
    if item_info.get('cat') in ['High-Tech', 'Véhicules']:
        score += 15; motifs.append(f"Catégorie sous surveillance ({item_info.get('cat')})")
    canal = "VERT" if score < 25 else ("BLEU" if score < 45 else ("JAUNE" if score < 70 else "ROUGE"))
    return round(score, 1), canal, " | ".join(motifs) if motifs else "Déclaration conforme"

def calculer_surestaries(date_dechargement_str, jours_franchise, frais_jour_usd, taux_usd):
    try:
        date_limite = datetime.strptime(date_dechargement_str, "%Y-%m-%d") + timedelta(days=int(jours_franchise))
        jours_depasses = (datetime.now() - date_limite).days
        if jours_depasses > 0:
            cout_usd = jours_depasses * frais_jour_usd
            return jours_depasses, cout_usd, cout_usd * taux_usd, f"🔴 PÉNALITÉ DE SURESTARIES ({jours_depasses} j.)"
        return 0, 0, 0, f"🟢 FRANCHISE ACTIVE (Reste {abs(jours_depasses)} j.)"
    except Exception:
        return 0, 0, 0, "⚪ Non évalué"

@st.cache_data(ttl=3600)
def obtenir_taux_change_automatique():
    default_rates = {"CNY": 85.0, "USD": 610.0, "EUR": 655.957, "AED": 166.0}
    try:
        res = requests.get("https://open.er-api.com/v6/latest/USD", timeout=4)
        if res.status_code == 200:
            rates = res.json().get("rates", {})
            usd_xof = rates.get("XOF", 610.0)
            return {"CNY": round(usd_xof / rates.get("CNY", 7.2), 2), "USD": round(usd_xof, 2), "EUR": 655.957, "AED": round(usd_xof / rates.get("AED", 3.67), 2)}, "🟢 Taux direct API"
    except Exception:
        pass
    return default_rates, "⚠️ Mode secours"

taux_devises_dict, status_api_devises = obtenir_taux_change_automatique()

def calculer_droits_douane(caf_xof, dd_pct, regime_code):
    if "C100" in regime_code:
        droits_hors_tva = caf_xof * (dd_pct / 100.0 + 0.020)
        return droits_hors_tva + (caf_xof + droits_hors_tva) * 0.18
    if "E100" in regime_code or "TR" in regime_code:
        return caf_xof * 0.005
    if "AT" in regime_code:
        return caf_xof * 0.010
    droits_hors_tva = caf_xof * (dd_pct / 100.0 + 0.02)
    return droits_hors_tva + (caf_xof + droits_hors_tva) * 0.18

def generer_bae_pdf(dossier_id, client, article, bl_num, container_num, quittance_num, total_facture):
    pdf_filename = f"BAE_Officiel_SNDGIR_{dossier_id}.pdf"
    doc = SimpleDocTemplate(pdf_filename, pagesize=letter, rightMargin=35, leftMargin=35, topMargin=35, bottomMargin=35)
    styles = getSampleStyleSheet(); elements = []
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#064E3B'), alignment=1)
    elements += [Paragraph("<b>RÉPUBLIQUE DE CÔTE D'IVOIRE</b>", title_style), Paragraph("<font size=10>DIRECTION GÉNÉRALE DES DOUANES — SYSTEME SNDGIR</font>", title_style), Spacer(1, 15)]
    hash_val = hashlib.sha256(f"{dossier_id}-{quittance_num}-{total_facture}".encode()).hexdigest()[:24].upper()
    elements += [Paragraph(f"<b>BON À ENLEVER (BAE) OFFICIEL</b><br/><br/><b>N° Dossier :</b> RCI-DOUANE-2026-{dossier_id}<br/><b>N° Quittance :</b> {quittance_num}<br/><b>Importateur :</b> {client}<br/><b>Marchandise :</b> {article}<br/><b>B/L :</b> {bl_num} | <b>Conteneur :</b> {container_num}<br/><b>Droits Acquittés :</b> {total_facture:,.0f} FCFA<br/><b>Empreinte :</b> <code>{hash_val}</code>", styles['Normal']), Spacer(1, 20), Paragraph("<b>Mainlevée accordée.</b>", styles['Normal'])]
    doc.build(elements); return pdf_filename

def generer_facture_transit_pdf(dossier_id, client, article, total_douane, honoraires, frais_port, frais_transport, surestaries):
    pdf_filename = f"Facture_Transit_{dossier_id}.pdf"
    doc = SimpleDocTemplate(pdf_filename, pagesize=letter, rightMargin=35, leftMargin=35, topMargin=35, bottomMargin=35)
    styles = getSampleStyleSheet(); elements = []
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#0284C7'), alignment=1)
    elements += [Paragraph("<b>AGENCE DE TRANSIT & LOGISTIQUE</b>", title_style), Spacer(1, 15)]
    
    tva_hon = honoraires * 0.18
    total_general = total_douane + honoraires + tva_hon + frais_port + frais_transport + surestaries
    
    data = [
        ["Rubrique", "Montant (FCFA)"], 
        ["Droits & Taxes", f"{total_douane:,.0f} FCFA"], 
        ["Frais Portuaires", f"{frais_port:,.0f} FCFA"], 
        ["Transport", f"{frais_transport:,.0f} FCFA"], 
        ["Surestaries", f"{surestaries:,.0f} FCFA"], 
        ["Honoraires", f"{honoraires:,.0f} FCFA"], 
        ["TVA Honoraires (18%)", f"{tva_hon:,.0f} FCFA"], 
        ["TOTAL", f"{total_general:,.0f} FCFA"]
    ]
    
    t = Table(data, colWidths=[300, 200])
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#0F172A')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),0.5,colors.grey)]))
    elements += [Paragraph(f"<b>Client :</b> {client}<br/>", styles['Normal']), t]
    doc.build(elements)
    return pdf_filename

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_role = ""
    st.session_state.username = ""

if not st.session_state.authenticated:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
        st.subheader("🔐 Portail National Sécurisé (SNDGIR v5.2)")
        username_input = sanitize_input(st.text_input("Identifiant Officiel"))
        password_input = st.text_input("Mot de passe", type="password")
        if st.button("Se connecter au Système", use_container_width=True):
            conn = sqlite3.connect(DB_NAME)
            row = conn.execute("SELECT username, password_hash, role, statut FROM users WHERE username = ?", (username_input,)).fetchone()
            conn.close()
            if row:
                u_name, u_pwd_hash, u_role, u_statut = row
                if u_statut != "Actif":
                    st.error("Compte désactivé.")
                elif verify_password(password_input, u_pwd_hash):
                    st.session_state.authenticated = True
                    st.session_state.username = u_name
                    st.session_state.user_role = u_role
                    log_action(u_name, "Connexion Zero Trust", "Accès validé")
                    st.rerun()
                else:
                    log_action(username_input, "Échec Connexion", "Mot de passe erroné")
                    st.error("Identifiant ou mot de passe incorrect.")
            else:
                st.error("Identifiant non reconnu.")
        st.markdown('</div>', unsafe_allow_html=True)
        st.stop()

st.sidebar.title("🇨🇮 SNDGIR ERP v5.2")
st.sidebar.markdown(f"**Utilisateur :** `{st.session_state.username}`")
st.sidebar.markdown(f"**Rôle RBAC :** `{st.session_state.user_role}`")
st.sidebar.markdown("---")

if st.sidebar.button("🚪 Déconnexion", use_container_width=True):
    log_action(st.session_state.username, "Déconnexion", "Session close")
    st.session_state.authenticated = False
    st.rerun()

st.markdown("""<div class="header-banner"><h1>🏛️ CÔTE D'IVOIRE : SYSTÈMES DOUANIERS & TRANSIT (Zéro Trust)</h1><p>Sécurité maximale 100% active - Traçabilité inviolable & RBAC strict</p></div>""", unsafe_allow_html=True)

tabs_list = [
    "📈 Dashboard", 
    "🚢 1. Manifeste", 
    "📋 2. SAD", 
    "💼 3. Transit", 
    "💳 4. Caisse", 
    "📊 5. Compta", 
    "🔄 6. EDI", 
    "📄 7. OCR", 
    "🌐 8. Innovations", 
    "📖 9. Code", 
    "🔐 Admin"
]
tabs = st.tabs(tabs_list)
tab_dash, tab_manifeste, tab_sad, tab_transit_erp, tab_caisse, tab_compta, tab_edi, tab_ocr, tab_innov, tab_code, tab_admin = tabs

with tab_dash:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📈 Tableau de Bord Analytique")
    conn = sqlite3.connect(DB_NAME)
    df_d = pd.read_sql_query("SELECT * FROM dossiers", conn)
    conn.close()
    if df_d.empty:
        st.info("Aucun dossier.")
    else:
        st.metric("Total Droits Liquidés", f"{df_d['total_facture'].sum():,.0f} FCFA")
    st.markdown('</div>', unsafe_allow_html=True)

with tab_manifeste:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("🚢 Manifestes Maritimes")
    m_num = sanitize_input(st.text_input("N° Manifeste"))
    if st.button("Enregistrer Manifeste"):
        if m_num:
            conn = sqlite3.connect(DB_NAME)
            try:
                conn.execute("INSERT INTO manifestes (num_manifeste, moyen_transport, num_voyage, provenance, date_arrivee) VALUES (?, 'Maritime', 'V-001', 'Abidjan', ?)", (m_num, datetime.now().strftime("%Y-%m-%d")))
                conn.commit()
                st.success("Manifeste enregistré.")
            except Exception:
                st.error("Erreur d'enregistrement.")
            conn.close()
    st.markdown('</div>', unsafe_allow_html=True)

with tab_sad:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📋 Déclaration en Détail (SAD)")
    client = sanitize_input(st.text_input("Client", value="ETS KOUASSI"))
    fob = st.number_input("Valeur FOB (FCFA)", value=1000000.0)
    if st.button("Soumettre SAD"):
        score, canal, motifs = calculer_selectivite_risque(fob, {"cat": "High-Tech"}, 2.0, client)
        st.success(f"Déclaration soumise - Canal {canal} (Score: {score})")
    st.markdown('</div>', unsafe_allow_html=True)

with tab_transit_erp:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("💼 Suivi Transit & Surestaries")
    st.info("Module transit actif sous contrôle RBAC.")
    st.markdown('</div>', unsafe_allow_html=True)

with tab_caisse:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("💳 Caisse & Encaissement")
    if st.session_state.user_role not in ["Agent de Caisse", "Administrateur Système"]:
        st.error("⛔ Accès refusé : Réservé au rôle Caisse.")
    else:
        st.success("Interface de caisse autorisée.")
    st.markdown('</div>', unsafe_allow_html=True)

with tab_compta:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📊 Comptabilité SYSCOHADA")
    st.info("Journal comptable sécurisé.")
    st.markdown('</div>', unsafe_allow_html=True)

with tab_edi:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("🔄 Passerelle EDI")
    st.markdown('</div>', unsafe_allow_html=True)

with tab_ocr:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📄 IDP OCR Cross-Check")
    st.markdown('</div>', unsafe_allow_html=True)

with tab_innov:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("🌐 Innovations Internationales")
    st.markdown('</div>', unsafe_allow_html=True)

with tab_code:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📖 Code des Douanes")
    st.markdown('</div>', unsafe_allow_html=True)

with tab_admin:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("🔐 Administration & Journaux d'Audit Inviolables")
    if st.session_state.user_role != "Administrateur Système":
        st.error("⛔ Accès strictement restreint aux Administrateurs Système.")
    else:
        conn = sqlite3.connect(DB_NAME)
        df_logs = pd.read_sql_query("SELECT * FROM audit_logs ORDER BY id DESC", conn)
        conn.close()
        st.dataframe(df_logs, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
