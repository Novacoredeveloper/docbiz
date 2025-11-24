import google.generativeai as genai
import openai
from anthropic import Anthropic
import time
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from .models import LLMProvider, LLMModel, LLMUsage, LLMQuota


class LLMService:
    """
    Main service for handling LLM interactions with rate limiting and usage tracking.
    Now with Gemini as default provider while maintaining backward compatibility.
    """
    
    def __init__(self, organization, user):
        self.organization = organization
        self.user = user
        self.quota = self._get_quota()
    
    def _get_quota(self):
        """Get or create quota for organization."""
        quota, created = LLMQuota.objects.get_or_create(
            organization=self.organization
        )
        return quota
    
    def _get_default_provider(self):
        """Get the default LLM provider - now prioritizes Gemini."""
        try:
            # First try to get Gemini provider
            gemini_provider = LLMProvider.objects.filter(
                provider_type=LLMProvider.ProviderType.GEMINI,
                is_active=True
            ).first()
            
            if gemini_provider:
                return gemini_provider
            
            # Fallback to any default provider for backward compatibility
            return LLMProvider.objects.get(is_default=True, is_active=True)
            
        except LLMProvider.DoesNotExist:
            raise Exception("No default LLM provider configured")
    
    def _get_default_model(self, provider, feature):
        """Get the default model for a provider and feature."""
        try:
            return LLMModel.objects.get(
                provider=provider,
                is_default=True,
                is_active=True
            )
        except LLMModel.DoesNotExist:
            # Fallback to any active model
            models = LLMModel.objects.filter(
                provider=provider,
                is_active=True
            )
            if models.exists():
                return models.first()
            raise Exception(f"No active models found for provider {provider.name}")
    
    def _check_rate_limit(self, provider):
        """Check rate limiting for provider."""
        cache_key = f"llm_rate_limit:{provider.id}:{int(time.time() // 60)}"
        current_requests = cache.get(cache_key, 0)
        
        if current_requests >= provider.requests_per_minute:
            raise Exception(f"Rate limit exceeded for {provider.name}")
        
        cache.set(cache_key, current_requests + 1, timeout=60)
    
    def _check_quota(self, estimated_tokens=0, estimated_cost=0):
        """Check if organization has quota for request."""
        can_proceed, message = self.quota.can_make_request(
            estimated_tokens, estimated_cost
        )
        if not can_proceed:
            raise Exception(message)
    
    def generate_content(self, prompt, feature, model=None, **kwargs):
        """
        Generate content using LLM with comprehensive tracking.
        Now supports Gemini as primary provider with fallbacks.
        
        Args:
            prompt: The input prompt
            feature: Feature type from LLMUsage.FeatureType
            model: Specific model to use (optional)
            **kwargs: Additional parameters for LLM call
        
        Returns:
            Generated content and usage information
        """
        start_time = time.time()
        
        try:
            # Get provider and model
            provider = self._get_default_provider()
            if not model:
                model = self._get_default_model(provider, feature)
            
            # Check rate limits and quotas
            self._check_rate_limit(provider)
            self._check_quota(estimated_tokens=len(prompt.split()))
            
            # Make API call based on provider
            if provider.provider_type == LLMProvider.ProviderType.GEMINI:
                result = self._call_gemini(provider, model, prompt, **kwargs)
            elif provider.provider_type == LLMProvider.ProviderType.OPENAI:
                result = self._call_openai(provider, model, prompt, **kwargs)
            elif provider.provider_type == LLMProvider.ProviderType.ANTHROPIC:
                result = self._call_anthropic(provider, model, prompt, **kwargs)
            else:
                raise Exception(f"Unsupported provider: {provider.provider_type}")
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Record usage
            self._record_usage(
                provider=provider,
                model=model,
                feature=feature,
                prompt=prompt,
                generated_content=result['content'],
                tokens_prompt=result['usage']['prompt_tokens'],
                tokens_completion=result['usage']['completion_tokens'],
                request_duration=duration,
                provider_request_id=result.get('request_id'),
                model_used=result.get('model_used', model.name),
                status=LLMUsage.StatusType.SUCCESS,
                **kwargs
            )
            
            return {
                'content': result['content'],
                'usage': {
                    'tokens_prompt': result['usage']['prompt_tokens'],
                    'tokens_completion': result['usage']['completion_tokens'],
                    'tokens_total': result['usage']['prompt_tokens'] + result['usage']['completion_tokens'],
                    'cost_estimated': result.get('cost_estimated', 0),
                    'request_duration': duration
                }
            }
            
        except Exception as e:
            # Record failed usage
            duration = time.time() - start_time
            self._record_usage(
                provider=provider if 'provider' in locals() else None,
                model=model if 'model' in locals() else None,
                feature=feature,
                prompt=prompt,
                generated_content='',
                tokens_prompt=0,
                tokens_completion=0,
                request_duration=duration,
                status=LLMUsage.StatusType.ERROR,
                error_message=str(e),
                **kwargs
            )
            raise e
    
    def _call_gemini(self, provider, model, prompt, **kwargs):
        """Make Gemini API call."""
        # Configure Gemini if not already configured
        if not genai.api_key:
            genai.configure(api_key=settings.GEMINI_API_KEY)
        
        # Create model instance
        gemini_model = genai.GenerativeModel(model.name)
        
        # Prepare generation config
        generation_config = genai.types.GenerationConfig(
            temperature=kwargs.get('temperature', 0.3),
            top_p=kwargs.get('top_p', 0.8),
            top_k=kwargs.get('top_k', 40),
            max_output_tokens=kwargs.get('max_tokens', model.max_output_tokens),
        )
        
        # Generate content
        response = gemini_model.generate_content(
            prompt,
            generation_config=generation_config
        )
        
        # Estimate token usage (Gemini doesn't provide exact counts in some tiers)
        prompt_tokens = self._estimate_gemini_tokens(prompt)
        completion_tokens = self._estimate_gemini_tokens(response.text)
        
        return {
            'content': response.text,
            'usage': {
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
            },
            'request_id': getattr(response, 'prompt_feedback', None),
            'model_used': model.name,
            'cost_estimated': model.calculate_cost(prompt_tokens, completion_tokens)
        }
    
    def _estimate_gemini_tokens(self, text):
        """Estimate token count for Gemini (rough approximation)."""
        # Gemini uses a similar tokenizer to GPT, roughly 1 token = 4 characters
        # This is a conservative estimate for billing purposes
        return max(1, len(text) // 4)
    
    def _call_openai(self, provider, model, prompt, **kwargs):
        """Make OpenAI API call."""
        client = openai.OpenAI(
            api_key=provider.api_key,
            base_url=provider.base_url if provider.base_url else None
        )
        
        response = client.chat.completions.create(
            model=model.name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=kwargs.get('max_tokens', model.max_output_tokens),
            temperature=kwargs.get('temperature', 0.3),
            **{k: v for k, v in kwargs.items() if k in ['functions', 'function_call']}
        )
        
        return {
            'content': response.choices[0].message.content,
            'usage': {
                'prompt_tokens': response.usage.prompt_tokens,
                'completion_tokens': response.usage.completion_tokens,
            },
            'request_id': response.id,
            'model_used': response.model,
            'cost_estimated': model.calculate_cost(
                response.usage.prompt_tokens,
                response.usage.completion_tokens
            )
        }
    
    def _call_anthropic(self, provider, model, prompt, **kwargs):
        """Make Anthropic API call."""
        client = Anthropic(api_key=provider.api_key)
        
        response = client.messages.create(
            model=model.name,
            max_tokens=kwargs.get('max_tokens', model.max_output_tokens),
            temperature=kwargs.get('temperature', 0.3),
            messages=[{"role": "user", "content": prompt}]
        )
        
        return {
            'content': response.content[0].text,
            'usage': {
                'prompt_tokens': response.usage.input_tokens,
                'completion_tokens': response.usage.output_tokens,
            },
            'request_id': response.id,
            'model_used': model.name,
            'cost_estimated': model.calculate_cost(
                response.usage.input_tokens,
                response.usage.output_tokens
            )
        }
    
    def _record_usage(self, provider, model, feature, prompt, generated_content, 
                     tokens_prompt, tokens_completion, request_duration, 
                     status, provider_request_id=None, model_used=None, 
                     error_message='', **kwargs):
        """Record LLM usage in database."""
        
        # Calculate cost
        cost_estimated = 0
        if model and tokens_prompt + tokens_completion > 0:
            cost_estimated = model.calculate_cost(tokens_prompt, tokens_completion)
        
        # Create usage record
        usage = LLMUsage.objects.create(
            organization=self.organization,
            user=self.user,
            provider=provider,
            model=model,
            feature=feature,
            status=status,
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
            tokens_total=tokens_prompt + tokens_completion,
            cost_estimated=cost_estimated,
            cost_calculated=cost_estimated,
            provider_request_id=provider_request_id,
            model_used=model_used,
            request_duration=request_duration,
            input_context=prompt,
            generated_content=generated_content,
            error_message=error_message,
            metadata={
                'temperature': kwargs.get('temperature'),
                'max_tokens': kwargs.get('max_tokens'),
                'additional_params': {k: v for k, v in kwargs.items() 
                                   if k not in ['temperature', 'max_tokens', 'contract']}
            }
        )
        
        # Add contract if provided
        contract = kwargs.get('contract')
        if contract:
            usage.contract = contract
            usage.save()
        
        # Update quota
        if status == LLMUsage.StatusType.SUCCESS:
            self.quota.record_usage(tokens_prompt, tokens_completion, cost_estimated)
        
        return usage


# Backward compatibility alias - existing code can continue using LLMService
# while automatically getting Gemini as default
PrimaryLLMService = LLMService


class MultiProviderLLMService:
    """
    Enhanced service with explicit provider selection and fallback capabilities.
    This provides more control while maintaining the same interface.
    """
    
    def __init__(self, organization, user):
        self.organization = organization
        self.user = user
        self.primary_service = LLMService(organization, user)
    
    def generate_content(self, prompt, feature, preferred_provider=None, **kwargs):
        """
        Generate content with optional provider preference.
        
        Args:
            prompt: The input prompt
            feature: Feature type from LLMUsage.FeatureType
            preferred_provider: Optional provider type to prefer
            **kwargs: Additional parameters for LLM call
        
        Returns:
            Generated content and usage information
        """
        # For now, delegate to primary service
        # Future enhancement: implement smart provider selection
        return self.primary_service.generate_content(prompt, feature, **kwargs)


class AnalyticsService:
    """
    Service for generating LLM usage analytics and reports.
    """
    
    def __init__(self, organization):
        self.organization = organization
    
    def get_usage_summary(self, days=30):
        """Get usage summary for the last N days."""
        from django.utils import timezone
        from datetime import timedelta
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        usage_data = LLMUsage.objects.filter(
            organization=self.organization,
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        total_usage = usage_data.aggregate(
            total_requests=models.Count('id'),
            successful_requests=models.Count('id', filter=models.Q(status='success')),
            total_tokens=models.Sum('tokens_total'),
            total_cost=models.Sum('cost_estimated')
        )
        
        # Feature breakdown
        feature_breakdown = usage_data.values('feature').annotate(
            count=models.Count('id'),
            tokens=models.Sum('tokens_total'),
            cost=models.Sum('cost_estimated')
        ).order_by('-tokens')
        
        # Provider breakdown
        provider_breakdown = usage_data.values('provider__name').annotate(
            count=models.Count('id'),
            tokens=models.Sum('tokens_total'),
            cost=models.Sum('cost_estimated')
        ).order_by('-tokens')
        
        return {
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': days
            },
            'summary': total_usage,
            'feature_breakdown': list(feature_breakdown),
            'provider_breakdown': list(provider_breakdown),
            'daily_usage': self._get_daily_usage(start_date, end_date)
        }
    
    def _get_daily_usage(self, start_date, end_date):
        """Get daily usage breakdown."""
        from django.db.models.functions import TruncDate
        
        daily_usage = LLMUsage.objects.filter(
            organization=self.organization,
            created_at__gte=start_date,
            created_at__lte=end_date
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            requests=models.Count('id'),
            tokens=models.Sum('tokens_total'),
            cost=models.Sum('cost_estimated')
        ).order_by('date')
        
        return list(daily_usage)
    
    def generate_monthly_report(self, year=None, month=None):
        """Generate monthly analytics report."""
        from django.utils import timezone
        from datetime import datetime
        
        if not year or not month:
            now = timezone.now()
            year = now.year
            month = now.month
        
        period_start = datetime(year, month, 1)
        if month == 12:
            period_end = datetime(year + 1, 1, 1)
        else:
            period_end = datetime(year, month + 1, 1)
        
        # Get or create analytics record
        analytics, created = LLMAnalytics.objects.get_or_create(
            organization=self.organization,
            period_start=period_start,
            period_end=period_end,
            period_type='monthly',
            defaults=self._calculate_analytics(period_start, period_end)
        )
        
        if not created:
            # Update existing record
            analytics_data = self._calculate_analytics(period_start, period_end)
            for key, value in analytics_data.items():
                setattr(analytics, key, value)
            analytics.save()
        
        return analytics
    
    def _calculate_analytics(self, period_start, period_end):
        """Calculate analytics for a period."""
        usage_data = LLMUsage.objects.filter(
            organization=self.organization,
            created_at__gte=period_start,
            created_at__lt=period_end
        )
        
        aggregates = usage_data.aggregate(
            total_requests=models.Count('id'),
            successful_requests=models.Count('id', filter=models.Q(status='success')),
            total_tokens=models.Sum('tokens_total'),
            prompt_tokens=models.Sum('tokens_prompt'),
            completion_tokens=models.Sum('tokens_completion'),
            total_cost=models.Sum('cost_estimated'),
            avg_response_time=models.Avg('request_duration')
        )
        
        # Feature breakdown
        feature_breakdown = {}
        for feature in usage_data.values('feature').annotate(
            count=models.Count('id'),
            tokens=models.Sum('tokens_total'),
            cost=models.Sum('cost_estimated')
        ):
            feature_breakdown[feature['feature']] = feature
        
        # Provider breakdown
        provider_breakdown = {}
        for provider in usage_data.values('provider__name').annotate(
            count=models.Count('id'),
            tokens=models.Sum('tokens_total'),
            cost=models.Sum('cost_estimated')
        ):
            provider_breakdown[provider['provider__name']] = provider
        
        return {
            'total_requests': aggregates['total_requests'] or 0,
            'successful_requests': aggregates['successful_requests'] or 0,
            'failed_requests': (aggregates['total_requests'] or 0) - (aggregates['successful_requests'] or 0),
            'total_tokens': aggregates['total_tokens'] or 0,
            'prompt_tokens': aggregates['prompt_tokens'] or 0,
            'completion_tokens': aggregates['completion_tokens'] or 0,
            'total_cost': aggregates['total_cost'] or 0,
            'avg_response_time': aggregates['avg_response_time'] or 0,
            'feature_breakdown': feature_breakdown,
            'provider_breakdown': provider_breakdown,
        }