echo "👀 watchmedo auto-restart collectstatic runserver 🐍"
DEBUG=True watchmedo auto-restart \
  --directory=static --directory=templates --directory=chesser \
  --pattern="*.js;*.css;*.html;*.py" \
  --recursive \
  -- bash -c "python manage.py collectstatic --noinput && python manage.py runserver"

