from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("host/<int:pk>/", views.host_detail, name="host_detail"),
]