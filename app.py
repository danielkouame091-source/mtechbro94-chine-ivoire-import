import hashlib
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from xml.sax.saxutils import escape

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

try:
    from groq import Groq
except ImportError:
    Groq = None

st.set_page_config(page_title="SNDGIR - Système National Douanier", page_icon="🇨🇮", layout="wide")
DB_NAME = "sndgir_national_customs.db"
UPLOAD_DIR = "uploads_dossiers"
ADMIN_ROLES = {"Administrateur", "Administrateur Système"}
os.makedirs(UPLOAD_DIR, exist_ok=True)


@contextmanager
def db_connection():
    conn = sqlite3.connect(DB_NAME, timeout=15)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=15000")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def password_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def init_db():
    with db_connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL, statut TEXT DEFAULT 'Actif');
        CREATE TABLE IF NOT EXISTS manifestes(id INTEGER PRIMARY KEY AUTOINCREMENT, num_manifeste TEXT UNIQUE NOT NULL, moyen_transport TEXT, num_voyage TEXT, provenance TEXT, date_arrivee TEXT, statut TEXT DEFAULT 'Enregistré');
        CREATE TABLE IF NOT EXISTS fret_lines(id INTEGER PRIMARY KEY AUTOINCREMENT, num_manifeste TEXT, bl_number TEXT UNIQUE NOT NULL, consignee TEXT, poids_brut REAL, nb_colis INTEGER, statut_apurement TEXT DEFAULT 'Non apuré');
        CREATE TABLE IF NOT EXISTS articles(id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT UNIQUE NOT NULL, sh TEXT, dd REAL, categorie TEXT);
        CREATE TABLE IF NOT EXISTS dossiers(id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, client TEXT, article TEXT, regime TEXT, fob_xof REAL, total_facture REAL, solde_du REAL, statut TEXT, bl_number TEXT, container_number TEXT, date_arrivee TEXT, score_risque REAL, canal_selectivite TEXT, motifs_risque TEXT, quittance_num TEXT, document_path TEXT);
        CREATE TABLE IF NOT EXISTS audit_logs(id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, username TEXT, action TEXT, details TEXT);
        CREATE INDEX IF NOT EXISTS idx_dossiers_date ON dossiers(date);
        CREATE INDEX IF NOT EXISTS idx_dossiers_canal ON dossiers(canal_selectivite);
        CREATE INDEX IF NOT EXISTS idx_fret_status ON fret_lines(statut_apurement);
        CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp);
        """)
        conn.executemany("INSERT OR IGNORE INTO users(username,password_hash,role,statut) VALUES(?,?,?,?)", [
            ("admin", password_hash("transit2026"), "Administrateur Système", "Actif"),
            ("verificateur", password_hash("douane2026"), "Vérificateur Douanier", "Actif"),
            ("caissier", password_hash("caisse2026"), "Agent de Caisse", "Actif"),
            ("declarant", password_hash("compta2026"), "Commissionnaire Agréé", "Actif"),
        ])
        conn.executemany("INSERT OR IGNORE INTO articles(nom,sh,dd,categorie) VALUES(?,?,?,?)", [
            ("Station Totale Topographique & GNSS/GPS", "9015.80.00", 5, "Topographie"),
            ("Smartphones & Téléphones portables", "8517.13.00", 20, "High-Tech"),
            ("Ordinateurs Portables & MacBooks", "8471.30.00", 5, "Informatique"),
            ("Vélos et Bicyclettes sans moteur", "8712.00.00", 20, "Transport"),
            ("Motos & Motocycles", "8711.20.00", 20, "Transport"),
            ("Voitures de Tourisme", "8703.22.00", 20, "Véhicules"),
            ("Vêtements", "6203.00.00", 20, "Textile"),
            ("Sacs à main", "4202.22.00", 20, "Maroquinerie"),
        ])


init_db()


def audit(user, action, details):
    with db_connection() as conn:
        conn.execute("INSERT INTO audit_logs(timestamp,username,action,details) VALUES(?,?,?,?)", (datetime.now().isoformat(timespec="seconds"), user, action, details))


@st.cache_data(ttl=30, show_spinner=False)
def read_table(query: str, params=()):
    with db_connection() as conn:
        return pd.read_sql_query(query, conn, params=params)


@st.cache_data(ttl=3600, show_spinner=False)
def get_rates():
    fallback = {"USD": 610.0, "CNY": 85.0, "EUR": 655.957, "AED": 166.0}
    try:
        response = requests.get("https://open.er-api.com/v6/latest/USD", timeout=3)
        response.raise_for_status()
        data = response.json().get("rates", {})
        usd = float(data.get("XOF", fallback["USD"]))
        return {"USD": round(usd, 2), "CNY": round(usd / float(data.get("CNY", 7.2)), 2), "EUR": 655.957, "AED": round(usd / float(data.get("AED", 3.67)), 2)}, "🟢 Taux API"
    except (requests.RequestException, ValueError, TypeError, KeyError, ZeroDivisionError):
        return fallback, "⚠️ Taux de secours hors ligne"


def invalidate_data_cache():
    read_table.clear()


def risk_score(value, category, divergence):
    score, reasons = 10.0, []
    if value > 50_000_000: score += 30; reasons.append("FOB supérieur à 50M FCFA")
    elif value > 10_000_000: score += 15; reasons.append("FOB supérieur à 10M FCFA")
    if divergence > 15: score += 40; reasons.append(f"Divergence OCR majeure ({divergence:.1f}%)")
    elif divergence > 5: score += 20; reasons.append(f"Écart OCR ({divergence:.1f}%)")
    if category in {"High-Tech", "Véhicules"}: score += 15; reasons.append(f"Catégorie sensible ({category})")
    return round(score, 1), ("VERT" if score < 25 else "BLEU" if score < 45 else "JAUNE" if score < 70 else "ROUGE"), " | ".join(reasons) or "Déclaration conforme"


def customs_tax(caf, rate, regime):
    if "E100" in regime or "TR" in regime: return caf * 0.005
    if "AT" in regime: return caf * 0.01
    base = caf * (rate / 100 + 0.02)
    return base + (caf + base) * 0.18


def make_edi(number, client, value, regime):
    now = datetime.now().strftime("%y%m%d:%H%M")
    return f"""UNB+UNOA:2+SNDGIR_CI+DECLARANT+{now}+00001'\nUNH+1+CUSDEC:D:96B:UN'\nBGM+107+{number}+9'\nCST+1+{str(regime).split(' - ', 1)[0]}'\nNAD+CZ++{str(client).upper().replace(chr(39), '?')}'\nLOC+11+CIABJ'\nMEA+WT+G+{float(value):.0f}'\nUNT+7+1'\nUNZ+1+00001'"""


