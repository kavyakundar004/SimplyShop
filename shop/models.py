from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Category(models.Model):
    # Human-friendly name for the category, e.g., "Fruits", "Vegetables"
    name = models.CharField(max_length=100, unique=True)

    # Optional description to help the shopkeeper remember what goes here
    description = models.TextField(blank=True)

    def __str__(self) -> str:
        # Display the category by its name in admin or shell
        return self.name


class Product(models.Model):
    # Category to which this product belongs (e.g., Fruits)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    # Name shown to the customer, e.g., "Apple"
    name = models.CharField(max_length=200)
    # Image of the product
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    # Short description to show details to customers
    description = models.TextField(blank=True)
    # Price for one unit (kg, piece, packet, etc.)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    # Cost price per unit from wholesaler (used for profit calculation)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # Discount amount in Rupees to be deducted from the selling price
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # Quantity available in stock; helps shopkeeper track inventory
    stock_quantity = models.PositiveIntegerField(default=0)
    # Machine-readable code for scanners (EAN/UPC or custom)
    barcode = models.CharField(max_length=64, unique=True, blank=True, null=True)
    # Optional QR payload for richer scanning workflows
    qr_payload = models.TextField(blank=True)
    # Base selling unit (e.g., piece, packet, kg, liter)
    unit = models.CharField(max_length=30, default="piece")
    # Optional subunit for conversion (e.g., piece in a packet, gram for kg)
    subunit = models.CharField(max_length=30, blank=True)
    # Number of subunits per one unit (e.g., 1 packet = 12 pieces; 1 kg = 1000 grams)
    conversion_factor = models.PositiveIntegerField(default=1)
    # Per-product tax rate (GST) as percentage (e.g., 5.00 for 5%)
    tax_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    reorder_threshold = models.PositiveIntegerField(default=5)
    expiry_date = models.DateField(null=True, blank=True)
    # Whether the product is visible to customers
    is_active = models.BooleanField(default=True)
    # Timestamp fields to audit when products are created/updated
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        # Display both name and price for clarity
        return f"{self.name} ({self.price})"


class Order(models.Model):
    # Customer name captured at checkout (simple, no auth for now)
    customer_name = models.CharField(max_length=150)
    # Customer contact number
    customer_phone = models.CharField(max_length=20, blank=True)
    # Optional address for delivery orders
    customer_address = models.TextField(blank=True)
    # Time when order was created
    created_at = models.DateTimeField(auto_now_add=True)
    # Time when order was last updated (e.g., packed/delivered)
    updated_at = models.DateTimeField(auto_now=True)
    # Basic status for the shopkeeper to track
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("preparing", "Preparing"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("returned", "Returned"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    def __str__(self) -> str:
        # Show customer and status for quick identification
        return f"Order #{self.id} - {self.customer_name} ({self.status})"

    @property
    def total_amount(self) -> float:
        # Compute total based on all related items in the order
        return sum(item.subtotal for item in self.items.all())


class Expense(models.Model):
    CATEGORY_CHOICES = [
        ('rent', 'Rent'),
        ('electricity', 'Electricity'),
        ('salary', 'Staff Salary'),
        ('maintenance', 'Maintenance'),
        ('transport', 'Transport'),
        ('other', 'Other'),
    ]
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='other')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_category_display()} - {self.amount}"


class OrderItem(models.Model):
    # Link to the containing order
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    # Product that was purchased
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    # Quantity of the product in this order
    quantity = models.PositiveIntegerField(default=1)
    # Snapshot of price at the time of order (before discount)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    # Discount applied per unit at the time of order
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    @property
    def subtotal(self) -> float:
        # Calculate cost for this line item (price - discount) * qty
        return (self.unit_price - self.discount_amount) * self.quantity

    def __str__(self) -> str:
        # Helpful representation for admin or logs
        return f"{self.quantity} x {self.product.name}"


class Customer(models.Model):
    # Name of the customer who can take items on credit (udhari)
    name = models.CharField(max_length=150)
    # Optional contact number to identify the customer
    phone = models.CharField(max_length=20, blank=True)
    # Optional address or extra details
    address = models.TextField(blank=True)
    # Whether this customer is currently active
    is_active = models.BooleanField(default=True)
    # Notes for the shopkeeper about this customer
    notes = models.TextField(blank=True)
    # When the last payment reminder was sent
    last_reminder_date = models.DateField(null=True, blank=True)

    def __str__(self) -> str:
        # Show customer name and phone together
        if self.phone:
            return f"{self.name} ({self.phone})"
        return self.name


class CreditEntry(models.Model):
    # Which customer took the item on credit
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="credits",
    )
    # Which product was taken (optional, in case it is not from catalog)
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="credit_entries",
    )
    # Free-text item name so shopkeeper can write anything (e.g. "Sugar 2kg")
    item_name = models.CharField(max_length=200)
    # Quantity of the item taken on credit
    quantity = models.PositiveIntegerField(default=1)
    # Total amount for this credit entry
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    # When the customer took this item on credit
    date_taken = models.DateTimeField(auto_now_add=True)
    # Whether this credit is cleared
    is_paid = models.BooleanField(default=False)
    # When the customer paid back (only filled if is_paid is True)
    date_paid = models.DateTimeField(null=True, blank=True)
    # Extra notes, for example "Paid half in cash, half online"
    notes = models.TextField(blank=True)
    # When this record was created (for auditing)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        # Short description of the credit entry
        status = "Paid" if self.is_paid else "Unpaid"
        return f"{self.customer} - {self.item_name} ({status})"


class Wholesaler(models.Model):
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    def __str__(self) -> str:
        if self.phone:
            return f"{self.name} ({self.phone})"
        return self.name


class Purchase(models.Model):
    wholesaler = models.ForeignKey(
        Wholesaler,
        on_delete=models.CASCADE,
        related_name="purchases",
    )
    date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Purchase #{self.id} from {self.wholesaler}"


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(
        Purchase,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    expiry_date = models.DateField(null=True, blank=True)

    @property
    def total_cost(self) -> float:
        return self.unit_cost * self.quantity


class OrderPayment(models.Model):
    METHOD_CHOICES = [
        ("cash", "Cash"),
        ("card", "Card"),
        ("upi", "UPI"),
    ]
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reference = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class OrderReturn(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="returns")
    reason = models.TextField(blank=True)
    refund_method = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Return #{self.id} for Order #{self.order_id}"


class OrderReturnItem(models.Model):
    order_return = models.ForeignKey(OrderReturn, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def subtotal(self) -> float:
        return self.unit_price * self.quantity


class MessageTemplate(models.Model):
    name = models.CharField(max_length=100, unique=True)
    body = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ("stock_change", "Stock Change"),
        ("price_change", "Price Change"),
        ("credit_paid", "Credit Paid"),
    ]
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    model = models.CharField(max_length=100)
    object_id = models.PositiveIntegerField()
    field = models.CharField(max_length=100)
    old_value = models.CharField(max_length=255, blank=True)
    new_value = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Expense(models.Model):
    CATEGORY_CHOICES = [
        ("Rent", "Rent"),
        ("Electricity", "Electricity"),
        ("Salary", "Salary"),
        ("Maintenance", "Maintenance"),
        ("Other", "Other"),
    ]
    date = models.DateField(default=timezone.now)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    description = models.CharField(max_length=200, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.category} - {self.amount}"
