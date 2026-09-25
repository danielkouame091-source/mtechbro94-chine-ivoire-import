import sqlite3
import pandas as pd
import streamlit as st

# Importation sécurisée de Groq (si disponible)
try:
  from groq import Groq
except ImportError:
  Groq = None

# Configuration de la page Streamlit
st.set_page_config(
    page_title="SNDGIR - Système National Douanier",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Style CSS personnalisé pour des cartes avec effet 3D léger
st.markdown(
    """
    <style>
    .custom-card-3d {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1), 0 1px 3px rgba(0,0,0,0.08);
        margin-bottom: 20px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

DB_NAME = "sndgir_database.db"

# =========================================================
# INITIALISATION DE LA BASE DE DONNÉES ET DES TABLES
# =========================================================


def init_db():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()

  # Table des utilisateurs
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL,
            statut TEXT NOT NULL
        )
    """)

  # Table des journaux d'audit
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            action TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

  # Insertion d'utilisateurs par défaut si la table est vide
  cursor.execute("SELECT COUNT(*) FROM users")
  if cursor.fetchone()[0] == 0:
    cursor.execute(
        "INSERT INTO users (username, role, statut) VALUES (?, ?, ?)",
        ("admin", "Administrateur Système", "Actif"),
    )
    cursor.execute(
        "INSERT INTO users (username, role, statut) VALUES (?, ?, ?)",
        ("agent1", "Agent des Douanes", "Actif"),
    )

  conn.commit()
  conn.close()


init_db()


# Fonction utilitaire pour enregistrer les actions dans les logs d'audit
def log_action(username, action):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "INSERT INTO audit_logs (username, action) VALUES (?, ?)",
      (username, action),
  )
  conn.commit()
  conn.close()


# =========================================================
# GESTION DE LA SESSION ET AUTHENTIFICATION
# =========================================================
if "authenticated" not in st.session_state:
  st.session_state.authenticated = False
if "username" not in st.session_state:
  st.session_state.username = ""
if "user_role" not in st.session_state:
  st.session_state.user_role = ""

# Écran de connexion si l'utilisateur n'est pas authentifié
if not st.session_state.authenticated:
  st.title("🔐 Connexion - SNDGIR")
  col1, col2 = st.columns(2)
  with col1:
    input_user = st.text_input(
        "Nom d'utilisateur (essayez 'admin' ou 'agent1')"
    )
    if st.button("Se connecter", use_container_width=True):
      conn = sqlite3.connect(DB_NAME)
      cursor = conn.cursor()
      cursor.execute(
          "SELECT role, statut FROM users WHERE username = ?", (input_user,)
      )
      user_data = cursor.fetchone()
      conn.close()

      if user_data and user_data[1] == "Actif":
        st.session_state.authenticated = True
        st.session_state.username = input_user
        st.session_state.user_role = user_data[0]
        log_action(input_user, "Connexion réussie au système")
        st.rerun()
      else:
        st.error(
            "Utilisateur inconnu ou compte inactif. Essayez 'admin' ou"
            " 'agent1'."
        )
  st.stop()

# =========================================================
# INTERFACE PRINCIPALE (APRÈS AUTHENTIFICATION)
# =========================================================
st.sidebar.title("🛠️ Paramètres & Session")
st.sidebar.write(f"**Utilisateur :** {st.session_state.username}")
st.sidebar.write(f"**Rôle :** {st.session_state.user_role}")

# Récupération sécurisée de la clé API Groq (via st.secrets ou saisie manuelle)
groq_api_key = st.secrets.get("GROQ_API_KEY", "")
if not groq_api_key:
  groq_api_key = st.sidebar.text_input(
      "Clé API Groq", type="password", value=""
  )

if st.sidebar.button("Se déconnecter", use_container_width=True):
  log_action(st.session_state.username, "Déconnexion du système")
  st.session_state.authenticated = False
  st.session_state.username = ""
  st.session_state.user_role = ""
  st.rerun()

st.title("🇨🇮 Système National Douanier (SNDGIR)")

# Définition des 8 onglets principaux de l'application
(
    tab_dash,
    tab_manifest,
    tab_dec,
    tab_liq,
    tab_bae,
    tab_code,
    tab_ai,
    tab_admin,
) = st.tabs([
    "📊 Tableau de Bord",
    "🚢 Manifeste",
    "📝 Déclaration",
    "💰 Liquidation",
    "✅ BAE",
    "📖 Code des Douanes",
    "🤖 Assistant IA",
    "🔐 Administration",
])

# =========================================================
# TAB 1 : TABLEAU DE BORD GÉNÉRAL
# =========================================================
with tab_dash:
  st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
  st.subheader("📊 Tableau de Bord Général")
  col1, col2, col3 = st.columns(3)
  col1.metric("Déclarations du jour", "142", "+12%")
  col2.metric("Droits liquidés (XOF)", "45.2M", "+5.4%")
  col3.metric("BAE délivrés", "128", "98%")
  st.markdown("</div>", unsafe_allow_html=True)

# =========================================================
# TAB 2 : MANIFESTE DE CARGAISON
# =========================================================
with tab_manifest:
  st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
  st.subheader("🚢 Module 2 : Gestion des Manifestes de Cargaison")
  st.text_input("Numéro de Manifeste", placeholder="EX: MAN202600123")
  st.text_input("Compagnie de Transport / Navire")
  if st.button("Enregistrer le Manifeste"):
    log_action(st.session_state.username, "Enregistrement d'un manifeste")
    st.success("Manifeste enregistré avec succès.")
  st.markdown("</div>", unsafe_allow_html=True)

