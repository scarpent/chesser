rm data/chesser.sqlite3 -fv
rm chesser/migrations/000* -fv
python manage.py makemigrations
python manage.py migrate
python manage.py load_courses
python manage.py create_local_superuser
