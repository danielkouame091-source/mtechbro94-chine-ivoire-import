import streamlit as st
import pandas as pd
from datetime import datetime

# =========================================================
# 1. CONFIGURATION DE LA PAGE & STYLES CSS SUR-MESURE
# =========================================================
st.set_page_config(
    page_title="Cabinet Transit & Douane CI - Calculateur Expert",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS pour une interface Ultra-Professionnelle
st.markdown("""
    <style>
    /* Palette de couleurs Corporate Douane */
    :root {
        --primary-color: #0F172A;
        --secondary-color: #1E3A8A;
        --accent-color: #D97706;
        --bg-light: #F8FAFC;
    }
    
    .main-header {
        background: linear-gradient(135deg, #0F172A 0%, #1E3A8A 100%);
        padding: 24px;
        border-radius: 12px;
        color: white;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 25px;
    }
    
    .main-header h1 {
        color: #F8FAFC !important;
        font-size: 28px !important;
        font-weight: 700 !important;
        margin-bottom: 8px !important;
    }
    
    .main-header p {
        color: #94A3B8 !important;
        font-size: 15px !important;
        margin: 0 !important;
    }

    .section-card {
        background-color: white;
        border: 1px solid #E2E8F0;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
        margin-bottom: 20px;
    }

    .proforma-card {
        background-color: #FFFFFF;
        border: 2px solid #1E3A8A;
        padding: 25px;
        border-radius: 12px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }

    .badge-sh {
        background-color: #EFF6FF;
        color: #1D4ED8;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
        font-family: monospace;
    }
    
    .price-highlight {
        font-size: 24px;
        font-weight: 800;
        color: #059669;
    }
    </style>
""", unsafe_allow_html=True)

# =========================================================
# 2. BASE DE DONNÉES NOMENCLATURE TARIFATION TEC-CEDEAO / SYDAM
# =========================================================
NOMENCLATURE_EXPERT = {
    "💇‍♀️ Perruques, Tissages & Mèches de Cheveux Humains (Cat. 3 - DD 20%)": {
        "sh": "6704.20.00", "dd": 20.0, "cat": "Catégorie 3 (Biens de consommation)",
        "desc": "Perruques, barbes, sourcils et articles similaires en cheveux humains.",
        "image": "https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?auto=format&fit=crop&w=600&q=80"
    },
    "💇‍♀️ Perruques & Mèches en Fibres Synthétiques / Artificielles (Cat. 3 - DD 20%)": {
        "sh": "6704.11.00", "dd": 20.0, "cat": "Catégorie 3 (Biens de consommation)",
        "desc": "Perruques complètes et mèches en matières textiles synthétiques.",
        "image": "https://images.unsplash.com/photo-1560869713-7d0a29430803?auto=format&fit=crop&w=600&q=80"
    },
    "💄 Produits Cosmétiques, Parfums, Soins & Maquillage (Cat. 3 - DD 20%)": {
        "sh": "3304.99.00", "dd": 20.0, "cat": "Catégorie 3 (Biens de consommation)",
        "desc": "Produits de beauté, de maquillage et préparations pour les soins de la peau.",
        "image": "https://images.unsplash.com/photo-1522338242992-e1a54906a8da?auto=format&fit=crop&w=600&q=80"
    },
    "📱 Smartphones, Tablettes & Téléphones Mobiles (Cat. 3 - DD 20%)": {
        "sh": "8517.13.00", "dd": 20.0, "cat": "Catégorie 3 (Biens de consommation)",
        "desc": "Smartphones et appareils cellulaires pour réseaux sans fil.",
        "image": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=600&q=80"
    },
    "💻 Ordinateurs Portables, PC Bureau & Serveurs (Cat. 1 - DD 5%)": {
        "sh": "8471.30.00", "dd": 5.0, "cat": "Catégorie 1 (Biens de première nécessité/Équipements)",
        "desc": "Machines automatiques de traitement de l'information portatives.",
        "image": "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=600&q=80"
    },
    "👕 Vêtements, Chaussures, Sacs à main & Maroquinerie (Cat. 3 - DD 20%)": {
        "sh": "6204.62.00", "dd": 20.0, "cat": "Catégorie 3 (Biens de consommation)",
        "desc": "Vêtements, pantalons, sacs et accessoires de mode.",
        "image": "https://images.unsplash.com/photo-1441986300917-64674bd600d8?auto=format&fit=crop&w=600&q=80"
    },
    "🚴 Vélos, Trottinettes & Vélo-cargos (Cat. 3 - DD 20%)": {
        "sh": "8712.00.00", "dd": 20.0, "cat": "Catégorie 3 (Biens de consommation)",
        "desc": "Cycles sans moteur (y compris les tricycles de livraison).",
        "image": "https://images.unsplash.com/photo-1485965120184-e220f721d03e?auto=format&fit=crop&w=600&q=80"
    },
    "🏍️ Motos, Scooters à essence & Triporteurs (Cat. 3 - DD 20%)": {
        "sh": "8711.20.00", "dd": 20.0, "cat": "Catégorie 3 (Biens de consommation)",
        "desc": "Motocycles et cycles équipés d'un moteur à piston.",
        "image": "https://images.unsplash.com/photo-1558981806-ec527fa84c39?auto=format&fit=crop&w=600&q=80"
    },
    "🚗 Voitures de Tourisme & Véhicules Personnels (Cat. 3 - DD 20%)": {
        "sh": "8703.22.00", "dd": 20.0, "cat": "Catégorie 3 (Biens de consommation)",
        "desc": "Voitures de tourisme et autres véhicules automobiles.",
        "image": "https://images.unsplash.com/photo-1503376780353-7e6692767b70?auto=format&fit=crop&w=600&q=80"
    },
    "🧊 Réfrigérateurs, Climatiseurs & Électroménager (Cat. 3 - DD 20%)": {
        "sh": "8418.10.00", "dd": 20.0, "cat": "Catégorie 3 (Biens de consommation)",
        "desc": "Appareils électroménagers pour le froid et le confort.",
        "image": "https://images.unsplash.com/photo-1584622650111-993a426fbf0a?auto=format&fit=crop&w=600&q=80"
    },
    "☀️ Panneaux Solaires Photovoltaïques (Cat. 1 - DD 5%)": {
        "sh": "8541.43.00", "dd": 5.0, "cat": "Catégorie 1 (Équipements stratégiques)",
        "desc": "Modules photovoltaïques pour la production d'énergie solaire.",
        "image": "https://images.unsplash.com/photo-1509391365360-2e959784a276?auto=format&fit=crop&w=600&q=80"
    },
    "🏗️ Machines Industrielles & Outillage Lourd (Cat. 1 - DD 5%)": {
        "sh": "8479.89.00", "dd": 5.0, "cat": "Catégorie 1 (Biens d'équipement)",
        "desc": "Machines et appareils mécaniques ayant une fonction propre.",
        "image": "https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?auto=format&fit=crop&w=600&q=80"
    },
    "💊 Médicaments & Produits Pharmaceutiques (Cat. 0 - DD 0%)": {
        "sh": "3004.90.00", "dd": 0.0, "cat": "Catégorie 0 (Biens sociaux essentiels)",
        "desc": "Médicaments préparés à des fins thérapeutiques ou prophylactiques.",
        "image": "https://images.unsplash.com/photo-1471864190281-a93a3070b6de?auto=format&fit=crop&w=600&q=80"
    }
}

# =========================================================
# 3. BARRE LATÉRALE - MENU ET PARAMÈTRES
# =========================================================
st.sidebar.image("https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?auto=format&fit=crop&w=600&q=80", use_container_width=True)
st.sidebar.title("🏛️ Expertise Douanière")
st.sidebar.caption("République de Côte d'Ivoire — DGD")

navigation = st.sidebar.radio(
    "Navigation Spécialisée :",
    ["📋 Éditeur de Devis Proforma", "📖 Tarif Douanier SH (TEC)", "⚙️ Moteur de Calcul & Taxes SYDAM"]
)

st.sidebar.markdown("---")
st.sidebar.subheader("💱 Taux de Conversion Officiel")
taux_cny_xof = st.sidebar.number_input(
    "1 CNY (Yuan) en FCFA",
    min_value=50.0,
    max_value=120.0,
    value=82.0,
    step=0.5,
    help="Taux de change légal retenu pour la conversion en Douane"
)

# =========================================================
# 4. PAGE 1 : ÉDITEUR DE DEVIS PROFORMA (EXPERT CLIENT)
# =========================================================
if navigation == "📋 Éditeur de Devis Proforma":
    
    # En-tête Principal
    st.markdown("""
        <div class="main-header">
            <h1>🇨🇮 Cabinet d'Expertise en Transit & Dédouanement</h1>
            <p>Calculateur Officiel d'Importation Chine ➔ Côte d'Ivoire (Conforme SYDAM & TEC-CEDEAO)</p>
        </div>
    """, unsafe_allow_html=True)

    col_top1, col_top2 = st.columns([2, 1])

    with col_top1:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subsection = st.subheader("👤 1. Fiche d'Identification du Client & Expédition")
        
        c1, c2 = st.columns(2)
        with c1:
            nom_client = st.text_input("Nom / Raison Sociale du Client", value="MADAME KOUASSI - BOUTIQUE GLAMOUR")
            ref_devis = st.text_input("N° Référence Dossier / Cotation", value=f"COT-CI-{datetime.now().strftime('%Y%m%d%H%M')}")
        with c2:
            mode_expedition = st.selectbox("Mode de Transport International", ["Fret Maritime (Container / LCL)", "Fret Aérien Express (Avion)", "Fret Aérien Standard"])
            port_arrivee = st.selectbox("Port / Aéroport de Destination", ["Port Autonome d'Abidjan (CIABJ)", "Aéroport International Félix Houphouët-Boigny (CIAID)"])
        st.markdown('</div>', unsafe_allow_html=True)

    with col_top2:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("💡 Note de l'Expert")
        st.info(
            "Le dédouanement en Côte d'Ivoire s'effectue sur la **Valeur CAF** (Coût + Assurance + Fret). "
            "Les droits et taxes sont obligatoirement exigibles avant le levée du Bon à Enlever (BAE)."
        )
        st.markdown('</div>', unsafe_allow_html=True)

    # Section Marchandise
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("📦 2. Caractéristiques Techniques de la Marchandise")
    
    col_m1, col_m2, col_m3 = st.columns([1.5, 1, 1])

    with col_m1:
        produit_cle = st.selectbox(
            "Désignation commerciale de la marchandise",
            list(NOMENCLATURE_EXPERT.keys()),
            index=0
        )
        data_prod = NOMENCLATURE_EXPERT[produit_cle]
        
        st.markdown(f"**Code SH Officiel :** <span class='badge-sh'>{data_prod['sh']}</span>", unsafe_allow_html=True)
        st.caption(f"**Nomenclature :** {data_prod['desc']}")

    with col_m2:
        valeur_fob_cny = st.number_input(
            "Valeur d'Achat Marchandise (CNY / Yuan)",
            min_value=0.0,
            value=5000.0,
            step=500.0,
            help="Valeur d'achat chez le fournisseur en Chine"
        )
        fret_cny = st.number_input(
            "Frais de Transport / Fret (CNY / Yuan)",
            min_value=0.0,
            value=800.0,
            step=100.0,
            help="Coût de transport de la Chine jusqu'à Abidjan"
        )

    with col_m3:
        st.image(data_prod["image"], caption=f"{produit_cle.split('(')[0]}", use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # =========================================================
    # JEU DE CALCULS CONFORME AU CODE DES DOUANES
    # =========================================================
    # 1. Sous-total Coût & Fret
    fob_plus_fret_cny = valeur_fob_cny + fret_cny
    
    # 2. Assurance Douanière Forfaitaire (0.5%)
    assurance_cny = fob_plus_fret_cny * 0.005
    
    # 3. Valeur CAF (Coût, Assurance, Fret)
    caf_cny = fob_plus_fret_cny + assurance_cny
    caf_xof = caf_cny * taux_cny_xof

    # 4. Taux de Droit de Douane
    dd_rate = data_prod["dd"]

    # 5. Liquidation des Taxes Douanières (SYDAM)
    dd_xof = caf_xof * (dd_rate / 100.0)                  # Droit de Douane (DD)
    rse_xof = caf_xof * 0.010                               # Redevance Statistique (RSE - 1.0%)
    pcs_xof = caf_xof * 0.008                               # Prélèvement Communautaire UEMOA (PCS - 0.8%)
    pc_xof = caf_xof * 0.005                                # Prélèvement Communautaire CEDEAO (PC - 0.5%)

    total_taxes_comm_xof = rse_xof + pcs_xof + pc_xof

    # 6. Assiette de Calcul de la TVA (18%)
    base_tva_xof = caf_xof + dd_xof + total_taxes_comm_xof
    tva_xof = base_tva_xof * 0.18                           # TVA (18.0%)

    # 7. Cumul Final
    total_droits_taxes_xof = dd_xof + total_taxes_comm_xof + tva_xof
    achat_fret_xof = fob_plus_fret_cny * taux_cny_xof
    budget_global_importation_xof = achat_fret_xof + total_droits_taxes_xof

    # =========================================================
    # PRESENTATION DU DEVIS PROFORMA CLIENT
    # =========================================================
    st.markdown("---")
    st.subheader("📄 Fiche de Cotation & Devis Proforma Client")

    st.markdown(f"""
        <div class="proforma-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h2>COTATION DOUANIÈRE PROFORMA</h2>
                <span style="font-weight: bold; color: #1E3A8A;">RÉF : {ref_devis}</span>
            </div>
            <hr>
            <p><strong>Client :</strong> {nom_client} | <strong>Date :</strong> {datetime.now().strftime('%d/%m/%Y')} | <strong>Origine :</strong> Chine (CN) ➔ <strong>Destination :</strong> {port_arrivee}</p>
            <p><strong>Marchandise :</strong> {produit_cle} | <strong>Code SH :</strong> <span class='badge-sh'>{data_prod['sh']}</span></p>
            <hr>
    """, unsafe_allow_html=True)

    col_res1, col_res2 = st.columns(2)

    with col_res1:
        st.markdown("#### 1. Éléments de la Valeur CAF (Base Imposable)")
        st.write(f"• **Valeur d'Achat (FOB Chine) :** `{valeur_fob_cny:,.2f} CNY` ({valeur_fob_cny * taux_cny_xof:,.0f} FCFA)")
        st.write(f"• **Transport / Fret International :** `{fret_cny:,.2f} CNY` ({fret_cny * taux_cny_xof:,.0f} FCFA)")
        st.write(f"• **Assurance Douanière (0.5%) :** `{assurance_cny:,.2f} CNY` ({assurance_cny * taux_cny_xof:,.0f} FCFA)")
        st.markdown(f"👉 **VALEUR CAF RETENUE :** **`{caf_xof:,.0f} FCFA`**")

    with col_res2:
        st.markdown("#### 2. Décompte Officiel des Droits & Taxes Douanières")
        st.write(f"• **Droit de Douane (DD - {dd_rate}%) :** `{dd_xof:,.0f} FCFA`")
        st.write(f"• **Redevance Statistique (RSE - 1%) :** `{rse_xof:,.0f} FCFA`")
        st.write(f"• **Prélèvement UEMOA (PCS - 0.8%) :** `{pcs_xof:,.0f} FCFA`")
        st.write(f"• **Prélèvement CEDEAO (PC - 0.5%) :** `{pc_xof:,.0f} FCFA`")
        st.write(f"• **TVA à l'importation (18%) :** `{tva_xof:,.0f} FCFA`")
        st.markdown(f"👉 **TOTAL TAXES DOUANIÈRES :** **`{total_droits_taxes_xof:,.0f} FCFA`**")

    st.markdown("---")
    
    st.markdown(f"""
        <div style="background-color: #F1F5F9; padding: 15px; border-radius: 8px; text-align: center;">
            <span style="font-size: 18px; color: #475569;">BUDGET TOTAL ESTIMÉ POUR L'OPÉRATION :</span><br>
            <span class="price-highlight">{budget_global_importation_xof:,.0f} FCFA</span>
            <p style="font-size: 12px; color: #64748B; margin-top: 5px;">(Inclut l'achat du produit, le fret international et l'intégralité des taxes douanières ivoiriennes)</p>
        </div>
        </div>
    """, unsafe_allow_html=True)

    # Exportation CSV / Excel
    df_export = pd.DataFrame({
        "Réf Cotation": [ref_devis],
        "Client": [nom_client],
        "Marchandise": [produit_cle],
        "Code SH": [data_prod['sh']],
        "Valeur FOB (CNY)": [valeur_fob_cny],
        "Fret (CNY)": [fret_cny],
        "Valeur CAF (FCFA)": [caf_xof],
        "Droit de Douane (FCFA)": [dd_xof],
        "RSE (FCFA)": [rse_xof],
        "PCS + PC (FCFA)": [pcs_xof + pc_xof],
        "TVA 18% (FCFA)": [tva_xof],
        "Total Taxes Douane (FCFA)": [total_droits_taxes_xof],
        "Budget Total Global (FCFA)": [budget_global_importation_xof]
    })

    st.markdown("<br>", unsafe_allow_html=True)
    st.download_button(
        label="📥 Télécharger ce devis professionnel pour le Client (Fichier CSV)",
        data=df_export.to_csv(index=False).encode('utf-8'),
        file_name=f"Devis_Douane_{nom_client.replace(' ', '_')}_{ref_devis}.csv",
        mime="text/csv"
    )

# =========================================================
# 5. PAGE 2 : TARIF DOUANIER SYDAM & NOMENCLATURE
# =========================================================
elif navigation == "📖 Tarif Douanier SH (TEC)":
    st.title("📖 Nomenclature Tarifaire & Système Harmonisé (SH)")
    st.write("Base de données exhaustive du Tarif Extérieur Commun de la CEDEAO appliquée en Côte d'Ivoire.")
    st.markdown("---")

    grid_data = []
    for name, item in NOMENCLATURE_EXPERT.items():
        grid_data.append({
            "Marchandise": name,
            "Code SH": item["sh"],
            "Catégorie TEC": item["cat"],
            "Taux Droit de Douane (DD)": f"{item['dd']} %",
            "Description Règlementaire": item["desc"]
        })

    df_grid = pd.DataFrame(grid_data)
    st.dataframe(df_grid, use_container_width=True)

# =========================================================
# 6. PAGE 3 : MOTEUR DE CALCUL & FISCALITÉ
# =========================================================
elif navigation == "⚙️ Moteur de Calcul & Taxes SYDAM":
    st.title("⚙️ Moteur de Calcul SYDAM & Fiscalité Douanière")
    st.markdown("---")

    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.subheader("1. Formules de Liquidation des Taxes")
        st.markdown("""
        * **Valeur CAF :** `FOB + Fret + Insurance (0.5%)`
        * **Droit de Douane (DD) :** `CAF × Taux DD (0%, 5%, 10%, 20%)`
        * **Redevance Statistique (RSE) :** `CAF × 1,0 %`
        * **Prélèvement UEMOA (PCS) :** `CAF × 0,8 %`
        * **Prélèvement CEDEAO (PC) :** `CAF × 0,5 %`
        * **Base Imposable TVA :** `CAF + DD + RSE + PCS + PC`
        * **TVA à l'Importation :** `Base TVA × 18,0 %`
        """)

    with col_g2:
        st.image("https://images.unsplash.com/photo-1578575437130-527eed3abbec?auto=format&fit=crop&w=600&q=80", caption="Gestion des Containers & Fret Maritime à Abidjan", use_container_width=True)

    st.subheader("2. Différence entre Taxes Douanières et Frais de Transit")
    st.warning(
        "**Important :** Ce calculateur évalue avec une précision chirurgicale l'intégralité des **droits et taxes perçus par l'État Ivoirien**. "
        "Il convient d'ajouter à cette cotation les frais de débarquement (acconage/manutention) et les honoraires de votre transitaire."
    )
