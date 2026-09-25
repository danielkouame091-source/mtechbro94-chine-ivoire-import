import hashlib
import html
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

st.set_page_config(
    page_title="SNDGIR - Système National Douanier",
    page_icon="🇨🇮",
    layout="wide",
)

st.markdown(
    """
<style>
.stApp { background-color:#060911; color:#F8FAFC; font-family:Inter,system-ui,sans-serif; }
.header-banner { background:linear-gradient(135deg,#064E3B,#047857 40%,#0284C7); padding:25px 30px; border-radius:20px; color:white; margin-bottom:25px; box-shadow:0 20px 25px -5px rgba(0,0,0,.7); }
.custom-card-3d { background:#0F172A; border-radius:18px; padding:22px; border:1px solid #1E293B; margin-bottom:22px; box-shadow:6px 6px 18px #03060D; }
.kpi-card { background:linear-gradient(145deg,#1e293b,#0f172a); border-radius:14px; padding:16px; border:1px solid #334155; text-align:center; }
.kpi-title { font-size:.8rem; color:#9CA3AF; text-transform:uppercase; letter-spacing:.05em; }
.kpi-value { font-size:1.4rem; font-weight:700; color:#38BDF8; }
.canal-vert,.canal-bleu,.canal-jaune,.canal-rouge { padding:6px 12px; border-radius:8px; font-weight:bold; }
.canal-vert { background:#064E3B; color:#34D399; } .canal-bleu { background:#1E3A8A; color:#60A5FA; }
.canal-jaune { background:#78350F; color:#FBBF24; } .canal-rouge { background:#7F1D1D; color:#F87171; }
</style>
""",
    unsafe_allow_html=True,
)

DB_NAME = "sndgir_national_customs.db"
UPLOAD_DIR = "uploads_dossiers"
os.makedirs(UPLOAD_DIR, exist_ok=True)
ROLES_ADMIN = {"Administrateur Système", "Administrateur"}
ROLES_CAISSE = ROLES_ADMIN | {"Agent de Caisse"}
ROLES_DECLARATION = ROLES_ADMIN | {"Commissionnaire Agréé", "Vérificateur Douanier"}


