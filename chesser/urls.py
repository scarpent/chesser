from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from chesser import views

admin.site.site_header = "♟️ Chesser Admin ♟️"
admin.site.site_title = "Chesser"
admin.site.index_title = "Admin"

handler404 = "chesser.views.custom_404_view"
handler500 = "chesser.views.custom_500_view"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("service-worker.js", views.service_worker, name="service-worker"),
    path("error/", views.trigger_error),
    path("", views.home, name="home"),
    path("home-upcoming/", views.home_upcoming, name="home_upcoming"),
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
    path("edit-shared-move/", views.edit_shared_move, name="edit_shared_move"),
    path("save-shared-move/", views.save_shared_move, name="save_shared_move"),
    path(
        "save-shared-move-old/", views.save_shared_move_old, name="save_shared_move_old"
    ),
    path(
        "update-shared-move-link/",
        views.update_shared_move_link,
        name="update_shared_move_link",
    ),
    path(
        "update-grouped-move-values/",
        views.update_grouped_move_values,
        name="update_grouped_move_values",
    ),
    path("variation/", views.variation, name="variation_default"),
    path("variation/<int:variation_id>/", views.variation, name="variation"),
    path("import/", views.import_view, name="import"),
    path(
        "import-json/",
        views.ImportVariationView.as_view(),
        name="import_json",
    ),
    path("clone/", views.clone, name="clone"),
    path("upload-json-data/", views.upload_json_data, name="upload_json_data"),
    path("export/<int:variation_id>/", views.export, name="export"),
    path("variations.tsv/", views.variations_tsv, name="variations_tsv"),
    path("variations-table/", views.variations_table, name="variations_table"),
    path("stats/", views.stats, name="stats"),
]
