import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# Configuration de la page Streamlit
st.set_page_config(
    page_title="Hub Logistique & Transit Pan-Africain",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialisation des variables de session pour le pays sélectionné
if 'pays_transit' not in st.session_state:
    st.session_state.pays_transit = "Côte d'Ivoire (UEMOA - Port de Abidjan)"
if 'username' not in st.session_state:
    st.session_state.username = "Kouassi Daniel"

# =========================================================
# DESIGN CSS & BANNIÈRE PAN-AFRICAINE
# =========================================================
st.markdown("""
<style>
    .panafricain-header-container {
        background: linear-gradient(135deg, #064E3B 0%, #0F766E 50%, #1E293B 100%);
        border: 1px solid rgba(16, 185, 129, 0.3);
        border-radius: 14px;
        padding: 24px 30px;
        margin-bottom: 25px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
        position: relative;
        overflow: hidden;
    }
    
    .panafricain-header-title {
        font-size: 26px;
        font-weight: 800;
        color: #F8FAFC;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 12px;
        letter-spacing: -0.5px;
    }

    .panafricain-header-subtitle {
        font-size: 14px;
        font-weight: 400;
        color: #A7F3D0;
        margin-top: 8px;
        margin-bottom: 0;
        letter-spacing: 0.2px;
    }

    .continent-badge {
        background-color: rgba(16, 185, 129, 0.2);
        color: #34D399;
        border: 1px solid rgba(52, 211, 153, 0.4);
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin-left: auto;
    }
    
    .header-flex {
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
</style>

<div class="panafricain-header-container">
    <div class="header-flex">
        <div class="panafricain-header-title">
            <span>🌍</span> Hub Transit & Douanes <span style="color: #34D399; font-weight: 400;">|</span> Afrique & Corridors
        </div>
        <div class="continent-badge">Réseau Continental</div>
    </div>
    <p class="panafricain-header-subtitle">
        Système Informatisé de Suivi des Cargaisons, Dédouanement et Gestion Logistique Multi-Pays (CEDEAO, CEMAC, Maghreb, etc.)
    </p>
</div>
""", unsafe_allow_html=True)

# Barre latérale pour sélectionner le pays d'exercice douanier
with st.sidebar:
    st.image("https://img.icons8.com/color/96/africa.png", width=60)
    st.subheader("🌐 Corridor Douanier")
    
    pays_selectionne = st.selectbox(
        "Sélectionner le Pays / Zone d'Opération",
        [
            "Côte d'Ivoire (Port d'Abidjan / San Pédro)",
            "Sénégal (Port Autonome de Dakar)",
            "Cameroun (Port de Douala / Kribi)",
            "Maroc (Port de Tanger Med / Casablanca)",
            "Bénin (Port de Cotonou)",
            "Togo (Port Autonome de Lomé)",
            "Ghana (Port de Tema / Takoradi)",
            "Nigeria (Port de Lagos / Apapa)",
            "Kenya (Port de Mombasa)"
        ]
    )
    st.session_state.pays_transit = pays_selectionne
    st.info(f"📍 Zone active : \n**{st.session_state.pays_transit}**")

# Simulation de variables et fonctions
DB_NAME = "transit_afrique.db"
taux_usd_xof = 600.0

def calculer_surestaries(date_arrivee, franchises, taux_jour, taux_change):
    return 3, 150.0, 90000.0, "3 jours de surestaries appliqués selon les barèmes portuaires."

def generer_facture_transit_pdf(*args):
    return "facture_transit_afrique.pdf"

def generer_bae_pdf(*args):
    return "bon_enlevement_portuaire.pdf"

def generer_message_edifact_cusdec(dossier, client, article, fob, regime):
    return f"UNB+UNOA:1+CUSTOMS+{st.session_state.pays_transit[:3].upper()}+260925:1350+999'\nUNH+1+CUSDEC:D:96B:UN'\nBGM+85+{dossier}+9'\nFTX+REG++{regime}'\nNAD+MS+{client}'\nAUT+END'"

# Création des onglets principaux axés sur le transit multi-pays
tab_transit_erp, tab_portail_client, tab_caisse, tab_edi, tab_ocr, tab_innov, tab_code, tab_ai = st.tabs([
    "💼 ERP Transit & Port", 
    "📱 Portail Importateur", 
    "💳 Guichet & BAE", 
    "🔄 Échange EDI", 
    "📄 IDP OCR Douane", 
    "🌐 Hub Corridors", 
    "📖 Tarifs & Réglementations", 
    "🤖 Assistant IA Douanes"
])

# =========================================================
# TAB 1 : ERP TRANSIT & PORT
# =========================================================
with tab_transit_erp:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader(f"💼 Gestion des Dossiers de Transit — {st.session_state.pays_transit}")

    # Simulation d'un DataFrame vide ou chargé
    data_mock = {
        'id': [101, 102],
        'client': ['SARL Import Afrique', 'Global Trading Abidjan'],
        'article': ['Matériel Électronique (Chine)', 'Quincaillerie Générale (Inde)'],
        'total_facture': [1500000, 3200000],
        'surestaries_xof': [90000, 0],
        'statut_livraison': ['En douane', 'Quittancé']
    }
    df_dossiers = pd.DataFrame(data_mock)

    if df_dossiers.empty:
        st.info("Aucun dossier de transit actif pour cette zone.")
    else:
        dossier_id_choisi = st.selectbox("Sélectionner un Dossier Logistique", df_dossiers['id'].tolist())
        dossier_sel = df_dossiers[df_dossiers['id'] == dossier_id_choisi].iloc[0]

        col_e1, col_e2 = st.columns(2)
        with col_e1:
            st.markdown("##### ⚙️ Paramétrage des Frais Portuaires & Terrestres")
            f_port = st.number_input("Frais de Port, Manutention & Acconage", value=120000.0)
            f_transp = st.number_input("Frais de Transport Corridor / Hinterland", value=250000.0)
            f_hon = st.number_input("Honoraires Commissionnaire en Douane", value=180000.0)
            
            jours_ret, cout_usd_surest, cout_xof_surest, msg_surest = calculer_surestaries("2026-09-01", 7, 150, taux_usd_xof)
            st.markdown(f"**Surestaries / Détention Conteneur :** {msg_surest}")

        with col_e2:
            st.markdown("##### 📄 Facturation Transit Définitive")
            st.info(f"Client : **{dossier_sel['client']}** | Marchandise : **{dossier_sel['article']}**")
            
            if st.button("🖨️ Générer la Note de Frais & Facture PDF", use_container_width=True):
                pdf_f = generer_facture_transit_pdf(
                    dossier_id_choisi, dossier_sel['client'], dossier_sel['article'],
                    dossier_sel['total_facture'], f_hon, f_port, f_transp, cout_xof_surest
                )
                with open(pdf_f, "rb") as f_pdf:
                    st.download_button("📥 Télécharger la Facture PDF", f_pdf, file_name=pdf_f, mime="application/pdf", use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 2 : PORTAIL IMPORTATEUR
# =========================================================
with tab_portail_client:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📱 Suivi des Conteneurs en Temps Réel pour les Importateurs PME")
    st.caption("Visibilité complète sur l'acheminement depuis les ports asiatiques (Chine, Inde) jusqu'aux entrepôts intérieurs.")
    
    st.markdown("""
    <div style="background:#0F172A; padding:15px; border-radius:10px; border:1px solid #334155; margin-bottom:10px;">
        <b>Dossier REF-AFR-2026-01</b> | Importateur : <b>SARL Import Afrique</b><br/>
        Route : Ningbo / Shanghai ➔ <b>{}</b><br/>
        Conteneur : <code>TGBU9823710</code> | Circuit Douane : <span style="color:#38BDF8;">CIRCUIT VERT (Mainlevée rapide)</span>
    </div>
    """.format(st.session_state.pays_transit), unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 3 : CAISSE & BAE
# =========================================================
with tab_caisse:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("💳 Guichet Unique de Paiement & Émission du BAE / Mainlevée")
    
    st.metric("Droits & Taxes Douanières Estimés", "2,850,000 FCFA")
    quittance_input = st.text_input("Référence de Quittance Bancaire / Trésor Public", value="QUITT-TR-2026-4491")

    if st.button("✅ Valider l'Encaissement & Délivrer le BAE", use_container_width=True):
        st.success("Paiement enregistré avec succès. Le Bon à Enlever (BAE) / Mainlevée portuaire a été émis.")
    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 4 : PASSERELLE EDI
# =========================================================
with tab_edi:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("🔄 Passerelle EDI Douanière (Messages CUSDEC / Manifestes)")
    st.caption("Génération des structures d'échanges électroniques normalisées pour les douanes nationales.")
    
    msg_edi = generer_message_edifact_cusdec("REF-01", "SARL Import Afrique", "Électronique", 25000, "IM4")
    st.code(msg_edi, language="text")
    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 5 : IDP OCR CROSS-CHECK
# =========================================================
with tab_ocr:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📄 Module IDP & Rapprochement Automatique Facture / Connaissement (B/L)")
    
    f_facture = st.file_uploader("📥 Importer la Facture Fournisseur (Asie/International)", type=["pdf", "png", "jpg", "jpeg"])
    if f_facture:
        st.success("Extraction OCR réussie : Fournisseur vérifié, concordance des montants FOB validée sans écart majeur.")
    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 6 : INNOVATIONS & CORRIDORS
# =========================================================
with tab_innov:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("🌐 Hub d'Optimisation des Corridors Logistiques Internationaux")
    st.write("Connexion directe avec les routes maritimes majeures (Asie ➔ Ports Africains) et suivi inter-États (Corridors Abidjan-Ouagadougou, Dakar-Bamako, Douala-N'Djamena, etc.).")
    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 7 : CODE & TARIFS DOUANIERS
# =========================================================
with tab_code:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader(f"📖 Référentiel Douanier & Tarifs — {st.session_state.pays_transit}")
    st.write("Consultation rapide du Tarif Extérieur Commun (TEC) et des réglementations applicables aux importations.")
    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 8 : ASSISTANT IA
# =========================================================
with tab_ai:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("🤖 Assistant Virtuel Spécialisé en Transit & Douanes Africaines")
    prompt_ai = st.text_input("Posez votre question sur le dédouanement, les régimes économiques ou la fiscalité portuaire :")
    if prompt_ai:
        st.info("Analyse de la réglementation douanière en cours...")
    st.markdown('</div>', unsafe_allow_html=True)
