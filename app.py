import os
from urllib.parse import urlencode

import pandas as pd
import streamlit as st

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# =========================================================
# CONFIGURATION ET STYLES CSS ULTRA-PROFESSIONNELS EN 3D
# =========================================================
st.set_page_config(page_title="SYDAM Pro Transit CI", page_icon="🇨🇮", layout="wide")

st.markdown("""
<style>
.stApp { 
    background-color: #0B0F19; 
    color: #F8FAFC; 
    font-family: 'Inter', sans-serif;
}

/* En-tête avec effet de relief 3D */
.header-banner { 
    background: linear-gradient(135deg, #047857 0%, #10B981 50%, #0284C7 100%); 
    padding: 30px; 
    border-radius: 20px; 
    color: white; 
    margin-bottom: 25px; 
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
    border: 1px solid rgba(255, 255, 255, 0.1);
}

/* Cartes en relief 3D Glassmorphism */
.custom-card-3d { 
    background: #1E293B; 
    border-radius: 18px; 
    padding: 25px; 
    border: 1px solid #334155; 
    margin-bottom: 25px; 
    box-shadow: 8px 8px 16px #070a11, -8px -8px 16px #151a27;
}

/* Boîte de bénéfices en 3D */
.profit-box-3d { 
    background: linear-gradient(135deg, #15803D, #166534); 
    color: white; 
    padding: 20px; 
    border-radius: 16px; 
    text-align: center; 
    margin-top: 15px; 
    box-shadow: inset 2px 2px 5px rgba(255,255,255,0.2), 0 10px 15px -3px rgba(21, 128, 61, 0.4);
    font-size: 1.2rem;
}

/* Boîte Assistant IA 3D */
.ai-box-3d { 
    background: linear-gradient(135deg, #1E1B4B 0%, #312E81 100%); 
    border: 1px solid #6366F1; 
    padding: 22px; 
    border-radius: 16px; 
    margin-top: 15px; 
    box-shadow: 0 10px 20px rgba(99, 102, 241, 0.25);
}

/* Style de l'expert */
.expert-profile-card {
    background: #1E293B;
    border-radius: 16px;
    padding: 15px;
    text-align: center;
    border: 1px solid #334155;
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.4);
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# BASE DE DONNÉES ARTICLES (CHINE & INTERNATIONAL)
# =========================================================
DATABASE_ARTICLES = {
    # --- VÉLOS & TRANSPORT DUOTOUX ---
    "Vélos & Bicyclettes (Non motorisés)": {"sh": "8712.00.00", "dd": 20.0},
    "Vélos Électriques & VAE": {"sh": "8711.60.00", "dd": 20.0},
    "Tricycles / Pousse-pousse / Moto-keke": {"sh": "8711.20.00", "dd": 20.0},
    "Trottinettes Électriques": {"sh": "8711.60.10", "dd": 20.0},
    "Pièces détachées de vélos": {"sh": "8714.91.00", "dd": 10.0},

    # --- ÉLECTRONIQUE & HIGH-TECH ---
    "Smartphones, iPhones & Téléphones": {"sh": "8517.13.00", "dd": 20.0},
    "Ordinateurs Portables, MacBooks & Tablettes": {"sh": "8471.30.00", "dd": 5.0},
    "Téléviseurs Smart TV & Écrans LED": {"sh": "8528.72.00", "dd": 20.0},
    "Refrigérateurs & Congélateurs": {"sh": "8418.10.00", "dd": 20.0},
    "Climatiseurs & Split systems": {"sh": "8415.10.00", "dd": 20.0},

    # --- ÉNERGIE SOLAIRE ---
    "Panneaux Photovoltaïques / Solaires": {"sh": "8541.43.00", "dd": 5.0},
    "Batteries Lithium & GEL": {"sh": "8507.60.00", "dd": 10.0},
    "Onduleurs & Convertisseurs Solaires": {"sh": "8504.40.00", "dd": 5.0},

    # --- MODE & BEAUTÉ ---
    "Perruques & Mèches en Cheveux Humains": {"sh": "6704.20.00", "dd": 20.0},
    "Vêtements & Prêt-à-porter": {"sh": "6204.62.00", "dd": 20.0},
    "Chaussures & Baskets de Sport": {"sh": "6403.99.00", "dd": 20.0},
}

# =========================================================
# BARRE LATÉRALE - INCARNATION PAR L'EXPERT DE LA PHOTO
# =========================================================
st.sidebar.title("🇨🇮 TRANSIT AUTOMATION")

# Affichage direct de votre photo de profil transmise
EXPERT_PHOTO_PATH = "PHOTO-2026-06-07-20-02-59.jpg"

if os.path.exists(EXPERT_PHOTO_PATH):
    st.sidebar.image(EXPERT_PHOTO_PATH, caption="Kouassi Kouame Daniel - Expert Transitaire Agréé", use_container_width=True)
else:
    st.sidebar.info("📷 Image de l'expert chargée")

st.sidebar.markdown("---")
openai_api_key = st.sidebar.text_input("Clé API OpenAI (ChatGPT)", type="password")
taux_cny_xof = st.sidebar.number_input("Taux 1 CNY -> FCFA", value=82.0)
taux_usd_xof = st.sidebar.number_input("Taux 1 USD -> FCFA", value=610.0)

# =========================================================
# ENTÊTE PRINCIPALE
# =========================================================
st.markdown("""
<div class="header-banner">
    <h1>📦 SYDAM PRO : COTATION AUTOMATISÉE ET INTELLIGENTE</h1>
    <p>Cabinet d'Expertise en Transit & Dédouanement UEMOA - Côte d'Ivoire</p>
</div>
""", unsafe_allow_html=True)

# =========================================================
# 1. COORDONNÉES DU CLIENT
# =========================================================
st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
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
st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# 2. DÉTAILS DE LA MARCHANDISE (PRIX UNITAIRE, QUANTITÉ, FOB)
# =========================================================
st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
st.subheader("📋 2. Informations Marchandise (Prix Unitaire & Quantité)")
c1, c2 = st.columns([2, 1])

with c1:
    article_nom = st.selectbox("Article à dédouaner (Import Chine & Monde)", list(DATABASE_ARTICLES))
    item = DATABASE_ARTICLES[article_nom]
    devise = st.selectbox("Devise Facture", ["CNY (Yuan)", "USD (Dollar)"])
    
    col_u1, col_u2, col_u3 = st.columns(3)
    with col_u1:
        quantite = st.number_input("Quantité d'articles", min_value=1, value=50)
    with col_u2:
        prix_unitaire_devise = st.number_input(f"Prix Unitaire ({devise.split()[0]})", min_value=0.0, value=300.0)
    with col_u3:
        fret_devise = st.number_input(f"Frais de Fret Total ({devise.split()[0]})", min_value=0.0, value=2500.0)

    fob_devise = quantite * prix_unitaire_devise
    st.markdown(f"**Montant Total Marchandise (FOB) :** `{fob_devise:,.2f} {devise.split()[0]}`")

with c2:
    st.info(f"**Code SH SYDAM :** {item['sh']}\n\n**Droits de Douane (DD) :** {item['dd']}%")
st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# 3. HONORAIRES ET BÉNÉFICES DU TRANSITAIRE
# =========================================================
st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
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

benefice_net = honoraires - charges_ops
st.markdown(f'<div class="profit-box-3d">💰 BÉNÉFICE NET DU TRANSITAIRE SUR CE DOSSIER : <b>{benefice_net:,.0f} FCFA</b></div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# CALCULS DOUANIERS SYDAM (CÔTE D'IVOIRE / UEMOA)
# =========================================================
taux_conv = taux_cny_xof if "CNY" in devise else taux_usd_xof
prix_unitaire_xof = prix_unitaire_devise * taux_conv
fob_xof = fob_devise * taux_conv
fret_xof = fret_devise * taux_conv

caf_devise = (fob_devise + fret_devise) * 1.005
caf_xof = caf_devise * taux_conv

# Droits et Taxes Douane CI (DD + RSE + PCS + PC + PFI)
total_droits = caf_xof * (item["dd"] / 100 + .010 + .008 + .005 + .010)
tva_xof = (caf_xof + total_droits) * .18
total_douane = total_droits + tva_xof

total_transit = frais_port + frais_guce + honoraires
total_facture = fob_xof + fret_xof + total_douane + total_transit
solde_du = total_facture - acompte

# =========================================================
# RÉSUMÉ FINANCIER STRUCTURÉ POUR LE CLIENT
# =========================================================
st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
st.subheader("📑 Résumé Financier Détaillé pour le Client")

df_client = pd.DataFrame([{
    "Désignation": article_nom,
    "Code SH": item["sh"],
    "Quantité": quantite,
    "Prix Unitaire (FCFA)": round(prix_unitaire_xof),
    "Montant Marchandise (FCFA)": round(fob_xof),
    "Frais Fret (FCFA)": round(fret_xof),
    "Droits & Taxes Douane (FCFA)": round(total_douane),
    "Total Général Facturé (FCFA)": round(total_facture),
    "Solde Restant Dû (FCFA)": round(solde_du),
}])

st.dataframe(df_client, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# 4. ASSISTANT IA & GÉNÉRATION AUTOMATIQUE DU MESSAGE CLIENT
# =========================================================
st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
st.subheader("🤖 4. Assistant IA & Génération Automatique de la Réponse")

prompt = f"""
Vous êtes Kouassi Kouame Daniel, un expert transitaire senior basé en Côte d'Ivoire.
Rédigez un message très professionnel et clair pour le client {nom_client}.

Détails de la cotation :
- Article : {article_nom} (Code SH: {item['sh']})
- Quantité : {quantite} unités
- Prix unitaire : {prix_unitaire_xof:,.0f} FCFA
- Total Marchandise FOB : {fob_xof:,.0f} FCFA
- Frais de Fret : {fret_xof:,.0f} FCFA
- Droits & Taxes Douane (SYDAM World) : {total_douane:,.0f} FCFA
- Prestations Transit & Formalités : {total_transit:,.0f} FCFA
- Total Global : {total_facture:,.0f} FCFA
- Acompte Reçu : {acompte:,.0f} FCFA
- Solde Restant à Régler : {solde_du:,.0f} FCFA

Instructions :
1. Présentez la cotation de manière détaillée (Prix unitaire, quantité, droits de douane et frais de transit).
2. Invitez le client à valider l'accord pour le traitement sur le Guichet Unique (GUCE).
3. Conservez une signature professionnelle et courtoise.
"""

if openai_api_key and OpenAI:
    try:
        response = OpenAI(api_key=openai_api_key).chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        message_genere = response.choices[0].message.content
    except Exception as exc:
        st.warning(f"Note OpenAI : {exc}")
        message_genere = None
else:
    message_genere = None

if not message_genere:
    message_genere = f"""Bonjour {nom_client},

Voici le détail récapitulatif de votre cotation pour l'importation de votre marchandise :

- Article : {article_nom} (Code SH: {item['sh']})
- Quantité : {quantite} unités
- Prix Unitaire : {prix_unitaire_xof:,.0f} FCFA
- Valeur Marchandise (FOB) : {fob_xof:,.0f} FCFA
- Frais de Fret : {fret_xof:,.0f} FCFA
- Droits & Taxes Douanières (SYDAM) : {total_douane:,.0f} FCFA
- Prestations Transit & Passage Portuaire : {total_transit:,.0f} FCFA

---------------------------------------------------
MONTANT TOTAL DU DOSSIER : {total_facture:,.0f} FCFA
Acompte reçu : {acompte:,.0f} FCFA
SOLDE RESTANT À RÉGLER : {solde_du:,.0f} FCFA
---------------------------------------------------

Merci de nous donner votre accord afin de lancer les formalités sur le GUCE / Douane.

Cordialement,
Kouassi Kouame Daniel
Département Transit & Dédouanement."""

message_genere = st.text_area("Message structuré rédigé pour le client :", value=message_genere, height=260)

# Lien dynamique vers Gmail
gmail_params = urlencode({
    "view": "cm",
    "fs": "1",
    "to": email_client.strip(),
    "su": f"Cotation Transit & Dédouanement - {article_nom} ({quantite} unités)",
    "body": message_genere,
    **({"authuser": sender_email.strip()} if sender_email.strip() else {}),
})
gmail_link = f"https://mail.google.com/mail/?{gmail_params}"

st.link_button("📧 Envoyer directement le message par Gmail", gmail_link, use_container_width=True)
st.caption("Le message s'ouvrira directement prérempli dans votre interface Gmail. Vous n'aurez plus qu'à cliquer sur Envoyer.")
st.markdown('</div>', unsafe_allow_html=True)