def hash_password(password: str) -> str:
    # Conservé pour assurer la compatibilité avec la base SQLite existante.
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with db_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL, role TEXT NOT NULL, statut TEXT DEFAULT 'Actif'
            );
            CREATE TABLE IF NOT EXISTS manifestes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, num_manifeste TEXT UNIQUE NOT NULL,
                moyen_transport TEXT, num_voyage TEXT, provenance TEXT, date_arrivee TEXT,
                statut TEXT DEFAULT 'Enregistré'
            );
            CREATE TABLE IF NOT EXISTS fret_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT, num_manifeste TEXT, bl_number TEXT UNIQUE NOT NULL,
                consignee TEXT, poids_brut REAL, nb_colis INTEGER, statut_apurement TEXT DEFAULT 'Non apuré'
            );
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT UNIQUE NOT NULL, sh TEXT, dd REAL, categorie TEXT
            );
            CREATE TABLE IF NOT EXISTS dossiers (
                id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, client TEXT, article TEXT, regime TEXT,
                fob_xof REAL, total_facture REAL, solde_du REAL, statut TEXT, bl_number TEXT,
                container_number TEXT, date_arrivee TEXT, score_risque REAL, canal_selectivite TEXT,
                motifs_risque TEXT, quittance_num TEXT, document_path TEXT
            );
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, username TEXT, action TEXT, details TEXT
            );
            """
        )
        users = [
            ("admin", hash_password("transit2026"), "Administrateur Système", "Actif"),
            ("verificateur", hash_password("douane2026"), "Vérificateur Douanier", "Actif"),
            ("caissier", hash_password("caisse2026"), "Agent de Caisse", "Actif"),
            ("declarant", hash_password("compta2026"), "Commissionnaire Agréé", "Actif"),
        ]
        conn.executemany("INSERT OR IGNORE INTO users(username,password_hash,role,statut) VALUES (?,?,?,?)", users)
        articles = [
            ("Station Totale Topographique & GNSS/GPS", "9015.80.00", 5.0, "Topographie"),
            ("Smartphones & Téléphones portables", "8517.13.00", 20.0, "High-Tech"),
            ("Ordinateurs Portables & MacBooks", "8471.30.00", 5.0, "Informatique"),
            ("Vélos et Bicyclettes sans moteur", "8712.00.00", 20.0, "Transport"),
            ("Motos & Motocycles (125cc - 250cc)", "8711.20.00", 20.0, "Transport"),
            ("Voitures de Tourisme (Berlines / SUV)", "8703.22.00", 20.0, "Véhicules"),
            ("Vêtements Homme / Femme / Enfant", "6203.00.00", 20.0, "Textile"),
            ("Sacs à main pour Dames", "4202.22.00", 20.0, "Maroquinerie"),
        ]
        conn.executemany("INSERT OR IGNORE INTO articles(nom,sh,dd,categorie) VALUES (?,?,?,?)", articles)


init_db()


def log_action(username, action, details):
    with db_connection() as conn:
        conn.execute(
            "INSERT INTO audit_logs(timestamp,username,action,details) VALUES (?,?,?,?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), username, action, details),
        )


def calculer_selectivite_risque(fob_xof, item_info, diff_ocr_pct):
    score, motifs = 10.0, []
    if fob_xof > 50_000_000:
        score += 30; motifs.append("Valeur FOB supérieure à 50M FCFA")
    elif fob_xof > 10_000_000:
        score += 15; motifs.append("Valeur FOB supérieure à 10M FCFA")
    if diff_ocr_pct > 15:
        score += 40; motifs.append(f"Divergence majeure OCR ({diff_ocr_pct:.1f}%)")
    elif diff_ocr_pct > 5:
        score += 20; motifs.append(f"Écart OCR ({diff_ocr_pct:.1f}%)")
    if item_info["cat"] in {"High-Tech", "Véhicules"}:
        score += 15; motifs.append(f"Catégorie sous surveillance ({item_info['cat']})")
    canal = "VERT" if score < 25 else "BLEU" if score < 45 else "JAUNE" if score < 70 else "ROUGE"
    return round(score, 1), canal, " | ".join(motifs) or "Déclaration conforme"


@st.cache_data(ttl=3600)
def obtenir_taux_change_automatique():
    defaults = {"CNY": 85.0, "USD": 610.0, "EUR": 655.957, "AED": 166.0}
    try:
        response = requests.get("https://open.er-api.com/v6/latest/USD", timeout=4)
        response.raise_for_status()
        rates = response.json().get("rates", {})
        usd_xof = rates.get("XOF", defaults["USD"])
        return {
            "CNY": round(usd_xof / rates.get("CNY", 7.2), 2),
            "USD": round(usd_xof, 2), "EUR": 655.957,
            "AED": round(usd_xof / rates.get("AED", 3.67), 2),
        }, "🟢 Taux direct API (Temps réel)"
    except (requests.RequestException, ValueError, TypeError, KeyError):
        return defaults, "⚠️ Mode secours (Hors ligne)"


rates, status_api_devises = obtenir_taux_change_automatique()


def calculer_droits_douane(caf_xof, dd_pct, regime_code):
    if "C100" in regime_code:
        hors_tva = caf_xof * (dd_pct / 100 + 0.020)
        return hors_tva + (caf_xof + hors_tva) * 0.18
    if "E100" in regime_code or "TR" in regime_code:
        return caf_xof * 0.005
    if "AT" in regime_code:
        return caf_xof * 0.010
    hors_tva = caf_xof * (dd_pct / 100 + 0.02)
    return hors_tva + (caf_xof + hors_tva) * 0.18


def generer_message_edifact_cusdec(num_dossier, client, fob_xof, regime):
    # La date UNB doit être générée une seule fois au format YYMMDD:HHMM.
    now_str = datetime.now().strftime("%y%m%d:%H%M")
    safe_client = str(client).upper().replace("'", "?")
    safe_regime = str(regime).split(" - ", 1)[0].replace("'", "?")
    return f"""UNB+UNOA:2+SNDGIR_CI+DECLARANT+{now_str}+00001'
UNH+1+CUSDEC:D:96B:UN'
BGM+107+{num_dossier}+9'
CST+1+{safe_regime}'
NAD+CZ++{safe_client}'
LOC+11+CIABJ'
MEA+WT+G+{float(fob_xof):.0f}'
UNT+7+1'
UNZ+1+00001'"""


