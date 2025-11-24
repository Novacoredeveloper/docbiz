from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.utils import timezone

from .models import User
from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    UserProfileSerializer,
    UserSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    EmailVerificationSerializer
)


class UserRegistrationView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            
            # Send email verification
            user.generate_email_verification_token()
            # TODO: Send verification email
            
            return Response({
                'message': 'User registered successfully. Please check your email for verification.',
                'user_id': user.id
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserLoginView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            password = serializer.validated_data['password']
            
            user = authenticate(request, email=email, password=password)
            
            if user:
                if user.is_account_locked():
                    return Response({
                        'error': 'Account is temporarily locked due to too many failed login attempts.'
                    }, status=status.HTTP_423_LOCKED)
                
                if not user.email_verified:
                    return Response({
                        'error': 'Please verify your email before logging in.'
                    }, status=status.HTTP_403_FORBIDDEN)
                
                # Update session activity
                user.update_session_activity(request.META.get('REMOTE_ADDR'))
                
                # Generate tokens
                refresh = RefreshToken.for_user(user)
                
                return Response({
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                    'user': UserProfileSerializer(user).data
                })
            
            return Response({
                'error': 'Invalid credentials'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)
    
    def put(self, request):
        serializer = UserProfileSerializer(
            request.user, 
            data=request.data, 
            partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserListView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Only show users from the same organization
        if request.user.organization:
            users = User.objects.filter(
                organization=request.user.organization,
                is_active=True
            )
        else:
            users = User.objects.none()
            
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)


class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        try:
            user = User.objects.get(pk=pk, is_active=True)
            # Ensure user can only access users from their organization
            if request.user.organization and user.organization != request.user.organization:
                return Response(
                    {'error': 'Permission denied'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            serializer = UserSerializer(user)
            return Response(serializer.data)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )


class EmailVerificationView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request, token):
        serializer = EmailVerificationSerializer(data={'token': token})
        if serializer.is_valid():
            email = serializer.validated_data['email']
            
            try:
                user = User.objects.get(
                    email_verification_token=token,
                    email=email
                )
                
                if user.verify_email(token):
                    return Response({
                        'message': 'Email verified successfully'
                    })
                else:
                    return Response({
                        'error': 'Invalid or expired verification token'
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            except User.DoesNotExist:
                return Response({
                    'error': 'Invalid verification token'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResendVerificationView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response(
                {'error': 'Email is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(email=email)
            if user.email_verified:
                return Response({
                    'error': 'Email is already verified'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            token = user.generate_email_verification_token()
            # TODO: Send verification email with new token
            
            return Response({
                'message': 'Verification email sent successfully'
            })
            
        except User.DoesNotExist:
            return Response({
                'error': 'User with this email does not exist'
            }, status=status.HTTP_404_NOT_FOUND)


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            
            try:
                user = User.objects.get(email=email, is_active=True)
                token = user._generate_secure_token()
                user.password_reset_token = token
                user.password_reset_sent_at = timezone.now()
                user.save()
                
                # TODO: Send password reset email
                
                return Response({
                    'message': 'Password reset instructions sent to your email'
                })
                
            except User.DoesNotExist:
                # Don't reveal whether email exists
                return Response({
                    'message': 'If the email exists, password reset instructions have been sent'
                })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request, token):
        serializer = PasswordResetConfirmSerializer(data={
            **request.data,
            'token': token
        })
        
        if serializer.is_valid():
            email = serializer.validated_data['email']
            new_password = serializer.validated_data['new_password']
            
            try:
                user = User.objects.get(
                    email=email,
                    password_reset_token=token,
                    is_active=True
                )
                
                # Check token expiration (1 hour)
                if (user.password_reset_sent_at and 
                    (timezone.now() - user.password_reset_sent_at).total_seconds() > 3600):
                    return Response({
                        'error': 'Password reset token has expired'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                user.set_password(new_password)
                user.password_reset_token = ''
                user.password_reset_sent_at = None
                user.save()
                
                return Response({
                    'message': 'Password reset successfully'
                })
                
            except User.DoesNotExist:
                return Response({
                    'error': 'Invalid password reset token'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TokenRefreshView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {'error': 'Refresh token is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            refresh = RefreshToken(refresh_token)
            user_id = refresh['user_id']
            user = User.objects.get(id=user_id)
            
            # Create new access token
            new_access = str(refresh.access_token)
            
            return Response({
                'access': new_access
            })
            
        except Exception as e:
            return Response({
                'error': 'Invalid refresh token'
            }, status=status.HTTP_401_UNAUTHORIZED)


def logout_view(request):
    # For JWT, logout is handled client-side by discarding tokens
    return Response({'message': 'Logged out successfully'})


class OrganizationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.is_superuser:
            return Organization.objects.all()
        elif self.request.user.organization:
            return Organization.objects.filter(id=self.request.user.organization.id)
        return Organization.objects.none()
    
    @action(detail=True, methods=['post'])
    def invite_user(self, request, pk=None):
        # TODO: Implement organization user invitation
        pass


class OrganizationContactViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        organization_id = self.kwargs['organization_id']
        # Ensure user has access to this organization
        if (self.request.user.organization and 
            self.request.user.organization.id == organization_id):
            return OrganizationContact.objects.filter(organization_id=organization_id)
        return OrganizationContact.objects.none()