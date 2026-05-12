from django.urls import path

from . import views

app_name = "demo_app"

urlpatterns = [
    path("", views.ThingList.as_view(), name="thing-list"),
    path("uid-stream/", views.UidStreamView.as_view(), name="uid-stream"),
    path("<int:pk>/", views.ThingDetail.as_view(), name="thing-detail"),
]
