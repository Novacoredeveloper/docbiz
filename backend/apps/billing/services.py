from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from .models import SubscriptionPlan, OrganizationSubscription, Invoice


class BillingService:
    """
    Service for handling billing operations and subscription management.
    """
    
    def __init__(self, organization):
        self.organization = organization
        self.subscription = self._get_subscription()
    
    def _get_subscription(self):
        """Get organization's subscription."""
        try:
            return OrganizationSubscription.objects.get(organization=self.organization)
        except OrganizationSubscription.DoesNotExist:
            # Create free subscription if none exists
            free_plan = SubscriptionPlan.objects.get(tier=SubscriptionPlan.TierType.FREE)
            return OrganizationSubscription.objects.create(
                organization=self.organization,
                plan=free_plan,
                status=OrganizationSubscription.StatusType.ACTIVE
            )
    
    def can_upgrade(self, target_plan_tier):
        """Check if organization can upgrade to target plan."""
        try:
            target_plan = SubscriptionPlan.objects.get(tier=target_plan_tier, is_active=True)
            return self.subscription.plan.can_upgrade_to(target_plan)
        except SubscriptionPlan.DoesNotExist:
            return False
    
    def upgrade_subscription(self, target_plan_tier, billing_cycle='monthly'):
        """Upgrade organization's subscription."""
        if not self.can_upgrade(target_plan_tier):
            raise Exception(f"Cannot upgrade from {self.subscription.plan.tier} to {target_plan_tier}")
        
        target_plan = SubscriptionPlan.objects.get(tier=target_plan_tier, is_active=True)
        
        # Calculate prorated amount for the current period
        prorated_credit = self._calculate_prorated_credit()
        
        # Create invoice for the upgrade
        invoice = self._create_upgrade_invoice(target_plan, billing_cycle, prorated_credit)
        
        # Update subscription
        old_plan = self.subscription.plan
        self.subscription.plan = target_plan
        self.subscription.billing_cycle = billing_cycle
        self.subscription.current_price = self._get_plan_price(target_plan, billing_cycle)
        self.subscription.save()
        
        # Update usage metrics
        self.subscription.update_usage_metrics()
        
        return {
            'success': True,
            'old_plan': old_plan.name,
            'new_plan': target_plan.name,
            'invoice': invoice.invoice_number,
            'amount_due': invoice.amount_due
        }
    
    def downgrade_subscription(self, target_plan_tier):
        """Downgrade organization's subscription (effective at end of billing period)."""
        target_plan = SubscriptionPlan.objects.get(tier=target_plan_tier, is_active=True)
        
        if not self.subscription.plan.can_upgrade_to(target_plan):
            # This is a downgrade
            self.subscription.plan = target_plan
            self.subscription.billing_cycle = 'monthly'  # Downgrades always to monthly
            self.subscription.current_price = target_plan.monthly_price
            self.subscription.save()
            
            return {
                'success': True,
                'message': f'Subscription will be downgraded to {target_plan.name} at the end of the billing period',
                'effective_date': self.subscription.current_period_end
            }
        
        raise Exception(f"Cannot downgrade to {target_plan_tier}")
    
    def cancel_subscription(self):
        """Cancel organization's subscription."""
        self.subscription.status = OrganizationSubscription.StatusType.CANCELLED
        self.subscription.cancelled_at = timezone.now()
        self.subscription.save()
        
        return {
            'success': True,
            'message': 'Subscription cancelled successfully',
            'cancelled_at': self.subscription.cancelled_at
        }
    
    def create_invoice(self):
        """Create invoice for the current billing period."""
        # Check if invoice already exists for this period
        period_start = self.subscription.current_period_start
        period_end = self.subscription.current_period_end
        
        existing_invoice = Invoice.objects.filter(
            subscription=self.subscription,
            invoice_date__gte=period_start,
            invoice_date__lte=period_end,
            status__in=[Invoice.StatusType.DRAFT, Invoice.StatusType.OPEN]
        ).first()
        
        if existing_invoice:
            return existing_invoice
        
        # Create new invoice
        line_items = [{
            'description': f"{self.subscription.plan.name} Subscription",
            'amount': float(self.subscription.current_price),
            'quantity': 1,
            'total': float(self.subscription.current_price)
        }]
        
        total_amount = self.subscription.current_price
        
        invoice = Invoice.objects.create(
            organization=self.organization,
            subscription=self.subscription,
            amount_due=total_amount,
            total_amount=total_amount,
            due_date=timezone.now() + timedelta(days=30),
            line_items=line_items
        )
        
        return invoice
    
    def _calculate_prorated_credit(self):
        """Calculate prorated credit for unused portion of current subscription."""
        now = timezone.now()
        period_start = self.subscription.current_period_start
        period_end = self.subscription.current_period_end
        
        total_days = (period_end - period_start).days
        days_used = (now - period_start).days
        days_remaining = total_days - days_used
        
        if days_remaining <= 0:
            return Decimal('0')
        
        daily_rate = self.subscription.current_price / total_days
        return daily_rate * days_remaining
    
    def _get_plan_price(self, plan, billing_cycle):
        """Get price for plan based on billing cycle."""
        if billing_cycle == 'annual':
            return plan.annual_price or plan.monthly_price * 12 * Decimal('0.8')
        return plan.monthly_price
    
    def _create_upgrade_invoice(self, target_plan, billing_cycle, prorated_credit):
        """Create invoice for subscription upgrade."""
        new_price = self._get_plan_price(target_plan, billing_cycle)
        amount_due = new_price - prorated_credit
        
        line_items = []
        
        if prorated_credit > 0:
            line_items.append({
                'description': f"Prorated credit from {self.subscription.plan.name}",
                'amount': float(-prorated_credit),
                'quantity': 1,
                'total': float(-prorated_credit)
            })
        
        line_items.append({
            'description': f"{target_plan.name} Subscription",
            'amount': float(new_price),
            'quantity': 1,
            'total': float(new_price)
        })
        
        invoice = Invoice.objects.create(
            organization=self.organization,
            subscription=self.subscription,
            amount_due=max(amount_due, Decimal('0')),  # Ensure non-negative
            total_amount=new_price,
            due_date=timezone.now() + timedelta(days=30),
            line_items=line_items
        )
        
        return invoice