def generer_bae_pdf(dossier_id, client, article, bl_num, container_num, quittance_num, total_facture):
    filename = os.path.join(UPLOAD_DIR, f"BAE_Officiel_SNDGIR_{dossier_id}.pdf")
    doc = SimpleDocTemplate(filename, pagesize=letter, rightMargin=35, leftMargin=35, topMargin=35, bottomMargin=35)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("TitleStyle", parent=styles["Heading1"], fontSize=16, textColor=colors.HexColor("#064E3B"), alignment=1)
    safe = lambda value: escape(str(value))
    hash_val = hashlib.sha256(f"{dossier_id}-{quittance_num}-{total_facture}".encode()).hexdigest()[:24].upper()
    info = f"""
    <b>BON À ENLEVER (BAE) OFFICIEL — MAINLEVÉE ACCORDÉE</b><br/><br/>
    <b>N° de Dossier :</b> RCI-DOUANE-2026-{dossier_id}<br/>
    <b>N° de Quittance Caisse :</b> {safe(quittance_num)}<br/>
    <b>Importateur / Destinataire :</b> {safe(client)}<br/>
    <b>Désignation :</b> {safe(article)}<br/>
    <b>N° Connaissement / B/L :</b> {safe(bl_num)} | <b>N° Conteneur :</b> {safe(container_num)}<br/>
    <b>Montant Droits Acquittés :</b> {float(total_facture):,.0f} FCFA<br/>
    <b>Empreinte Électronique Sécurisée :</b> <font name="Courier">{hash_val}</font>
    """
    elements = [
        Paragraph("<b>RÉPUBLIQUE DE CÔTE D'IVOIRE</b>", title),
        Paragraph("<font size=10>DIRECTION GÉNÉRALE DES DOUANES — SYSTÈME SNDGIR</font>", title),
        Spacer(1, 15), Paragraph(info, styles["Normal"]), Spacer(1, 20),
        Paragraph("<b>Le Chef du Bureau de Douane certifie que la marchandise ci-dessus a satisfait à toutes les obligations douanières et autorise son enlèvement du port.</b>", styles["Normal"]),
    ]
    doc.build(elements)
    return filename


if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_role = ""
    st.session_state.username = ""

if not st.session_state.authenticated:
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
        st.subheader("🔐 Portail National Douanier (SNDGIR)")
        username = st.text_input("Identifiant Officiel")
        password = st.text_input("Mot de passe", type="password")
        if st.button("Se connecter au Système", use_container_width=True):
            with db_connection() as conn:
                row = conn.execute("SELECT username,password_hash,role,statut FROM users WHERE username=?", (username,)).fetchone()
            if not row:
                st.error("Identifiant non reconnu.")
            elif row[3] != "Actif":
                st.error("Compte désactivé.")
            elif hash_password(password) != row[1]:
                st.error("Mot de passe incorrect.")
            else:
                st.session_state.authenticated = True
                st.session_state.username, st.session_state.user_role = row[0], row[2]
                log_action(row[0], "Connexion", "Accès accordé au portail")
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

st.sidebar.title("🇨🇮 SNDGIR NATIONAL")
st.sidebar.markdown(f"**Agent :** `{st.session_state.username}`")
st.sidebar.markdown(f"**Rôle :** `{st.session_state.user_role}`")
groq_default_key = st.secrets.get("GROQ_API_KEY", "") if hasattr(st, "secrets") else ""
groq_api_key = st.sidebar.text_input("🔑 Clé API Groq Llama 3", value=groq_default_key, type="password")
st.sidebar.caption(status_api_devises)
taux_cny_xof = st.sidebar.number_input("1 CNY (Chine)", value=rates["CNY"], step=0.1)
taux_usd_xof = st.sidebar.number_input("1 USD (Dollar)", value=rates["USD"], step=1.0)
taux_eur_xof = st.sidebar.number_input("1 EUR (Euro)", value=rates["EUR"], step=0.1)
taux_aed_xof = st.sidebar.number_input("1 AED (Dirham)", value=rates["AED"], step=0.1)
if st.sidebar.button("🚪 Déconnexion", use_container_width=True):
    st.session_state.clear()
    st.rerun()

st.markdown("""
<div class="header-banner"><h1>🏛️ CÔTE D'IVOIRE : SYSTÈME NATIONAL DE DÉDOUANEMENT (SNDGIR v5.0)</h1>
<p>Manifeste, sélectivité, caisse, EDI et gestion des risques</p></div>
""", unsafe_allow_html=True)

