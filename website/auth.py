from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required
from website.models import User, CartItem, Variant
from website import db

auth = Blueprint('auth', __name__)


def merge_guest_cart(user):
    """Move anything the person added to their cart before logging in into their real account."""
    guest_cart = session.get('cart', [])
    for entry in guest_cart:
        variant = Variant.query.filter_by(product_id=entry['product_id'], size=entry['size']).first()
        if not variant:
            continue
        existing = CartItem.query.filter_by(user_id=user.id, product_id=entry['product_id'], size=entry['size']).first()
        if existing:
            existing.quantity += entry['quantity']
        else:
            db.session.add(CartItem(user_id=user.id, product_id=entry['product_id'], size=entry['size'], quantity=entry['quantity']))
    db.session.commit()
    session.pop('cart', None)


@auth.route('/sign-up', methods=['GET', 'POST'])
def sign_up():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user_name = request.form.get('userName', '').strip()
        password1 = request.form.get('password1', '')

        if not email or not user_name or not password1:
            flash('Please fill out every field.', 'error')
            return redirect(url_for('auth.sign_up'))

        if len(password1) < 4:
            flash('Password must be at least 4 characters.', 'error')
            return redirect(url_for('auth.sign_up'))

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('An account with that email already exists. Try logging in instead.', 'error')
            return redirect(url_for('auth.sign_up'))

        new_user = User(
            email=email,
            user_name=user_name,
            password=generate_password_hash(password1)
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        merge_guest_cart(new_user)
        flash(f'Welcome, {new_user.user_name}!', 'success')

        if request.args.get('next') == 'checkout':
            return redirect(url_for('views.cart'))
        return redirect(url_for('views.home'))

    return render_template('signup.html')


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            merge_guest_cart(user)
            flash(f'Welcome back, {user.user_name}!', 'success')

            if request.args.get('next') == 'checkout':
                return redirect(url_for('views.cart'))
            return redirect(url_for('views.home'))
        else:
            flash('Incorrect email or password.', 'error')
            return redirect(url_for('auth.login'))

    return render_template('login.html')


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('auth.login'))