class UsageService:
    """
    Service for tracking and validating usage against subscription limits.
    """
    
    def __init__(self, organization):
        self.organization = organization
        self.subscription = OrganizationSubscription.objects.get(organization=organization)
    
    def check_user_limit(self):
        """Check if organization can add another user."""
        return self.subscription.can_add_user()
    
    def check_entity_limit(self):
        """Check if organization can add another entity."""
        return self.subscription.can_add_entity()
    
    def check_contract_limit(self):
        """Check if organization can create another contract."""
        return self.subscription.can_create_contract()
    
    def check_llm_limit(self, estimated_tokens):
        """Check if organization can use estimated LLM tokens."""
        if self.subscription.plan.monthly_llm_tokens == 0:  # Unlimited
            return True
        
        available_tokens = self.subscription.plan.monthly_llm_tokens - self.subscription.llm_tokens_used_this_month
        return estimated_tokens <= available_tokens
    
    def check_feature_access(self, feature):
        """Check if organization has access to a specific feature."""
        return self.subscription.has_feature(feature)
    
    def record_contract_usage(self):
        """Record contract creation usage."""
        if not self.check_contract_limit():
            raise Exception("Contract limit exceeded for current subscription")
        
        self.subscription.contracts_used_this_month += 1
        self.subscription.save()
    
    def record_llm_usage(self, tokens_used):
        """Record LLM token usage."""
        if not self.check_llm_limit(tokens_used):
            raise Exception("LLM token limit exceeded for current subscription")
        
        self.subscription.llm_tokens_used_this_month += tokens_used
        self.subscription.save()
    
    def get_usage_summary(self):
        """Get comprehensive usage summary."""
        return {
            'users': {
                'current': self.subscription.users_count,
                'limit': self.subscription.plan.max_users,
                'percentage': self._calculate_percentage(
                    self.subscription.users_count, 
                    self.subscription.plan.max_users
                )
            },
            'entities': {
                'current': self.subscription.entities_count,
                'limit': self.subscription.plan.max_entities,
                'percentage': self._calculate_percentage(
                    self.subscription.entities_count, 
                    self.subscription.plan.max_entities
                )
            },
            'contracts': {
                'current': self.subscription.contracts_used_this_month,
                'limit': self.subscription.plan.max_contracts_per_month,
                'percentage': self._calculate_percentage(
                    self.subscription.contracts_used_this_month, 
                    self.subscription.plan.max_contracts_per_month
                )
            },
            'llm_tokens': {
                'current': self.subscription.llm_tokens_used_this_month,
                'limit': self.subscription.plan.monthly_llm_tokens,
                'percentage': self._calculate_percentage(
                    self.subscription.llm_tokens_used_this_month, 
                    self.subscription.plan.monthly_llm_tokens
                )
            }
        }
    
    def _calculate_percentage(self, current, limit):
        """Calculate usage percentage."""
        if not limit:  # Unlimited
            return 0
        return min((current / limit) * 100, 100)