def make_bae(dossier_id, client, article, bl, container, receipt, total):
    path = os.path.join(UPLOAD_DIR, f"BAE_Officiel_SNDGIR_{dossier_id}.pdf")
    styles = getSampleStyleSheet()
    title = ParagraphStyle("title", parent=styles["Heading1"], alignment=1, textColor=colors.HexColor("#064E3B"), fontSize=16)
    safe = lambda value: escape(str(value))
    fingerprint = hashlib.sha256(f"{dossier_id}-{receipt}-{total}".encode()).hexdigest()[:24].upper()
    body = f"<b>BON À ENLEVER (BAE) OFFICIEL</b><br/><br/><b>Dossier :</b> RCI-DOUANE-2026-{dossier_id}<br/><b>Quittance :</b> {safe(receipt)}<br/><b>Destinataire :</b> {safe(client)}<br/><b>Désignation :</b> {safe(article)}<br/><b>B/L :</b> {safe(bl)} | <b>Conteneur :</b> {safe(container)}<br/><b>Montant :</b> {float(total):,.0f} FCFA<br/><b>Empreinte :</b> {fingerprint}"
    doc = SimpleDocTemplate(path, pagesize=letter, rightMargin=35, leftMargin=35, topMargin=35, bottomMargin=35)
    doc.build([Paragraph("<b>RÉPUBLIQUE DE CÔTE D'IVOIRE</b>", title), Paragraph("DIRECTION GÉNÉRALE DES DOUANES — SYSTÈME SNDGIR", title), Spacer(1, 15), Paragraph(body, styles["Normal"])])
    return path


if "authenticated" not in st.session_state:
    st.session_state.update(authenticated=False, username="", user_role="")

