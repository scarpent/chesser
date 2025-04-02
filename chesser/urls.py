"""
URL configuration for chesser project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from chesser import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("", views.home, name="home"),
    path("course/<int:course_id>/", views.home, name="course_view"),
    path(
        "course/<int:course_id>/chapter/<int:chapter_id>/",
        views.home,
        name="chapter_view",
    ),
    path("review/", views.review, name="review_default"),
    path("review/<int:variation_id>/", views.review, name="review_with_id"),
    path("review/random/", views.review_random, name="review_random"),
    path("report-result/", views.report_result, name="report_result"),
    path("edit/", views.edit, name="edit_default"),
    path("edit/<int:variation_id>/", views.edit, name="edit_with_id"),
    path("save-variation/", views.save_variation, name="save_variation"),
    path("variation/", views.variation, name="variation_default"),
    path("variation/<int:variation_id>/", views.variation, name="variation"),
    path("import/", views.import_view, name="import"),
    path(
        "import-json/",
        views.ImportVariationView.as_view(),
        name="import_json",
    ),
    path("upload-json-data/", views.upload_json_data, name="upload_json_data"),
    path("variations.tsv/", views.variations_tsv, name="variations_tsv"),
    path("variations-table/", views.variations_table, name="variations_table"),
]
