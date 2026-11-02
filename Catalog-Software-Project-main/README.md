# Catalog-Software-Project
CIS 4103 Project Class. Task: Design flexible catalog software for OBU and other universities.

## Database setup (Neon PostgreSQL)

The Django project uses PostgreSQL. Create a Neon database and set `DATABASE_URL`
to its connection string, including the database name and credentials. Keep this
value secret and do not commit it. The application defaults to requiring SSL.

In PowerShell, from the `catalog` directory:

```powershell
python -m pip install -r requirements.txt
$env:DATABASE_URL = "postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require"
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Replace the example URL with the connection string from Neon. Existing MongoDB
data is not copied by these commands; they create the PostgreSQL schema only.
