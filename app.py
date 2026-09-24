cat << 'EOF' > app.py
import urllib.parse
from flask import Flask, jsonify, render_template

app = Flask(__name__)

WHATSAPP_NUMBER = "2250748492991"
PHONE_DISPLAY = "+225 07 48 49 29 91"
CONTACT_EMAIL = "danielkouame091@gmail.com"

PRODUCTS = [
    {
        "id": 1,
        "name": "Smart TV 55\" 4K UHD Smart Android",
        "category": "Télévisions",
        "china_price": 95000,
        "shipping_customs": 40000,
        "your_margin": 25000,
        "badge": "Offre Spéciale",
        "image": "https://images.unsplash.com/photo-1593784991095-a205069470b6?w=600&auto=format&fit=crop&q=60",
        "description": "Qualité d'image 4K, applications intégrées (Netflix, YouTube), Wi-Fi & Bluetooth."
    },
    {
        "id": 2,
        "name": "Moto Tricycle Cargo 250cc (Grand Format)",
        "category": "Motos & Engins",
        "china_price": 750000,
        "shipping_customs": 350000,
        "your_margin": 150000,
        "badge": "Haute Rentabilité",
        "image": "https://images.unsplash.com/photo-1558981806-ec527fa84c39?w=600&auto=format&fit=crop&q=60",
        "description": "Châssis renforcé spécial transport lourd. Moteur très robuste pour Abidjan."
    }
]

for p in PRODUCTS:
    p["total_price"] = p["china_price"] + p["shipping_customs"] + p["your_margin"]

def generate_whatsapp_link(product_name, total_price):
    message = f"Bonjour Chine-Ivoire Express !\n\nJe souhaite commander le produit suivant :\n📦 *Produit* : {product_name}\n💰 *Prix Tout Compris* : {total_price:,} FCFA"
    return f"https://wa.me/{WHATSAPP_NUMBER}?text={urllib.parse.quote(message)}"

@app.route('/')
def home():
    products_with_links = []
    for product in PRODUCTS:
        p = product.copy()
        p["whatsapp_url"] = generate_whatsapp_link(p["name"], p["total_price"])
        products_with_links.append(p)
    return render_template('index.html', products=products_with_links, phone_display=PHONE_DISPLAY, email=CONTACT_EMAIL)

if __name__ == '__main__':
    app.run(debug=True, port=5001)
EOF