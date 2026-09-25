import hashlib
import os
import sqlite3
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
os.makedirs(UPLOAD_DIR, exist_ok=True)
ADMIN_ROLES = {"Administrateur", "Administrateur Système"}


def db():
    return sqlite3.connect(DB_NAME)


def password_hash(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def init_db():
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password_hash TEXT, role TEXT, statut TEXT DEFAULT 'Actif');
        CREATE TABLE IF NOT EXISTS manifestes(id INTEGER PRIMARY KEY AUTOINCREMENT, num_manifeste TEXT UNIQUE, moyen_transport TEXT, num_voyage TEXT, provenance TEXT, date_arrivee TEXT, statut TEXT DEFAULT 'Enregistré');
        CREATE TABLE IF NOT EXISTS fret_lines(id INTEGER PRIMARY KEY AUTOINCREMENT, num_manifeste TEXT, bl_number TEXT UNIQUE, consignee TEXT, poids_brut REAL, nb_colis INTEGER, statut_apurement TEXT DEFAULT 'Non apuré');
        CREATE TABLE IF NOT EXISTS articles(id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT UNIQUE, sh TEXT, dd REAL, categorie TEXT);
        CREATE TABLE IF NOT EXISTS dossiers(id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, client TEXT, article TEXT, regime TEXT, fob_xof REAL, total_facture REAL, solde_du REAL, statut TEXT, bl_number TEXT, container_number TEXT, date_arrivee TEXT, score_risque REAL, canal_selectivite TEXT, motifs_risque TEXT, quittance_num TEXT, document_path TEXT);
        CREATE TABLE IF NOT EXISTS audit_logs(id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, username TEXT, action TEXT, details TEXT);
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
    with db() as conn:
        conn.execute("INSERT INTO audit_logs(timestamp,username,action,details) VALUES(?,?,?,?)", (datetime.now().isoformat(timespec="seconds"), user, action, details))


def rates():
    fallback = {"USD": 610.0, "CNY": 85.0, "EUR": 655.957, "AED": 166.0}
    try:
        response = requests.get("https://open.er-api.com/v6/latest/USD", timeout=4)
        response.raise_for_status()
        data = response.json().get("rates", {})
        usd = float(data.get("XOF", fallback["USD"]))
        return {"USD": round(usd, 2), "CNY": round(usd / float(data.get("CNY", 7.2)), 2), "EUR": 655.957, "AED": round(usd / float(data.get("AED", 3.67)), 2)}, "🟢 Taux direct API"
    except (requests.RequestException, ValueError, TypeError, KeyError):
        return fallback, "⚠️ Taux de secours hors ligne"


@st.cache_data(ttl=3600)
def cached_rates():
    return rates()


def risk_score(value, category, divergence):
    score, reasons = 10.0, []
    if value > 50_000_000: score += 30; reasons.append("FOB supérieur à 50M FCFA")
    elif value > 10_000_000: score += 15; reasons.append("FOB supérieur à 10M FCFA")
    if divergence > 15: score += 40; reasons.append(f"Divergence OCR majeure ({divergence:.1f}%)")
    elif divergence > 5: score += 20; reasons.append(f"Écart OCR ({divergence:.1f}%)")
    if category in {"High-Tech", "Véhicules"}: score += 15; reasons.append(f"Catégorie sensible ({category})")
    channel = "VERT" if score < 25 else "BLEU" if score < 45 else "JAUNE" if score < 70 else "ROUGE"
    return round(score, 1), channel, " | ".join(reasons) or "Déclaration conforme"


def customs_tax(caf, rate, regime):
    if "E100" in regime or "TR" in regime: return caf * .005
    if "AT" in regime: return caf * .01
    base = caf * (rate / 100 + .02)
    return base + (caf + base) * .18


def edifact(number, client, value, regime):
    now = datetime.now().strftime("%y%m%d:%H%M")
    clean_client = str(client).upper().replace("'", "?")
    clean_regime = str(regime).split(" - ", 1)[0].replace("'", "?")
    return f"""UNB+UNOA:2+SNDGIR_CI+DECLARANT+{now}+00001'\nUNH+1+CUSDEC:D:96B:UN'\nBGM+107+{number}+9'\nCST+1+{clean_regime}'\nNAD+CZ++{clean_client}'\nLOC+11+CIABJ'\nMEA+WT+G+{float(value):.0f}'\nUNT+7+1'\nUNZ+1+00001'"""


