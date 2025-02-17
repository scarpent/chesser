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
from django.urls import path

from chesser import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.home, name="home"),
    path("review/", views.review, name="review_default"),
    path("review/<int:variation_id>/", views.review, name="review_with_id"),
    path("report-result/", views.report_result, name="report_result"),
    path("import/", views.importer, name="import"),
    path("edit/", views.edit, name="edit_default"),
    path("edit/<int:variation_id>/", views.edit, name="edit_with_id"),
    path("save-variation/", views.save_variation, name="save_variation"),
]
