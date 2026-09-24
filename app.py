import os
from urllib.parse import urlencode

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

# =========================================================
# BASE DE DONNÉES ÉTENDUE : PRODUITS DE CHINE & VÉLOS (UEMOA / CI)
# =========================================================
DATABASE_ARTICLES = {
    # --- VÉLOS & TRANSPORT DUOTOUX ---
    "Vélos & Bicyclettes (Non motorisés)": {"sh": "8712.00.00", "dd": 20.0},
    "Vélos Électriques & VAE": {"sh": "8711.60.00", "dd": 20.0},
    "Tricycles / Pousse-pousse / Moto-keke": {"sh": "8711.20.00", "dd": 20.0},
    "Trottinettes Électriques": {"sh": "8711.60.10", "dd": 20.0},
    "Pièces détachées de vélos (Pneus, Chambres, Freins)": {"sh": "8714.91.00", "dd": 10.0},

    # --- ÉLECTRONIQUE, ÉLECTROMÉNAGER & HIGH-TECH ---
    "Smartphones, iPhones & Téléphones portable": {"sh": "8517.13.00", "dd": 20.0},
    "Ordinateurs Portables, MacBooks & Tablettes": {"sh": "8471.30.00", "dd": 5.0},
    "Téléviseurs Smart TV & Écrans LED": {"sh": "8528.72.00", "dd": 20.0},
    "Refrigérateurs & Congélateurs": {"sh": "8418.10.00", "dd": 20.0},
    "Climatiseurs & Split systems": {"sh": "8415.10.00", "dd": 20.0},
    "Machines à laver le linge": {"sh": "8450.11.00", "dd": 20.0},
    "Écouteurs, Casques & Enceintes Bluetooth": {"sh": "8518.30.00", "dd": 20.0},
    "Montres Connectées / Smartwatches": {"sh": "8517.62.00", "dd": 20.0},

    # --- ÉNERGIE SOLAIRE & ÉLECTRICITÉ (Produits très importés de Chine) ---
    "Panneaux Photovoltaïques / Solaires": {"sh": "8541.43.00", "dd": 5.0},
    "Onduleurs & Convertisseurs Solaires": {"sh": "8504.40.00", "dd": 5.0},
    "Batteries Lithium & GEL pour Solaire": {"sh": "8507.60.00", "dd": 10.0},
    "Projecteurs & Lampes Solaires LED": {"sh": "9405.42.00", "dd": 20.0},

    # --- MODE, TEXTILE & BEAUTÉ ---
    "Perruques & Mèches en Cheveux Humains": {"sh": "6704.20.00", "dd": 20.0},
    "Perruques & Mèches Synthétiques": {"sh": "6704.11.00", "dd": 20.0},
    "Vêtements & Prêt-à-porter (Hommes/Femmes)": {"sh": "6204.62.00", "dd": 20.0},
    "Chaussures & Baskets de Sport": {"sh": "6403.99.00", "dd": 20.0},
    "Sacs à main, Sacs à dos & Valises": {"sh": "4202.22.00", "dd": 20.0},
    "Produits Cosmétiques, Maquillage & Soins": {"sh": "3304.99.00", "dd": 20.0},

    # --- QUINCAILLERIE, MACHINES & MATÉRIAUX ---
    "Groupes Électrogènes (Générateurs)": {"sh": "8502.11.00", "dd": 5.0},
    "Machines Industrielles & Outillage de chantier": {"sh": "8479.89.00", "dd": 5.0},
    "Imprimantes & Recharges d'encre": {"sh": "8443.31.00", "dd": 5.0},
    "Pneus pour Automobiles & Camions": {"sh": "4011.10.00", "dd": 10.0},
    "Meubles & Mobilier de bureau / Maison": {"sh": "9403.60.00", "dd": 20.0},
    "Ustensiles de Cuisine & Vaisselle en Inox/Plastique": {"sh": "7323.93.00", "dd": 20.0},
}

AVATARS = {
    "Expert Douane & Cotation": "https://images.unsplash.com/photo-1560250097-0b93528c311a?auto=format&fit=crop&w=800&q=80",
    "Conseiller Logistics & Fret": "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&w=800&q=80",
    "Inspecteur SYDAM World": "https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?auto=format&fit=crop&w=800&q=80",
}

st.sidebar.title("🇨🇮 TRANSIT AUTOMATION")
openai_api_key = st.sidebar.text_input("Clé API OpenAI (ChatGPT)", type="password")
taux_cny_xof = st.sidebar.number_input("Taux 1 CNY -> FCFA", value=82.0)
taux_usd_xof = st.sidebar.number_input("Taux 1 USD -> FCFA", value=610.0)
selected_avatar = st.sidebar.selectbox("Choisissez l'Expert Visuel 3D", list(AVATARS))
st.sidebar.image(AVATARS[selected_avatar], caption=selected_avatar, use_container_width=True)

st.markdown('<div class="header-banner"><h1>📦 SYDAM PRO : COTATION & AUTOMATISATION CLIENT</h1><p>Calculateur Douanier UEMOA Côte d’Ivoire & Assistant de Réponse</p></div>', unsafe_allow_html=True)

