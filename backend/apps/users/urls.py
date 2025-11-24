from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'organizations', views.OrganizationViewSet, basename='organization')
router.register(r'organizations/(?P<organization_id>\d+)/contacts', views.OrganizationContactViewSet, basename='organization-contacts')

urlpatterns = [
    # Specific endpoints first
    path('profile/', views.UserProfileView.as_view(), name='user-profile'),
    path('register/', views.UserRegistrationView.as_view(), name='user-register'),
    path('login/', views.UserLoginView.as_view(), name='user-login'),
    path('logout/', views.logout_view, name='user-logout'),
    path('users/', views.UserListView.as_view(), name='user-list'),
    path('users/<int:pk>/', views.UserDetailView.as_view(), name='user-detail'),
    
    # Email verification
    path('verify-email/<str:token>/', views.EmailVerificationView.as_view(), name='verify-email'),
    path('resend-verification/', views.ResendVerificationView.as_view(), name='resend-verification'),
    
    # Password reset
    path('password-reset/', views.PasswordResetRequestView.as_view(), name='password-reset'),
    path('password-reset/confirm/<str:token>/', views.PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    
    # Token
    path('token/refresh/', views.TokenRefreshView.as_view(), name='token-refresh'),
    
    # Include router URLs last
    path('', include(router.urls)),
]from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = User
        fields = [
            'email', 'password', 'password_confirm', 'first_name', 'last_name',
            'phone_number', 'terms_accepted', 'privacy_policy_accepted'
        ]
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password_confirm": "Password fields didn't match."})
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True)


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'uuid', 'email', 'first_name', 'last_name', 'phone_number',
            'role', 'organization', 'email_verified', 'mfa_enabled',
            'timezone', 'language', 'date_format', 'notification_settings',
            'last_login', 'date_joined'
        ]
        read_only_fields = ['id', 'uuid', 'email', 'role', 'organization', 
                          'email_verified', 'last_login', 'date_joined']


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'uuid', 'email', 'first_name', 'last_name', 'role',
            'phone_number', 'is_active', 'last_activity'
        ]


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True)
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password_confirm": "Password fields didn't match."})
        return attrs


class EmailVerificationSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    email = serializers.EmailField(required=True)