from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_required, current_user
from website.models import Product, CartItem, Order, OrderItem, Variant
from website import db

views = Blueprint('views', __name__)

CATEGORIES = ['Shirts', 'Jackets', 'Shoes', 'Pants', 'Accessories']


@views.route('/')
def home():
    category = request.args.get('category')
    search = request.args.get('search')

    query = Product.query
    if category:
        query = query.filter_by(category=category)
    if search:
        query = query.filter(Product.name.ilike(f'%{search}%'))

    products = query.order_by(Product.id.desc()).all()
    return render_template(
        'home.html',
        products=products,
        categories=CATEGORIES,
        selected_category=category,
        search=search
    )


@views.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template('product_detail.html', product=product)


@views.route('/add-to-cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    size = request.form.get('size')
    product = Product.query.get_or_404(product_id)

    variant = Variant.query.filter_by(product_id=product_id, size=size).first()
    if not variant or variant.stock < 1:
        flash('Sorry, that size is out of stock.', 'error')
        return redirect(url_for('views.product_detail', product_id=product_id))

    if current_user.is_authenticated:
        existing_item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id, size=size).first()
        if existing_item:
            if existing_item.quantity + 1 > variant.stock:
                flash('No more stock available for that size.', 'error')
                return redirect(url_for('views.product_detail', product_id=product_id))
            existing_item.quantity += 1
        else:
            db.session.add(CartItem(user_id=current_user.id, product_id=product_id, size=size, quantity=1))
        db.session.commit()
    else:
        cart = session.get('cart', [])
        for entry in cart:
            if entry['product_id'] == product_id and entry['size'] == size:
                if entry['quantity'] + 1 > variant.stock:
                    flash('No more stock available for that size.', 'error')
                    return redirect(url_for('views.product_detail', product_id=product_id))
                entry['quantity'] += 1
                break
        else:
            cart.append({'product_id': product_id, 'size': size, 'quantity': 1})
        session['cart'] = cart
        session.modified = True

    flash(f'{product.name} ({size}) added to your cart.', 'success')
    return redirect(url_for('views.product_detail', product_id=product_id))


@views.route('/cart')
def cart():
    if current_user.is_authenticated:
        db_items = CartItem.query.filter_by(user_id=current_user.id).all()
        cart_items = [
            {'key': f'd-{i.id}', 'product': i.product, 'size': i.size, 'quantity': i.quantity}
            for i in db_items
        ]
    else:
        cart_items = []
        for entry in session.get('cart', []):
            product = Product.query.get(entry['product_id'])
            if product:
                cart_items.append({
                    'key': f"g-{entry['product_id']}-{entry['size']}",
                    'product': product,
                    'size': entry['size'],
                    'quantity': entry['quantity']
                })

    total = sum(i['product'].price * i['quantity'] for i in cart_items)
    return render_template('cart.html', cart_items=cart_items, total=total)


@views.route('/update-cart-item/<key>', methods=['POST'])
def update_cart_item(key):
    new_qty = int(request.form.get('quantity', 1))

    if key.startswith('d-'):
        if not current_user.is_authenticated:
            return redirect(url_for('views.cart'))
        item = CartItem.query.get_or_404(int(key[2:]))
        if item.user_id != current_user.id:
            flash('Not authorized.', 'error')
            return redirect(url_for('views.cart'))
        variant = Variant.query.filter_by(product_id=item.product_id, size=item.size).first()
        if new_qty <= 0:
            db.session.delete(item)
        elif variant and new_qty > variant.stock:
            flash(f'Only {variant.stock} left in stock for that size.', 'error')
        else:
            item.quantity = new_qty
        db.session.commit()

    elif key.startswith('g-'):
        product_id_str, size = key[2:].split('-', 1)
        product_id = int(product_id_str)
        variant = Variant.query.filter_by(product_id=product_id, size=size).first()
        cart = session.get('cart', [])
        for entry in cart:
            if entry['product_id'] == product_id and entry['size'] == size:
                if new_qty <= 0:
                    cart.remove(entry)
                elif variant and new_qty > variant.stock:
                    flash(f'Only {variant.stock} left in stock for that size.', 'error')
                else:
                    entry['quantity'] = new_qty
                break
        session['cart'] = cart
        session.modified = True

    return redirect(url_for('views.cart'))