# =========================================================
# TAB 3 : DÉCLARATION EN DÉTAIL (SAD)
# =========================================================
with tab_dec:
  st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
  st.subheader("📝 Module 3 : Déclaration en Détail (SAD)")
  st.text_input("Référence de la Déclaration")
  st.selectbox(
      "Régime Douanier", ["Importation définitive", "Transit", "Entrepôt"]
  )
  if st.button("Soumettre la Déclaration"):
    log_action(st.session_state.username, "Soumission d'une déclaration")
    st.success("Déclaration enregistrée.")
  st.markdown("</div>", unsafe_allow_html=True)

# =========================================================
# TAB 4 : LIQUIDATION DES DROITS ET TAXES
# =========================================================
with tab_liq:
  st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
  st.subheader("💰 Module 4 : Liquidation des Droits et Taxes")
  st.text_input("Rechercher par N° de Déclaration")
  st.info(
      "Montant estimé des droits : 1 250 000 XOF (Droits de douane, TVA, PC)"
  )
  if st.button("Valider la Liquidation"):
    log_action(st.session_state.username, "Validation liquidation")
    st.success("Liquidation validée.")
  st.markdown("</div>", unsafe_allow_html=True)

# =========================================================
# TAB 5 : BON À ENLEVER (BAE)
# =========================================================
with tab_bae:
  st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
  st.subheader("✅ Module 5 : Délivrance du Bon à Enlever (BAE)")
  st.text_input("N° de Quittance de Paiement")
  if st.button("Générer le BAE"):
    log_action(st.session_state.username, "Génération BAE")
    st.success("BAE généré avec succès ! Marchandise libérable.")
  st.markdown("</div>", unsafe_allow_html=True)

# =========================================================
# TAB 6 : CODE DES DOUANES & LÉGISLATION
# =========================================================
with tab_code:
  st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
  st.subheader("📖 Module 6 : Code des Douanes & Réglementation Nationale")
  st.text_input(
      "Rechercher dans la réglementation ou nomenclature SH", value="Taxation"
  )
  st.markdown("""
    * **Article 15 :** Obligation de dépôt du manifeste de cargaison dès l'arrivée du moyen de transport dans le rayon douanier.
    * **Article 28 :** Régime de la déclaration en détail des marchandises (SAD - Single Administrative Document).
    * **Article 45 :** Modalités de liquidation des droits et taxes exigibles à l'importation.
    * **Article 82 :** Conditions d'octroi du Bon à Enlever (BAE) après acquittement total ou constitution de garantie.
    """)
  st.markdown("</div>", unsafe_allow_html=True)

# =========================================================
# TAB 7 : ASSISTANT IA DOUANES (LLAMA 3 / GROQ)
# =========================================================
with tab_ai:
  st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
  st.subheader("🤖 Module 7 : Assistant IA Douanier (Llama 3 via Groq)")

  prompt_ia = st.text_area(
      "Posez votre question réglementaire ou douanière à l'IA :",
      value=(
          "Quelles sont les conditions d'exonération pour le matériel"
          " topographique ?"
      ),
  )

  if st.button("Interroger l'Assistant IA", use_container_width=True):
    if not groq_api_key:
      st.error(
          "Veuillez configurer votre clé API Groq (dans secrets.toml ou via la"
          " barre latérale)."
      )
    elif Groq is None:
      st.error("Le package `groq` n'est pas installé.")
    else:
      try:
        client_groq = Groq(api_key=groq_api_key)
        response = client_groq.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Vous êtes un expert supérieur des douanes et du"
                        " commerce international en Côte d'Ivoire, spécialisé"
                        " dans le système SNDGIR."
                    ),
                },
                {"role": "user", "content": prompt_ia},
            ],
        )
        st.markdown("##### 💡 Réponse de l'Expert IA :")
        st.write(response.choices[0].message.content)

        # Traçabilité de l'action dans les logs
        log_action(
            st.session_state.username,
            f"Interrogation IA sur : {prompt_ia[:30]}...",
        )
      except Exception as e:
        st.error(f"Erreur lors de l'appel à l'API Groq : {e}")

  st.markdown("</div>", unsafe_allow_html=True)

# =========================================================
# TAB 8 : ADMINISTRATION & AUDIT LOGS
# =========================================================
with tab_admin:
  st.markdown('<div class="custom-card-3d">', unsafe_allow_html=True)
  st.subheader("🔐 Module 8 : Administration du Système & Journaux d'Audit")

  if st.session_state.user_role != "Administrateur Système":
    st.warning("⚠️ Accès restreint aux Administrateurs Système.")
  else:
    st.markdown("##### 📋 Journaux d'Audit & Traçabilité des Actions")
    conn = sqlite3.connect(DB_NAME)
    df_logs = pd.read_sql_query(
        "SELECT * FROM audit_logs ORDER BY id DESC", conn
    )
    conn.close()
    st.dataframe(df_logs, use_container_width=True)

    st.markdown("##### 👥 Gestion des Utilisateurs")
    conn = sqlite3.connect(DB_NAME)
    df_users = pd.read_sql_query(
        "SELECT id, username, role, statut FROM users", conn
    )
    conn.close()
    st.dataframe(df_users, use_container_width=True)

  st.markdown("</div>", unsafe_allow_html=True)
