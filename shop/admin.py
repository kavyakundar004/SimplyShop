from django.contrib import admin
from .models import (
    Category,
    Product,
    Order,
    OrderItem,
    Customer,
    CreditEntry,
    Wholesaler,
    Purchase,
    PurchaseItem,
    MessageTemplate,
    AuditLog,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    # Columns to show in the category list in admin
    list_display = ("name", "description")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # Columns to show in the product list in admin
    list_display = ("name", "category", "price", "cost_price", "stock_quantity", "unit", "subunit", "conversion_factor", "tax_rate_percent", "barcode", "is_active")
    # Quick filters in the sidebar
    list_filter = ("category", "is_active")
    # Search box fields
    search_fields = ("name", "description", "barcode")


class OrderItemInline(admin.TabularInline):
    # Inline editor so shopkeeper can see items within an order
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    # Columns to show in the order list in admin
    list_display = ("id", "customer_name", "status", "created_at")
    # Filters for status and creation date
    list_filter = ("status", "created_at")
    # Allow searching by customer information
    search_fields = ("customer_name", "customer_phone")
    # Attach order items inline for easy editing
    inlines = [OrderItemInline]


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    # Show main customer info in admin list
    list_display = ("name", "phone", "is_active")
    # Filters for quick search
    list_filter = ("is_active",)
    # Make it easy to search by name or phone
    search_fields = ("name", "phone")


@admin.register(CreditEntry)
class CreditEntryAdmin(admin.ModelAdmin):
    # Show important udhari information in admin list
    list_display = ("customer", "item_name", "amount", "is_paid", "date_taken", "date_paid")
    # Filters for paid/unpaid and date
    list_filter = ("is_paid", "date_taken")
    # Allow searching by customer name or item name
    search_fields = ("customer__name", "item_name")


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 0


@admin.register(Wholesaler)
class WholesalerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "email")
    search_fields = ("name", "phone")


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ("id", "wholesaler", "date")
    list_filter = ("wholesaler", "date")
    inlines = [PurchaseItemInline]


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "body")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "model", "field", "old_value", "new_value", "user")
    list_filter = ("action", "model")
    search_fields = ("model", "field", "old_value", "new_value", "user__username")
