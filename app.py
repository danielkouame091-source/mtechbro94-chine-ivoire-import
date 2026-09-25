import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# Configuration de la page Streamlit
st.set_page_config(
    page_title="SNDGIR SaaS - Transit Ivoire",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialisation des variables de session si non existantes
if 'tenant_id' not in st.session_state:
    st.session_state.tenant_id = 1
if 'tenant_name' not in st.session_state:
    st.session_state.tenant_name = "Société Générale de Transit (SGT)"
if 'username' not in st.session_state:
    st.session_state.username = "Kouassi Daniel"

# =========================================================
# DESIGN CSS & BANNIÈRE PROFESSIONNELLE SAAS
# =========================================================
st.markdown("""
<style>
    /* Conteneur principal de la bannière avec effet de dégradé élégant et bordure lumineuse */
    .saas-header-container {
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #0F766E 100%);
        border: 1px solid rgba(56, 189, 248, 0.2);
        border-radius: 14px;
        padding: 24px 30px;
        margin-bottom: 25px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
        position: relative;
        overflow: hidden;
    }
    
    /* Effet de brillance subtil en arrière-plan */
    .saas-header-container::before {
        content: "";
        position: absolute;
        top: 0;
        right: 0;
        width: 300px;
        height: 100%;
        background: radial-gradient(circle, rgba(56, 189, 248, 0.15) 0%, transparent 70%);
        pointer-events: none;
    }

    /* Titre principal avec police épurée et espacement parfait */
    .saas-header-title {
        font-size: 26px;
        font-weight: 800;
        color: #F8FAFC;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 12px;
        letter-spacing: -0.5px;
    }

    /* Sous-titre descriptif élégant */
    .saas-header-subtitle {
        font-size: 14px;
        font-weight: 400;
        color: #94A3B8;
        margin-top: 8px;
        margin-bottom: 0;
        letter-spacing: 0.2px;
    }

    /* Badge de statut "Démo" ou "Production" moderne */
    .saas-badge {
        background-color: rgba(14, 165, 233, 0.15);
        color: #38BDF8;
        border: 1px solid rgba(56, 189, 248, 0.3);
        padding: 4px 10px;
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

<div class="saas-header-container">
    <div class="header-flex">
        <div class="saas-header-title">
            <span>🏛️</span> SNDGIR SaaS <span style="color: #38BDF8; font-weight: 400;">|</span> TRANSIT IVOIRE
        </div>
        <div class="saas-badge">Mode Démo</div>
    </div>
    <p class="saas-header-subtitle">
        Gestion Intégrée Multi-Sociétés : Cargo, Douanes, ERP Transit, Portail Importateur & Intelligence Artificielle
    </p>
</div>
""", unsafe_allow_html=True)

# Simulation de variables ou fonctions pour que le code soit exécutable si besoin
DB_NAME = "transit.db"
taux_usd_xof = 600.0

def calculer_surestaries(date_arrivee, franchises, taux_jour, taux_change):
    return 3, 150.0, 90000.0, "3 jours de surestaries appliqués."

def generer_facture_transit_pdf(*args):
    return "facture_transit.pdf"

def generer_bae_pdf(*args):
    return "bae_officiel.pdf"

def generer_message_edifact_cusdec(*args):
    return "UNB+UNOA:1+SNDGIR+CUSTOMS+260925:1350+999'UNH+1+CUSDEC:D:96B:UN'"

# Création des onglets principaux (ajustez selon votre code complet d'onglets)
tab_transit_erp, tab_portail_client, tab_caisse, tab_edi, tab_ocr, tab_innov, tab_code, tab_ai, tab_admin = st.tabs([
    "💼 ERP Transit", "📱 Portail Client", "💳 Caisse & BAE", "🔄 Passerelle EDI", 
    "📄 IDP OCR", "🌐 Innovations", "📖 Code Douanes", "🤖 Assistant IA", "🔐 Administration"
])

# =========================================================
# TAB 3 : TRANSIT ERP & FACTURATION
# =========================================================
with tab_transit_erp:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("💼 ERP Transit & Gestion des Prestations Logistiques")

    conn = sqlite3.connect(DB_NAME)
    # Assurez-vous que la table 'dossiers' existe ou gérez l'exception selon votre configuration
    try:
        df_dossiers = pd.read_sql_query("SELECT id, client, article, total_facture, surestaries_xof, statut_livraison FROM dossiers WHERE tenant_id = ?", conn, params=(st.session_state.tenant_id,))
    except Exception:
        df_dossiers = pd.DataFrame(columns=['id', 'client', 'article', 'total_facture', 'surestaries_xof', 'statut_livraison'])
    conn.close()

    if df_dossiers.empty:
        st.info("Aucun dossier de transit actif.")
    else:
        dossier_id_choisi = st.selectbox("Sélectionner un Dossier", df_dossiers['id'].tolist())
        dossier_sel = df_dossiers[df_dossiers['id'] == dossier_id_choisi].iloc[0]

        col_e1, col_e2 = st.columns(2)
        with col_e1:
            st.markdown("##### ⚙️ Paramétrage des Frais Annexes")
            f_port = st.number_input("Frais de Port & Acconage (FCFA)", value=85000.0)
            f_transp = st.number_input("Frais de Transport Terrestre (FCFA)", value=120000.0)
            f_hon = st.number_input("Honoraires de Transit (FCFA)", value=150000.0)
            
            jours_ret, cout_usd_surest, cout_xof_surest, msg_surest = calculer_surestaries(datetime.now().strftime("%Y-%m-%d"), 7, 150, taux_usd_xof)
            st.markdown(f"**Calcul Surestaries :** {msg_surest}")

        with col_e2:
            st.markdown("##### 📄 Édition Facture Définitive Client")
            st.info(f"Client : **{dossier_sel['client']}** | Article : **{dossier_sel['article']}**")
            
            if st.button("🖨️ Générer la Facture PDF Officielle", use_container_width=True):
                pdf_f = generer_facture_transit_pdf(
                    dossier_id_choisi, dossier_sel['client'], dossier_sel['article'],
                    dossier_sel['total_facture'], f_hon, f_port, f_transp, cout_xof_surest
                )
                with open(pdf_f, "rb") as f_pdf:
                    st.download_button("📥 Télécharger la Facture PDF", f_pdf, file_name=pdf_f, mime="application/pdf", use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 4 : PORTAIL IMPORTATEUR (SELF-SERVICE)
# =========================================================
with tab_portail_client:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📱 Portail Client Importateur — Suivi & Téléchargement BAE")
    st.caption("Espace dédié aux PME et importateurs pour suivre leurs conteneurs en temps réel")

    conn = sqlite3.connect(DB_NAME)
    try:
        df_portail = pd.read_sql_query("SELECT id, client, article, bl_number, container_number, statut, canal_selectivite, document_path FROM dossiers WHERE tenant_id = ?", conn, params=(st.session_state.tenant_id,))
    except Exception:
        df_portail = pd.DataFrame(columns=['id', 'client', 'article', 'bl_number', 'container_number', 'statut', 'canal_selectivite', 'document_path'])
    conn.close()

    if df_portail.empty:
        st.info("Aucune information de suivi disponible.")
    else:
        for idx, row in df_portail.iterrows():
            st.markdown(f"""
            <div style="background:#0F172A; padding:15px; border-radius:10px; border:1px solid #334155; margin-bottom:10px;">
                <b>Dossier RCI-2026-{row['id']}</b> | Client : <b>{row['client']}</b><br/>
                Marchandise : {row['article']} | Conteneur : <code>{row['container_number']}</code><br/>
                Statut Douane : <b>{row['statut']}</b> | Circuit : <span style="color:#38BDF8;">{row['canal_selectivite']}</span>
            </div>
            """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 5 : CAISSE & BAE
# =========================================================
with tab_caisse:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("💳 Guichet Unique de Paiement & Émission BAE")

    conn = sqlite3.connect(DB_NAME)
    try:
        df_ca = pd.read_sql_query("SELECT id, client, article, total_facture, bl_number, container_number FROM dossiers WHERE tenant_id = ? AND statut LIKE '%Liquidé%'", conn, params=(st.session_state.tenant_id,))
    except Exception:
        df_ca = pd.DataFrame(columns=['id', 'client', 'article', 'total_facture', 'bl_number', 'container_number'])
    conn.close()

    if df_ca.empty:
        st.info("Aucun dossier en attente de paiement en caisse.")
    else:
        d_id_c = st.selectbox("Choisir le Dossier à Quitter", df_ca['id'].tolist())
        d_row_c = df_ca[df_ca['id'] == d_id_c].iloc[0]

        st.metric("Montant Total Droits & Taxes à Acquitter", f"{d_row_c['total_facture']:,.0f} FCFA")
        quittance_input = st.text_input("N° de Quittance Bancaire / Trésor", value="QUIT-2026-99882")

        if st.button("✅ Encaisser et Délivrer le BAE Officiel", use_container_width=True):
            pdf_bae = generer_bae_pdf(
                d_id_c, d_row_c['client'], d_row_c['article'],
                d_row_c['bl_number'], d_row_c['container_number'], quittance_input, d_row_c['total_facture']
            )
            
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("UPDATE dossiers SET statut = 'Apure et BAE Délivré', quittance_num = ? WHERE id = ?", (quittance_input, d_id_c))
            conn.commit()
            conn.close()

            st.success("Paiement validé avec succès ! Le Bon à Enlever (BAE) a été généré.")
            with open(pdf_bae, "rb") as f_bae:
                st.download_button("📥 Télécharger le BAE Officiel PDF", f_bae, file_name=pdf_bae, mime="application/pdf", use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 6 : PASSERELLE EDI
# =========================================================
with tab_edi:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("🔄 Passerelle EDI — Échange de Données Informatisé (CUSDEC)")
    st.caption("Génération automatique des messages EDIFACT normalisés pour les douanes nationales")

    conn = sqlite3.connect(DB_NAME)
    try:
        df_edi = pd.read_sql_query("SELECT id, client, article, fob_xof, regime FROM dossiers WHERE tenant_id = ?", conn, params=(st.session_state.tenant_id,))
    except Exception:
        df_edi = pd.DataFrame(columns=['id', 'client', 'article', 'fob_xof', 'regime'])
    conn.close()

    if not df_edi.empty:
        sel_edi = st.selectbox("Sélectionner un dossier pour export EDI", df_edi['id'].tolist())
        row_edi = df_edi[df_edi['id'] == sel_edi].iloc[0]

        message_edifact = generer_message_edifact_cusdec(f"RCI-2026-{row_edi['id']}", row_edi['client'], row_edi['article'], row_edi['fob_xof'], row_edi['regime'])
        st.code(message_edifact, language="text")
    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 7 : IDP OCR CROSS-CHECK MULTIMODAL
# =========================================================
with tab_ocr:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📄 Module IDP (Intelligent Document Processing) & OCR IA")
    st.caption("Extraction automatique des données de factures, B/L et rapprochement avec la déclaration douanière[cite: 1]")

    col_ocr_up1, col_ocr_up2 = st.columns(2)
    with col_ocr_up1:
        f_facture = st.file_uploader("📥 Importer la Facture Commerciale (PDF ou Image)", type=["pdf", "png", "jpg", "jpeg"])
    with col_ocr_up2:
        f_bl_doc = st.file_uploader("📥 Importer le Connaissement / B/L (PDF ou Image)", type=["pdf", "png", "jpg", "jpeg"])

    if f_facture is not None:
        st.markdown("---")
        st.info("🔄 Analyse du document par vision artificielle et extraction des métadonnées en cours...")
        
        montant_extrait_ocr = 28500.0  
        fournisseur_extrait = "SHENZHEN ELECTRONICS LTD (Chine)"
        poids_brut_ocr = 1450.0

        col_res1, col_res2, col_res3 = st.columns(3)
        with col_res1:
            st.metric("Fournisseur Détecté", fournisseur_extrait)
        with col_res2:
            st.metric("Montant FOB Extr. (OCR)", f"$ {montant_extrait_ocr:,.2f} USD")
        with col_res3:
            st.metric("Poids Brut Extrait (B/L)", f"{poids_brut_ocr:,.1f} kg")

        st.markdown("##### 🔍 Rapport de Cross-Checking Automatique")
        
        valeur_declaree_systeme = 25000.0  
        ecart_valeur = ((montant_extrait_ocr - valeur_declaree_systeme) / valeur_declaree_systeme) * 100

        if abs(ecart_valeur) > 5.0:
            st.error(f"🔴 **ALERTE DISCORDANCE MAJEURE :** Écart de **{ecart_valeur:+.1f}%** entre la facture OCR ($ {montant_extrait_ocr:,.2f}) et le montant déclaré ($ {valeur_declaree_systeme:,.2f}). Le dossier est automatiquement basculé en **CIRCUIT ROUGE** pour fraude potentielle sur la valeur.")
        else:
            st.success("🟢 **CONCORDANCE VALIDÉE :** Les données de la facture concordent avec les déclarations du manifeste.")

        if st.button("🚀 Transférer automatiquement les données OCR vers la Déclaration SAD", use_container_width=True):
            st.success("Données injectées avec succès dans le formulaire de déclaration en détail !")

    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# TAB 8 à 11 : INNOVATIONS, CODE, ASSISTANT IA & ADMIN
# =========================================================
with tab_innov:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("🌐 Hub d'Innovations Internationales (Inde & Chine)")
    st.info("Connexion aux corridors logistiques mondiaux pour l'optimisation des flux d'importation.")
    st.markdown('</div>', unsafe_allow_html=True)

with tab_code:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("📖 Référentiel du Code des Douanes & Réglementation")
    st.write("Accès rapide aux articles clés de la législation douanière en vigueur.")
    st.markdown('</div>', unsafe_allow_html=True)

with tab_ai:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("🤖 Assistant Virtuel Intelligent (Propulsé par Llama 3)")
    prompt_ai = st.text_input("Posez votre question sur la réglementation douanière ou la logistique :")
    if prompt_ai:
        st.info("Traitement de la requête par l'assistant virtuel...")
    st.markdown('</div>', unsafe_allow_html=True)

with tab_admin:
    st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
    st.subheader("🔐 Administration SaaS & Gestion Multi-Tenants")
    st.write(f"Connecté en tant qu'administrateur de l'entreprise : **{st.session_state.tenant_name}**")
    
    conn = sqlite3.connect(DB_NAME)
    try:
        df_tenants = pd.read_sql_query("SELECT * FROM tenants", conn)
    except Exception:
        df_tenants = pd.DataFrame(columns=['id', 'nom_entreprise', 'statut'])
    conn.close()
    st.dataframe(df_tenants, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
