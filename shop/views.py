from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from datetime import datetime
from django.db.models import Sum, F, DecimalField, ExpressionWrapper
from django.http import HttpResponse, JsonResponse
from .models import (
    Product,
    Order,
    OrderItem,
    Category,
    Customer,
    CreditEntry,
    Wholesaler,
    Purchase,
    PurchaseItem,
    OrderPayment,
    OrderReturn,
    OrderReturnItem,
    MessageTemplate,
    AuditLog,
    Expense,
)

# Helper to check if user is staff (shopkeeper)
def is_shopkeeper(user):
    return user.is_authenticated and user.is_staff

def shop_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect('shop_dashboard')
    else:
        form = AuthenticationForm()
    return render(request, 'shop/login.html', {'form': form})

def shop_logout(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('product_list')


def _audit_log(user, action, model_name, object_id, field, old_value, new_value):
    AuditLog.objects.create(
        user=user if user.is_authenticated else None,
        action=action,
        model=model_name,
        object_id=object_id,
        field=field,
        old_value=str(old_value) if old_value is not None else "",
        new_value=str(new_value) if new_value is not None else "",
    )

@login_required
@user_passes_test(is_shopkeeper)
def shop_dashboard(request):
    Product.objects.filter(stock_quantity=0, is_active=True).update(is_active=False)
    products = Product.objects.order_by("stock_quantity", "name")
    orders = Order.objects.order_by("-created_at").prefetch_related("items__product")[:10]
    price_expr = ExpressionWrapper(
        F("unit_price") * F("quantity"),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )
    gross_sales = (
        OrderItem.objects.filter(order__status__in=["pending", "preparing", "completed", "returned"])
        .aggregate(total=Sum(price_expr))["total"]
        or 0
    )
    return_expr = ExpressionWrapper(
        F("unit_price") * F("quantity"),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )
    returns_total = (
        OrderReturnItem.objects.aggregate(total=Sum(return_expr))["total"] or 0
    )
    total_sales = gross_sales - returns_total
    pending_orders_count = Order.objects.filter(status='pending').count()
    today = timezone.now().date()
    near_expiry_limit = today + timezone.timedelta(days=7)
    
    context = {
        "products": products,
        "recent_orders": orders,
        "total_sales": total_sales,
        "pending_orders_count": pending_orders_count,
        "today": today,
        "near_expiry_limit": near_expiry_limit,
    }
    return render(request, "shop/shop_dashboard.html", context)


@login_required
@user_passes_test(is_shopkeeper)
def manage_orders(request):
    status = request.GET.get("status", "")
    orders = Order.objects.all().order_by("-created_at")
    if status:
        orders = orders.filter(status=status)
    orders = orders.prefetch_related("items__product")

    context = {
        "orders": orders,
        "current_status": status,
        "status_choices": Order.STATUS_CHOICES,
    }
    return render(request, "shop/manage_orders.html", context)


@login_required
@user_passes_test(is_shopkeeper)
def manage_products(request):
    edit_id = request.GET.get("edit")
    product_to_edit = None
    if edit_id:
        product_to_edit = get_object_or_404(Product, id=edit_id)

    if request.method == "POST":
        category_name = (request.POST.get("category_name") or "").strip()
        if category_name:
            category_description = (request.POST.get("category_description") or "").strip()
            category, created = Category.objects.get_or_create(
                name=category_name,
                defaults={"description": category_description},
            )
            if not created and category_description and category.description != category_description:
                category.description = category_description
                category.save(update_fields=["description"])
            messages.success(request, "Category added successfully.")
            return redirect("manage_products")

        product_id = request.POST.get("product_id")
        name = request.POST.get("name", "").strip()
        price = request.POST.get("price") or "0"
        cost_price = request.POST.get("cost_price") or "0"
        discount_price = request.POST.get("discount_price") or "0"
        stock_quantity = request.POST.get("stock_quantity") or "0"
        category_id = request.POST.get("category_id") or None
        is_active = request.POST.get("is_active") == "on"

        if not name:
            messages.error(request, "Product name is required.")
            return redirect("manage_products")

        if product_id:
            product = get_object_or_404(Product, id=product_id)
            old_price = product.price
            old_stock = product.stock_quantity
            success_message = "Product updated successfully."
        else:
            product = Product()
            old_price = None
            old_stock = None
            success_message = "Product added successfully."

        product.name = name
        product.price = price
        product.cost_price = cost_price
        product.discount_price = discount_price
        product.stock_quantity = stock_quantity
        product.is_active = is_active
        if category_id:
            product.category_id = category_id
        else:
            product.category = None
        product.save()

        if old_price is not None and str(old_price) != str(product.price):
            _audit_log(
                request.user,
                "price_change",
                "Product",
                product.id,
                "price",
                old_price,
                product.price,
            )
        if old_stock is not None and int(old_stock) != int(product.stock_quantity):
            _audit_log(
                request.user,
                "stock_change",
                "Product",
                product.id,
                "stock_quantity",
                old_stock,
                product.stock_quantity,
            )

        messages.success(request, success_message)
        return redirect("manage_products")

    products = Product.objects.order_by("name")
    categories = Category.objects.order_by("name")

    context = {
        "products": products,
        "categories": categories,
        "product_to_edit": product_to_edit,
    }
    return render(request, "shop/manage_products.html", context)


@login_required
@user_passes_test(is_shopkeeper)
def customer_details(request):
    period = request.GET.get("period", "day")
    customer_filter = request.GET.get("customer", "").strip()

    customers = Customer.objects.filter(is_active=True)
    if customer_filter:
        customers = customers.filter(name__icontains=customer_filter)
    customers = customers.order_by("name")

    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == "day":
        start = today_start
    elif period == "week":
        start = today_start - timezone.timedelta(days=today_start.weekday())
    elif period == "month":
        start = today_start.replace(day=1)
    else:
        start = None

    if start:
        end = now
    else:
        end = None

    price_expr = ExpressionWrapper(
        F("unit_price") * F("quantity"),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )

    customer_rows = []

    for customer in customers:
        orders = Order.objects.all()
        if start and end:
            orders = orders.filter(created_at__gte=start, created_at__lte=end)
        if customer.phone:
            orders = orders.filter(customer_phone=customer.phone)
        else:
            orders = orders.filter(customer_name__iexact=customer.name)

        items = OrderItem.objects.filter(order__in=orders)
        total_products = items.aggregate(total=Sum("quantity"))["total"] or 0
        total_spent = items.aggregate(total=Sum(price_expr))["total"] or 0

        credits = CreditEntry.objects.filter(customer=customer)
        outstanding = (
            credits.filter(is_paid=False).aggregate(total=Sum("amount"))["total"] or 0
        )

        customer_rows.append(
            {
                "customer": customer,
                "total_products": total_products,
                "total_spent": total_spent,
                "outstanding": outstanding,
            }
        )

    context = {
        "customer_rows": customer_rows,
        "current_period": period,
        "current_customer": customer_filter,
    }
    return render(request, "shop/customer_details.html", context)


@login_required
@user_passes_test(is_shopkeeper)
def manage_customers(request):
    edit_id = request.GET.get("edit")
    customer_to_edit = None
    if edit_id:
        customer_to_edit = get_object_or_404(Customer, id=edit_id)

    if request.method == "POST":
        mark_reminder_id = request.POST.get("mark_reminder_id")
        if mark_reminder_id:
            customer = get_object_or_404(Customer, id=mark_reminder_id)
            customer.last_reminder_date = timezone.now().date()
            customer.save(update_fields=["last_reminder_date"])
            messages.success(request, f"Reminder marked sent for {customer.name}.")
            return redirect("manage_customers")

        delete_id = request.POST.get("delete_customer_id")
        if delete_id:
            customer = get_object_or_404(Customer, id=delete_id)
            customer.delete()
            messages.success(request, "Customer deleted successfully.")
            return redirect("manage_customers")

        customer_id = request.POST.get("customer_id")
        name = (request.POST.get("name") or "").strip()
        phone = (request.POST.get("phone") or "").strip()
        address = (request.POST.get("address") or "").strip()
        notes = (request.POST.get("notes") or "").strip()
        is_active = request.POST.get("is_active") == "on"

        if not name:
            messages.error(request, "Customer name is required.")
            return redirect("manage_customers")

        if customer_id:
            customer = get_object_or_404(Customer, id=customer_id)
            message = "Customer updated successfully."
        else:
            customer = Customer()
            message = "Customer added successfully."

        customer.name = name
        customer.phone = phone
        customer.address = address
        customer.notes = notes
        customer.is_active = is_active
        customer.save()

        messages.success(request, message)
        return redirect("manage_customers")

    customers = Customer.objects.order_by("name")
    context = {
        "customers": customers,
        "customer_to_edit": customer_to_edit,
    }
    return render(request, "shop/manage_customers.html", context)


def customer_lookup(request):
    name = (request.GET.get("name") or "").strip()
    if not name:
        return JsonResponse({"found": False})
    customer = (
        Customer.objects.filter(name__iexact=name, is_active=True)
        .order_by("-id")
        .first()
    )
    if not customer:
        return JsonResponse({"found": False})
    return JsonResponse(
        {
            "found": True,
            "name": customer.name,
            "phone": customer.phone,
            "address": customer.address,
        }
    )


def customer_suggest(request):
    q = (request.GET.get("q") or "").strip()
    if not q:
        return JsonResponse({"results": []})
    customers = (
        Customer.objects.filter(is_active=True, name__icontains=q)
        .order_by("name")[:10]
    )
    results = []
    for c in customers:
        results.append(
            {
                "name": c.name,
                "phone": c.phone,
                "address": c.address,
            }
        )
    return JsonResponse({"results": results})

def product_list(request):
    # Fetch all active products
    products = Product.objects.filter(is_active=True).order_by("name")
    categories = Category.objects.all()
    
    # Search functionality
    query = request.GET.get('q')
    if query:
        products = products.filter(name__icontains=query)
        
    # Category filter
    category_id = request.GET.get('category')
    if category_id:
        products = products.filter(category_id=category_id)

    context = {
        "products": products,
        "categories": categories,
        "current_category": int(category_id) if category_id else None,
        "search_query": query,
    }
    return render(request, "shop/product_list.html", context)


@login_required
@user_passes_test(is_shopkeeper)
def pos(request):
    products = Product.objects.filter(is_active=True).order_by("name")
    categories = Category.objects.order_by("name")
    context = {"products": products, "categories": categories}
    return render(request, "shop/pos.html", context)


def _find_product_by_code(code: str):
    code = (code or "").strip()
    if not code:
        return None
    # Try barcode exact match
    try:
        p = Product.objects.get(barcode=code)
        return p
    except Product.DoesNotExist:
        pass
    # Try QR payload exact match
    try:
        p = Product.objects.get(qr_payload=code)
        return p
    except Product.DoesNotExist:
        pass
    # Try numeric ID
    try:
        pid = int(code)
        return Product.objects.filter(id=pid).first()
    except ValueError:
        return None


def scan_add_to_cart(request):
    code = request.GET.get("code") or request.POST.get("code") or ""
    qty_text = request.GET.get("qty") or request.POST.get("qty") or "1"
    product = _find_product_by_code(code)
    if product is None or not product.is_active:
        messages.error(request, "Product not found for the scanned code.")
        return redirect("product_list")
    try:
        qty = int(qty_text)
    except ValueError:
        qty = 1
    if qty < 1:
        qty = 1
    cart = request.session.get("cart", {})
    key = str(product.id)
    cart[key] = cart.get(key, 0) + qty
    request.session["cart"] = cart
    messages.success(request, f"Added {qty} x {product.name} to cart")
    return redirect("cart_summary")


@login_required
@user_passes_test(is_shopkeeper)
def scan_stock_increment(request):
    code = request.GET.get("code") or request.POST.get("code") or ""
    delta_text = request.GET.get("delta") or request.POST.get("delta") or "1"
    product = _find_product_by_code(code)
    if product is None:
        messages.error(request, "Product not found for the scanned code.")
        return redirect("sales_dashboard")
    try:
        delta = int(delta_text)
    except ValueError:
        delta = 1
    if delta < 1:
        delta = 1
    old_stock = product.stock_quantity
    product.stock_quantity = product.stock_quantity + delta
    product.save(update_fields=["stock_quantity"])

    _audit_log(
        request.user,
        "stock_change",
        "Product",
        product.id,
        "stock_quantity",
        old_stock,
        product.stock_quantity,
    )

    messages.success(request, f"Stock updated: {product.name} +{delta}")
    return redirect("sales_dashboard")


@login_required
@user_passes_test(is_shopkeeper)
def price_checker(request):
    code = ""
    product = None
    if request.method == "POST":
        code = request.POST.get("code", "").strip()
        if code:
            product = _find_product_by_code(code)
            if product is None:
                messages.error(request, "Product not found for the scanned code.")
    else:
        code = request.GET.get("code", "").strip()
        if code:
            product = _find_product_by_code(code)
            if product is None:
                messages.error(request, "Product not found for the scanned code.")
    context = {
        "code": code,
        "product": product,
    }
    return render(request, "shop/price_checker.html", context)


def add_to_cart(request, product_id):
    cart = request.session.get('cart', {})
    product_id_str = str(product_id)
    qty = 1
    if request.method == "POST":
        try:
            qty = int(request.POST.get('quantity', '1'))
        except ValueError:
            qty = 1
        if qty < 1:
            qty = 1
    if product_id_str in cart:
        cart[product_id_str] += qty
    else:
        cart[product_id_str] = qty
    request.session['cart'] = cart
    if request.method == "POST":
        return redirect('cart_summary')
    messages.success(request, "Item added to cart")
    return redirect('product_list')

def update_cart(request, product_id):
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
        cart = request.session.get('cart', {})
        product_id_str = str(product_id)
        
        if quantity > 0:
            cart[product_id_str] = quantity
            messages.success(request, "Cart updated")
        else:
            if product_id_str in cart:
                del cart[product_id_str]
                messages.success(request, "Item removed from cart")
        
        request.session['cart'] = cart
    return redirect('cart_summary')

def remove_from_cart(request, product_id):
    cart = request.session.get('cart', {})
    product_id_str = str(product_id)
    
    if product_id_str in cart:
        del cart[product_id_str]
        request.session['cart'] = cart
        messages.success(request, "Item removed from cart")
    
    return redirect('cart_summary')

def cart_summary(request):
    cart = request.session.get('cart', {})
    cart_items = []
    total_amount = 0
    
    products = Product.objects.filter(id__in=cart.keys())
    
    for product in products:
        quantity = cart[str(product.id)]
        price = product.price - product.discount_price
        subtotal = price * quantity
        total_amount += subtotal
        cart_items.append({
            'product': product,
            'quantity': quantity,
            'subtotal': subtotal,
            'unit_price': price,
            'discount': product.discount_price
        })
    
    context = {
        'cart_items': cart_items,
        'cart_total': total_amount
    }
    return render(request, 'shop/cart_summary.html', context)

def checkout(request):
    cart = request.session.get('cart', {})
    if not cart:
        messages.warning(request, "Your cart is empty")
        return redirect('product_list')
        
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        method1 = request.POST.get('payment_method_1')
        amount1 = request.POST.get('payment_amount_1') or "0"
        method2 = request.POST.get('payment_method_2')
        amount2 = request.POST.get('payment_amount_2') or "0"
        ref1 = request.POST.get('payment_ref_1', "")
        ref2 = request.POST.get('payment_ref_2', "")
        
        if name and phone and address:
            customer, created = Customer.objects.get_or_create(
                name=name,
                defaults={"phone": phone, "address": address}
            )
            if not created:
                updated_fields = []
                if phone and customer.phone != phone:
                    customer.phone = phone
                    updated_fields.append("phone")
                if address and customer.address != address:
                    customer.address = address
                    updated_fields.append("address")
                if updated_fields:
                    customer.save(update_fields=updated_fields)

            order = Order.objects.create(
                customer_name=name,
                customer_phone=phone,
                customer_address=address,
                status='pending'
            )
            
            products = Product.objects.filter(id__in=cart.keys())
            for product in products:
                quantity = cart[str(product.id)]
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    unit_price=product.price,
                    discount_amount=product.discount_price
                )
                old_stock = product.stock_quantity
                if product.stock_quantity >= quantity:
                    product.stock_quantity = product.stock_quantity - quantity
                else:
                    product.stock_quantity = 0
                product.save(update_fields=["stock_quantity"])

                _audit_log(
                    request.user,
                    "stock_change",
                    "Product",
                    product.id,
                    "stock_quantity",
                    old_stock,
                    product.stock_quantity,
                )

            total_amount = 0
            for product in products:
                price = product.price - product.discount_price
                total_amount += price * cart[str(product.id)]
            try:
                a1 = float(amount1)
            except ValueError:
                a1 = 0
            try:
                a2 = float(amount2)
            except ValueError:
                a2 = 0
            if method1 and a1 > 0:
                OrderPayment.objects.create(
                    order=order, method=method1, amount=a1, reference=ref1
                )
            if method2 and a2 > 0:
                OrderPayment.objects.create(
                    order=order, method=method2, amount=a2, reference=ref2
                )
            if round((a1 + a2), 2) != round(float(total_amount), 2):
                messages.warning(request, "Payment total does not match order total.")
            
            request.session['cart'] = {}
            messages.success(request, f"Order #{order.id} placed successfully!")
            return redirect('order_success', order_id=order.id)
            
    total_amount = 0
    products = Product.objects.filter(id__in=cart.keys())
    for product in products:
        price = product.price - product.discount_price
        total_amount += price * cart[str(product.id)]
        
    return render(request, 'shop/checkout.html', {'total_amount': total_amount})

