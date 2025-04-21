#!/bin/bash

DEBUG=true

while getopts ":d" opt; do
  case $opt in
    d)
      DEBUG=false
      ;;
    \?)
      echo "Invalid option: -$OPTARG" >&2
      exit 1
      ;;
  esac
done

echo "👀 watchmedo auto-restart collectstatic runserver 🐍 (DEBUG=$DEBUG)"

watchmedo auto-restart \
  --directory=static --directory=templates --directory=chesser \
  --pattern="*.js;*.css;*.html;*.py" \
  --recursive \
  -- bash -c "export DEBUG=$DEBUG && python manage.py collectstatic --noinput && python manage.py runserver 0.0.0.0:8000"
