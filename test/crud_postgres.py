import os
from datetime import datetime

import django
import dj_database_url
from dotenv import load_dotenv
from django.conf import settings
from django.db import connection, models

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is missing. Create a .env file with your Neon Postgres connection string."
    )

# Configure Django settings for a standalone script.
if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY=os.getenv("DJANGO_SECRET_KEY", "dev-only-secret-key"),
        INSTALLED_APPS=[
            "__main__",
        ],
        DATABASES={
            "default": dj_database_url.parse(
                DATABASE_URL,
                conn_max_age=600,
                ssl_require=True,
            )
        },
        TIME_ZONE="UTC",
        USE_TZ=True,
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
    )

django.setup()


# ==========================================
# MODEL DEFINITION
# ==========================================
class DemoCustomer(models.Model):
    """Simple test model for managing sample data in Neon Postgres."""

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    signup_source = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "__main__"
        db_table = "demo_customer"

    def __str__(self):
        return f"{self.first_name} {self.last_name} <{self.email}>"


def create_table_if_not_exists():
    """Create the demo_customer table if it does not already exist."""
    existing_tables = connection.introspection.table_names()

    if DemoCustomer._meta.db_table in existing_tables:
        print(f"Table '{DemoCustomer._meta.db_table}' already exists.")
        return

    with connection.schema_editor() as schema_editor:
        schema_editor.create_model(DemoCustomer)

    print(f"Created table '{DemoCustomer._meta.db_table}'.")


# ==========================================
# CRUD OPERATIONS
# ==========================================

# 1. CREATE
def create_customer(first_name: str, last_name: str, email: str, signup_source: str):
    """Create a single customer record or retrieve it if the email already exists."""
    customer, created = DemoCustomer.objects.get_or_create(
        email=email,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "signup_source": signup_source,
        },
    )
    if created:
        print(f"[CREATE] Created customer: {customer}")
    else:
        print(f"[CREATE] Record already exists for email '{email}': {customer}")
    return customer


# 2. READ / RETURN
def get_customer_by_email(email: str):
    """Return a single customer by email or None if not found."""
    try:
        customer = DemoCustomer.objects.get(email=email)
        print(f"[READ] Found customer: {customer}")
        return customer
    except DemoCustomer.DoesNotExist:
        print(f"[READ] No customer found with email: {email}")
        return None


def get_all_customers():
    """Return and list all customer records."""
    customers = DemoCustomer.objects.all().order_by("id")
    print(f"\n[READ ALL] Listing all {customers.count()} customer(s):")
    for customer in customers:
        print(
            f"  ID={customer.id} | "
            f"Name={customer.first_name} {customer.last_name} | "
            f"Email={customer.email} | "
            f"Source={customer.signup_source} | "
            f"Created={customer.created_at}"
        )
    return customers


# 3. UPDATE
def update_customer_source(email: str, new_source: str):
    """Update the signup source for an existing customer."""
    try:
        customer = DemoCustomer.objects.get(email=email)
        old_source = customer.signup_source
        customer.signup_source = new_source
        customer.save(update_fields=["signup_source"])
        print(
            f"[UPDATE] Updated {customer.email}: source changed from '{old_source}' to '{new_source}'."
        )
        return customer
    except DemoCustomer.DoesNotExist:
        print(f"[UPDATE] Cannot update. Customer with email '{email}' does not exist.")
        return None


# 4. DELETE
def delete_customer_by_email(email: str):
    """Delete a customer record by email."""
    try:
        customer = DemoCustomer.objects.get(email=email)
        customer_info = str(customer)
        customer.delete()
        print(f"[DELETE] Deleted customer: {customer_info}")
        return True
    except DemoCustomer.DoesNotExist:
        print(f"[DELETE] Cannot delete. No customer found with email: {email}")
        return False


# ==========================================
# MAIN DEMONSTRATION WORKFLOW
# ==========================================
def main():
    print("Connecting to Neon Postgres with Django...")
    print(f"Started at: {datetime.utcnow().isoformat()}Z\n")

    # Step 0: Ensure table schema exists
    create_table_if_not_exists()

    # Step 1: CREATE records
    print("\n--- 1. CREATE ---")
    create_customer("Ava", "Johnson", "ava.johnson@example.com", "landing_page")
    create_customer("Marcus", "Lee", "marcus.lee@example.com", "referral")
    create_customer("Sofia", "Garcia", "sofia.garcia@example.com", "newsletter")

    # Step 2: READ / RETURN records
    print("\n--- 2. READ / RETURN ---")
    get_customer_by_email("marcus.lee@example.com")
    get_all_customers()

    # Step 3: UPDATE a record
    print("\n--- 3. UPDATE ---")
    update_customer_source("marcus.lee@example.com", "partner_promo")

    # Step 4: DELETE a record
    print("\n--- 4. DELETE ---")
    delete_customer_by_email("sofia.garcia@example.com")

    # Final Verification
    print("\n--- FINAL STATE ---")
    get_all_customers()

    print("\nDone.")


if __name__ == "__main__":
    main()