def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    items = order.items.select_related("product")
    lines = [f"{i.quantity} x {i.product.name} = ₹{i.subtotal}" for i in items]
    payments = order.payments.all()
    pay_lines = [f"{p.method.title()}: ₹{p.amount}" for p in payments]
    text = f"Order #{order.id} - {order.customer_name}\n" + "\n".join(lines) + f"\nTotal: ₹{order.total_amount}\n" + (" | ".join(pay_lines) if pay_lines else "")
    return render(request, 'shop/order_success.html', {'order': order, 'share_text': text})


@login_required
@user_passes_test(is_shopkeeper)
def mark_order_completed(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if order.status != "completed":
        order.status = "completed"
        order.save()
        messages.success(request, "Order marked as completed.")
    else:
        messages.info(request, "Order is already completed.")
    return redirect("shop_dashboard")


@login_required
@user_passes_test(is_shopkeeper)
def sales_dashboard(request):
    if request.method == "POST" and request.POST.get("action") == "export_gst":
        month = request.POST.get("month") or ""
        try:
            year_i, month_i = map(int, month.split("-"))
            start = timezone.datetime(year_i, month_i, 1, tzinfo=timezone.utc)
        except Exception:
            now = timezone.now()
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        items = OrderItem.objects.filter(order__status="completed", order__created_at__gte=start, order__created_at__lt=end)
        price_expr = ExpressionWrapper(F("unit_price") * F("quantity"), output_field=DecimalField(max_digits=12, decimal_places=2))
        tax_expr = ExpressionWrapper(
            F("unit_price") * F("quantity") * (F("product__tax_rate_percent") / 100),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
        rows = (
            items.values("product__name", "product__tax_rate_percent")
            .annotate(
                revenue=Sum(price_expr),
                tax=Sum(tax_expr),
            )
            .order_by("product__name")
        )
        import csv
        response = HttpResponse(content_type="text/csv")
        filename = f"gst_{start.year}_{start.month:02d}.csv"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        writer = csv.writer(response)
        writer.writerow(["Product", "Tax Rate (%)", "Taxable Value", "GST Amount"])
        for r in rows:
            writer.writerow(
                [
                    r["product__name"],
                    float(r["product__tax_rate_percent"] or 0),
                    float(r["revenue"] or 0),
                    float(r["tax"] or 0),
                ]
            )
        return response

    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timezone.timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)
    year_start = today_start.replace(month=1, day=1)

    def sales_stats(start, end):
        price_expr = ExpressionWrapper(
            F("unit_price") * F("quantity"),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
        profit_expr = ExpressionWrapper(
            (F("unit_price") - F("product__cost_price")) * F("quantity"),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
        items = OrderItem.objects.filter(
            order__status__in=["completed", "returned"],
            order__created_at__gte=start,
            order__created_at__lt=end,
        )
        revenue = items.aggregate(total=Sum(price_expr))["total"] or 0
        profit = items.aggregate(total=Sum(profit_expr))["total"] or 0
        # Subtract returns in the same period
        return_items = OrderReturnItem.objects.filter(
            order_return__created_at__gte=start,
            order_return__created_at__lt=end,
        )
        returns_revenue = return_items.aggregate(total=Sum(price_expr))["total"] or 0
        revenue = revenue - returns_revenue
        # Profit impact: subtract unit_price - cost_price for returned quantities
        return_profit_expr = ExpressionWrapper(
            (F("unit_price") - F("product__cost_price")) * F("quantity"),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
        returns_profit = return_items.aggregate(total=Sum(return_profit_expr))["total"] or 0
        profit = profit - returns_profit

        purchase_expr = ExpressionWrapper(
            F("unit_cost") * F("quantity"),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
        purchase_items = PurchaseItem.objects.filter(
            purchase__date__gte=start,
            purchase__date__lt=end,
        )
        spent = purchase_items.aggregate(total=Sum(purchase_expr))["total"] or 0

        # Expenses
        expenses = Expense.objects.filter(
            date__gte=start.date(),
            date__lt=end.date()
        ).aggregate(total=Sum('amount'))['total'] or 0

        return {
            "revenue": revenue,
            "profit": profit,
            "spent": spent,
            "expenses": expenses,
            "net_profit": profit - expenses,
        }

    stats_today = sales_stats(today_start, today_start + timezone.timedelta(days=1))
    stats_week = sales_stats(week_start, week_start + timezone.timedelta(days=7))
    stats_month = sales_stats(month_start, (month_start + timezone.timedelta(days=32)).replace(day=1))
    stats_year = sales_stats(year_start, year_start.replace(year=year_start.year + 1))

    recent_completed_orders = (
        Order.objects.filter(status="completed")
        .order_by("-created_at")[:20]
    )

    products = Product.objects.filter(is_active=True).order_by("name")

    # Top sellers and slow movers (last 30 days)
    last_30 = today_start - timezone.timedelta(days=30)
    oi = OrderItem.objects.filter(
        order__status__in=["completed", "returned"],
        order__created_at__gte=last_30,
        order__created_at__lt=today_start + timezone.timedelta(days=1),
    ).values("product_id", "product__name", "product__category__name")
    returns_oi = OrderReturnItem.objects.filter(
        order_return__created_at__gte=last_30,
        order_return__created_at__lt=today_start + timezone.timedelta(days=1),
    ).values("product_id")
    from collections import defaultdict
    sold_qty = defaultdict(int)
    for row in oi.annotate(qsum=Sum("quantity")):
        sold_qty[row["product_id"]] += int(row["qsum"] or 0)
    for r in returns_oi.annotate(qsum=Sum("quantity")):
        sold_qty[r["product_id"]] -= int(r["qsum"] or 0)
    # Build rows with product info
    prod_info = {p.id: p for p in products}
    rows = []
    for pid, qty in sold_qty.items():
        p = prod_info.get(pid)
        if p:
            rows.append({
                "product": p,
                "category": p.category.name if p.category else "",
                "qty": qty,
            })
    top_sellers = sorted(rows, key=lambda r: r["qty"], reverse=True)[:10]
    slow_movers = sorted(rows, key=lambda r: r["qty"])[:10]

    # Hourly heatmap (last 7 days)
    last_7 = today_start - timezone.timedelta(days=7)
    hourly_counts = [0] * 24
    for o in Order.objects.filter(status__in=["completed", "returned"], created_at__gte=last_7):
        h = o.created_at.hour
        hourly_counts[h] += 1

    # Weekly trends for top 5 products over last 8 weeks
    weeks = []
    week_data = {}
    base = today_start
    for i in range(8):
        start = (base - timezone.timedelta(days=base.weekday())) - timezone.timedelta(weeks=i)
        end = start + timezone.timedelta(days=7)
        weeks.append(start.date())
        items = OrderItem.objects.filter(order__status__in=["completed", "returned"], order__created_at__gte=start, order__created_at__lt=end).values("product_id").annotate(qsum=Sum("quantity"))
        for it in items:
            pid = it["product_id"]
            week_data.setdefault(pid, [0] * 8)
            week_data[pid][7 - i] = int(it["qsum"] or 0)
    trend_products = [r["product"].id for r in top_sellers[:5]]
    trends = {pid: week_data.get(pid, [0] * 8) for pid in trend_products}

    # Profit by product and category (last 30 days) with returns impact
    price_expr = ExpressionWrapper(F("unit_price") * F("quantity"), output_field=DecimalField(max_digits=12, decimal_places=2))
    profit_expr = ExpressionWrapper((F("unit_price") - F("product__cost_price")) * F("quantity"), output_field=DecimalField(max_digits=12, decimal_places=2))
    base_items = OrderItem.objects.filter(order__status__in=["completed", "returned"], order__created_at__gte=last_30, order__created_at__lt=today_start + timezone.timedelta(days=1))
    by_product = base_items.values("product_id", "product__name", "product__category__name").annotate(
        revenue=Sum(price_expr),
        profit=Sum(profit_expr),
    )
    rprofit_expr = ExpressionWrapper((F("unit_price") - F("product__cost_price")) * F("quantity"), output_field=DecimalField(max_digits=12, decimal_places=2))
    ritems = OrderReturnItem.objects.filter(order_return__created_at__gte=last_30, order_return__created_at__lt=today_start + timezone.timedelta(days=1)).values("product_id").annotate(rprofit=Sum(rprofit_expr), rrev=Sum(price_expr))
    rmap = {row["product_id"]: (row["rrev"] or 0, row["rprofit"] or 0) for row in ritems}
    profit_by_product = []
    for row in by_product:
        rrev, rprof = rmap.get(row["product_id"], (0, 0))
        profit_by_product.append({
            "product_name": row["product__name"],
            "category_name": row["product__category__name"],
            "revenue": (row["revenue"] or 0) - rrev,
            "profit": (row["profit"] or 0) - rprof,
        })
    # Aggregate by category
    from collections import defaultdict as dd
    cat_map = dd(lambda: {"revenue": 0, "profit": 0})
    for p in profit_by_product:
        cat = p["category_name"] or ""
        cat_map[cat]["revenue"] += p["revenue"]
        cat_map[cat]["profit"] += p["profit"]
    profit_by_category = [{"category_name": k, "revenue": v["revenue"], "profit": v["profit"]} for k, v in cat_map.items()]

    # GST summary for current month
    gst_items = base_items.values("product_id", "product__name").annotate(
        revenue=Sum(price_expr),
        tax=Sum(
            ExpressionWrapper(
                F("unit_price") * F("quantity") * (F("product__tax_rate_percent") / 100),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        ),
    )
    gst_summary = list(gst_items)

    context = {
        "stats_today": stats_today,
        "stats_week": stats_week,
        "stats_month": stats_month,
        "stats_year": stats_year,
        "recent_completed_orders": recent_completed_orders,
        "products": products,
        "top_sellers": top_sellers,
        "slow_movers": slow_movers,
        "hourly_counts": hourly_counts,
        "trend_weeks": weeks[::-1],
        "trends": trends,
        "profit_by_product": sorted(profit_by_product, key=lambda r: r["profit"], reverse=True),
        "profit_by_category": sorted(profit_by_category, key=lambda r: r["profit"], reverse=True),
        "gst_summary": gst_summary,
    }
    return render(request, "shop/sales_dashboard.html", context)


@login_required
@user_passes_test(is_shopkeeper)
def suggested_purchases(request):
    today = timezone.now().date()
    near_days = 7
    rows = []
    for p in Product.objects.filter(is_active=True).order_by("name"):
        low = p.stock_quantity <= p.reorder_threshold
        expired = bool(p.expiry_date and p.expiry_date < today)
        near = bool(p.expiry_date and today <= p.expiry_date <= (today + timezone.timedelta(days=near_days)))
        suggested_qty = max(p.reorder_threshold * 2 - p.stock_quantity, 0)
        if low or expired or near:
            rows.append({
                "product": p,
                "low": low,
                "expired": expired,
                "near": near,
                "suggested_qty": suggested_qty,
            })
    return render(request, "shop/suggested_purchases.html", {"rows": rows, "near_days": near_days})


@login_required
@user_passes_test(is_shopkeeper)
def wholesaler_dashboard(request):
    if request.method == "POST":
        wholesaler_id = request.POST.get("wholesaler_id")
        wholesaler_name = (request.POST.get("wholesaler_name") or "").strip()
        wholesaler_phone = (request.POST.get("wholesaler_phone") or "").strip()
        wholesaler_email = ""
        product_id = request.POST.get("product_id")
        new_product_name = (request.POST.get("new_product_name") or "").strip()
        quantity_text = request.POST.get("quantity", "1")
        unit_cost_text = request.POST.get("unit_cost", "0")
        selling_price_text = request.POST.get("selling_price", "0")
        date_text = request.POST.get("date", "")
        expiry_text = request.POST.get("expiry_date", "")

        wholesaler = None
        if wholesaler_id:
            try:
                wholesaler = Wholesaler.objects.get(id=wholesaler_id)
            except Wholesaler.DoesNotExist:
                wholesaler = None
        if wholesaler is None and wholesaler_name:
            wholesaler, _ = Wholesaler.objects.get_or_create(
                name=wholesaler_name,
                defaults={
                    "phone": wholesaler_phone,
                    "email": wholesaler_email,
                },
            )
        if wholesaler is None:
            messages.error(request, "Wholesaler is required.")
            return redirect("wholesaler_dashboard")

        try:
            quantity = int(quantity_text)
        except ValueError:
            quantity = 1
        if quantity < 1:
            quantity = 1

        try:
            unit_cost = float(unit_cost_text)
        except ValueError:
            unit_cost = 0
        if unit_cost <= 0:
            messages.error(request, "Unit cost must be greater than zero.")
            return redirect("wholesaler_dashboard")

        try:
            selling_price = float(selling_price_text)
        except ValueError:
            selling_price = 0
        if selling_price <= 0:
            messages.error(request, "Selling price must be greater than zero.")
            return redirect("wholesaler_dashboard")

        product = None
        if product_id:
            try:
                product = Product.objects.get(id=product_id)
            except (Product.DoesNotExist, ValueError, TypeError):
                product = None
        if product is None and new_product_name:
            product = Product.objects.create(
                name=new_product_name,
                price=selling_price,
                cost_price=unit_cost,
                stock_quantity=0,
                is_active=True,
            )
        if product is None:
            messages.error(request, "Product is required.")
            return redirect("wholesaler_dashboard")

        if date_text:
            try:
                date_value = datetime.strptime(date_text, "%Y-%m-%d")
                date_value = timezone.make_aware(date_value, timezone.get_current_timezone())
            except Exception:
                date_value = timezone.now()
        else:
            date_value = timezone.now()

        if expiry_text:
            try:
                expiry_value = datetime.strptime(expiry_text, "%Y-%m-%d").date()
            except Exception:
                expiry_value = None
        else:
            expiry_value = None

        purchase = Purchase.objects.create(
            wholesaler=wholesaler,
            date=date_value,
        )
        PurchaseItem.objects.create(
            purchase=purchase,
            product=product,
            quantity=quantity,
            unit_cost=unit_cost,
            expiry_date=expiry_value,
        )

        product.stock_quantity = product.stock_quantity + quantity
        product.cost_price = unit_cost
        product.price = selling_price
        product.save(update_fields=["stock_quantity", "cost_price", "price"])

        messages.success(request, "Purchase recorded and stock updated.")
        return redirect("wholesaler_dashboard")

    wholesalers = Wholesaler.objects.order_by("name")
    products = Product.objects.filter(is_active=True).order_by("name")
    recent_purchases = (
        PurchaseItem.objects.select_related("purchase", "purchase__wholesaler", "product")
        .order_by("-purchase__date")[:50]
    )
    context = {
        "wholesalers": wholesalers,
        "products": products,
        "recent_purchases": recent_purchases,
    }
    return render(request, "shop/wholesaler_dashboard.html", context)


@login_required
@user_passes_test(is_shopkeeper)
def return_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    order_items = order.items.select_related("product")
    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()
        refund_method = request.POST.get("refund_method", "")
        # Create OrderReturn
        oreturn = OrderReturn.objects.create(order=order, reason=reason, refund_method=refund_method)
        total_refund = 0
        for item in order_items:
            qty_str = request.POST.get(f"qty_{item.id}", "0")
            try:
                rqty = int(qty_str)
            except ValueError:
                rqty = 0
            if rqty > 0:
                if rqty > item.quantity:
                    rqty = item.quantity
                OrderReturnItem.objects.create(
                    order_return=oreturn,
                    product=item.product,
                    quantity=rqty,
                    unit_price=item.unit_price,
                )
                # Stock adjustment: add returned quantity back
                item.product.stock_quantity = item.product.stock_quantity + rqty
                item.product.save(update_fields=["stock_quantity"])
                total_refund += float(item.unit_price) * rqty
        # Record negative payment to track refund (optional if method provided)
        if refund_method and total_refund > 0:
            OrderPayment.objects.create(
                order=order, method=refund_method, amount=-total_refund, reference="REFUND"
            )
        
        order.status = "returned"
        order.save(update_fields=["status"])
        
        messages.success(request, "Return processed successfully.")
        return redirect("manage_orders")
    return render(request, "shop/return_order.html", {"order": order, "order_items": order_items})


@login_required
@user_passes_test(is_shopkeeper)
def credit_list(request):
    sort = request.GET.get("sort", "")
    credits = CreditEntry.objects.select_related("customer")

    if sort == "customer_asc":
        credits = credits.order_by("is_paid", "customer__name")
    elif sort == "customer_desc":
        credits = credits.order_by("is_paid", "-customer__name")
    else:
        credits = credits.order_by("is_paid", "-date_taken")

    total_outstanding = sum(c.amount for c in credits if not c.is_paid)

    customers = Customer.objects.filter(is_active=True).order_by("name")
    products = Product.objects.filter(is_active=True).order_by("name")

    tpl = MessageTemplate.objects.filter(is_active=True).order_by("created_at").first()
    template_body = tpl.body if tpl else "Dear {customer_name}, your pending udhari is ₹{amount}. Please clear it. - {shop_name}"
    shop_name = "Your Shop"

    reminder_rows = []
    by_customer = {}
    for c in credits:
        if c.is_paid:
            continue
        key = c.customer_id
        if key not in by_customer:
            by_customer[key] = {
                "customer": c.customer,
                "total": 0,
            }
        by_customer[key]["total"] += float(c.amount)
    for _, row in by_customer.items():
        customer = row["customer"]
        amount_val = row["total"]
        body = template_body.format(
            customer_name=customer.name,
            amount=f"{amount_val:.2f}",
            shop_name=shop_name,
        )
        reminder_rows.append(
            {
                "customer": customer,
                "amount": amount_val,
                "body": body,
            }
        )

    context = {
        "credits": credits,
        "total_outstanding": total_outstanding,
        "customers": customers,
        "products": products,
        "current_sort": sort,
        "reminder_rows": reminder_rows,
    }
    return render(request, "shop/credit_list.html", context)


@login_required
@user_passes_test(is_shopkeeper)
def add_credit(request):
    # Handle both GET (show form) and POST (save new udhari entry)
    if request.method == "POST":
        customer_id = request.POST.get("customer_id")
        customer_name = request.POST.get("customer_name")
        customer_phone = request.POST.get("customer_phone", "")
        item_name = request.POST.get("item_name")
        product_id = request.POST.get("product_id")
        quantity = int(request.POST.get("quantity", 1))
        amount_text = request.POST.get("amount", "0")

        # Determine customer: prefer selected existing customer, otherwise create new
        customer = None
        if customer_id:
            try:
                customer = Customer.objects.get(id=customer_id)
            except Customer.DoesNotExist:
                customer = None

        if customer is None:
            if not customer_name:
                messages.error(request, "Customer is required.")
                return redirect("credit_list")


            customer, _ = Customer.objects.get_or_create(
                name=customer_name,
                phone=customer_phone or "",
            )

        # Link to existing product if provided
        product = None
        if product_id:
            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                product = None

        # If item_name not provided, derive from product
        if not item_name and product is not None:
            item_name = product.name

        # Basic validation: item must be present
        if not item_name:
            messages.error(request, "Item name is required.")
            return redirect("credit_list")

        # If amount is not provided or zero and product exists, calculate from price
        try:
            amount_value = float(amount_text)
        except ValueError:
            amount_value = 0

        if amount_value <= 0 and product is not None:
            amount_value = float(product.price) * quantity

        # Create the credit entry
        CreditEntry.objects.create(
            customer=customer,
            product=product,
            item_name=item_name,
            quantity=quantity,
            amount=amount_value,
        )

        messages.success(request, "Udhari entry added successfully.")
        return redirect("credit_list")

    # For GET request, show a simple form
    products = Product.objects.filter(is_active=True).order_by("name")
    customers = Customer.objects.filter(is_active=True).order_by("name")
    context = {
        "products": products,
        "customers": customers,
    }
    return render(request, "shop/add_credit.html", context)


@login_required
@user_passes_test(is_shopkeeper)
def mark_credit_paid(request, credit_id):
    # Mark a specific credit entry as paid and set payment date
    credit = get_object_or_404(CreditEntry, id=credit_id)
    if not credit.is_paid:
        credit.is_paid = True
        credit.date_paid = timezone.now()
        credit.save()

        _audit_log(
            request.user,
            "credit_paid",
            "CreditEntry",
            credit.id,
            "is_paid",
            "False",
            "True",
        )

        messages.success(request, "Marked as paid.")
    else:
        messages.info(request, "This entry is already marked as paid.")
    return redirect("credit_list")


@login_required
@user_passes_test(is_shopkeeper)
def manage_expenses(request):
    if request.method == "POST":
        category = request.POST.get("category")
        amount = request.POST.get("amount")
        description = request.POST.get("description")
        date_text = request.POST.get("date")

        if category and amount:
            try:
                date_val = datetime.strptime(date_text, "%Y-%m-%d").date() if date_text else timezone.now().date()
                Expense.objects.create(
                    category=category,
                    amount=amount,
                    description=description,
                    date=date_val
                )
                messages.success(request, "Expense added successfully.")
            except ValueError:
                messages.error(request, "Invalid input.")
        return redirect("manage_expenses")

    expenses = Expense.objects.order_by("-date", "-created_at")
    return render(request, "shop/manage_expenses.html", {
        "expenses": expenses, 
        "categories": Expense.CATEGORY_CHOICES,
        "today": timezone.now().date()
    })


@login_required
@user_passes_test(is_shopkeeper)
def backup_database(request):
    import os
    from django.conf import settings
    from django.http import FileResponse
    
    db_path = settings.DATABASES['default']['NAME']
    if os.path.exists(db_path):
        response = FileResponse(open(db_path, 'rb'))
        response['Content-Disposition'] = f'attachment; filename="db_backup_{timezone.now().date()}.sqlite3"'
        return response
    else:
        messages.error(request, "Database file not found.")
        return redirect("shop_dashboard")