@views.route('/remove-cart-item/<key>', methods=['POST'])
def remove_cart_item(key):
    if key.startswith('d-'):
        if current_user.is_authenticated:
            item = CartItem.query.get_or_404(int(key[2:]))
            if item.user_id == current_user.id:
                db.session.delete(item)
                db.session.commit()
    elif key.startswith('g-'):
        product_id_str, size = key[2:].split('-', 1)
        product_id = int(product_id_str)
        cart = session.get('cart', [])
        cart = [e for e in cart if not (e['product_id'] == product_id and e['size'] == size)]
        session['cart'] = cart
        session.modified = True

    flash('Item removed from cart.', 'success')
    return redirect(url_for('views.cart'))


@views.route('/checkout', methods=['POST'])
def checkout():
    if not current_user.is_authenticated:
        flash('Please log in or create an account to complete your purchase.', 'error')
        return redirect(url_for('auth.login', next='checkout'))

    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not cart_items:
        return redirect(url_for('views.cart'))

    for item in cart_items:
        variant = Variant.query.filter_by(product_id=item.product_id, size=item.size).first()
        if not variant or variant.stock < item.quantity:
            flash(f'{item.product.name} ({item.size}) no longer has enough stock. Please update your cart.', 'error')
            return redirect(url_for('views.cart'))

    total = sum(item.product.price * item.quantity for item in cart_items)
    new_order = Order(user_id=current_user.id, total=total)
    db.session.add(new_order)
    db.session.flush()

    for item in cart_items:
        order_item = OrderItem(
            order_id=new_order.id,
            product_id=item.product_id,
            size=item.size,
            quantity=item.quantity,
            price_at_purchase=item.product.price
        )
        variant = Variant.query.filter_by(product_id=item.product_id, size=item.size).first()
        variant.stock -= item.quantity
        db.session.add(order_item)
        db.session.delete(item)

    db.session.commit()
    flash('Order placed successfully!', 'success')
    return redirect(url_for('views.order_confirmation', order_id=new_order.id))


@views.route('/order-confirmation/<int:order_id>')
@login_required
def order_confirmation(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template('order_confirmation.html', order=order)


@views.route('/my-orders')
@login_required
def my_orders():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.date_created.desc()).all()
    return render_template('my_orders.html', orders=orders)


@views.route('/seed')
def seed():
    if Product.query.first():
        flash('Sample products already exist.', 'error')
        return redirect(url_for('views.home'))

    sample_data = [
        ('Classic T-Shirt', 19.99, 'Soft 100% cotton crewneck tee, everyday essential.', 'tshirt.png', 'Shirts',
         [('S', 10), ('M', 15), ('L', 10), ('XL', 6)]),
        ('Denim Jacket', 59.99, 'Vintage-wash denim jacket with a relaxed fit.', 'jacket.jpg', 'Jackets',
         [('S', 4), ('M', 8), ('L', 6)]),
        ('Everyday Hoodie', 39.99, 'Heavyweight fleece hoodie, brushed interior.', 'hoodie.jpg', 'Shirts',
         [('S', 8), ('M', 12), ('L', 10), ('XL', 5)]),
        ('Running Sneakers', 79.99, 'Lightweight, breathable, built for daily miles.', 'sneakers.jpg', 'Shoes',
         [('8', 5), ('9', 7), ('10', 7), ('11', 4)]),
        ('Slim Chinos', 49.99, 'Tapered stretch-cotton chinos for a clean look.', 'chinos.jpg', 'Pants',
         [('30', 5), ('32', 8), ('34', 6), ('36', 4)]),
        ('Canvas Belt', 14.99, 'Adjustable canvas belt with a brushed metal buckle.', 'belt.jpg', 'Accessories',
         [('One Size', 20)]),
    ]

    for name, price, desc, img, category, sizes in sample_data:
        product = Product(name=name, price=price, description=desc, image_url=img, category=category)
        db.session.add(product)
        db.session.flush()
        for size, stock in sizes:
            db.session.add(Variant(product_id=product.id, size=size, stock=stock))

    db.session.commit()
    flash('Sample products added!', 'success')
    return redirect(url_for('views.home'))