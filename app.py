import html
import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

import pandas as pd
import streamlit as st

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

st.set_page_config(page_title="SYDAM Pro Transit CI", page_icon="🇨🇮", layout="wide")
st.markdown("""
<style>
.stApp { background-color:#0F172A; color:#F8FAFC; }
.header-banner { background:linear-gradient(135deg,#047857,#10B981,#0284C7); padding:25px; border-radius:18px; color:white; margin-bottom:25px; }
.custom-card { background:#1E293B; border-radius:16px; padding:22px; border:1px solid #334155; margin-bottom:20px; }
.profit-box { background:linear-gradient(135deg,#15803D,#166534); color:white; padding:20px; border-radius:14px; text-align:center; margin-top:15px; }
.ai-box { background:linear-gradient(135deg,#312E81,#1E1B4B); border:1px solid #6366F1; padding:20px; border-radius:14px; margin-top:15px; }
</style>
""", unsafe_allow_html=True)

DATABASE_ARTICLES = {
    "Perruques & Mèches en Cheveux Humains": {"sh":"6704.20.00", "dd":20.0},
    "Smartphones, iPhones & Téléphones": {"sh":"8517.13.00", "dd":20.0},
    "Ordinateurs Portables & MacBooks": {"sh":"8471.30.00", "dd":5.0},
    "Vêtements & Prêt-à-porter": {"sh":"6204.62.00", "dd":20.0},
}
AVATARS = {
    "Expert Douane & Cotation":"https://images.unsplash.com/photo-1560250097-0b93528c311a?auto=format&fit=crop&w=800&q=80",
    "Conseiller Logistics & Fret":"https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&w=800&q=80",
    "Inspecteur SYDAM World":"https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?auto=format&fit=crop&w=800&q=80",
}

def setting(name, default=None):
    """Read Streamlit Cloud secrets first, then environment variables."""
    try:
        value = st.secrets.get(name)
    except Exception:
        value = None
    return value if value not in (None, "") else os.getenv(name.upper(), default)

def valid_email(value):
    return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value or ""))

def send_email(recipient, subject, body):
    host = setting("smtp_host")
    port = int(setting("smtp_port", 587))
    username = setting("smtp_username")
    password = setting("smtp_password")
    sender = setting("from_email", username)
    use_tls = str(setting("smtp_use_tls", "true")).lower() not in {"false", "0", "no"}
    missing = [key for key, value in {"smtp_host":host, "smtp_username":username, "smtp_password":password, "from_email":sender}.items() if not value]
    if missing:
        raise RuntimeError("Configuration SMTP manquante : " + ", ".join(missing) + ". Ajoutez ces valeurs dans les Secrets Streamlit.")
    message = MIMEMultipart("alternative")
    message["From"] = formataddr(("SYDAM Pro Transit CI", sender))
    message["To"] = recipient
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain", "utf-8"))
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.ehlo()
        if use_tls:
            smtp.starttls()
            smtp.ehlo()
        smtp.login(username, password)
        smtp.sendmail(sender, [recipient], message.as_string())

st.sidebar.title("🇨🇮 TRANSIT AUTOMATION")
openai_api_key = st.sidebar.text_input("Clé API OpenAI (ChatGPT)", type="password")
taux_cny_xof = st.sidebar.number_input("Taux 1 CNY -> FCFA", value=82.0)
taux_usd_xof = st.sidebar.number_input("Taux 1 USD -> FCFA", value=610.0)
selected_avatar = st.sidebar.selectbox("Choisissez l'Expert Visuel 3D", list(AVATARS))
st.sidebar.image(AVATARS[selected_avatar], caption=selected_avatar, use_container_width=True)

st.markdown('<div class="header-banner"><h1>📦 SYDAM PRO : COTATION & AUTOMATISATION CLIENT</h1><p>Calculateur Douanier UEMOA Côte d’Ivoire & Assistant de Réponse</p></div>', unsafe_allow_html=True)
with st.container():
    st.subheader("👤 1. Coordonnées du Client & Canal d’Envoi")
    c1, c2, c3 = st.columns(3)
    with c1: nom_client = st.text_input("Nom / Entreprise du Client", value="ETS KOUASSI & FRERES")
    with c2: email_client = st.text_input("Email du Client", value="client@example.com")
    with c3: tel_client = st.text_input("Téléphone / WhatsApp", value="+2250700000000")

