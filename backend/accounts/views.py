"""Vues publiques limitées à la création d'un compte acheteur."""
from rest_framework import filters, generics
from rest_framework import viewsets
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenObtainPairView,
    TokenRefreshView,
)

from accounts.models import User
from accounts.permissions import IsAdministrator
from accounts.serializers import (
    BuyerRegistrationSerializer,
    CurrentUserSerializer,
    UserAdminSerializer,
)


class BuyerRegistrationView(generics.CreateAPIView):
    serializer_class = BuyerRegistrationSerializer
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]


class RateLimitedTokenObtainPairView(TokenObtainPairView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


class RateLimitedTokenRefreshView(TokenRefreshView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


class CurrentUserView(RetrieveAPIView):
    serializer_class = CurrentUserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class UserAdminViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserAdminSerializer
    permission_classes = [IsAdministrator]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["username", "email", "first_name", "last_name"]
    ordering_fields = ["username", "email", "role", "is_active"]
    ordering = ["username"]


class RateLimitedTokenBlacklistView(TokenBlacklistView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"
