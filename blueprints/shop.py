from flask import Blueprint, render_template
from app import login_required, current_user

shop_bp = Blueprint("shop", __name__)

@shop_bp.route("/shop")
@login_required
def shop_page():
    user = current_user()
    products = [
        {
            "id": "tshirt",
            "title": "RunCoach AI T-shirt",
            "description": "High-quality, breathable running T-shirt with the RunCoach AI logo.",
            "price": "$25.00",
            "image": "tshirt.png"
        },
        {
            "id": "hoodie",
            "title": "Rico Runner hoodie",
            "description": "Warm and stylish hoodie featuring Rico Runner, perfect for warmups.",
            "price": "$45.00",
            "image": "hoodie.png"
        },
        {
            "id": "walker_shirt",
            "title": "Walker-friendly shirt",
            "description": "Relaxed fit, moisture-wicking shirt designed for comfort during long walks.",
            "price": "$22.00",
            "image": "walker_shirt.png"
        },
        {
            "id": "stickers",
            "title": "Sticker pack",
            "description": "Show your love with custom stickers of Rico Runner, Iggy, and Luna.",
            "price": "$5.00",
            "image": "stickers.png"
        }
    ]
    return render_template("shop.html", products=products, current_user=user)
