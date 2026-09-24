import base64
import os
from urllib.parse import quote, urlencode

import pandas as pd
import requests
import streamlit as st

try:
    from groq import Groq
except ImportError:
    Groq = None

# =========================================================
# CONFIGURATION ET STYLES CSS ULTRA-PROFESSIONNELS (3D & GLASSMORPHISM)
# =========================================================
st.set_page_config(
    page_title="Kelanewin Transit - SYDAM Pro CI",
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

/* En-tête avec effet de relief 3D & Gradient Ivoirien */
.header-banner { 
    background: linear-gradient(135deg, #047857 0%, #10B981 50%, #0284C7 100%); 
    padding: 30px; 
    border-radius: 20px; 
    color: white; 
    margin-bottom: 25px; 
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
    border: 1px solid rgba(255, 255, 255, 0.15);
}

/* Cartes Neumorphism & Glassmorphism 3D */
.custom-card-3d { 
    background: #1E293B; 
    border-radius: 18px; 
    padding: 25px; 
    border: 1px solid #334155; 
    margin-bottom: 25px; 
    box-shadow: 8px 8px 16px #070a11, -8px -8px 16px #151a27;
}

/* Cartes KPI pour métriques clés */
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

/* Boîte de bénéfices net du transitaire */
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

/* Boîte IA Conseils Douaniers */
.ai-box-3d { 
    background: linear-gradient(135deg, #1E1B4B 0%, #312E81 100%); 
    border: 1px solid #6366F1; 
    padding: 22px; 
    border-radius: 16px; 
    margin-top: 15px; 
    box-shadow: 0 10px 20px rgba(99, 102, 241, 0.25);
}

/* Badges SYDAM */
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
# FONCTION DE RÉCUPÉRATION AUTOMATIQUE DES TAUX DE CHANGE
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
# BASE DE DONNÉES TARIF D'USAGE (TEC UEMOA / CI SYDAM WORLD)
# =========================================================
DATABASE_ARTICLES = {
    "Station Totale Topographique & GNSS/GPS": {"sh": "9015.80.00", "dd": 5.0, "cat": "Topographie"},
    "Théodolites, Niveaux Optiques & Laser": {"sh": "9015.10.00", "dd": 5.0, "cat": "Topographie"},
    "Accessoires Topo (Mires, Trépieds, Cannes, Prismes)": {"sh": "9015.90.00", "dd": 5.0, "cat": "Topographie"},
    "Peluches & Doudou Rembourrés": {"sh": "9503.00.41", "dd": 20.0, "cat": "Jouets"},
    "Jouets Électroniques & Figurines Plastique": {"sh": "9503.00.70", "dd": 20.0, "cat": "Jouets"},
    "Vélos & Bicyclettes (Non motorisés)": {"sh": "8712.00.00", "dd": 20.0, "cat": "Véhicules"},
    "Vélos Électriques & VAE": {"sh": "8711.60.00", "dd": 20.0, "cat": "Véhicules"},
    "Tricycles / Pousse-pousse / Moto-keke": {"sh": "8711.20.00", "dd": 20.0, "cat": "Véhicules"},
    "Trottinettes Électriques": {"sh": "8711.60.10", "dd": 20.0, "cat": "Véhicules"},
    "Smartphones, iPhones & Téléphones portables": {"sh": "8517.13.00", "dd": 20.0, "cat": "High-Tech"},
    "Ordinateurs Portables, MacBooks & Tablettes": {"sh": "8471.30.00", "dd": 5.0, "cat": "Informatique"},
    "Téléviseurs Smart TV & Écrans LED": {"sh": "8528.72.00", "dd": 20.0, "cat": "Électronique"},
    "Panneaux Photovoltaïques / Solaires": {"sh": "8541.43.00", "dd": 5.0, "cat": "Énergie"},
    "Onduleurs & Convertisseurs Solaires": {"sh": "8504.40.00", "dd": 5.0, "cat": "Énergie"},
    "Batteries Lithium & GEL pour Solaire": {"sh": "8507.60.00", "dd": 10.0, "cat": "Énergie"},
    "Perruques & Mèches en Cheveux Humains": {"sh": "6704.20.00", "dd": 20.0, "cat": "Cosmétique"},
    "Vêtements & Prêt-à-porter": {"sh": "6204.62.00", "dd": 20.0, "cat": "Textile"},
    "Chaussures & Baskets de Sport": {"sh": "6403.99.00", "dd": 20.0, "cat": "Chaussures"},
    "Groupes Électrogènes (Générateurs)": {"sh": "8502.11.00", "dd": 5.0, "cat": "Machines"},
}

# =========================================================
# BARRE LATÉRALE - CONFIGURATION
# =========================================================
st.sidebar.title("🇨🇮 KELANEWIN TRANSIT")
st.sidebar.caption("Système Expert SYDAM World & GUCE CI")
st.sidebar.markdown("---")

default_key = st.secrets.get("GROQ_API_KEY", "") if hasattr(st, "secrets") else ""
groq_api_key = st.sidebar.text_input("🔑 Clé API Groq", value=default_key, type="password")

st.sidebar.subheader("💱 Taux de Change Automatiques")
st.sidebar.caption(status_api_devises)
taux_cny_xof = st.sidebar.number_input("1 CNY -> FCFA", value=taux_cny_auto, step=0.1)
taux_usd_xof = st.sidebar.number_input("1 USD -> FCFA", value=taux_usd_auto, step=1.0)

st.sidebar.subheader("⚓ Options Logistiques")
mode_transport = st.sidebar.selectbox("Mode de Transport", ["Maritime (FCL/LCL)", "Aérien Express"])
assurance_rate = st.sidebar.number_input("Taux Assurance CAF (%)", value=0.5, step=0.1) / 100

st.sidebar.markdown("---")
st.sidebar.markdown("💡 **Support Kelanewin Transit :**\n*Tel:* +225 07 00 00 00 00\n*Abidjan / San-Pédro*")

# =========================================================
# ENTÊTE PRINCIPALE
# =========================================================
st.markdown("""
<div class="header-banner">
    <h1>📦 KELANEWIN TRANSIT : COTATION & DÉDOUANEMENT CI</h1>
    <p>Calculateur Officiel SYDAM World, Tarifs UEMOA (TEC) & Générateur AI de Devis Client</p>
</div>
""", unsafe_allow_html=True)

tab_cotation, tab_ai_expert, tab_base_sh = st.tabs([
    "📊 Cotation & Calcul Douanier", 
    "🤖 Assistant IA SYDAM & Fret", 
    "📚 Nomenclature & Codes SH"
])

# =========================================================
# TAB 1 : COTATION & CALCUL DOUANIER
# =========================================================
with tab_cotation:
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

    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📋 2. Caractéristiques de la Marchandise & Facture")
    col_a, col_b = st.columns([2, 1])

    with col_a:
        article_nom = st.selectbox("Sélectionner l'article à dédouaner", list(DATABASE_ARTICLES.keys()))
        item_info = DATABASE_ARTICLES[article_nom]
        devise_facture = st.selectbox("Devise de la Facture Fournisseur", ["CNY (Yuan Chinois)", "USD (Dollar Américain)"])
        
        m1, m2, m3 = st.columns(3)
        with m1:
            quantite = st.number_input("Quantité d'unités", min_value=1, value=50, step=1)
        with m2:
            prix_unitaire_devise = st.number_input(f"Prix Unitaire ({devise_facture.split()[0]})", min_value=0.01, value=300.0, step=5.0)
        with m3:
            fret_devise = st.number_input(f"Frais de Fret Total ({devise_facture.split()[0]})", min_value=0.0, value=1500.0, step=50.0)

        fob_devise = quantite * prix_unitaire_devise
        st.markdown(f"👉 **Montant Total Marchandise (FOB) :** `{fob_devise:,.2f} {devise_facture.split()[0]}`")

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
    st.subheader("💼 3. Prestations de Transit, Acconage & Marge Transitaire")
    h1, h2, h3 = st.columns(3)
    with h1:
        frais_port = st.number_input("Passage Portuaire / Passage Aéroport (FCFA)", value=150000, step=5000)
        frais_guce = st.number_input("Frais GUCE & Webb Fontaine (FCFA)", value=35000, step=2500)
    with h2:
        honoraires = st.number_input("Honoraires Transit Facturés (FCFA)", value=250000, step=10000)
        charges_ops = st.number_input("Vos Charges Réelles/Débours (FCFA)", value=50000, step=5000)
    with h3:
        acompte = st.number_input("Acompte Réceptionné du Client (FCFA)", value=1000000, step=50000)

    benefice_net = honoraires - charges_ops
    st.markdown(f'<div class="profit-box-3d">💰 BÉNÉFICE NET DU TRANSITAIRE SUR CE DOSSIER : <b>{benefice_net:,.0f} FCFA</b></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Calculs douaniers
    taux_conversion = taux_cny_xof if "CNY" in devise_facture else taux_usd_xof
    prix_unitaire_xof = prix_unitaire_devise * taux_conversion
    fob_xof = fob_devise * taux_conversion
    fret_xof = fret_devise * taux_conversion
    
    assurance_xof = max((fob_xof + fret_xof) * assurance_rate, 5000.0)
    caf_xof = fob_xof + fret_xof + assurance_xof

    taux_dd = item_info["dd"] / 100.0
    taux_redevances = 0.010 + 0.008 + 0.005 + 0.010
    total_taux_droits = taux_dd + taux_redevances

    total_droits_hors_tva = caf_xof * total_taux_droits
    base_tva = caf_xof + total_droits_hors_tva
    tva_xof = base_tva * 0.18

    total_douane = total_droits_hors_tva + tva_xof
    total_transit = frais_port + frais_guce + honoraires
    total_facture = fob_xof + fret_xof + total_douane + total_transit
    solde_du = total_facture - acompte

    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📊 4. Synthèse Financière du Devis Client")

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Valeur CAF Douane</div><div class="kpi-value">{caf_xof:,.0f} FCFA</div></div>""", unsafe_allow_html=True)
    with k2:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Droits & Taxes Douane</div><div class="kpi-value">{total_douane:,.0f} FCFA</div></div>""", unsafe_allow_html=True)
    with k3:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Frais Transit & Port</div><div class="kpi-value">{total_transit:,.0f} FCFA</div></div>""", unsafe_allow_html=True)
    with k4:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title" style="color:#10B981;">Total Général Facturé</div><div class="kpi-value" style="color:#10B981;">{total_facture:,.0f} FCFA</div></div>""", unsafe_allow_html=True)

    st.markdown("<br/>", unsafe_allow_html=True)

    df_detail = pd.DataFrame([{
        "Désignation Article": article_nom,
        "Code SH": item_info["sh"],
        "Qté": quantite,
        "P.U. (FCFA)": round(prix_unitaire_xof),
        "Total FOB (FCFA)": round(fob_xof),
        "Fret (FCFA)": round(fret_xof),
        "Droits Douane & TVA (FCFA)": round(total_douane),
        "Passage Port & Formalités (FCFA)": round(total_transit),
        "Montant Total (FCFA)": round(total_facture),
        "Acompte (FCFA)": round(acompte),
        "Solde Dû (FCFA)": round(solde_du),
    }])

    st.dataframe(df_detail, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("🤖 5. Génération Automatique du Devis & Options d'Envoi")

    prompt_devis = f"""
    Vous êtes un expert transitaire de la société Kelanewin Transit en Côte d'Ivoire.
    Rédigez un message professionnel et clair destiné au client {nom_client}.

    Détails de la cotation :
    - Marchandise : {article_nom} (Code SH: {item_info['sh']})
    - Quantité : {quantite} unités
    - Total FOB : {fob_xof:,.0f} FCFA
    - Fret : {fret_xof:,.0f} FCFA
    - Droits & Taxes Douane (SYDAM World) : {total_douane:,.0f} FCFA
    - Prestations Transit & Passage Portuaire : {total_transit:,.0f} FCFA
    - TOTAL GLOBAL : {total_facture:,.0f} FCFA
    - Acompte reçu : {acompte:,.0f} FCFA
    - SOLDE RESTANT : {solde_du:,.0f} FCFA

    Invitez le client à valider pour engager la procédure sur le GUCE.
    """

    message_genere = None
    if groq_api_key and Groq:
        try:
            client_ai = Groq(api_key=groq_api_key)
            response = client_ai.chat.completions.create(
                model="llama-3.1-8b-instant",  # Modèle 100% garanti actif sur Groq
                messages=[{"role": "user", "content": prompt_devis}],
            )
            message_genere = response.choices[0].message.content
        except Exception as exc:
            pass  # En cas d'erreur API, le message par défaut s'affiche proprement

    if not message_genere:
        message_genere = f"""Bonjour {nom_client},

Voici la cotation éditée par la société Kelanewin Transit pour votre article : {article_nom}.

• Quantité : {quantite} unités
• Valeur Marchandise (FOB) : {fob_xof:,.0f} FCFA
• Frais de Fret : {fret_xof:,.0f} FCFA
• Droits & Taxes de Douane (SYDAM World) : {total_douane:,.0f} FCFA
• Prestations Transit & Formalités GUCE : {total_transit:,.0f} FCFA

---------------------------------------------------
MONTANT TOTAL FACTURÉ : {total_facture:,.0f} FCFA
Acompte reçu : {acompte:,.0f} FCFA
SOLDE RESTANT À RÉGLER : {solde_du:,.0f} FCFA
---------------------------------------------------

Merci de nous confirmer votre accord pour lancer les démarches de dédouanement.

Cordialement,
L'Équipe Kelanewin Transit
Abidjan, Côte d'Ivoire"""

    message_genere = st.text_area("Message structuré rédigé pour le client :", value=message_genere, height=280)

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        gmail_params = urlencode({
            "view": "cm",
            "fs": "1",
            "to": email_client.strip(),
            "su": f"Cotation Kelanewin Transit - {article_nom} ({quantite} unités)",
            "body": message_genere,
            **({"authuser": sender_email.strip()} if sender_email.strip() else {}),
        })
        st.link_button("📧 Envoyer par Gmail", f"https://mail.google.com/mail/?{gmail_params}", use_container_width=True)

    with col_btn2:
        whatsapp_url = f"https://wa.me/{tel_client.strip().replace('+', '')}?text={quote(message_genere)}"
        st.link_button("💬 Envoyer par WhatsApp", whatsapp_url, use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 2 : ASSISTANT IA SYDAM & CONSEIL DOUANIER
# =========================================================
with tab_ai_expert:
    st.markdown('<div class="ai-box-3d">', unsafe_allow_html=True)
    st.subheader("🤖 Assistant Expert Kelanewin Transit (SYDAM World & GUCE via Groq)")
    st.write("Posez vos questions sur le classement SH, les exonérations UEMOA, les procédures Webb Fontaine ou la documentation GUCE.")

    user_query = st.text_area("Exemple : Quel est le tarif de douane pour du matériel de topographie ? Faut-il une FDI ?")

    if st.button("🔍 Interroger l'Expert Douanier IA"):
        if groq_api_key and Groq:
            try:
                client_ai = Groq(api_key=groq_api_key)
                prompt_expert = f"Vous êtes un expert transitaire chez Kelanewin Transit en Côte d'Ivoire. Répondez de manière technique : {user_query}"
                res_ai = client_ai.chat.completions.create(
                    model="llama-3.1-8b-instant",  # Modèle 100% garanti actif sur Groq
                    messages=[{"role": "user", "content": prompt_expert}],
                )
                st.markdown("### 💡 Analyse & Recommandation Douanière :")
                st.info(res_ai.choices[0].message.content)
            except Exception as e:
                st.error(f"Erreur d'accès à l'API Groq : {e}")
        else:
            st.warning("Veuillez saisir une clé API Groq valide dans la barre latérale ou via les secrets.")
    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 3 : BASE NOMENCLATURE & SH
# =========================================================
with tab_base_sh:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📚 Base de Données Tarifaire Kelanewin Transit")
    
    df_db = pd.DataFrame.from_dict(DATABASE_ARTICLES, orient="index")
    df_db.reset_index(inplace=True)
    df_db.columns = ["Désignation Produit", "Code SH", "Droit Douane (DD %)", "Catégorie"]
    
    st.dataframe(df_db, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
