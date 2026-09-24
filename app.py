import base64
import os
import sqlite3
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime
from urllib.parse import quote, urlencode

import pandas as pd
import requests
import streamlit as st

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
# CONFIGURATION & STYLING 3D / GLASSMORPHISM
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
    padding: 30px; 
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
    padding: 22px; 
    border-radius: 16px; 
    text-align: center; 
    margin-top: 15px; 
    box-shadow: inset 2px 2px 5px rgba(255,255,255,0.2), 0 10px 20px rgba(21, 128, 61, 0.4);
    font-size: 1.25rem;
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
# GESTION DE LA BASE DE DONNÉES SQLITE & DOSSIERS UPLOAD
# =========================================================
DB_NAME = "transit_enterprise.db"
UPLOAD_DIR = "uploads_dossiers"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Table articles & SH
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT UNIQUE,
            sh TEXT,
            dd REAL,
            categorie TEXT
        )
    """)

    # Table dossiers CRM enrichie (Workflow & Pièces jointes)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dossiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            client TEXT,
            article TEXT,
            fob_xof REAL,
            total_facture REAL,
            solde_du REAL,
            statut TEXT,
            document_path TEXT
        )
    """)
    conn.commit()

    # Remplir par défaut si vide
    cursor.execute("SELECT COUNT(*) FROM articles")
    if cursor.fetchone()[0] == 0:
        default_data = [
            ("Station Totale Topographique & GNSS/GPS", "9015.80.00", 5.0, "Topographie"),
            ("Théodolites, Niveaux Optiques & Laser", "9015.10.00", 5.0, "Topographie"),
            ("Smartphones, iPhones & Téléphones portables", "8517.13.00", 20.0, "High-Tech"),
            ("Ordinateurs Portables, MacBooks & Tablettes", "8471.30.00", 5.0, "Informatique"),
            ("Panneaux Photovoltaïques / Solaires", "8541.43.00", 5.0, "Énergie"),
            ("Groupes Électrogènes (Générateurs)", "8502.11.00", 5.0, "Machines"),
        ]
        cursor.executemany("INSERT OR IGNORE INTO articles (nom, sh, dd, categorie) VALUES (?, ?, ?, ?)", default_data)
        conn.commit()
    conn.close()

init_db()

def get_articles_db():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM articles", conn)
    conn.close()
    return df

