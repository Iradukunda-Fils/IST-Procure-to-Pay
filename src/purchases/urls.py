"""
URL configuration for purchases app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PurchaseRequestViewSet

app_name = 'purchases'

router = DefaultRouter()
router.register(r'', PurchaseRequestViewSet, basename='purchaserequest')

urlpatterns = [
    path('', include(router.urls)),
]