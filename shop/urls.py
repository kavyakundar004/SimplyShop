from django.urls import path
from . import views

urlpatterns = [
    # Homepage showing product list for customers
    path('', views.product_list, name='product_list'),
    
    # Cart urls
    path('cart/', views.cart_summary, name='cart_summary'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/<int:product_id>/', views.update_cart, name='update_cart'),
    path('cart/remove/<int:product_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('order-success/<int:order_id>/', views.order_success, name='order_success'),
    path('orders/<int:order_id>/completed/', views.mark_order_completed, name='mark_order_completed'),
    path('orders/<int:order_id>/return/', views.return_order, name='return_order'),
    path('dashboard/orders/', views.manage_orders, name='manage_orders'),
    # Scanning endpoints
    path('scan/add/', views.scan_add_to_cart, name='scan_add_to_cart'),
    path('scan/stock/', views.scan_stock_increment, name='scan_stock_increment'),
    path('price-checker/', views.price_checker, name='price_checker'),
    path('api/customer-lookup/', views.customer_lookup, name='customer_lookup'),
    path('api/customer-suggest/', views.customer_suggest, name='customer_suggest'),
    
    # Shopkeeper urls
    path('dashboard/', views.shop_dashboard, name='shop_dashboard'),
    path('dashboard/products/', views.manage_products, name='manage_products'),
    path('wholesalers/', views.wholesaler_dashboard, name='wholesaler_dashboard'),
    path('pos/', views.pos, name='pos'),
    path('login/', views.shop_login, name='shop_login'),
    path('logout/', views.shop_logout, name='shop_logout'),
    path('sales/', views.sales_dashboard, name='sales_dashboard'),
    path('customers/', views.customer_details, name='customer_details'),
    path('customers/manage/', views.manage_customers, name='manage_customers'),
    
    # Udhari (credit) tracking urls
    path('credit/', views.credit_list, name='credit_list'),
    path('credit/add/', views.add_credit, name='add_credit'),
    path('credit/<int:credit_id>/paid/', views.mark_credit_paid, name='mark_credit_paid'),
    
    # New features
    path('expenses/', views.manage_expenses, name='manage_expenses'),
    path('backup/', views.backup_database, name='backup_database'),
    path('purchases/suggested/', views.suggested_purchases, name='suggested_purchases'),
]
