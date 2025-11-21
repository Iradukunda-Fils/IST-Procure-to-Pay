"""
URL configuration for users app.

JWT Authentication Endpoints:
- POST /api/auth/token/ - Obtain access and refresh tokens
- POST /api/auth/token/refresh/ - Refresh access token using refresh token
"""
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

app_name = 'users'

urlpatterns = [
    # JWT Authentication Endpoints
    # POST /api/auth/token/ - Obtain JWT tokens with username/password
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    
    # POST /api/auth/token/refresh/ - Refresh access token using refresh token
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]