import os
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/sydam_db")

def upsert_article_douanier(article_data: dict):
    """
    Insère ou met à jour la grille tarifaire d'un article douanier ivoirien.
    """
    query = """
    INSERT INTO tarif_douane_ci (
        code_sh, designation, categorie, droit_douane, tva, rse, pcs, pc, pfi, reference_circulaire, date_mise_a_jour
    ) VALUES (
        %(code_sh)s, %(designation)s, %(categorie)s, %(droit_douane)s, %(tva)s, 
        %(rse)s, %(pcs)s, %(pc)s, %(pfi)s, %(reference_circulaire)s, CURRENT_TIMESTAMP
    )
    ON CONFLICT (code_sh) 
    DO UPDATE SET
        designation = EXCLUDED.designation,
        categorie = EXCLUDED.categorie,
        droit_douane = EXCLUDED.droit_douane,
        tva = EXCLUDED.tva,
        rse = EXCLUDED.rse,
        pcs = EXCLUDED.pcs,
        pc = EXCLUDED.pc,
        pfi = EXCLUDED.pfi,
        reference_circulaire = EXCLUDED.reference_circulaire,
        date_mise_a_jour = CURRENT_TIMESTAMP;
    """
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute(query, article_data)
        conn.commit()
        print(f"✅ Article {article_data['code_sh']} - {article_data['designation']} mis à jour avec succès.")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Erreur lors de la mise à jour : {e}")

# Exemple d'application d'une nouvelle circulaire douanière
nouvelle_circulaire_station_totale = {
    "code_sh": "9015.80.00",
    "designation": "Station Totale Topographique & GNSS/GPS",
    "categorie": "Topographie",
    "droit_douane": 5.0,
    "tva": 18.0,
    "rse": 1.0,
    "pcs": 0.8,
    "pc": 0.5,
    "pfi": 1.0,
    "reference_circulaire": "Circulaire DGD N° 2154 / UEMOA 2026"
}

if __name__ == "__main__":
    upsert_article_douanier(nouvelle_circulaire_station_totale)
