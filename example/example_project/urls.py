from django.contrib import admin
from django.urls import path

from example_project import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.home, name="home"),
    path("send/", views.send, name="send"),
]