def ajouter_dossier_db(client, article, fob, total, solde, statut="En cours", doc_path=""):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    date_jour = datetime.now().strftime("%Y-%m-%d %H:%M")
    cursor.execute(
        "INSERT INTO dossiers (date, client, article, fob_xof, total_facture, solde_du, statut, document_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (date_jour, client, article, fob, total, solde, statut, doc_path)
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

# =========================================================
# AUTHENTIFICATION AVEC CONTRÔLE D'ACCÈS PAR RÔLES (RBAC)
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
        st.caption("Sécurité multicouche & Contrôle des Rôles (RBAC)")

        username_input = st.text_input("Identifiant utilisateur")
        password_input = st.text_input("Mot de passe", type="password")

        if st.button("Se connecter", use_container_width=True):
            utilisateurs = {
                "admin": {"password": "transit2026", "role": "Administrateur"},
                "commercial": {"password": "compta2026", "role": "Commercial / Déclarant"},
                "comptable": {"password": "finance2026", "role": "Comptable / Trésorerie"}
            }

            if username_input in utilisateurs and utilisateurs[username_input]["password"] == password_input:
                st.session_state.authenticated = True
                st.session_state.username = username_input
                st.session_state.user_role = utilisateurs[username_input]["role"]
                st.rerun()
            else:
                st.error("Identifiants erronés. (Essayez admin / transit2026)")
        st.markdown('</div>', unsafe_allow_html=True)
        st.stop()

# =========================================================
# FONCTION DE GÉNÉRATION DE PDF PROFESSIONNEL
# =========================================================
def generer_pdf_devis_pro(nom_client, article_nom, item_info, quantite, fob_xof, fret_xof, assurance_xof, caf_xof, total_douane, total_transit, post_acheminement, total_facture, acompte, solde_du):
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

    info_client_text = f"<b>Client / Importateur :</b> {nom_client}<br/><b>Date d'émission :</b> {datetime.now().strftime('%d/%m/%Y')}<br/><b>Objet :</b> Facture Proforma & Cotation Logistique Douanière"
    elements.append(Paragraph(info_client_text, styles['Normal']))
    elements.append(Spacer(1, 10))

    data = [
        ["Désignation / Prestation", "Code SH", "Qté", "Montant (FCFA)"],
        [article_nom, item_info['sh'], str(quantite), f"{fob_xof:,.0f}"],
        ["Fret International & Assurance", "-", "-", f"{(fret_xof + assurance_xof):,.0f}"],
        ["Valeur CAF (Douane)", "-", "-", f"{caf_xof:,.0f}"],
        ["Droits & Taxes de Douane (SYDAM)", "-", "-", f"{total_douane:,.0f}"],
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
# TAUX DE CHANGE AUTOMATIQUE
# =========================================================
@st.cache_data(ttl=3600)
def obtenir_taux_change_automatique():
    default_cny_xof = 82.0
    default_usd_xof = 610.0
    try:
        url = "https://open.er-api.com/v6/latest/USD"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            rates = response.json().get("rates", {})
            usd_xof = rates.get("XOF", default_usd_xof)
            usd_cny = rates.get("CNY", 7.2)
            cny_xof = usd_xof / usd_cny if usd_cny else default_cny_xof
            return round(cny_xof, 2), round(usd_xof, 2), "🟢 Taux direct API (Temps réel)"
    except Exception:
        pass
    return default_cny_xof, default_usd_xof, "⚠️ Mode secours (Hors ligne)"

taux_cny_auto, taux_usd_auto, status_api_devises = obtenir_taux_change_automatique()

# =========================================================
# BARRE LATÉRALE - CONFIGURATION & SMTP & RÔLE
# =========================================================
st.sidebar.title("🇨🇮 KELANEWIN TRANSIT")
st.sidebar.markdown(f"**Utilisateur :** `{st.session_state.username}`")
st.sidebar.markdown(f"**Rôle :** `{st.session_state.user_role}`")
st.sidebar.markdown("---")

default_key = st.secrets.get("GROQ_API_KEY", "") if hasattr(st, "secrets") else ""
groq_api_key = st.sidebar.text_input("🔑 Clé API Groq", value=default_key, type="password")

st.sidebar.subheader("💱 Taux de Change")
st.sidebar.caption(status_api_devises)
taux_cny_xof = st.sidebar.number_input("1 CNY -> FCFA", value=taux_cny_auto, step=0.1)
taux_usd_xof = st.sidebar.number_input("1 USD -> FCFA", value=taux_usd_auto, step=1.0)

st.sidebar.subheader("⚙️ Configuration SMTP (Envoi Email Auto)")
smtp_server = st.sidebar.text_input("Serveur SMTP", value="smtp.gmail.com")
smtp_port = st.sidebar.number_input("Port SMTP", value=587)
sender_email = st.sidebar.text_input("Email Expéditeur", value="")
smtp_password = st.sidebar.text_input("Mot de passe application", type="password")

st.sidebar.markdown("---")
if st.sidebar.button("🚪 Se déconnecter"):
    st.session_state.authenticated = False
    st.rerun()

# =========================================================
# EN-TÊTE PRINCIPALE
# =========================================================
st.markdown("""
<div class="header-banner">
    <h1>📦 KELANEWIN TRANSIT : ENTERPRISE SUITE 2026</h1>
    <p>Module Avancé : Sécurité RBAC, Workflow CRM, Upload Documents & Post-Acheminement</p>
</div>
""", unsafe_allow_html=True)

tab_cotation, tab_crm, tab_ai_expert, tab_base_sh = st.tabs([
    "📊 Cotation & Devis Pro + Documents", 
    "📂 CRM & Workflow Dynamique (Statuts)", 
    "🤖 Assistant IA SYDAM", 
    "📚 Base de Données SH"
])

# Charger les articles depuis SQLite
df_articles_db = get_articles_db()
liste_articles_noms = df_articles_db["nom"].tolist()

# =========================================================
# TAB 1 : COTATION, POST-ACHEMINEMENT & UPLOAD DE DOCUMENTS
# =========================================================
with tab_cotation:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("👤 1. Coordonnées & Pièces Justificatives du Dossier")
    c1, c2, c3 = st.columns(3)
    with c1:
        nom_client = st.text_input("Nom / Entreprise du Client", value="ETS KOUASSI & FRERES")
    with c2:
        email_client = st.text_input("Email du destinataire", value="client@example.com")
    with c3:
        tel_client = st.text_input("Téléphone / WhatsApp", value="+2250700000000")

    st.markdown("<br/>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader("📎 Joindre les pièces justificatives (Facture Proforma, B/L, Packing List en PDF ou Image)", type=["pdf", "png", "jpg", "jpeg"])

    saved_doc_path = ""
    if uploaded_file is not None:
        saved_doc_path = os.path.join(UPLOAD_DIR, f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uploaded_file.name}")
        with open(saved_doc_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"Document joint avec succès : {uploaded_file.name}")

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📋 2. Caractéristiques de la Marchandise & Fret")
    col_a, col_b = st.columns([2, 1])

    with col_a:
        article_nom = st.selectbox("Sélectionner l'article (depuis SQLite)", liste_articles_noms)
        item_row = df_articles_db[df_articles_db["nom"] == article_nom].iloc[0]
        item_info = {"sh": item_row["sh"], "dd": item_row["dd"], "cat": item_row["categorie"]}

        devise_facture = st.selectbox("Devise de la Facture Fournisseur", ["CNY (Yuan Chinois)", "USD (Dollar Américain)"])

        m1, m2, m3 = st.columns(3)
        with m1:
            quantite = st.number_input("Quantité d'unités", min_value=1, value=50, step=1)
        with m2:
            prix_unitaire_devise = st.number_input(f"Prix Unitaire ({devise_facture.split()[0]})", min_value=0.01, value=300.0, step=5.0)
        with m3:
            fret_devise = st.number_input(f"Frais de Fret Total ({devise_facture.split()[0]})", min_value=0.0, value=1500.0, step=50.0)

        fob_devise = quantite * prix_unitaire_devise
        st.markdown(f"👉 **Montant Total FOB :** `{fob_devise:,.2f} {devise_facture.split()[0]}`")

    with col_b:
        fob_xof_estim = fob_devise * (taux_cny_xof if "CNY" in devise_facture else taux_usd_xof)
        alerte_fdi = "✅ FDI non requise (< 1M FCFA)" if fob_xof_estim < 1000000 else "⚠️ FDI & RFC Obligatoires (GUCE)"

        st.markdown(f"""
        <div style="background:#0F172A; padding:18px; border-radius:12px; border:1px solid #334155;">
            <span class="badge-sydam">RÉGIME SYDAM</span><br/><br/>
            <b>Code SH :</b> <code>{item_info['sh']}</code><br/>
            <b>Catégorie :</b> {item_info['cat']}<br/>
            <b>Droit de Douane (DD) :</b> {item_info['dd']}%<br/>
            <b>TVA CI :</b> 18.0%<br/>
            <hr style="border-color:#334155">
            <small style="color:#38BDF8;">{alerte_fdi}</small>
        </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("🚚 3. Prestations de Transit, Post-Acheminement & Surestaries")
    h1, h2, h3 = st.columns(3)
    with h1:
        frais_port = st.number_input("Passage Portuaire / Aéroport (FCFA)", value=150000, step=5000)
        frais_guce = st.number_input("Frais GUCE & Webb Fontaine (FCFA)", value=35000, step=2500)
    with h2:
        honoraires = st.number_input("Honoraires Transit (FCFA)", value=250000, step=10000)
        charges_ops = st.number_input("Charges Réelles / Débours (FCFA)", value=50000, step=5000)
    with h3:
        transport_interieur = st.number_input("Transport & Post-Acheminement (FCFA)", value=120000, step=10000)
        surestaries = st.number_input("Provisions Surestaries / Détention (FCFA)", value=75000, step=5000)
        acompte = st.number_input("Acompte Reçu du Client (FCFA)", value=1000000, step=50000)

    post_acheminement_total = transport_interieur + surestaries
    benefice_net = honoraires - charges_ops
    st.markdown(f'<div class="profit-box-3d">💰 BÉNÉFICE NET DU TRANSITAIRE : <b>{benefice_net:,.0f} FCFA</b></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    taux_conversion = taux_cny_xof if "CNY" in devise_facture else taux_usd_xof
    fob_xof = fob_devise * taux_conversion
    fret_xof = fret_devise * taux_conversion
    assurance_xof = max((fob_xof + fret_xof) * 0.005, 5000.0)
    caf_xof = fob_xof + fret_xof + assurance_xof

    taux_dd = item_info["dd"] / 100.0
    taux_redevances = 0.010 + 0.008 + 0.005 + 0.010
    total_droits_hors_tva = caf_xof * (taux_dd + taux_redevances)
    tva_xof = (caf_xof + total_droits_hors_tva) * 0.18

    total_douane = total_droits_hors_tva + tva_xof
    total_transit = frais_port + frais_guce + honoraires
    total_facture = fob_xof + fret_xof + assurance_xof + total_douane + total_transit + post_acheminement_total
    solde_du = total_facture - acompte

    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📊 4. Synthèse Financière & Validation Professionnelle")

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Valeur CAF</div><div class="kpi-value">{caf_xof:,.0f} FCFA</div></div>""", unsafe_allow_html=True)
    with k2:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Droits Douane & TVA</div><div class="kpi-value">{total_douane:,.0f} FCFA</div></div>""", unsafe_allow_html=True)
    with k3:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Frais Port & Post-Ache.</div><div class="kpi-value">{(total_transit + post_acheminement_total):,.0f} FCFA</div></div>""", unsafe_allow_html=True)
    with k4:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title" style="color:#10B981;">Total Général Pro</div><div class="kpi-value" style="color:#10B981;">{total_facture:,.0f} FCFA</div></div>""", unsafe_allow_html=True)

    st.markdown("<br/>", unsafe_allow_html=True)

    if st.button("💾 Enregistrer ce dossier & Pièces dans la Base CRM", use_container_width=True):
        ajouter_dossier_db(nom_client, article_nom, fob_xof, total_facture, solde_du, "En cours", saved_doc_path)
        st.success("Dossier et pièces jointes enregistrés avec succès dans l'ERP CRM !")

    pdf_path = generer_pdf_devis_pro(nom_client, article_nom, item_info, quantite, fob_xof, fret_xof, assurance_xof, caf_xof, total_douane, total_transit, post_acheminement_total, total_facture, acompte, solde_du)

    with open(pdf_path, "rb") as pdf_file:
        PDFbyte = pdf_file.read()

    st.download_button(
        label="📥 Télécharger la Facture Proforma & Cotation Officielle (PDF)",
        data=PDFbyte,
        file_name=pdf_path,
        mime="application/octet-stream",
        use_container_width=True
    )

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📧 Envoi Automatisé au Client")

    msg_texte = f"""Bonjour {nom_client},
Veuillez trouver ci-joint la cotation officielle & proforma de Kelanewin Transit pour votre article {article_nom}.
Montant Total : {total_facture:,.0f} FCFA. Solde dû : {solde_du:,.0f} FCFA.
Cordialement, L'équipe Kelanewin Transit."""

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        if st.button("🚀 Envoyer l'Email Pro (SMTP)", use_container_width=True):
            if not sender_email or not smtp_password:
                st.error("Veuillez renseigner votre email et mot de passe SMTP dans la barre latérale.")
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
                    st.success("E-mail professionnel envoyé avec succès avec le PDF joint !")
                except Exception as e:
                    st.error(f"Erreur d'envoi SMTP : {e}")

    with col_s2:
        whatsapp_url = f"https://wa.me/{tel_client.strip().replace('+', '')}?text={quote(msg_texte)}"
        st.link_button("💬 Envoyer par WhatsApp", whatsapp_url, use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 2 : CRM & WORKFLOW DYNAMIQUE
# =========================================================
with tab_crm:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📂 Gestion & Suivi du Workflow des Dossiers (CRM)")
    df_dossiers = get_dossiers_db()

    if df_dossiers.empty:
        st.info("Aucun dossier enregistré dans l'ERP CRM pour le moment.")
    else:
        st.dataframe(df_dossiers[['id', 'date', 'client', 'article', 'fob_xof', 'total_facture', 'solde_du', 'statut']], use_container_width=True)

    st.markdown("---")
    st.subheader("⚙️ Mettre à jour l'avancement d'un dossier (Workflow Opérationnel)")

    col_w1, col_w2, col_w3 = st.columns(3)
    with col_w1:
        dossier_id_choisi = st.selectbox("ID du Dossier à modifier", df_dossiers['id'].tolist() if not df_dossiers.empty else [0])
    with col_w2:
        nouveau_statut = st.selectbox("Nouveau Statut Opérationnel", [
            "En cours", 
            "FDI & RFC Validées", 
            "Visite Douanière en Cours", 
            "Bon à Enlever (BAE) Émis", 
            "Livré au Client"
        ])
    with col_w3:
        st.markdown("<br/>", unsafe_allow_html=True)
        if st.button("Mettre à jour le Statut", use_container_width=True):
            if not df_dossiers.empty:
                mettre_a_jour_statut_db(dossier_id_choisi, nouveau_statut)
                st.success(f"Statut du dossier #{dossier_id_choisi} mis à jour avec succès : {nouveau_statut}")
                st.rerun()
            else:
                st.warning("Aucun dossier à modifier.")

    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 3 : ASSISTANT IA SYDAM (AVEC SÉCURITÉ DE SECOURS / FALLBACK MIS À JOUR)
# =========================================================
with tab_ai_expert:
    st.markdown('<div class="ai-box-3d">', unsafe_allow_html=True)
    st.subheader("🤖 Assistant Expert Kelanewin Transit (Groq Llama)")
    user_query = st.text_area("Posez votre question sur les procédures douanières ivoiriennes (SYDAM, GUCE, régimes suspensifs...)")

    if st.button("🔍 Interroger l'Expert"):
        if groq_api_key and Groq:
            try:
                client_ai = Groq(api_key=groq_api_key)
                prompt_expert = f"Vous êtes un expert transitaire en Côte d'Ivoire. Répondez précisément : {user_query}"

                # MODÈLES ACTIFS MIS À JOUR (Remplacement des modèles obsolètes)
                modeles_disponibles = [
                    "qwen/qwen3.8-27b",
                    "openai/gpt-oss-120b",
                    "openai/gpt-oss-20b"
                ]

                res_ai = None
                derniere_erreur = None
                erreurs = []

                for mod in modeles_disponibles:
                    try:
                        res_ai = client_ai.chat.completions.create(
                            model=mod,
                            messages=[{"role": "user", "content": prompt_expert}],
                            temperature=0.2,
                            max_tokens=1024,
                        )
                        break  # Si ça fonctionne, on sort de la boucle
                    except Exception as err:
                        derniere_erreur = err
                        erreurs.append(f"{mod}: {err}")
                        continue

                if res_ai:
                    st.info(res_ai.choices[0].message.content)
                else:
                    st.error("Erreur IA : Impossible d'utiliser les modèles Groq. Détails :")
                    with st.expander("Voir les détails techniques"):
                        st.code("\n".join(erreurs) if erreurs else "Aucune erreur détaillée disponible.")
            except Exception as e:
                st.error(f"Erreur d'initialisation Groq : {e}")
        else:
            st.warning("Veuillez renseigner votre clé API Groq dans la barre latérale.")
    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 4 : BASE DE DONNÉES SH
# =========================================================
with tab_base_sh:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📚 Gestion des Articles & Codes SH (Base SQLite)")

    if st.session_state.user_role in ["Administrateur", "Commercial / Déclarant"]:
        with st.form("form_ajout_article"):
            st.write("Ajouter un nouvel article au Tarif d'Usage UEMOA")
            n_nom = st.text_input("Désignation de l'article")
            n_sh = st.text_input("Code SH (ex: 8517.13.00)")
            n_dd = st.number_input("Droit de Douane - DD (%)", value=20.0)
            n_cat = st.text_input("Catégorie")
            submit_article = st.form_submit_button("Enregistrer dans la Base")

        if submit_article and n_nom and n_sh:
            try:
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                cursor.execute("INSERT INTO articles (nom, sh, dd, categorie) VALUES (?, ?, ?, ?)", (n_nom, n_sh, n_dd, n_cat))
                conn.commit()
                conn.close()
                st.success(f"Article '{n_nom}' ajouté avec succès !")
                st.rerun()
            except Exception as e:
                st.error(f"Erreur (l'article existe peut-être déjà) : {e}")
    else:
        st.info("Votre rôle actuel ne vous permet pas d'ajouter de nouveaux articles dans la base tarifaire.")

    st.markdown("---")
    st.markdown("### Liste actuelle enregistrée en base :")
    st.dataframe(get_articles_db(), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