st.subheader("👤 1. Coordonnées du Client & Canal d’Envoi")
c1, c2, c3, c4 = st.columns(4)
with c1:
    nom_client = st.text_input("Nom / Entreprise du Client", value="ETS KOUASSI & FRERES")
with c2:
    email_client = st.text_input("Email du destinataire", value="client@example.com")
with c3:
    sender_email = st.text_input("Votre email expéditeur", value="")
with c4:
    tel_client = st.text_input("Téléphone / WhatsApp", value="+2250700000000")

st.subheader("📋 2. Informations Marchandise & Facture")
c1, c2 = st.columns([2, 1])
with c1:
    article_nom = st.selectbox("Article à dédouaner (Import Chine & Monde)", list(DATABASE_ARTICLES))
    item = DATABASE_ARTICLES[article_nom]
    devise = st.selectbox("Devise Facture", ["CNY (Yuan)", "USD (Dollar)"])
    v1, v2 = st.columns(2)
    with v1:
        fob_devise = st.number_input("Montant Marchandise (FOB)", min_value=0.0, value=15000.0)
    with v2:
        fret_devise = st.number_input("Frais de Fret", min_value=0.0, value=2500.0)
with c2:
    st.info(f"Code SH : {item['sh']}\n\nDroits de douane (DD) : {item['dd']}%")

st.subheader("💼 3. Honoraires & Bénéfices du Transitaire")
h1, h2, h3 = st.columns(3)
with h1:
    frais_port = st.number_input("Acconage & Passage Portuaire (FCFA)", value=150000)
    frais_guce = st.number_input("Frais GUCE & Formalités (FCFA)", value=35000)
with h2:
    honoraires = st.number_input("Vos Honoraires Facturés (FCFA)", value=250000)
    charges_ops = st.number_input("Vos Charges Réelles (FCFA)", value=50000)
with h3:
    acompte = st.number_input("Acompte Réceptionné du Client (FCFA)", value=1000000)
st.markdown(f'<div class="profit-box">💰 BÉNÉFICE NET : <b>{honoraires - charges_ops:,.0f} FCFA</b></div>', unsafe_allow_html=True)

taux_conv = taux_cny_xof if "CNY" in devise else taux_usd_xof
caf_devise = (fob_devise + fret_devise) * 1.005
caf_xof = caf_devise * taux_conv
total_droits = caf_xof * (item["dd"] / 100 + .010 + .008 + .005 + .010)
tva_xof = (caf_xof + total_droits) * .18
total_douane = total_droits + tva_xof
total_transit = frais_port + frais_guce + honoraires
total_facture = (fob_devise * taux_conv) + (fret_devise * taux_conv) + total_douane + total_transit
solde_du = total_facture - acompte
df = pd.DataFrame([{
    "Désignation": article_nom,
    "Code SH": item["sh"],
    "Valeur CAF (FCFA)": round(caf_xof),
    "Droits & Taxes (FCFA)": round(total_douane),
    "Total Facturé (FCFA)": round(total_facture),
    "Solde (FCFA)": round(solde_du),
}])
st.subheader("📑 Résumé Financier")
st.dataframe(df, use_container_width=True)

st.subheader("🤖 4. Génération de la Réponse & Envoi")
prompt = f"Rédigez un message professionnel en français pour {nom_client}. Article: {article_nom}. Total: {total_facture:,.0f} FCFA. Acompte: {acompte:,.0f} FCFA. Solde: {solde_du:,.0f} FCFA. Invitez le client à valider les formalités GUCE / Douane."
if openai_api_key and OpenAI:
    try:
        response = OpenAI(api_key=openai_api_key).chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        message_genere = response.choices[0].message.content
    except Exception as exc:
        st.warning(f"OpenAI indisponible, message standard utilisé : {exc}")
        message_genere = None
else:
    message_genere = None

if not message_genere:
    message_genere = f"""Bonjour {nom_client},

Nous avons finalisé la cotation de votre marchandise ({article_nom}).

Montant total : {total_facture:,.0f} FCFA
Acompte reçu : {acompte:,.0f} FCFA
Solde restant : {solde_du:,.0f} FCFA

Merci de valider afin de lancer les formalités GUCE / Douane.

Cordialement,
Le Département Transit & Dédouanement."""

message_genere = st.text_area("Message à envoyer", value=message_genere, height=220)

# Opens Gmail compose with sender account selected when that account is logged in.
# The email is sent by Gmail only after the user reviews and taps Send.
gmail_params = urlencode({
    "view": "cm",
    "fs": "1",
    "to": email_client.strip(),
    "su": f"Votre cotation transit - {article_nom}",
    "body": message_genere,
    **({"authuser": sender_email.strip()} if sender_email.strip() else {}),
})
gmail_link = f"https://mail.google.com/mail/?{gmail_params}"
st.link_button("📧 Ouvrir Gmail pour envoyer", gmail_link, use_container_width=True)
st.caption("Le destinataire et le message sont préremplis. Si votre email expéditeur est connecté à Gmail, il sera sélectionné. Vérifiez puis appuyez sur Envoyer.")
