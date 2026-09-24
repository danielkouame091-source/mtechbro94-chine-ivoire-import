import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "transit_enterprise.db"


def init_tarif_base():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT UNIQUE,
            sh TEXT,
            dd REAL,
            categorie TEXT
        )
        """
    )

    default_data = [
        ("Station Totale Topographique & GNSS/GPS", "9015.80.00", 5.0, "Topographie"),
        ("Théodolites, Niveaux Optiques & Laser", "9015.10.00", 5.0, "Topographie"),
        ("Smartphones, iPhones & Téléphones portables", "8517.13.00", 20.0, "High-Tech"),
        ("Ordinateurs Portables, MacBooks & Tablettes", "8471.30.00", 5.0, "Informatique"),
        ("Panneaux Photovoltaïques / Solaires", "8541.43.00", 5.0, "Énergie"),
        ("Groupes Électrogènes (Générateurs)", "8502.11.00", 5.0, "Machines"),
    ]

    cursor.executemany(
        "INSERT OR IGNORE INTO articles (nom, sh, dd, categorie) VALUES (?, ?, ?, ?)",
        default_data,
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_tarif_base()
    print(f"Base tarifaire initialisée : {DB_PATH}")