tabs = st.tabs(["📈 Dashboard National", "🚢 1. Manifeste & Fret", "📋 2. Déclaration & Sélectivité", "💳 3. Caisse & BAE", "🔄 4. Passerelle EDI", "📄 5. IDP OCR", "📖 6. Code des Douanes", "🤖 7. Assistant IA", "🔐 Admin & Audit"])

with tabs[0]:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📈 Indicateurs Nationaux")
    with db_connection() as conn:
        df = pd.read_sql_query("SELECT * FROM dossiers", conn)
    if df.empty:
        st.info("Aucune déclaration enregistrée.")
    else:
        k1, k2, k3, k4 = st.columns(4)
        k1.markdown(f'<div class="kpi-card"><div class="kpi-title">Recettes</div><div class="kpi-value">{df.total_facture.sum():,.0f} FCFA</div></div>', unsafe_allow_html=True)
        k2.markdown(f'<div class="kpi-card"><div class="kpi-title">Déclarations</div><div class="kpi-value">{len(df)}</div></div>', unsafe_allow_html=True)
        k3.markdown(f'<div class="kpi-card"><div class="kpi-title">Circuits verts</div><div class="kpi-value">{(df.canal_selectivite == "VERT").sum()}</div></div>', unsafe_allow_html=True)
        k4.markdown(f'<div class="kpi-card"><div class="kpi-title">Circuits rouges</div><div class="kpi-value">{(df.canal_selectivite == "ROUGE").sum()}</div></div>', unsafe_allow_html=True)
        a, b = st.columns(2)
        with a:
            fig = px.pie(df, names="canal_selectivite", title="Répartition par canal", hole=.4)
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="white")
            st.plotly_chart(fig, use_container_width=True)
        with b:
            fig = px.bar(df, x="regime", y="total_facture", color="canal_selectivite", title="Recettes par régime")
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="white")
            st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with tabs[1]:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("🚢 Gestion des Manifestes et du Fret")
    a, b = st.columns(2)
    with a:
        with st.form("form_manifeste"):
            m_num = st.text_input("N° Manifeste")
            m_transport = st.selectbox("Moyen de transport", ["Maritime (Navire)", "Aérien (Avion)", "Routier (Camion)"])
            m_voyage = st.text_input("N° Voyage / Vol", "MSC-VITA-2026")
            m_prov = st.text_input("Port de provenance", "Guangzhou, Chine")
            m_date = st.date_input("Date d'arrivée prévue", datetime.now())
            submit_m = st.form_submit_button("Enregistrer le manifeste")
        if submit_m and m_num:
            try:
                with db_connection() as conn:
                    conn.execute("INSERT INTO manifestes(num_manifeste,moyen_transport,num_voyage,provenance,date_arrivee) VALUES(?,?,?,?,?)", (m_num,m_transport,m_voyage,m_prov,m_date.isoformat()))
                log_action(st.session_state.username, "Ajout Manifeste", m_num); st.success("Manifeste créé.")
            except sqlite3.IntegrityError: st.error("Ce numéro de manifeste existe déjà.")
    with b:
        with db_connection() as conn:
            manifests = pd.read_sql_query("SELECT num_manifeste FROM manifestes", conn)
        if not manifests.empty:
            with st.form("form_fret"):
                f_man = st.selectbox("Manifeste associé", manifests.num_manifeste.tolist())
                f_bl = st.text_input("N° Connaissement / B/L", "MEDU98765432")
                f_client = st.text_input("Destinataire", "ETS KOUASSI & FRERES")
                f_poids = st.number_input("Poids brut (kg)", min_value=0.0, value=1500.0)
                f_colis = st.number_input("Nombre de colis", min_value=1, value=45)
                submit_f = st.form_submit_button("Ajouter la ligne de fret")
            if submit_f and f_bl:
                try:
                    with db_connection() as conn:
                        conn.execute("INSERT INTO fret_lines(num_manifeste,bl_number,consignee,poids_brut,nb_colis) VALUES(?,?,?,?,?)", (f_man,f_bl,f_client,f_poids,f_colis))
                    st.success("Ligne de fret ajoutée.")
                except sqlite3.IntegrityError: st.error("Ce B/L existe déjà.")
    with db_connection() as conn:
        st.dataframe(pd.read_sql_query("SELECT * FROM fret_lines", conn), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with tabs[2]:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📋 Déclaration en détail et sélectivité")
    with db_connection() as conn:
        articles = pd.read_sql_query("SELECT * FROM articles", conn)
        bls = pd.read_sql_query("SELECT bl_number FROM fret_lines WHERE statut_apurement='Non apuré'", conn)
    c1, c2, c3 = st.columns(3)
    client = c1.text_input("Importateur / Client", "ETS KOUASSI & FRERES")
    bl = c2.selectbox("B/L", bls.bl_number.tolist() if not bls.empty else ["MEDU98765432"])
    container = c3.text_input("N° Conteneur", "MSCU1234567")
    article = st.selectbox("Produit", articles.nom.tolist())
    item = articles[articles.nom == article].iloc[0]
    regime = st.selectbox("Régime douanier", ["C100 - Mise à la consommation directe", "E100 - Entrepôt de douane (Suspensif)", "AT - Admission Temporaire", "TR - Transit / Réexportation"])
    currency = st.selectbox("Devise", ["USD", "CNY", "EUR", "AED"])
    x, y = st.columns(2)
    qty = x.number_input("Quantité", min_value=1, value=100)
    unit = y.number_input("Prix unitaire", min_value=.01, value=250.0)
    conversion = {"USD": taux_usd_xof, "CNY": taux_cny_xof, "EUR": taux_eur_xof, "AED": taux_aed_xof}
    fob_xof = qty * unit * conversion[currency]
    total = calculer_droits_douane(fob_xof * 1.08, float(item.dd), regime)
    diff = st.slider("Divergence OCR simulée (%)", 0.0, 30.0, 2.0)
    score, canal, motifs = calculer_selectivite_risque(fob_xof, {"cat": item.categorie}, diff)
    st.info(f"Score : {score}/100 — Canal : {canal} — {motifs}")
    can_submit = st.session_state.user_role in ROLES_DECLARATION
    if not can_submit: st.warning("Votre rôle ne permet pas de soumettre une déclaration.")
    if st.button("🚀 Soumettre la SAD", disabled=not can_submit, use_container_width=True):
        with db_connection() as conn:
            conn.execute("INSERT INTO dossiers(date,client,article,regime,fob_xof,total_facture,solde_du,statut,bl_number,container_number,date_arrivee,score_risque,canal_selectivite,motifs_risque) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (datetime.now().strftime("%Y-%m-%d %H:%M"),client,article,regime,fob_xof,total,total,"En cours de contrôle" if canal in {"JAUNE","ROUGE"} else "Liquidé - En attente de paiement",bl,container,datetime.now().strftime("%Y-%m-%d"),score,canal,motifs))
            conn.execute("UPDATE fret_lines SET statut_apurement='Apuré par SAD' WHERE bl_number=?", (bl,))
        log_action(st.session_state.username, "Soumission SAD", f"{client} - {canal}"); st.success("Déclaration enregistrée.")
    st.markdown('</div>', unsafe_allow_html=True)

with tabs[3]:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("💳 Caisse et Bon à Enlever")
    with db_connection() as conn:
        dossiers = pd.read_sql_query("SELECT * FROM dossiers ORDER BY id DESC", conn)
    if dossiers.empty: st.info("Aucune déclaration enregistrée.")
    else:
        st.dataframe(dossiers[["id","client","article","canal_selectivite","total_facture","solde_du","statut"]], use_container_width=True)
        selected = st.selectbox("Dossier à encaisser", dossiers.id.tolist())
        row = dossiers[dossiers.id == selected].iloc[0]
        st.write(f"Client : **{row.client}** — Solde : **{row.solde_du:,.0f} FCFA**")
        payment = st.selectbox("Mode de règlement", ["TrésorPay / RTGS", "Chèque certifié", "Virement SWIFT", "Mobile Money"])
        allowed = st.session_state.user_role in ROLES_CAISSE
        if not allowed: st.warning("Votre rôle ne permet pas d'encaisser.")
        if st.button("💳 Valider le paiement et émettre le BAE", disabled=not allowed, use_container_width=True):
            if float(row.solde_du or 0) <= 0 or row.statut == "Liquidé & Payé (BAE Émis)":
                st.warning("Ce dossier a déjà été payé.")
            else:
                quittance = f"QUIT-{datetime.now():%Y}-{int(selected):05d}"
                with db_connection() as conn:
                    cur = conn.execute("UPDATE dossiers SET solde_du=0, statut='Liquidé & Payé (BAE Émis)', quittance_num=? WHERE id=? AND solde_du>0", (quittance, int(selected)))
                    if cur.rowcount != 1: st.error("Paiement refusé : dossier déjà réglé ou introuvable.")
                if cur.rowcount == 1:
                    pdf = generer_bae_pdf(selected,row.client,row.article,row.bl_number,row.container_number,quittance,row.total_facture)
                    log_action(st.session_state.username, "Paiement Caisse", f"{quittance} via {payment}")
                    st.success(f"Paiement enregistré : {quittance}")
                    with open(pdf, "rb") as handle: st.download_button("📥 Télécharger le BAE PDF", handle.read(), os.path.basename(pdf), "application/pdf", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with tabs[4]:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("🔄 Passerelle EDI")
    with db_connection() as conn: edi = pd.read_sql_query("SELECT * FROM dossiers ORDER BY id DESC LIMIT 5", conn)
    if not edi.empty:
        eid = st.selectbox("Déclaration à exporter", edi.id.tolist())
        row = edi[edi.id == eid].iloc[0]
        message = generer_message_edifact_cusdec(f"SAD-{datetime.now():%Y}-{eid}", row.client, row.fob_xof, row.regime)
        st.code(message, language="text")
        st.download_button("📥 Télécharger le fichier EDI", message, f"CUSDEC_D{eid}.edi", "text/plain", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with tabs[5]:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📄 IDP OCR et cross-check")
    uploaded = st.file_uploader("Joindre une facture", type=["pdf", "png", "jpg", "txt"])
    if uploaded:
        # L'ancien écran affichait des montants fictifs. On signale clairement que l'OCR réel doit être branché.
        st.success(f"Fichier reçu : {uploaded.name} ({uploaded.size:,} octets)")
        st.info("Extraction OCR non activée dans cette version : aucun montant n'est inventé et aucune alerte automatique n'est créée.")
    st.markdown('</div>', unsafe_allow_html=True)

with tabs[6]:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📖 Référentiel douanier")
    for title, text in {
        "Article 12 - Valeur transactionnelle (OMC / CAF)": "La valeur en douane est la valeur transactionnelle ajustée du transport et de l'assurance.",
        "Article 85 - Régime C100": "Mise en libre circulation après paiement des droits et taxes.",
        "Article 142 - Entrepôt E100": "Stockage sous douane en suspension des droits et taxes.",
        "Programme VOC / CoC": "Les formalités de vérification dépendent de la valeur et de la réglementation applicable.",
    }.items():
        with st.expander(title): st.write(text)
    st.markdown('</div>', unsafe_allow_html=True)

with tabs[7]:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("🤖 Assistant IA Douanes")
    question = st.text_area("Posez votre question réglementaire")
    if st.button("🔍 Consulter l'Expert IA"):
        if not question.strip(): st.warning("Saisissez une question.")
        elif not groq_api_key or Groq is None: st.warning("Renseignez la clé API Groq.")
        else:
            try:
                result = Groq(api_key=groq_api_key).chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":f"Vous êtes un expert des douanes de Côte d'Ivoire. Répondez avec prudence : {question}"}], temperature=.2, max_tokens=1024)
                st.info(result.choices[0].message.content)
            except Exception as exc: st.error(f"Erreur Groq : {exc}")
    st.markdown('</div>', unsafe_allow_html=True)

if st.session_state.user_role in ROLES_ADMIN:
    with tabs[8]:
        st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
        st.subheader("🔐 Administration et audit")
        a, b = st.columns(2)
        with a:
            with st.form("form_agent"):
                name = st.text_input("Identifiant agent")
                pwd = st.text_input("Mot de passe", type="password")
                role = st.selectbox("Rôle", ["Vérificateur Douanier", "Agent de Caisse", "Commissionnaire Agréé"])
                create = st.form_submit_button("Créer le compte")
            if create and name and pwd:
                try:
                    with db_connection() as conn: conn.execute("INSERT INTO users(username,password_hash,role,statut) VALUES(?,?,?,'Actif')", (name,hash_password(pwd),role))
                    log_action(st.session_state.username, "Création Agent", name); st.success("Compte créé.")
                except sqlite3.IntegrityError: st.error("Cet identifiant existe déjà.")
        with db_connection() as conn:
            b.dataframe(pd.read_sql_query("SELECT id,username,role,statut FROM users", conn), use_container_width=True)
            st.dataframe(pd.read_sql_query("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 100", conn), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
