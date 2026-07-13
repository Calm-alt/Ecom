from flask import Blueprint, render_template, redirect, url_for, request, abort, flash
from flask_login import login_required, current_user
from functools import wraps
from website.models import Product, Order, Variant
from website import db

admin = Blueprint('admin', __name__)

CATEGORIES = ['Shirts', 'Jackets', 'Shoes', 'Pants', 'Accessories']


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return func(*args, **kwargs)
    return wrapper


@admin.route('/admin')
@login_required
@admin_required
def dashboard():
    products = Product.query.order_by(Product.id.desc()).all()
    orders = Order.query.order_by(Order.date_created.desc()).all()
    return render_template('admin_dashboard.html', products=products, orders=orders)


@admin.route('/admin/update-variant-stock/<int:variant_id>', methods=['POST'])
@login_required
@admin_required
def update_variant_stock(variant_id):
    variant = Variant.query.get_or_404(variant_id)
    variant.stock = int(request.form.get('stock', 0))
    db.session.commit()
    flash('Stock updated.', 'success')
    return redirect(url_for('admin.dashboard'))


@admin.route('/admin/update-order/<int:order_id>', methods=['POST'])
@login_required
@admin_required
def update_order(order_id):
    order = Order.query.get_or_404(order_id)
    order.status = request.form.get('status')
    db.session.commit()
    flash(f'Order #{order.id} marked {order.status}.', 'success')
    return redirect(url_for('admin.dashboard'))


@admin.route('/admin/add-product', methods=['GET', 'POST'])
@login_required
@admin_required
def add_product():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        price = request.form.get('price')
        description = request.form.get('description', '').strip()
        image_url = request.form.get('image_url', '').strip() or 'placeholder.svg'
        category = request.form.get('category')
        sizes_raw = request.form.get('sizes', '')

        if not name or not price or not sizes_raw:
            flash('Name, price, and sizes are required.', 'error')
            return redirect(url_for('admin.add_product'))

        new_product = Product(name=name, price=float(price), description=description, image_url=image_url, category=category)
        db.session.add(new_product)
        db.session.flush()

        try:
            for pair in sizes_raw.split(','):
                size, stock = pair.strip().split(':')
                db.session.add(Variant(product_id=new_product.id, size=size.strip(), stock=int(stock.strip())))
        except ValueError:
            db.session.rollback()
            flash('Sizes must look like "S:10, M:15, L:5".', 'error')
            return redirect(url_for('admin.add_product'))

        db.session.commit()
        flash(f'{name} added.', 'success')
        return redirect(url_for('admin.dashboard'))

    return render_template('admin_add_product.html', categories=CATEGORIES)


@admin.route('/admin/edit-product/<int:product_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)

    if request.method == 'POST':
        product.name = request.form.get('name', '').strip()
        product.price = float(request.form.get('price'))
        product.description = request.form.get('description', '').strip()
        product.image_url = request.form.get('image_url', '').strip() or 'placeholder.svg'
        product.category = request.form.get('category')
        db.session.commit()
        flash('Product updated.', 'success')
        return redirect(url_for('admin.dashboard'))

    return render_template('admin_edit_product.html', product=product, categories=CATEGORIES)


@admin.route('/admin/delete-product/<int:product_id>', methods=['POST'])
@login_required
@admin_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    Variant.query.filter_by(product_id=product.id).delete()
    db.session.delete(product)
    db.session.commit()
    flash('Product deleted.', 'success')
    return redirect(url_for('admin.dashboard'))


@admin.route('/admin/add-variant/<int:product_id>', methods=['POST'])
@login_required
@admin_required
def add_variant(product_id):
    size = request.form.get('size', '').strip()
    stock = request.form.get('stock', '0').strip()
    if size:
        db.session.add(Variant(product_id=product_id, size=size, stock=int(stock or 0)))
        db.session.commit()
        flash(f'Added size {size}.', 'success')
    return redirect(url_for('admin.dashboard'))
