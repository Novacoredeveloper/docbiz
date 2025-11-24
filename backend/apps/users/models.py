from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.crypto import get_random_string
from safedelete.models import SafeDeleteModel
from phonenumber_field.modelfields import PhoneNumberField
import secrets
import uuid

from datetime import timedelta
from typing import Optional, Dict, Any
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _
from encrypted_model_fields.fields import EncryptedCharField
import pyotp
from auditlog.registry import auditlog
from django_countries.fields import CountryField


class CustomUserManager(BaseUserManager):
    """Custom user manager for DocBiz platform."""
    
    def create_user(self, email: str, password: str = None, **extra_fields):
        """
        Create and save a regular user with the given email and password.
        """
        if not email:
            raise ValueError(_('The Email field must be set'))
            
        email = self.normalize_email(email)
        
        # Set default values for required JSON fields
        extra_fields.setdefault('previous_passwords', [])
        extra_fields.setdefault('mfa_backup_codes', [])
        extra_fields.setdefault('metadata', {})
        extra_fields.setdefault('notification_settings', {})
        
        # Set default values for other required fields
        extra_fields.setdefault('role', User.Role.ORG_USER)
        extra_fields.setdefault('terms_accepted', False)
        extra_fields.setdefault('privacy_policy_accepted', False)
        
        # Ensure UUID is generated for new users
        if 'uuid' not in extra_fields:
            extra_fields['uuid'] = uuid.uuid4()
            
        user = self.model(email=email, **extra_fields)
        
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
            
        user.full_clean()
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str = None, **extra_fields):
        """
        Create and save a SuperUser with the given email and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('email_verified', True)
        
        # For superusers, set required fields
        extra_fields.setdefault('role', User.Role.SUPER_ADMIN)
        extra_fields.setdefault('terms_accepted', True)
        extra_fields.setdefault('privacy_policy_accepted', True)
        extra_fields.setdefault('previous_passwords', [])
        extra_fields.setdefault('mfa_backup_codes', [])
        extra_fields.setdefault('metadata', {})
        extra_fields.setdefault('notification_settings', {})

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser, SafeDeleteModel):
    """
    Enhanced User model for DocBiz with comprehensive security features,
    role-based access control, and audit capabilities.
    """
    
    class Role(models.TextChoices):
        SUPER_ADMIN = 'super_admin', _('Super Administrator')
        ORG_ADMIN = 'org_admin', _('Organization Administrator')
        ORG_USER = 'org_user', _('Organization User')
    
    class SecurityLevel(models.IntegerChoices):
        BASIC = 1, _('Basic')  # Password only
        STANDARD = 2, _('Standard')  # Password + Email OTP
        ENHANCED = 3, _('Enhanced')  # Password + TOTP
        STRICT = 4, _('Strict')  # Password + TOTP + Hardware key
    
    # Core Profile Fields
    uuid = models.UUIDField(
        default=uuid.uuid4, 
        unique=True, 
        editable=False,
        verbose_name=_('Unique Identifier')
    )
    role = models.CharField(
        max_length=20, 
        choices=Role.choices, 
        default=Role.ORG_USER,
        verbose_name=_('User Role')
    )
    
    # Remove username, use email as primary identifier
    username = None
    email = models.EmailField(_('email address'), unique=True)
    
    # Organization relationship
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='users',
        null=True,
        blank=True,
        verbose_name=_('Organization')
    )
    
    # Identity Provider (for SSO)
    identity_provider = models.CharField(
        max_length=20,
        choices=[
            ('email', 'Email + Password'),
            ('google', 'Google OAuth'),
            ('microsoft', 'Microsoft OAuth'),
        ],
        default='email',
        verbose_name=_('Identity Provider')
    )
    
    # Contact Information
    phone_number = PhoneNumberField(
        blank=True, 
        verbose_name=_('Phone Number')
    )
    phone_verified = models.BooleanField(
        default=False,
        verbose_name=_('Phone Verified')
    )
    phone_verification_code = models.CharField(
        max_length=6, 
        blank=True,
        verbose_name=_('Phone Verification Code')
    )
    phone_verification_sent_at = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name=_('Phone Verification Sent At')
    )
    
    # Email Verification
    email_verified = models.BooleanField(
        default=False,
        verbose_name=_('Email Verified')
    )
    email_verification_token = models.CharField(
        max_length=100, 
        blank=True,
        verbose_name=_('Email Verification Token')
    )
    email_verification_sent_at = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name=_('Email Verification Sent At')
    )
    
    # Password Security
    password_changed_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Password Changed At')
    )
    password_expires_at = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name=_('Password Expires At')
    )
    previous_passwords = models.JSONField(
        default=list,
        verbose_name=_('Previous Passwords Hashes'),
        help_text=_('Stores hashes of previous passwords to prevent reuse'),
        blank=True
    )
    password_reset_token = EncryptedCharField(
        max_length=100, 
        blank=True,
        verbose_name=_('Password Reset Token')
    )
    password_reset_sent_at = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name=_('Password Reset Sent At')
    )
    
    # Multi-Factor Authentication
    mfa_enabled = models.BooleanField(
        default=False,
        verbose_name=_('MFA Enabled')
    )
    mfa_method = models.CharField(
        max_length=20,
        choices=[
            ('totp', _('TOTP (Google Authenticator)')),
            ('email', _('Email OTP')),
            ('sms', _('SMS OTP')),
        ],
        default='totp',
        verbose_name=_('MFA Method')
    )
    mfa_secret = EncryptedCharField(
        max_length=100, 
        blank=True,
        verbose_name=_('MFA Secret')
    )
    mfa_backup_codes = models.JSONField(
        default=list,
        verbose_name=_('MFA Backup Codes'),
        help_text=_('Encrypted backup codes for MFA recovery'),
        blank=True
    )
    mfa_setup_completed = models.BooleanField(
        default=False,
        verbose_name=_('MFA Setup Completed')
    )
    
    # Security Settings
    security_level = models.IntegerField(
        choices=SecurityLevel.choices,
        default=SecurityLevel.BASIC,
        verbose_name=_('Security Level')
    )
    failed_login_attempts = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Failed Login Attempts')
    )
    locked_until = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name=_('Locked Until')
    )
    last_login_ip = models.GenericIPAddressField(
        null=True, 
        blank=True,
        verbose_name=_('Last Login IP')
    )
    current_login_ip = models.GenericIPAddressField(
        null=True, 
        blank=True,
        verbose_name=_('Current Login IP')
    )
    
    # Session Management
    last_activity = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Last Activity')
    )
    session_expiry = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name=_('Session Expiry')
    )
    concurrent_sessions = models.PositiveIntegerField(
        default=3,
        verbose_name=_('Max Concurrent Sessions')
    )
    
    # Account Status & Compliance
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Active')
    )
    deactivated_at = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name=_('Deactivated At')
    )
    deactivation_reason = models.TextField(
        blank=True,
        verbose_name=_('Deactivation Reason')
    )
    must_change_password = models.BooleanField(
        default=False,
        verbose_name=_('Must Change Password')
    )
    terms_accepted = models.BooleanField(
        default=False,
        verbose_name=_('Terms Accepted')
    )
    terms_accepted_at = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name=_('Terms Accepted At')
    )
    privacy_policy_accepted = models.BooleanField(
        default=False,
        verbose_name=_('Privacy Policy Accepted')
    )
    privacy_policy_accepted_at = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name=_('Privacy Policy Accepted At')
    )
    
    # Profile & Preferences
    timezone = models.CharField(
        max_length=50, 
        default='UTC',
        verbose_name=_('Timezone')
    )
    language = models.CharField(
        max_length=10, 
        default='en',
        verbose_name=_('Language')
    )
    date_format = models.CharField(
        max_length=20, 
        default='YYYY-MM-DD',
        verbose_name=_('Date Format')
    )
    
    notification_settings = models.JSONField(
        default=dict,
        verbose_name=_('Notification Preferences'),
        blank=True
    )
    
    # Audit & Metadata
    created_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_users',
        verbose_name=_('Created By')
    )
    last_modified_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='modified_users',
        verbose_name=_('Last Modified By')
    )
    metadata = models.JSONField(
        default=dict,
        verbose_name=_('Metadata'),
        blank=True
    )

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        db_table = 'users'
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['email', 'is_active']),
            models.Index(fields=['role', 'is_active']),
            models.Index(fields=['organization', 'is_active']),
            models.Index(fields=['email_verification_token']),
            models.Index(fields=['password_reset_token']),
            models.Index(fields=['uuid']),
            models.Index(fields=['last_activity']),
            models.Index(fields=['locked_until']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['email'],
                name='unique_active_email',
                condition=models.Q(is_active=True)
            ),
        ]

    def __str__(self):
        return f"{self.get_full_name()} ({self.email}) - {self.get_role_display()}"

    def save(self, *args, **kwargs):
        """
        Enhanced save method with comprehensive validation and automation.
        """
        self._pre_save_validation()
        super().save(*args, **kwargs)
        self._post_save_actions()

    def _pre_save_validation(self):
        """Pre-save validation and field automation."""
        # Email normalization
        if self.email:
            self.email = self.__class__.objects.normalize_email(self.email)
        
        # Generate email verification token if needed
        if not self.email_verification_token and not self.email_verified:
            self.email_verification_token = self._generate_secure_token()
            self.email_verification_sent_at = timezone.now()
        
        # Set password expiry for non-admin users
        if not self.is_superuser and not self.password_expires_at:
            self.password_expires_at = timezone.now() + timedelta(days=90)
        
        # Track deactivation
        if self.pk and not self.is_active:
            try:
                original = User.objects.get(pk=self.pk)
                if original.is_active and not self.is_active:
                    self.deactivated_at = timezone.now()
            except User.DoesNotExist:
                pass

    def _post_save_actions(self):
        """Actions to perform after saving."""
        pass

    # Security Methods
    def _generate_secure_token(self, length: int = 32) -> str:
        """Generate cryptographically secure token."""
        return secrets.token_urlsafe(length)

    def generate_email_verification_token(self) -> str:
        """Generate new email verification token."""
        self.email_verification_token = self._generate_secure_token()
        self.email_verification_sent_at = timezone.now()
        self.email_verified = False
        self.save()
        return self.email_verification_token

    def verify_email(self, token: str) -> bool:
        """Verify email with token (with expiration check)."""
        if not self.email_verification_token or not self.email_verification_sent_at:
            return False
            
        token_age = timezone.now() - self.email_verification_sent_at
        if token_age.total_seconds() > 24 * 3600:  # 24 hours
            return False
            
        if secrets.compare_digest(self.email_verification_token, token):
            self.email_verified = True
            self.email_verification_token = ''
            self.email_verification_sent_at = None
            self.save()
            return True
        return False

    def generate_phone_verification_code(self) -> str:
        """Generate phone verification code."""
        self.phone_verification_code = get_random_string(6, '0123456789')
        self.phone_verification_sent_at = timezone.now()
        self.phone_verified = False
        self.save()
        return self.phone_verification_code

    def verify_phone(self, code: str) -> bool:
        """Verify phone with code (with expiration check)."""
        if not self.phone_verification_code or not self.phone_verification_sent_at:
            return False
            
        code_age = timezone.now() - self.phone_verification_sent_at
        if code_age.total_seconds() > 600:  # 10 minutes
            return False
            
        if secrets.compare_digest(self.phone_verification_code, code):
            self.phone_verified = True
            self.phone_verification_code = ''
            self.phone_verification_sent_at = None
            self.save()
            return True
        return False

    # Password Management
    def set_password(self, raw_password: str):
        """Enhanced password setter with history tracking."""
        from django.contrib.auth.hashers import make_password
        
        # Validate password strength
        try:
            validate_password(raw_password, self)
        except ValidationError as e:
            raise ValidationError({'password': e.messages})
        
        # Store current password in history before changing
        if self.password:
            self.previous_passwords = self.previous_passwords[-4:]  # Keep last 5 passwords
            self.previous_passwords.append(self.password)
        
        # Set new password
        self.password = make_password(raw_password)
        self.password_changed_at = timezone.now()
        self.password_expires_at = timezone.now() + timedelta(days=90)
        self.must_change_password = False
        self.failed_login_attempts = 0
        self.locked_until = None

    def check_password(self, raw_password: str) -> bool:
        """Check password with additional security checks."""
        if self.is_account_locked():
            return False
            
        result = super().check_password(raw_password)
        
        if result:
            self.reset_failed_logins()
        else:
            self.increment_failed_login()
            
        return result

    def is_password_expired(self) -> bool:
        """Check if password has expired."""
        if self.password_expires_at and timezone.now() > self.password_expires_at:
            return True
        return False

    def is_password_reused(self, raw_password: str) -> bool:
        """Check if password has been used before."""
        from django.contrib.auth.hashers import check_password
        
        for old_password_hash in self.previous_passwords:
            if check_password(raw_password, old_password_hash):
                return True
        return False

    # MFA Methods
    def setup_totp_mfa(self) -> Dict[str, Any]:
        """Setup TOTP-based MFA."""
        secret = pyotp.random_base32()
        self.mfa_secret = secret
        self.mfa_method = 'totp'
        self.mfa_enabled = True
        self.mfa_setup_completed = False
        
        # Generate backup codes
        self.mfa_backup_codes = [self._generate_secure_token(8) for _ in range(10)]
        
        self.save()
        
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=self.email,
            issuer_name="DocBiz"
        )
        
        return {
            'secret': secret,
            'provisioning_uri': provisioning_uri,
            'backup_codes': self.mfa_backup_codes
        }

    def verify_totp_code(self, code: str) -> bool:
        """Verify TOTP code."""
        if not self.mfa_secret or not self.mfa_enabled:
            return False
            
        totp = pyotp.TOTP(self.mfa_secret)
        return totp.verify(code, valid_window=1)

    def use_backup_code(self, code: str) -> bool:
        """Use and invalidate a backup code."""
        if code in self.mfa_backup_codes:
            self.mfa_backup_codes.remove(code)
            self.save()
            return True
        return False

    # Account Security
    def increment_failed_login(self):
        """Increment failed login attempts and lock if necessary."""
        self.failed_login_attempts += 1
        
        if self.failed_login_attempts >= 15:
            self.locked_until = timezone.now() + timedelta(hours=24)
        elif self.failed_login_attempts >= 10:
            self.locked_until = timezone.now() + timedelta(hours=2)
        elif self.failed_login_attempts >= 5:
            self.locked_until = timezone.now() + timedelta(minutes=30)
            
        self.save()

    def reset_failed_logins(self):
        """Reset failed login attempts."""
        self.failed_login_attempts = 0
        self.locked_until = None
        self.save()

    def is_account_locked(self) -> bool:
        """Check if account is currently locked."""
        if self.locked_until and timezone.now() < self.locked_until:
            return True
        elif self.locked_until and timezone.now() >= self.locked_until:
            self.reset_failed_logins()
        return False

    def force_password_change(self):
        """Force user to change password on next login."""
        self.must_change_password = True
        self.save()

    # Role & Permission Methods
    def has_role(self, role: str) -> bool:
        """Check if user has specific role."""
        return self.role == role

    def is_super_admin(self) -> bool:
        """Check if user is a super admin."""
        return self.role == self.Role.SUPER_ADMIN

    def is_org_admin(self) -> bool:
        """Check if user is an organization admin."""
        return self.role == self.Role.ORG_ADMIN

    def is_org_user(self) -> bool:
        """Check if user is an organization user."""
        return self.role == self.Role.ORG_USER

    def get_permission_level(self) -> int:
        """Get numeric permission level for role hierarchy."""
        permission_levels = {
            self.Role.ORG_USER: 1,
            self.Role.ORG_ADMIN: 2,
            self.Role.SUPER_ADMIN: 3,
        }
        return permission_levels.get(self.role, 0)

    # Session Management
    def update_session_activity(self, ip_address: str = None):
        """Update user's last activity and IP address."""
        self.last_activity = timezone.now()
        if ip_address:
            self.last_login_ip = self.current_login_ip
            self.current_login_ip = ip_address
        self.save()

    def is_session_expired(self) -> bool:
        """Check if user's session has expired."""
        if self.session_expiry and timezone.now() > self.session_expiry:
            return True
        return False

    # Utility Methods
    def get_display_name(self) -> str:
        """Get user's display name."""
        if self.get_full_name():
            return self.get_full_name()
        return self.email

    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary for serialization."""
        return {
            'id': self.id,
            'uuid': str(self.uuid),
            'email': self.email,
            'role': self.role,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'phone_number': str(self.phone_number) if self.phone_number else None,
            'is_active': self.is_active,
            'email_verified': self.email_verified,
            'mfa_enabled': self.mfa_enabled,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
        }

    @classmethod
    def get_by_email(cls, email: str) -> Optional['User']:
        """Get user by email."""
        try:
            return cls.objects.get(email__iexact=email)
        except cls.DoesNotExist:
            return None

    # Cleanup and Compliance
    def anonymize_data(self):
        """Anonymize user data for GDPR compliance."""
        self.email = f"anonymous_{self.uuid}@anonymized.example"
        self.first_name = "Anonymous"
        self.last_name = "User"
        self.phone_number = ""
        self.save()


# Register with auditlog for comprehensive auditing
auditlog.register(User)