st.subheader("📋 2. Informations Marchandise & Facture")
c1, c2 = st.columns([2, 1])
with c1:
    article_nom = st.selectbox("Article à dédouaner", list(DATABASE_ARTICLES))
    item = DATABASE_ARTICLES[article_nom]
    devise = st.selectbox("Devise Facture", ["CNY (Yuan)", "USD (Dollar)"])
    v1, v2 = st.columns(2)
    with v1: fob_devise = st.number_input("Montant Marchandise (FOB)", min_value=0.0, value=15000.0)
    with v2: fret_devise = st.number_input("Frais de Fret", min_value=0.0, value=2500.0)
with c2:
    st.info(f"Code SH : {item['sh']}\n\nDroits de douane : {item['dd']}%")

st.subheader("💼 3. Honoraires & Bénéfices du Transitaire")
h1, h2, h3 = st.columns(3)
with h1:
    frais_port = st.number_input("Acconage & Passage Portuaire (FCFA)", value=150000)
    frais_guce = st.number_input("Frais GUCE & Formalités (FCFA)", value=35000)
with h2:
    honoraires = st.number_input("Vos Honoraires Facturés (FCFA)", value=250000)
    charges_ops = st.number_input("Vos Charges Réelles (FCFA)", value=50000)
with h3: acompte = st.number_input("Acompte Réceptionné du Client (FCFA)", value=1000000)
st.markdown(f'<div class="profit-box">💰 BÉNÉFICE NET : <b>{honoraires - charges_ops:,.0f} FCFA</b></div>', unsafe_allow_html=True)

taux_conv = taux_cny_xof if "CNY" in devise else taux_usd_xof
caf_devise = (fob_devise + fret_devise) * 1.005
caf_xof = caf_devise * taux_conv
total_droits = caf_xof * (item["dd"] / 100 + .010 + .008 + .005 + .010)
tva_xof = (caf_xof + total_droits) * .18
total_douane = total_droits + tva_xof
total_transit = frais_port + frais_guce + honoraires
total_facture = fob_devise * taux_conv + fret_devise * taux_conv + total_douane + total_transit
solde_du = total_facture - acompte
df = pd.DataFrame([{"Désignation":article_nom, "Code SH":item["sh"], "Valeur CAF (FCFA)":round(caf_xof), "Droits & Taxes (FCFA)":round(total_douane), "Total Facturé (FCFA)":round(total_facture), "Solde (FCFA)":round(solde_du)}])
st.subheader("📑 Résumé Financier")
st.dataframe(df, use_container_width=True)

st.subheader("🤖 4. Génération de la Réponse & Envoi")
prompt = f"Rédigez un message professionnel en français pour {nom_client}. Article: {article_nom}. Total: {total_facture:,.0f} FCFA. Acompte: {acompte:,.0f} FCFA. Solde: {solde_du:,.0f} FCFA. Invitez le client à valider les formalités GUCE/Douane."
if openai_api_key and OpenAI:
    try:
        response = OpenAI(api_key=openai_api_key).chat.completions.create(model="gpt-4o-mini", messages=[{"role":"user", "content":prompt}])
        message_genere = response.choices[0].message.content
    except Exception as exc:
        st.warning(f"OpenAI indisponible, message standard utilisé : {exc}")
        message_genere = None
else: message_genere = None
if not message_genere:
    message_genere = f"""Bonjour {nom_client},\n\nNous avons finalisé la cotation de votre marchandise ({article_nom}).\n\nMontant total : {total_facture:,.0f} FCFA\nAcompte reçu : {acompte:,.0f} FCFA\nSolde restant : {solde_du:,.0f} FCFA\n\nMerci de valider afin de lancer les formalités GUCE / Douane.\n\nCordialement,\nLe Département Transit & Dédouanement."""
st.text_area("Message à envoyer", value=message_genere, height=220)

if st.button("📧 Envoyer par Email au Client", type="primary", use_container_width=True):
    if not valid_email(email_client):
        st.error("Veuillez saisir une adresse email valide.")
    else:
        try:
            send_email(email_client, f"Votre cotation transit - {article_nom}", message_genere)
            st.success(f"Email envoyé avec succès à {email_client}.")
        except (smtplib.SMTPException, OSError, RuntimeError, ValueError) as exc:
            st.error(f"L'envoi a échoué : {exc}")
            st.info("Vérifiez les Secrets Streamlit et le dossier spam du destinataire.")

with st.expander("Configuration email requise"):
    st.code('''smtp_host = "smtp.gmail.com"
smtp_port = 587
smtp_username = "votre-adresse@gmail.com"
smtp_password = "mot-de-passe-application"
from_email = "votre-adresse@gmail.com"
smtp_use_tls = true''', language="toml")
    st.caption("Pour Gmail, utilisez un mot de passe d’application (2FA activée), jamais votre mot de passe habituel.")
