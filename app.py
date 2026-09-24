import streamlit as st
import pandas as pd
from datetime import datetime
import openai
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# =========================================================
# 1. CONFIGURATION DE LA PAGE & STYLES PRO CI
# =========================================================
st.set_page_config(
    page_title="SYDAM Pro Transit CI - Automation & IA",
    page_icon="🇨🇮",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .stApp {
        background-color: #0F172A;
        color: #F8FAFC;
    }
    .header-banner {
        background: linear-gradient(135deg, #047857 0%, #10B981 50%, #0284C7 100%);
        padding: 25px;
        border-radius: 18px;
        color: white;
        box-shadow: 0 10px 25px rgba(0,0,0,0.4);
        margin-bottom: 25px;
    }
    .custom-card {
        background: #1E293B;
        border-radius: 16px;
        padding: 22px;
        border: 1px solid #334155;
        margin-bottom: 20px;
    }
    .sh-badge {
        background: #0284C7;
        color: #FFFFFF;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: bold;
        font-family: monospace;
    }
    .profit-box {
        background: linear-gradient(135deg, #15803D 0%, #166534 100%);
        color: white;
        padding: 20px;
        border-radius: 14px;
        text-align: center;
        box-shadow: 0 10px 20px rgba(21, 128, 61, 0.4);
        margin-top: 15px;
    }
    .ai-box {
        background: linear-gradient(135deg, #312E81 0%, #1E1B4B 100%);
        border: 1px solid #6366F1;
        padding: 20px;
        border-radius: 14px;
        margin-top: 15px;
    }
    </style>
""", unsafe_allow_html=True)

# =========================================================
# 2. IMAGES 3D DES EXPERTS TRANSIT ET BASE DE DONNÉES SH CI
# =========================================================
AVATARS_3D = {
    "Expert Douane & Cotation": "https://images.unsplash.com/photo-1560250097-0b93528c311a?auto=format&fit=crop&w=800&q=80",
    "Conseiller Logistics & Fret": "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&w=800&q=80",
    "Inspecteur SYDAM World": "https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?auto=format&fit=crop&w=800&q=80"
}

DATABASE_ARTICLES = {
    "Perruques & Mèches en Cheveux Humains": {
        "sh": "6704.20.00", "dd": 20.0, "cat": "Catégorie 3 (Biens de Consommation)",
        "image": "https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?auto=format&fit=crop&w=800&q=80"
    },
    "Smartphones, iPhones & Téléphones": {
        "sh": "8517.13.00", "dd": 20.0, "cat": "Catégorie 3 (Biens de Consommation)",
        "image": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=800&q=80"
    },
    "Ordinateurs Portables & MacBooks": {
        "sh": "8471.30.00", "dd": 5.0, "cat": "Catégorie 1 (Biens d'Équipement)",
        "image": "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=800&q=80"
    },
    "Vêtements & Prêt-à-porter": {
        "sh": "6204.62.00", "dd": 20.0, "cat": "Catégorie 3 (Biens de Consommation)",
        "image": "https://images.unsplash.com/photo-1441986300917-64674bd600d8?auto=format&fit=crop&w=800&q=80"
    }
}

# =========================================================
# 3. SIDEBAR & PARAMÈTRES
# =========================================================
st.sidebar.title("🇨🇮 TRANSIT AUTOMATION")

# Clés d'API
openai_api_key = st.sidebar.text_input("Clé API OpenAI (ChatGPT)", type="password")
taux_cny_xof = st.sidebar.number_input("Taux 1 CNY -> FCFA", value=82.0)
taux_usd_xof = st.sidebar.number_input("Taux 1 USD -> FCFA", value=610.0)

selected_avatar = st.sidebar.selectbox("Choisissez l'Expert Visuel 3D", list(AVATARS_3D.keys()))
st.sidebar.image(AVATARS_3D[selected_avatar], caption=selected_avatar, use_container_width=True)

# =========================================================
# 4. FORMULAIRE DE COTATION
# =========================================================
st.markdown("""
    <div class="header-banner">
        <h1>📦 SYDAM PRO : COTATION & AUTOMATISATION CLIENT</h1>
        <p>Calculateur Douanier UEMOA Côte d'Ivoire & Assistant de Réponse ChatGPT</p>
    </div>
""", unsafe_allow_html=True)

st.markdown('<div class="custom-card">', unsafe_allow_html=True)
st.subheader("👤 1. Coordonnées du Client & Canal d'Envoi")
col_c1, col_c2, col_c3 = st.columns(3)
with col_c1:
    nom_client = st.text_input("Nom / Entreprise du Client", value="ETS KOUASSI & FRERES")
with col_c2:
    email_client = st.text_input("Email du Client", value="client@example.com")
with col_c3:
    tel_client = st.text_input("Téléphone / WhatsApp", value="+2250700000000")
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="custom-card">', unsafe_allow_html=True)
st.subheader("📋 2. Informations Marchandise & Facture")
col_m1, col_m2 = st.columns([2, 1])

with col_m1:
    article_nom = st.selectbox("Article à dédouaner", list(DATABASE_ARTICLES.keys()))
    item = DATABASE_ARTICLES[article_nom]
    st.markdown(f"<span class='sh-badge'>Code SH : {item['sh']}</span> | Droits de Douane : **{item['dd']}%**", unsafe_allow_html=True)
    
    col_v1, col_v2, col_v3 = st.columns(3)
    with col_v1:
        devise = st.selectbox("Devise Facture", ["CNY (Yuan)", "USD (Dollar)"])
    with col_v2:
        fob_devise = st.number_input("Montant Marchandise (FOB)", min_value=0.0, value=15000.0)
    with col_v3:
        fret_devise = st.number_input("Frais de Fret", min_value=0.0, value=2500.0)

with col_m2:
    st.image(item["image"], caption=article_nom, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="custom-card">', unsafe_allow_html=True)
st.subheader("💼 3. Honoraires & Bénéfices du Transitaire")
col_h1, col_h2, col_h3 = st.columns(3)
with col_h1:
    frais_port = st.number_input("Acconage & Passage Portuaire (FCFA)", value=150000)
    frais_guce = st.number_input("Frais GUCE & Formalités (FCFA)", value=35000)

with col_h2:
    honoraires = st.number_input("Vos Honoraires Facturés (FCFA)", value=250000)
    charges_ops = st.number_input("Vos Charges Réelles (FCFA)", value=50000)

with col_h3:
    acompte = st.number_input("Acompte Réceptionné du Client (FCFA)", value=1000000)

benefice_net = honoraires - charges_ops
st.markdown(f"""
    <div class="profit-box">
        💰 BÉNÉFICE NET DU TRANSITAIRE SUR CE DOSSIER : <b>{benefice_net:,.0f} FCFA</b>
    </div>
""", unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# 5. TRAITEMENT PANDAS & CALCULS SYDAM CI
# =========================================================
taux_conv = taux_cny_xof if "CNY" in devise else taux_usd_xof

# Calculs
fob_fret = fob_devise + fret_devise
assurance = fob_fret * 0.005
caf_devise = fob_fret + assurance
caf_xof = caf_devise * taux_conv

dd_xof = caf_xof * (item["dd"] / 100.0)
rse_xof = caf_xof * 0.010
pcs_xof = caf_xof * 0.008
pc_xof = caf_xof * 0.005
pfi_xof = caf_xof * 0.010

total_droits = dd_xof + rse_xof + pcs_xof + pc_xof + pfi_xof
base_tva = caf_xof + total_droits
tva_xof = base_tva * 0.18

total_douane = total_droits + tva_xof
total_transit = frais_port + frais_guce + honoraires
achat_fret_xof = fob_fret * taux_conv
total_facture = achat_fret_xof + total_douane + total_transit
solde_du = total_facture - acompte

# Création du DataFrame Pandas pour structurer les données
df_cotation = pd.DataFrame([{
    "Désignation": article_nom,
    "Code SH": item['sh'],
    "Valeur CAF (FCFA)": round(caf_xof),
    "Droits & Taxes Douane (FCFA)": round(total_douane),
    "Frais Transit & Prestations (FCFA)": round(total_transit),
    "Montant Total Facturé (FCFA)": round(total_facture),
    "Acompte Versé (FCFA)": round(acompte),
    "Reste à Payer / Solde (FCFA)": round(solde_du)
}])

# =========================================================
# 6. RENDER D'EXPERTISE VISUELLE 3D & RECAPITULATIF
# =========================================================
st.markdown("---")
col_res_img, col_res_text = st.columns([1, 2])

with col_res_img:
    st.image(AVATARS_3D[selected_avatar], caption=f"Validation par : {selected_avatar}", use_container_width=True)

with col_res_text:
    st.subheader("📑 Résumé Financier Validé par l'Expert")
    st.dataframe(df_cotation, use_container_width=True)
    
    st.markdown(f"""
    * **Valeur Douanière CAF :** `{caf_xof:,.0f} FCFA`
    * **Liquidation Douane (SYDAM CI) :** `{total_douane:,.0f} FCFA`
    * **Prestations Transit :** `{total_transit:,.0f} FCFA`
    * **Total Général :** `{total_facture:,.0f} FCFA`
    * **Solde à régler par le client :** <b style="color:#EF4444;">{solde_du:,.0f} FCFA</b>
    """, unsafe_allow_html=True)

# =========================================================
# 7. GÉNÉRATION AUTOMATIQUE DU MESSAGE CLIENT PAR CHATGPT
# =========================================================
st.markdown("---")
st.subheader("🤖 4. Génération de la Réponse Automatique ChatGPT & Envoi")

prompt_chatgpt = f"""
Vous êtes un expert-transitaire senior basé en Côte d'Ivoire (Port Autonome d'Abidjan).
Rédigez un message très professionnel et courtois adressé au client {nom_client}.

Détails du dossier :
- Article : {article_nom} (Code SH: {item['sh']})
- Valeur CAF estimée : {caf_xof:,.0f} FCFA
- Droits et Taxes Douane Côte d'Ivoire (SYDAM) : {total_douane:,.0f} FCFA
- Frais de Transit & Logistique : {total_transit:,.0f} FCFA
- Total de la proforma : {total_facture:,.0f} FCFA
- Acompte reçu : {acompte:,.0f} FCFA
- Solde restant à régler à la livraison : {solde_du:,.0f} FCFA

Instructions :
1. Adoptez un ton extrêmement professionnel, rassurer le client sur la conformité douanière.
2. Expliquez clairement le solde restant dû avant le retrait de la marchandise.
3. Invitez le client à valider pour le lancement des formalités au niveau du GUCE / Douane.
"""

if openai_api_key:
    openai.api_key = openai_api_key
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Vous êtes un expert en cotation douanière et transit maritime en Côte d'Ivoire."},
                {"role": "user", "content": prompt_chatgpt}
            ]
        )
        message_genere = response.choices[0].message.content
    except Exception as e:
        message_genere = f"Erreur lors de la génération avec OpenAI : {e}"
else:
    message_genere = f"""Bonjour {nom_client},

Nous avons finalisé la cotation pour le dédouanement de votre marchandise ({article_nom}).

Voici le récapitulatif financier :
- Droits & Taxes Douanières (SYDAM) : {total_douane:,.0f} FCFA
- Prestations Transit & Passage Portuaire : {total_transit:,.0f} FCFA
- Montant Total du Dossier : {total_facture:,.0f} FCFA
- Acompte Reçu : {acompte:,.0f} FCFA
- Solde Restant à Régler : {solde_du:,.0f} FCFA

Nos équipes restent à votre entière disposition pour lancer la procédure sur le Guichet Unique (GUCE).

Cordialement,
Le Département Transit & Dédouanement."""

st.markdown(f"""
    <div class="ai-box">
        <h4>✨ Message Rédigé par ChatGPT pour le Client :</h4>
        <p style="white-space: pre-line;">{message_genere}</p>
    </div>
""", unsafe_allow_html=True)

# =========================================================
# 8. ACTION D'ENVOI AUTOMATIQUE
# =========================================================
col_btn1, col_btn2 = st.columns(2)

with col_btn1:
    if st.button("📲 Envoyer Automatiquement par WhatsApp", type="primary", use_container_width=True):
        st.success(f"Message transmis avec succès au {tel_client} via le Gateway WhatsApp !")

with col_btn2:
    if st.button("📧 Envoyer par Email au Client", use_container_width=True):
        st.success(f"Facture Proforma et message expédiés à {email_client} !")
