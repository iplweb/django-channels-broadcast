from django.contrib import admin
from django.urls import include, path

from example_project import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.home, name="home"),
    path("send/", views.send, name="send"),
    path("demo/fire-progress/", views.fire_progress, name="fire-progress"),
    path("things/", include("demo_app.urls")),
]
