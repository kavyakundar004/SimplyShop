import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'grocery_shop.settings')
django.setup()

from django.contrib.auth.models import User
from shop.models import Category, Product

# Create Superuser
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print("Superuser created: admin/admin123")
else:
    print("Superuser already exists")

# Create Categories
categories = ['Fruits', 'Vegetables', 'Dairy', 'Bakery', 'Beverages']
cat_objs = {}
for cat_name in categories:
    cat, created = Category.objects.get_or_create(name=cat_name)
    cat_objs[cat_name] = cat
    if created:
        print(f"Created category: {cat_name}")

# Create Products
products_data = [
    {'name': 'Apple', 'category': 'Fruits', 'price': 2.50, 'stock': 100, 'desc': 'Fresh red apples'},
    {'name': 'Banana', 'category': 'Fruits', 'price': 1.20, 'stock': 150, 'desc': 'Organic bananas'},
    {'name': 'Milk', 'category': 'Dairy', 'price': 3.00, 'stock': 50, 'desc': 'Whole milk 1L'},
    {'name': 'Bread', 'category': 'Bakery', 'price': 2.00, 'stock': 30, 'desc': 'Whole wheat bread'},
    {'name': 'Orange Juice', 'category': 'Beverages', 'price': 4.50, 'stock': 40, 'desc': 'Freshly squeezed'},
]

for p_data in products_data:
    if not Product.objects.filter(name=p_data['name']).exists():
        Product.objects.create(
            name=p_data['name'],
            category=cat_objs[p_data['category']],
            price=p_data['price'],
            stock_quantity=p_data['stock'],
            description=p_data['desc']
        )
        print(f"Created product: {p_data['name']}")
    else:
        print(f"Product already exists: {p_data['name']}")

print("Setup complete!")
