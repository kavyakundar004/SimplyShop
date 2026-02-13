# Grocery Shop Management System

A comprehensive, web-based management system designed for small to medium-sized grocery shops. Built with Django, this application helps shopkeepers manage inventory, track sales, handle customer credits (Udhari), and monitor expenses.

## 🚀 Features

### 📦 Inventory Management
- **Product Catalog:** Manage products with categories, prices (cost & selling), and images.
- **Stock Tracking:** Real-time stock quantity monitoring with reorder thresholds.
- **Barcode & QR Support:** Integration for scanning workflows and machine-readable codes.
- **Expiry Tracking:** Monitor product expiry dates to reduce waste.
- **Tax Management:** Per-product GST/tax rate configuration.

### 💰 Sales & POS (Point of Sale)
- **POS Interface:** Fast checkout process for shopkeepers.
- **Order Management:** Track order status from pending to completed or returned.
- **Payment Methods:** Supports Cash, Card, and UPI payments.
- **Price Checker:** Quick lookup tool for product prices.

### 💳 Customer Credit (Udhari) System
- **Customer Profiles:** Maintain detailed records of regular customers.
- **Credit Tracking:** Log items taken on credit and track repayment status.
- **Reminders:** Track last reminder dates for outstanding payments.

### 📊 Analytics & Reporting
- **Sales Dashboard:** Visual overview of sales performance.
- **Expense Tracking:** Monitor shop overheads like rent, electricity, and salaries.
- **Suggested Purchases:** Automated recommendations based on low stock levels.
- **Audit Logs:** Track changes for accountability.

## 🛠️ Tech Stack
- **Backend:** [Django](https://www.djangoproject.com/) (Python)
- **Frontend:** HTML5, CSS3, [Bootstrap 5](https://getbootstrap.com/)
- **Database:** SQLite (Default), PostgreSQL compatible
- **Deployment:** [Vercel](https://vercel.com/)

## 🏁 Getting Started

### Prerequisites
- Python 3.8+
- pip (Python package manager)

### Installation
1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd shop
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up the database:**
   ```bash
   python manage.py migrate
   ```

4. **Create a superuser (for admin access):**
   ```bash
   python manage.py createsuperuser
   ```

5. **Run the development server:**
   ```bash
   python manage.py runserver
   ```
   Access the app at `http://127.0.0.1:8000/`

## 📁 Project Structure
- `shop/`: Main application logic (models, views, templates).
- `grocery_shop/`: Project configuration and settings.
- `static/`: CSS, JavaScript, and images.
- `templates/`: HTML templates for the UI.

## ☁️ Deployment (Vercel)
The project is configured for easy deployment on Vercel using `vercel.json`.
1. Install Vercel CLI: `npm i -g vercel`
2. Run `vercel` in the project root.

## 📄 License
This project is licensed under the MIT License.
