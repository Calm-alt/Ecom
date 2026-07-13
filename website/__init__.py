import os
from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user

db = SQLAlchemy()


def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY",
        "change-this-later"
    )

    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL",
        "sqlite:///database.db"
    )

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    from website.models import User, CartItem

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(id):
        return User.query.get(int(id))

    @app.context_processor
    def inject_cart_count():
        if current_user.is_authenticated:
            count = sum(
                item.quantity
                for item in CartItem.query.filter_by(user_id=current_user.id).all()
            )
        else:
            count = sum(
                entry["quantity"]
                for entry in session.get("cart", [])
            )
        return {"cart_count": count}

    from website.auth import auth
    from website.views import views
    from website.admin import admin

    app.register_blueprint(auth, url_prefix="/")
    app.register_blueprint(views, url_prefix="/")
    app.register_blueprint(admin, url_prefix="/")

    with app.app_context():
        db.create_all()

        ADMIN_EMAIL = "kamranopu07@gmail.com"

        admin_user = User.query.filter_by(email=ADMIN_EMAIL).first()

        if admin_user and not admin_user.is_admin:
            admin_user.is_admin = True
            db.session.commit()

    return app