def bae_pdf(dossier_id, client, article, bl, container, receipt, total):
    path = os.path.join(UPLOAD_DIR, f"BAE_Officiel_SNDGIR_{dossier_id}.pdf")
    styles = getSampleStyleSheet()
    title = ParagraphStyle("title", parent=styles["Heading1"], alignment=1, textColor=colors.HexColor("#064E3B"), fontSize=16)
    safe = lambda x: escape(str(x))
    fingerprint = hashlib.sha256(f"{dossier_id}-{receipt}-{total}".encode()).hexdigest()[:24].upper()
    body = f"""<b>BON À ENLEVER (BAE) OFFICIEL</b><br/><br/><b>Dossier :</b> RCI-DOUANE-2026-{dossier_id}<br/><b>Quittance :</b> {safe(receipt)}<br/><b>Destinataire :</b> {safe(client)}<br/><b>Désignation :</b> {safe(article)}<br/><b>B/L :</b> {safe(bl)} | <b>Conteneur :</b> {safe(container)}<br/><b>Montant acquitté :</b> {float(total):,.0f} FCFA<br/><b>Empreinte :</b> {fingerprint}"""
    doc = SimpleDocTemplate(path, pagesize=letter, rightMargin=35, leftMargin=35, topMargin=35, bottomMargin=35)
    doc.build([Paragraph("<b>RÉPUBLIQUE DE CÔTE D'IVOIRE</b>", title), Paragraph("DIRECTION GÉNÉRALE DES DOUANES — SYSTÈME SNDGIR", title), Spacer(1, 15), Paragraph(body, styles["Normal"])])
    return path


if "authenticated" not in st.session_state: st.session_state.update(authenticated=False, username="", user_role="")

if not st.session_state.authenticated:
    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.title("🔐 Portail National Douanier")
        user = st.text_input("Identifiant")
        pwd = st.text_input("Mot de passe", type="password")
        if st.button("Se connecter", use_container_width=True):
            with db() as conn: row = conn.execute("SELECT username,password_hash,role,statut FROM users WHERE username=?", (user,)).fetchone()
            if row and row[3] == "Actif" and password_hash(pwd) == row[1]:
                st.session_state.update(authenticated=True, username=row[0], user_role=row[2]); audit(row[0], "Connexion", "Accès accordé"); st.rerun()
            else: st.error("Identifiants incorrects ou compte désactivé.")
    st.stop()

st.sidebar.title("🇨🇮 SNDGIR NATIONAL")
st.sidebar.write(f"Agent : **{st.session_state.username}**")
st.sidebar.write(f"Rôle : **{st.session_state.user_role}**")
api_key = st.sidebar.text_input("🔑 Clé API Groq", value=st.secrets.get("GROQ_API_KEY", ""), type="password")
exchange, exchange_status = cached_rates()
st.sidebar.caption(exchange_status)
manual = {key: st.sidebar.number_input(f"1 {key}", value=value, step=.1) for key, value in exchange.items()}
if st.sidebar.button("🚪 Déconnexion"):
    st.session_state.clear(); st.rerun()

st.markdown("<div class='header'><h1>🏛️ SYSTÈME NATIONAL DE DÉDOUANEMENT (SNDGIR v5.0)</h1></div>", unsafe_allow_html=True)
tabs = st.tabs(["📈 Dashboard", "🚢 Manifeste & Fret", "📋 Déclaration", "💳 Caisse & BAE", "🔄 EDI", "📄 OCR", "📖 Code", "🤖 Assistant IA", "🔐 Admin"])

with tabs[0]:
    with db() as conn: data = pd.read_sql_query("SELECT * FROM dossiers", conn)
    st.subheader("📈 Dashboard National")
    if data.empty: st.info("Aucune déclaration enregistrée.")
    else:
        a,b,c,d = st.columns(4); a.metric("Recettes", f"{data.total_facture.sum():,.0f} FCFA"); b.metric("Déclarations", len(data)); c.metric("Canal vert", (data.canal_selectivite == "VERT").sum()); d.metric("Canal rouge", (data.canal_selectivite == "ROUGE").sum())
        st.plotly_chart(px.pie(data, names="canal_selectivite", hole=.4), use_container_width=True)

with tabs[1]:
    st.subheader("🚢 Manifestes et fret")
    with st.form("manifest_form"):
        number = st.text_input("N° manifeste"); transport = st.selectbox("Transport", ["Maritime", "Aérien", "Routier"]); voyage = st.text_input("Voyage / Vol"); origin = st.text_input("Provenance", "Guangzhou, Chine"); submit = st.form_submit_button("Enregistrer")
    if submit and number:
        try:
            with db() as conn: conn.execute("INSERT INTO manifestes(num_manifeste,moyen_transport,num_voyage,provenance,date_arrivee) VALUES(?,?,?,?,?)", (number,transport,voyage,origin,datetime.now().date().isoformat()))
            st.success("Manifeste enregistré.")
        except sqlite3.IntegrityError: st.error("Ce manifeste existe déjà.")
    with db() as conn: st.dataframe(pd.read_sql_query("SELECT * FROM manifestes", conn), use_container_width=True)