if not st.session_state.authenticated:
    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.title("🔐 Portail National Douanier")
        user = st.text_input("Identifiant")
        pwd = st.text_input("Mot de passe", type="password")
        if st.button("Se connecter", use_container_width=True):
            row = read_table("SELECT username,password_hash,role,statut FROM users WHERE username=?", (user,))
            if not row.empty and row.iloc[0].statut == "Actif" and password_hash(pwd) == row.iloc[0].password_hash:
                st.session_state.update(authenticated=True, username=row.iloc[0].username, user_role=row.iloc[0].role)
                audit(user, "Connexion", "Accès accordé"); st.rerun()
            st.error("Identifiants incorrects ou compte désactivé.")
    st.stop()

st.sidebar.title("🇨🇮 SNDGIR NATIONAL")
st.sidebar.write(f"Agent : **{st.session_state.username}**")
st.sidebar.write(f"Rôle : **{st.session_state.user_role}**")
api_key = st.sidebar.text_input("🔑 Clé API Groq", value=st.secrets.get("GROQ_API_KEY", ""), type="password")
exchange, exchange_status = get_rates()
st.sidebar.caption(exchange_status)
manual_rates = {key: st.sidebar.number_input(f"1 {key}", value=value, step=0.1, key=f"rate_{key}") for key, value in exchange.items()}
if st.sidebar.button("🚪 Déconnexion"):
    st.session_state.clear(); st.rerun()

st.title("🏛️ SYSTÈME NATIONAL DE DÉDOUANEMENT — SNDGIR v5.0")
tabs = st.tabs(["📈 Dashboard", "🚢 Manifeste & Fret", "📋 Déclaration", "💳 Caisse & BAE", "🔄 EDI", "📄 OCR", "📖 Code", "🤖 Assistant IA", "🔐 Admin"])

with tabs[0]:
    st.subheader("📈 Dashboard National")
    data = read_table("SELECT canal_selectivite, regime, total_facture FROM dossiers")
    if data.empty: st.info("Aucune déclaration enregistrée.")
    else:
        a, b, c, d = st.columns(4)
        a.metric("Recettes", f"{data.total_facture.sum():,.0f} FCFA"); b.metric("Déclarations", len(data)); c.metric("Canal vert", int((data.canal_selectivite == 'VERT').sum())); d.metric("Canal rouge", int((data.canal_selectivite == 'ROUGE').sum()))
        st.plotly_chart(px.pie(data, names="canal_selectivite", hole=.4), use_container_width=True)

with tabs[1]:
    st.subheader("🚢 Manifestes et fret")
    with st.form("manifest_form"):
        number = st.text_input("N° manifeste"); transport = st.selectbox("Transport", ["Maritime", "Aérien", "Routier"]); voyage = st.text_input("Voyage / Vol"); origin = st.text_input("Provenance", "Guangzhou, Chine"); submit = st.form_submit_button("Enregistrer")
    if submit and number:
        try:
            with db_connection() as conn: conn.execute("INSERT INTO manifestes(num_manifeste,moyen_transport,num_voyage,provenance,date_arrivee) VALUES(?,?,?,?,?)", (number, transport, voyage, origin, datetime.now().date().isoformat()))
            invalidate_data_cache(); st.success("Manifeste enregistré.")
        except sqlite3.IntegrityError: st.error("Ce manifeste existe déjà.")
    st.dataframe(read_table("SELECT * FROM manifestes ORDER BY id DESC LIMIT 100"), use_container_width=True)

