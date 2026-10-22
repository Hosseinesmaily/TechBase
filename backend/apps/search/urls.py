from django.urls import path

from . import views

app_name = "search"

urlpatterns = [
    path("", views.SearchView.as_view(), name="search"),
    path("autocomplete/", views.SearchAutocompleteView.as_view(), name="autocomplete"),
    path("products/", views.CatalogSearchListView.as_view(), name="product-search"),
]
