from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("host/<int:pk>/", views.host_detail, name="host_detail"),
    path("host/<int:pk>/ping/", views.host_ping, name="host_ping"),
    path("directory/", views.ldap_search_view, name="ldap_search"),
    path("export/", views.export_page, name="export_page"),
    path("export/xlsx/", views.export_xlsx, name="export_xlsx"),
]