with tabs[2]:
    st.subheader("📋 Déclaration et sélectivité")
    articles = read_table("SELECT * FROM articles ORDER BY nom")
    bls = read_table("SELECT bl_number FROM fret_lines WHERE statut_apurement='Non apuré' ORDER BY id DESC LIMIT 500")
    client = st.text_input("Importateur", "ETS KOUASSI & FRERES")
    article = st.selectbox("Article", articles.nom.tolist())
    item = articles[articles.nom == article].iloc[0]
    regime = st.selectbox("Régime", ["C100 - Consommation", "E100 - Entrepôt", "AT - Admission temporaire", "TR - Transit"])
    bl = st.selectbox("B/L", bls.bl_number.tolist() if not bls.empty else ["MEDU98765432"])
    container = st.text_input("Conteneur", "MSCU1234567")
    currency = st.selectbox("Devise", list(manual_rates)); quantity = st.number_input("Quantité", min_value=1, value=100); unit = st.number_input("Prix unitaire", min_value=0.01, value=250.0)
    fob = quantity * unit * manual_rates[currency]; total = customs_tax(fob * 1.08, float(item.dd), regime); divergence = st.slider("Divergence OCR (%)", 0.0, 30.0, 2.0); score, channel, reasons = risk_score(fob, item.categorie, divergence)
    st.info(f"Score {score}/100 — Canal {channel} — {reasons}")
    if st.button("🚀 Soumettre la déclaration"):
        with db_connection() as conn:
            conn.execute("INSERT INTO dossiers(date,client,article,regime,fob_xof,total_facture,solde_du,statut,bl_number,container_number,date_arrivee,score_risque,canal_selectivite,motifs_risque) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (datetime.now().isoformat(timespec="minutes"), client, article, regime, fob, total, total, "En cours de contrôle" if channel in {"JAUNE", "ROUGE"} else "En attente de paiement", bl, container, datetime.now().date().isoformat(), score, channel, reasons))
            conn.execute("UPDATE fret_lines SET statut_apurement='Apuré par SAD' WHERE bl_number=?", (bl,))
        invalidate_data_cache(); audit(st.session_state.username, "Soumission SAD", f"{client} - {channel}"); st.success("Déclaration enregistrée.")

with tabs[3]:
    st.subheader("💳 Caisse et BAE")
    dossiers = read_table("SELECT * FROM dossiers ORDER BY id DESC LIMIT 500")
    if dossiers.empty: st.info("Aucun dossier.")
    else:
        selected = st.selectbox("Dossier", dossiers.id.tolist()); row = dossiers[dossiers.id == selected].iloc[0]; st.write(f"Solde : **{row.solde_du:,.0f} FCFA**")
        if st.button("💳 Payer et émettre le BAE"):
            if float(row.solde_du or 0) <= 0: st.warning("Ce dossier est déjà payé.")
            else:
                receipt = f"QUIT-{datetime.now():%Y}-{int(selected):05d}"
                with db_connection() as conn: cur = conn.execute("UPDATE dossiers SET solde_du=0,statut='Liquidé & Payé (BAE Émis)',quittance_num=? WHERE id=? AND solde_du>0", (receipt, int(selected)))
                if cur.rowcount == 1:
                    path = make_bae(selected, row.client, row.article, row.bl_number, row.container_number, receipt, row.total_facture); invalidate_data_cache(); audit(st.session_state.username, "Paiement", receipt); st.success(f"Paiement enregistré : {receipt}")
                    with open(path, "rb") as file: st.download_button("📥 Télécharger le BAE", file.read(), os.path.basename(path), "application/pdf")
                else: st.warning("Paiement déjà effectué ou dossier introuvable.")

with tabs[4]:
    st.subheader("🔄 Passerelle EDI")
    records = read_table("SELECT id,client,fob_xof,regime FROM dossiers ORDER BY id DESC LIMIT 20")
    if not records.empty:
        ident = st.selectbox("Dossier EDI", records.id.tolist()); item = records[records.id == ident].iloc[0]; message = make_edi(f"SAD-{ident}", item.client, item.fob_xof, item.regime); st.code(message); st.download_button("📥 Télécharger EDI", message, f"CUSDEC_{ident}.edi")

with tabs[5]:
    st.subheader("📄 OCR")
    uploaded = st.file_uploader("Joindre une facture", type=["pdf", "png", "jpg", "txt"])
    if uploaded: st.success(f"Fichier reçu : {uploaded.name}. Extraction OCR à connecter.")

with tabs[6]:
    st.subheader("📖 Code des douanes"); st.info("Référentiel juridique à compléter avec les textes officiels validés.")

with tabs[7]:
    st.subheader("🤖 Assistant IA Douanes"); question = st.text_area("Votre question")
    if st.button("🔍 Consulter l'Expert IA"):
        if not question.strip(): st.warning("Saisissez une question.")
        elif not api_key or Groq is None: st.warning("Renseignez la clé API Groq.")
        else:
            try:
                result = Groq(api_key=api_key).chat.completions.create(model="openai/gpt-oss-120b", messages=[{"role": "user", "content": f"Vous êtes un expert prudent des douanes de Côte d'Ivoire. Répondez : {question}"}], temperature=0.2, max_tokens=1024)
                st.info(result.choices[0].message.content)
            except Exception as exc: st.error(f"Erreur Groq : {exc}")

if st.session_state.user_role in ADMIN_ROLES:
    with tabs[8]:
        st.subheader("🔐 Administration et audit")
        st.dataframe(read_table("SELECT id,username,role,statut FROM users"), use_container_width=True)
        st.dataframe(read_table("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 100"), use_container_width=True)
