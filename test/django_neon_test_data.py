"""
django_neon_test_data.py

A minimal standalone Django script that connects to a Neon Postgres database
and inserts test data.

Setup:
1. Install dependencies:
   pip install django psycopg[binary] dj-database-url python-dotenv

2. Create a .env file in the same folder with your Neon connection string:
   DATABASE_URL=postgresql://USER:PASSWORD@HOST.neon.tech/DBNAME?sslmode=require

3. Run the script:
   python django_neon_test_data.py

Notes:
- This script creates a simple table named demo_customer if it does not exist.
- It then inserts a few rows of test customer data.
- Neon requires SSL, so make sure your DATABASE_URL includes sslmode=require.
"""

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


class DemoCustomer(models.Model):
    """Simple test model for inserting sample data into Neon Postgres."""

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


def insert_test_data():
    """Insert test rows into the Neon Postgres database."""
    test_customers = [
        {
            "first_name": "Ava",
            "last_name": "Johnson",
            "email": "ava.johnson@example.com",
            "signup_source": "landing_page",
        },
        {
            "first_name": "Marcus",
            "last_name": "Lee",
            "email": "marcus.lee@example.com",
            "signup_source": "referral",
        },
        {
            "first_name": "Sofia",
            "last_name": "Garcia",
            "email": "sofia.garcia@example.com",
            "signup_source": "newsletter",
        },
    ]

    created_count = 0
    skipped_count = 0

    for customer_data in test_customers:
        customer, created = DemoCustomer.objects.get_or_create(
            email=customer_data["email"],
            defaults=customer_data,
        )

        if created:
            created_count += 1
            print(f"Inserted: {customer}")
        else:
            skipped_count += 1
            print(f"Skipped existing record: {customer}")

    print("\nTest data insert complete.")
    print(f"Rows created: {created_count}")
    print(f"Rows skipped: {skipped_count}")


def show_current_rows():
    """Print all rows currently stored in the demo_customer table."""
    customers = DemoCustomer.objects.all().order_by("id")

    print("\nCurrent demo_customer rows:")
    for customer in customers:
        print(
            f"ID={customer.id}, "
            f"Name={customer.first_name} {customer.last_name}, "
            f"Email={customer.email}, "
            f"Source={customer.signup_source}, "
            f"Created={customer.created_at}"
        )


def main():
    print("Connecting to Neon Postgres with Django...")
    print(f"Started at: {datetime.utcnow().isoformat()}Z\n")

    create_table_if_not_exists()
    insert_test_data()
    show_current_rows()

    print("\nDone.")


if __name__ == "__main__":
    main()
