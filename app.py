import streamlit as st
import pandas as pd
import datetime
import uuid
import httpx

# -----------------------------------------------------------------------------
# CONFIGURATION ET CHARTE GRAPHIQUE BANCAIRE PAN-AFRICAINE
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Plateforme FinTech & Anti-Fraude Pan-Africaine (BCEAO / BEAC / PAPSS)",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
    }
    .stTabs [data-baseweb="tab"] {
        padding-left: 12px;
        padding-right: 12px;
        font-weight: bold;
    }
    .metric-card {
        background-color: #f8f9fa;
        border-left: 5px solid #0d6efd;
        padding: 12px;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

# Adresse du serveur backend FastAPI
API_URL = "http://127.0.0.1:8000"

# -----------------------------------------------------------------------------
# BARRE LATÉRALE : SÉLECTION DES ZONES BANCAIRES ET RÉSEAUX D'AFRIQUE
# -----------------------------------------------------------------------------
st.sidebar.image("https://img.icons8.com/color/96/shield-with-signature.png", width=65)
st.sidebar.title("Configuration Panafricaine")

zone_reglementaire = st.sidebar.selectbox(
    "Zone Réglementaire / Banque Centrale",
    [
        "UEMOA (BCEAO - Côte d'Ivoire, Sénégal, Bénin...)",
        "CEMAC (BEAC - Cameroun, Gabon, Congo...)",
        "Afrique de l'Est / M-Pesa (CBK - Kenya, Ouganda...)",
        "Afrique du Nord & Austral (SARB, CBE - Afrique du Sud, Égypte)",
        "Réseau Transfrontalier Panafricain (PAPSS / Afreximbank)"
    ]
)

institution_type = st.sidebar.selectbox(
    "Établissement Opérateur",
    [
        "Banque Commerciale (SGBCI, Ecobank, Coris, Attijariwafa, UBA, Stanbic)",
        "Opérateur Mobile Money (Wave, Orange Money, MTN MoMo, Moov, M-Pesa, Airtel)",
        "FinTech / Neobanque (Djamo, Kuda, Chipper Cash)",
        "Institution de Microfinance (Baobab, Advans, Cofina)",
        "Régulateur / Cellule de Renseignement Financier (CENTIF, ANIF, BCEAO)"
    ]
)

st.sidebar.markdown("---")
st.sidebar.subheader("🔒 Protocoles Panafricains Intégrés")
st.sidebar.write("✔️ Standard ISO 20022 (pacs/camt)")
st.sidebar.write("✔️ Règlementation LCB-FT (CENTIF / ANIF / GAFI)")
st.sidebar.write("✔️ Compensation PAPSS (Paiements Transfrontaliers)")
st.sidebar.write("✔️ Normes Prudentielles Bâle III / IFRS 9")

# Titre principal
st.title("🏛️ Système National & Panafricain de Sécurité Financière et de Scoring")
st.caption(f"Plateforme unifiée d'interception et d'octroi de crédit — Zone : **{zone_reglementaire}** | Organisme : **{institution_type}**")

# -----------------------------------------------------------------------------
# ONGLETS OPÉRATIONNELS
# -----------------------------------------------------------------------------
tab_fraud, tab_credit, tab_mobile, tab_agri, tab_papss, tab_stress, tab_compliance = st.tabs([
    "🚨 1. Gel en Cascade & Fraud Rings",
    "💳 2. Scoring d'Octroi Prudentiel",
    "📱 3. Scoring Mobile Money & Neobanques",
    "🌱 4. Risque Agro-Saisonnier Panafricain",
    "🌍 5. Interconnexion Transfrontalière PAPSS",
    "📈 6. Stress-Test Prudentiel (Bâle III / IFRS 9)",
    "📜 7. Conformité CENTIF / ANIF / ISO 20022"
])

# -----------------------------------------------------------------------------
# TAB 1 : DÉTECTION & GEL EN CASCADE (CONNECTÉ À FASTAPI)
# -----------------------------------------------------------------------------
with tab_fraud:
    st.header("Moteur d'Interception des Fraudes & Traçage des Comptes Mules (Panafricain)")
    st.info("Ce module est relié en temps réel avec le serveur FastAPI (`backend/main.py`) pour reconstituer le graphe et diffuser les ordres de séquestre conservatoire.")

    c1, c2 = st.columns(2)
    with c1:
        utrn = st.text_input("Référence Transactionnelle Unique (UTRN)", "UTRN-2A49DEB232")
        compte_victime = st.text_input("Compte Émetteur / Victime", "+2250746464608")
        montant_conteste = st.number_input("Montant Contesté (FCFA)", min_value=1000, value=2500000, step=50000)

    with c2:
        plateforme_source = st.selectbox("Plateforme d'Origine", ["Wave", "Orange Money", "MTN MoMo", "Moov Money", "Ecobank"])
        typologie_fraude = st.selectbox("Typologie de l'Incident", [
            "Ingénierie Sociale / Phishing / Faux Agents",
            "Compte Mule / Blanchiment Suspecté",
            "Piratage SIM Swap / Usurpation d'Identité",
            "Erreur de Saisie (Wrong Beneficiary)"
        ])
        niveau_urgence = st.select_slider("Urgence Réglementaire", options=["HIGH", "MEDIUM", "LOW"])

    st.markdown("---")
    
    # 1. BOUTON : RECONSTITUER LE GRAPHE VIA FASTAPI
    if st.button("🔍 Interroger le Graphe de Fraude (FastAPI)"):
        payload_trace = {
            "utrn": utrn,
            "platform_origin": plateforme_source,
            "sender_account": compte_victime,
            "incident_type": typologie_fraude,
            "amount": float(montant_conteste),
            "urgency": niveau_urgence
        }
        
        try:
            res = httpx.post(f"{API_URL}/api/v1/fraud/trace-graph", json=payload_trace)
            if res.status_code == 200:
                data = res.json()
                st.session_state["current_chain"] = data.get("detected_chain", [])
                st.success(f"Graphe reconstitué avec succès ! Profondeur : {data.get('chain_depth')} niveau(x).")
            else:
                st.error("Erreur du serveur backend lors de la récupération du graphe.")
        except Exception as e:
            st.error(f"Impossible de contacter FastAPI. Vérifiez que `uvicorn backend.main:app` est bien lancé. Erreur : {e}")

    # Affichage du graphe récupéré depuis le backend
    if "current_chain" in st.session_state and st.session_state["current_chain"]:
        st.subheader("🕸️ Arbre de Propagation Réseau Détecté")
        st.table(pd.DataFrame(st.session_state["current_chain"]))

        # 2. BOUTON : DÉCLENCHER LE GEL PAR BACKGROUND TASKS VIA FASTAPI
        if st.button("🚨 DÉCLENCHER L'ORDRE NATIONAL / PANAFRICAIN DE GEL"):
            target_accounts = [item["account"] for item in st.session_state["current_chain"] if "account" in item]
            
            payload_freeze = {
                "utrn": utrn,
                "target_accounts": target_accounts
            }
            
            try:
                res_freeze = httpx.post(f"{API_URL}/api/v1/fraud/execute-freeze", json=payload_freeze)
                if res_freeze.status_code == 200:
                    freeze_data = res_freeze.json()
                    st.error(f"🛑 ORDRE DE BLOCAGE SYSTÉMIQUE TRANSMIS PAR LA BANQUE CENTRALE — RÉF : {utrn}")
                    st.json(freeze_data)
                    st.success("✅ **Mesures de blocage actives :** Retraits DAB/Kiosques désactivés, virements sortants bloqués.")
                else:
                    st.error("Échec de l'exécution de l'ordre de gel.")
            except Exception as e:
                st.error(f"Erreur de connexion au backend lors de l'envoi du gel : {e}")

# -----------------------------------------------------------------------------
# TAB 2 : SCORING D'OCTROI DE PRÊT PRUDENTIEL
# -----------------------------------------------------------------------------
with tab_credit:
    st.header("Analyse Solvabilité & Octroi Prudentiel (BCEAO / BEAC / Bâle III)")
    st.info("Évaluation automatique du risque de crédit pour les entreprises, PME, commerçants et salariés.")

    col_cr1, col_cr2 = st.columns(2)
    with col_cr1:
        secteur = st.selectbox("Secteur d'Activité", ["Agro-industrie (Cacao, Café, Hévéa, Anacarde)", "Commerce Général & Import-Export", "BTP & Infrastructure", "Transport & Logistique", "Services & Salariés"])
        chiffre_affaires = st.number_input("Chiffre d'Affaires / Revenu mensuel moyen (FCFA)", min_value=100000, value=5000000, step=100000)
        engagements_encours = st.number_input("Remboursements de prêts en cours / mois (FCFA)", min_value=0, value=500000, step=20000)

    with col_cr2:
        pret_demande = st.number_input("Montant du Prêt Demandé (FCFA)", min_value=100000, value=10000000, step=250000)
        duree_mois = st.slider("Durée du remboursement (Mois)", 1, 60, 12)
        registre_impayes = st.radio("Fichage Banque Centrale (CIP / Bureau de Crédit - Creditinfo)", ["Aucun incident", "Régularisé", "Incident actif / Interdit bancaire"])

    mensualite = (pret_demande * 1.02) / duree_mois
    taux_endettement = ((engagements_encours + mensualite) / chiffre_affaires) * 100 if chiffre_affaires > 0 else 100

    st.markdown("---")
    st.subheader("📋 Décision Automatisée d'Octroi de Crédit")

    m1, m2, m3 = st.columns(3)
    m1.metric("Mensualité Calculée", f"{mensualite:,.0f} FCFA / mois")
    m2.metric("Taux d'Endettement Projeté", f"{taux_endettement:.1f} %", delta="Norme max : 33%" if taux_endettement <= 33 else "Dépassement de norme", delta_color="normal" if taux_endettement <= 33 else "inverse")
    m3.metric("Capacité d'Endettement Dispo", f"{max(0, (chiffre_affaires * 0.33) - engagements_encours):,.0f} FCFA")

    if registre_impayes == "Incident actif / Interdit bancaire":
        st.error("❌ **OCTROI REFUSÉ :** Emprunteur fiché au Bureau d'Information sur le Crédit (BIC) / Liste Rouge.")
    elif taux_endettement > 33:
        st.error(f"❌ **OCTROI REFUSÉ :** Taux d'endettement ({taux_endettement:.1f}%) supérieur au plafond prudentiel réglementaire de 33%.")
    else:
        st.success(f"✅ **PRÊT VALIDÉ :** Déblocage autorisé de {pret_demande:,.0f} FCFA vers le compte client.")

# -----------------------------------------------------------------------------
# TAB 3 : SCORING COMPORTEMENTAL MOBILE MONEY
# -----------------------------------------------------------------------------
with tab_mobile:
    st.header("Alternative Credit Scoring pour le Secteur Informel & Neobanques")
    st.info("Permet d'accorder du crédit aux marchands, chauffeurs VTC et indépendants sans fiche de paie, grâce à leurs données de portefeuille électronique (Wave, Orange, MTN, M-Pesa).")

    col_mb1, col_mb2 = st.columns(2)
    with col_mb1:
        flux_entrants_3mois = st.number_input("Cumul des encaissements sur 3 mois (FCFA)", min_value=50000, value=3000000)
        frequence_vente_jour = st.number_input("Nombre moyen de paiements reçus par jour", min_value=1, value=25)
        anciennete_portefeuille = st.slider("Ancienneté du compte marchand (Mois)", 1, 48, 18)

    with col_mb2:
        solde_moyen_nuit = st.number_input("Solde moyen conservé à la fermeture (FCFA)", min_value=0, value=250000)
        taux_retrait_cash = st.slider("% du solde converti immédiatement en espèces", 0, 100, 35)
        stabilité_geographique = st.selectbox("Stabilité de la zone d'activité (Données GSM)", ["Très stable (Même commune/marché)", "Mobile (Régional)", "Instable"])

    score_fintech = 400
    if anciennete_portefeuille >= 12: score_fintech += 120
    if solde_moyen_nuit >= 100000: score_fintech += 180
    if taux_retrait_cash < 50: score_fintech += 150
    if stabilité_geographique == "Très stable (Même commune/marché)": score_fintech += 100

    st.markdown("---")
    st.subheader("📊 Score FinTech Alternative")
    st.metric("Score de Crédit Digital", f"{score_fintech} / 950 points")

    if score_fintech >= 750:
        st.success("🌟 **Catégorie A (Excellente) :** Prêt de trésorerie instantané déblocable en 1 clic sans garantie.")
    elif score_fintech >= 600:
        st.warning("⚡ **Catégorie B (Modérée) :** Prêt accordé avec plafonnement à 50% de la demande.")
    else:
        st.error("🚫 **Catégorie C (Élevée) :** Historique de conservation du solde insuffisant.")

# -----------------------------------------------------------------------------
# TAB 4 : RISQUE AGRO-SAISONNIER
# -----------------------------------------------------------------------------
with tab_agri:
    st.header("Modélisation Agricole Panafricaine & Campagnes Cacao / Café")
    st.info("Ajuste les échéanciers de remboursement des coopératives et planteurs sur les calendriers réels des récoltes en Afrique.")

    col_ag1, col_ag2 = st.columns(2)
    with col_ag1:
        bassin_prod = st.selectbox("Zone de Production", ["Côte d'Ivoire - Bas-Sassandra (Soubré/San-Pédro)", "Côte d'Ivoire - Haut-Sassandra (Daloa)", "Ghana - Ashanti Region", "Cameroun - Centre/Littoral", "Kenya - Rift Valley"])
        culture_type = st.selectbox("Culture Spéculative", ["Cacao", "Café", "Anacarde (Cajou)", "Coton", "Hévéa / Palmier"])
        surface_ha = st.number_input("Surface exploitée (Hectares)", min_value=0.5, value=8.0)

    with col_ag2:
        rendement_estime = st.number_input("Rendement moyen (Kg / Hectare)", min_value=100, value=750)
        prix_fixe_etat = st.number_input("Prix d'achat bord champ (FCFA / Kg)", min_value=500, value=1500)
        aléa_climatique = st.select_slider("Risque Météo / Sécheresse", options=["Conditions Optimales", "Déficit hydrique modéré", "Sécheresse Sévère / Inondation"])

    prod_totale = surface_ha * rendement_estime
    revenu_agri = prod_totale * prix_fixe_etat
    if aléa_climatique == "Sécheresse Sévère / Inondation":
        revenu_agri *= 0.55

    st.markdown("---")
    st.subheader("📅 Échéancier Flottant Aligné sur les Récoltes")
    st.metric("Revenu Net Estimé de la Campagne", f"{revenu_agri:,.0f} FCFA")
    st.write("• **Grande Campagne (Octobre à Mars) :** Prélèvement automatique de 85% du remboursement principal.")
    st.write("• **Petite Campagne (Avril à Juillet) :** Prélèvement du solde complémentaire de 15%.")
    st.write("• **Période de Soudure (Août/Septembre) :** Suspension automatique des échéances sans pénalités.")

# -----------------------------------------------------------------------------
# TAB 5 : PAPSS
# -----------------------------------------------------------------------------
with tab_papss:
    st.header("Plateforme Interbancaire de Paiement Transfrontalier (PAPSS)")
    st.info("Gère les règlements instantanés et la conversion automatique des devises locales entre pays d'Afrique (ex: Franc CFA XOF ↔ Naira Nigérian NGN ↔ Shilling Kényan KES).")

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        pays_origine = st.selectbox("Pays Émetteur", ["Côte d'Ivoire (XOF)", "Sénégal (XOF)", "Nigéria (NGN)", "Kenya (KES)", "Cameroun (XAF)"])
        banque_emetteur = st.selectbox("Banque / Opérateur Source", ["Ecobank Côte d'Ivoire", "SGBCI", "Wave CI", "Zenith Bank Nigéria", "KCB Kenya"])
        montant_devise_source = st.number_input("Montant à envoyer (Monnaie Locale)", min_value=10000, value=5000000)

    with col_p2:
        pays_destination = st.selectbox("Pays Destinataire", ["Nigéria (NGN)", "Kenya (KES)", "Ghana (GHS)", "Côte d'Ivoire (XOF)"])
        banque_destinataire = st.selectbox("Banque / Opérateur Cible", ["Access Bank Nigéria", "M-Pesa Kenya", "GCB Ghana", "NSIA Banque CI"])
        motif_commercial = st.selectbox("Type d'Échange ZLECAF", ["Importation Marchandises B2B", "Règlement Prestation de Service", "Transfert de Trésorerie Filiale"])

    st.markdown("---")
    if st.button("💱 SIMULER LA COMPENSATION EN MONNAIE LOCALE VIA PAPSS"):
        st.success("✅ **Règlement Transfrontalier Autorisé sous Accord Afreximbank / Banque Centrale :**")
        st.write("• **Élimination du besoin en Dollars USD / Euros :** Conversion directe XOF ↔ NGN/KES.")
        st.write("• **Temps de Règlement Interbancaire :** Transaction exécutée sous 120 secondes.")
        st.write("• **Vérification Anti-Blanchiment :** Validation instantanée de l'origine des fonds.")

# -----------------------------------------------------------------------------
# TAB 6 : STRESS-TEST
# -----------------------------------------------------------------------------
with tab_stress:
    st.header("Module Prudentiel d'Analyse des Chocs (Bâle III / IFRS 9)")
    st.info("Évalue la résistance du portefeuille de prêt bancaire face aux chocs macroéconomiques (dévaluation, crise des matières premières, hausse de l'inflation).")

    col_st1, col_st2 = st.columns(2)
    with col_st1:
        choc_chiffre_affaires = st.slider("Choc de baisse du Chiffre d'Affaires (%)", 0, 70, 35)
        hausse_taux_interet = st.slider("Hausse du taux directeur Banque Centrale (+ points de base)", 0, 500, 150)

    with col_st2:
        provision_requise_ifrs9 = "Stage 1 (Normal)" if choc_chiffre_affaires < 20 else ("Stage 2 (Dégradation significative)" if choc_chiffre_affaires < 40 else "Stage 3 (Défaillance / NPL)")
        st.metric("Classification IFRS 9 du Prêt", provision_requise_ifrs9)

    st.markdown("---")
    st.subheader("🧪 Résultat de la Simulation sous Choc")
    if choc_chiffre_affaires > 30:
        st.error("🚨 **RISQUE DE DÉFAUT ÉLEVÉ :** Le client nécessite une restructuration de dette ou la mise en jeu des garanties réelles.")
    else:
        st.success("🛡️ **CAPACITÉ DE RÉSISTANCE CONFIRMÉE :** Les marges opérationnelles absorbent le choc économique.")

# -----------------------------------------------------------------------------
# TAB 7 : COMPLIANCE
# -----------------------------------------------------------------------------
with tab_compliance:
    st.header("Registre d'Audit & Déclarations Officielles d'Alerte")
    st.markdown("""
    Exportation automatisée des déclarations de transactions suspectes (DTS) directement transmises aux cellules de renseignement financier nationales (**CENTIF Côte d'Ivoire**, **ANIF**, **BCEAO**, **BEAC**).
    """)

    if st.button("📄 GÉNÉRER LE RAPPORT STRUCTURÉ D'ALERTE (ISO 20022 camt.056)"):
        rapport_iso = {
            "Document": {
                "FIToFIPmtCxlReq": {
                    "GrpHdr": {
                        "MsgId": f"CENTIF-CI-{uuid.uuid4().hex[:12].upper()}",
                        "CreDtTm": datetime.datetime.now().isoformat(),
                        "NbOfTxs": "1"
                    },
                    "TxInf": {
                        "CancellationReasonInformation": {
                            "Rsn": {"Cd": "FRAD"},
                            "AddtlInf": "Mule Account Cascade Freezing Executed under BCEAO Regulations"
                        }
                    }
                }
            }
        }
        st.json(rapport_iso)
        st.success("✅ Fichier d'instruction réglementaire prêt pour téléversement automatique au régulateur.")