with tabs[2]:
    st.subheader("📋 Déclaration et sélectivité")
    with db() as conn: articles = pd.read_sql_query("SELECT * FROM articles", conn); bls = pd.read_sql_query("SELECT bl_number FROM fret_lines WHERE statut_apurement='Non apuré'", conn)
    client = st.text_input("Importateur", "ETS KOUASSI & FRERES"); article = st.selectbox("Article", articles.nom.tolist()); item = articles[articles.nom == article].iloc[0]
    regime = st.selectbox("Régime", ["C100 - Consommation", "E100 - Entrepôt", "AT - Admission temporaire", "TR - Transit"]); bl = st.selectbox("B/L", bls.bl_number.tolist() if not bls.empty else ["MEDU98765432"]); container = st.text_input("Conteneur", "MSCU1234567")
    currency = st.selectbox("Devise", list(manual)); quantity = st.number_input("Quantité", min_value=1, value=100); unit = st.number_input("Prix unitaire", min_value=.01, value=250.0); fob = quantity * unit * manual[currency]; total = customs_tax(fob * 1.08, float(item.dd), regime); divergence = st.slider("Divergence OCR (%)", 0., 30., 2.); score, channel, reasons = risk_score(fob, item.categorie, divergence); st.info(f"Score {score}/100 — Canal {channel} — {reasons}")
    if st.button("🚀 Soumettre la déclaration"):
        with db() as conn:
            conn.execute("INSERT INTO dossiers(date,client,article,regime,fob_xof,total_facture,solde_du,statut,bl_number,container_number,date_arrivee,score_risque,canal_selectivite,motifs_risque) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (datetime.now().isoformat(timespec="minutes"),client,article,regime,fob,total,total,"En cours de contrôle" if channel in {"JAUNE","ROUGE"} else "En attente de paiement",bl,container,datetime.now().date().isoformat(),score,channel,reasons)); conn.execute("UPDATE fret_lines SET statut_apurement='Apuré par SAD' WHERE bl_number=?", (bl,))
        audit(st.session_state.username, "Soumission SAD", f"{client} - {channel}"); st.success("Déclaration enregistrée.")

with tabs[3]:
    st.subheader("💳 Caisse et BAE")
    with db() as conn: dossiers = pd.read_sql_query("SELECT * FROM dossiers ORDER BY id DESC", conn)
    if dossiers.empty: st.info("Aucun dossier.")
    else:
        selected = st.selectbox("Dossier", dossiers.id.tolist()); row = dossiers[dossiers.id == selected].iloc[0]; st.write(f"Solde : **{row.solde_du:,.0f} FCFA**")
        if st.button("💳 Payer et émettre le BAE"):
            if float(row.solde_du or 0) <= 0: st.warning("Ce dossier est déjà payé.")
            else:
                receipt = f"QUIT-{datetime.now():%Y}-{int(selected):05d}"
                with db() as conn: cur = conn.execute("UPDATE dossiers SET solde_du=0,statut='Liquidé & Payé (BAE Émis)',quittance_num=? WHERE id=? AND solde_du>0", (receipt,int(selected)))
                if cur.rowcount == 1:
                    path = bae_pdf(selected,row.client,row.article,row.bl_number,row.container_number,receipt,row.total_facture); st.success(f"Paiement enregistré : {receipt}"); audit(st.session_state.username, "Paiement", receipt)
                    with open(path,"rb") as file: st.download_button("📥 Télécharger le BAE", file.read(), os.path.basename(path), "application/pdf")
                else: st.warning("Paiement déjà effectué ou dossier introuvable.")

with tabs[4]:
    st.subheader("🔄 Passerelle EDI")
    with db() as conn: records = pd.read_sql_query("SELECT * FROM dossiers ORDER BY id DESC LIMIT 5", conn)
    if not records.empty:
        ident = st.selectbox("Dossier EDI", records.id.tolist()); item = records[records.id == ident].iloc[0]; message = edifact(f"SAD-{ident}", item.client, item.fob_xof, item.regime); st.code(message); st.download_button("📥 Télécharger EDI", message, f"CUSDEC_{ident}.edi")

with tabs[5]:
    st.subheader("📄 OCR")
    uploaded = st.file_uploader("Joindre une facture", type=["pdf","png","jpg","txt"])
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
                # llama-3.3-70b-versatile a été retiré de Groq : utiliser un modèle actif.
                result = Groq(api_key=api_key).chat.completions.create(model="openai/gpt-oss-120b", messages=[{"role":"user","content":f"Vous êtes un expert prudent des douanes de Côte d'Ivoire. Répondez : {question}"}], temperature=.2, max_tokens=1024)
                st.info(result.choices[0].message.content)
            except Exception as exc:
                st.error(f"Erreur Groq : {exc}")
                st.caption("Vérifiez la clé API et la disponibilité du modèle openai/gpt-oss-120b dans votre compte Groq.")

if st.session_state.user_role in ADMIN_ROLES:
    with tabs[8]:
        st.subheader("🔐 Administration et audit")
        with db() as conn:
            st.dataframe(pd.read_sql_query("SELECT id,username,role,statut FROM users", conn), use_container_width=True); st.dataframe(pd.read_sql_query("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 100", conn), use_container_width=True)
