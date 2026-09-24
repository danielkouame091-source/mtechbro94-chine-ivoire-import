import streamlit as st

# Configuration de la page Streamlit
st.set_page_config(
    page_title="China–Côte d'Ivoire Import & Export",
    page_icon="🇨🇮",
    layout="wide"
)

st.title("China–Côte d'Ivoire Import & Export")
st.caption("Plateforme d'estimation conforme au Code des Douanes Ivoirien et au TEC-CEDEAO")

st.markdown("---")

st.header("📋 Calculateur de Devis Douanier (Normes Côte d'Ivoire)")

# Définition des catégories réglementaires
categories = {
    "Informatique, Laptops, Serveurs, Panneaux Solaires (DD 5%)": 5.0,
    "Matériel Réseau, Commutateurs, Intrants (DD 10%)": 10.0,
    "Smartphones, Électronique Grand Public, Accessoires, Électroménager (DD 20%)": 20.0,
    "Produits de Luxe ou Biens spécifiques (DD 35%)": 35.0,
    "Biens d'Intérêt Social / Médicaments (DD 0%)": 0.0
}

col_in1, col_in2 = st.columns(2)

with col_in1:
    product_value_cny = st.number_input(
        "Valeur de la marchandise (CNY)", 
        min_value=0.0, 
        value=1000.0, 
        step=50.0,
        help="Prix d'achat global des produits en Yuan"
    )
    
    shipping_cost_cny = st.number_input(
        "Frais de transport / Fret (CNY)", 
        min_value=0.0, 
        value=200.0, 
        step=10.0,
        help="Coût total d'expédition vers la Côte d'Ivoire"
    )

    category_selected = st.selectbox(
        "Catégorie de la marchandise", 
        list(categories.keys()),
        index=2 # Sélection par défaut: 20%
    )

with col_in2:
    exchange_rate = st.number_input(
        "Taux de change (1 CNY en XOF / FCFA)", 
        min_value=1.0, 
        value=82.0, 
        step=0.5,
        help="Taux de conversion appliqué (ex: 82 FCFA pour 1 CNY)"
    )

    apply_insurance = st.checkbox(
        "Appliquer l'assurance forfaitaire douanière (0,5%)", 
        value=True,
        help="La douane ivoirienne ajoute 0,5% de valeur d'assurance par défaut si elle n'est pas fournie."
    )
    
    apply_tva = st.checkbox(
        "Inclure la TVA ivoirienne (18%)", 
        value=True,
        help="TVA obligatoire à l'importation en Côte d'Ivoire."
    )

# --- CALCULS RÉGLEMENTAIRES ---

# 1. Sous-total Coût + Fret (CNY)
subtotal_cny = product_value_cny + shipping_cost_cny

# 2. Assurance douanière (0.5% si activée)
insurance_cny = (product_value_cny + shipping_cost_cny) * 0.005 if apply_insurance else 0.0

# 3. Valeur CAF en CNY puis conversion en FCFA (XOF)
caf_cny = subtotal_cny + insurance_cny
caf_xof = caf_cny * exchange_rate

# 4. Taux de droit de douane retenu
duty_rate = categories[category_selected]

# 5. Calcul des Taxes douanières en FCFA
dd_xof = caf_xof * (duty_rate / 100.0)             # Droit de Douane (DD)
rse_xof = caf_xof * 0.010                          # Redevance Statistique (1.0%)
pcs_xof = caf_xof * 0.008                          # PCS UEMOA (0.8%)
pc_xof = caf_xof * 0.005                           # PC CEDEAO (0.5%)

taxes_annexes_xof = rse_xof + pcs_xof + pc_xof

# 6. Assiette de calcul de la TVA
base_tva_xof = caf_xof + dd_xof + taxes_annexes_xof
tva_xof = base_tva_xof * 0.18 if apply_tva else 0.0

# 7. Totaux
total_douane_taxes_xof = dd_xof + taxes_annexes_xof + tva_xof
marchandise_fret_xof = subtotal_cny * exchange_rate
cout_total_importation_xof = marchandise_fret_xof + total_douane_taxes_xof

# --- AFFICHAGE DU DEVIS COMPLET ---

st.markdown("---")
st.subheader("📊 Résultats & Devis Douanier détaillé (FCFA)")

m1, m2, m3 = st.columns(3)
m1.metric("Valeur CAF Imposable", f"{caf_xof:,.0f} FCFA".replace(",", " "))
m2.metric("Total Droits & Taxes Douane", f"{total_douane_taxes_xof:,.0f} FCFA".replace(",", " "))
m3.metric("Coût Total Global Estimé", f"{cout_total_importation_xof:,.0f} FCFA".replace(",", " "))

st.markdown("#### 📑 Détail du décompte officiel de la Douane :")

col_det1, col_det2 = st.columns(2)

with col_det1:
    st.write(f"• **Achat + Fret (CNY) :** `{subtotal_cny:,.2f} CNY`")
    st.write(f"• **Valeur CAF retenue :** `{caf_xof:,.0f} FCFA` *(Base imposable de départ)*")
    st.write(f"• **Droit de Douane (DD - {duty_rate}%) :** `{dd_xof:,.0f} FCFA`")

with col_det2:
    st.write(f"• **Redevance Statistique (RSE - 1%) :** `{rse_xof:,.0f} FCFA`")
    st.write(f"• **Prélèvements Communautaires (PCS + PC - 1,3%) :** `{pcs_xof + pc_xof:,.0f} FCFA`")
    st.write(f"• **TVA à l'importation (18%) :** `{tva_xof:,.0f} FCFA`")

st.info("💡 **Remarque :** Ce devis respecte le système de dédouanement ivoirien (SYDAM). Les frais de transitaires locaux ou de manutention au port/aéroport d'Abidjan ne sont pas inclus dans cette estimation douanière directe.")