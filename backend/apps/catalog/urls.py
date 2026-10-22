from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("entities/", views.EntityListView.as_view(), name="entity-list"),
    path("entities/<slug:slug>/", views.EntityDetailView.as_view(), name="entity-detail"),
    path("products/", views.ProductListView.as_view(), name="product-list"),
    path("products/<slug:sku>/", views.ProductDetailView.as_view(), name="product-detail"),
    path("brands/", views.BrandListView.as_view(), name="brand-list"),
    path("categories/", views.CategoryListView.as_view(), name="category-list"),
]
