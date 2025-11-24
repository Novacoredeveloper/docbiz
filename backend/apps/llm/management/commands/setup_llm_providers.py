from django.core.management.base import BaseCommand
from apps.llm.models import LLMProvider, LLMModel

class Command(BaseCommand):
    help = 'Setup LLM providers and models with Gemini as default'
    
    def handle(self, *args, **options):
        # Create Gemini provider (now as default)
        gemini, created = LLMProvider.objects.get_or_create(
            name='Google Gemini',
            provider_type='gemini',
            defaults={
                'is_default': True,  # Gemini is now the default
                'is_active': True,
                'requests_per_minute': 60,
                'tokens_per_minute': 100000
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('Created Gemini provider as default'))
        else:
            # Update existing Gemini to be default
            gemini.is_default = True
            gemini.save()
            self.stdout.write(self.style.SUCCESS('Updated Gemini provider as default'))
        
        # Create OpenAI provider (now as fallback)
        openai, created = LLMProvider.objects.get_or_create(
            name='OpenAI',
            provider_type='openai',
            defaults={
                'is_default': False,  # No longer default
                'is_active': True,
                'requests_per_minute': 60,
                'tokens_per_minute': 100000
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('Created OpenAI provider as fallback'))
        else:
            # Ensure OpenAI is not default
            openai.is_default = False
            openai.save()
            self.stdout.write(self.style.SUCCESS('Updated OpenAI provider as fallback'))
        
        # Create Anthropic provider (as secondary fallback)
        anthropic, created = LLMProvider.objects.get_or_create(
            name='Anthropic',
            provider_type='anthropic',
            defaults={
                'is_default': False,
                'is_active': True,
                'requests_per_minute': 60,
                'tokens_per_minute': 100000
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('Created Anthropic provider as fallback'))
        
        # Create default models - Gemini first
        models_data = [
            # Gemini models (now primary)
            {
                'provider': gemini,
                'name': 'gemini-pro',
                'model_type': 'chat',
                'context_window': 32768,
                'input_price': 0.000125,  # Much cheaper than GPT-4
                'output_price': 0.000375,
                'is_default': True,  # Default model for Gemini
                'description': 'Google Gemini Pro - Best for most tasks'
            },
            {
                'provider': gemini,
                'name': 'gemini-pro-vision',
                'model_type': 'chat',
                'context_window': 32768,
                'input_price': 0.000125,
                'output_price': 0.000375,
                'is_default': False,
                'supports_vision': True,
                'description': 'Google Gemini Pro Vision - Supports image analysis'
            },
            # OpenAI models (fallback)
            {
                'provider': openai,
                'name': 'gpt-4',
                'model_type': 'chat',
                'context_window': 8192,
                'input_price': 0.03,
                'output_price': 0.06,
                'is_default': True,  # Default model for OpenAI
                'description': 'OpenAI GPT-4 - High quality but expensive'
            },
            {
                'provider': openai,
                'name': 'gpt-4-turbo',
                'model_type': 'chat',
                'context_window': 128000,
                'input_price': 0.01,
                'output_price': 0.03,
                'is_default': False,
                'description': 'OpenAI GPT-4 Turbo - Larger context, cheaper than GPT-4'
            },
            {
                'provider': openai,
                'name': 'gpt-3.5-turbo',
                'model_type': 'chat',
                'context_window': 4096,
                'input_price': 0.0015,
                'output_price': 0.002,
                'is_default': False,
                'description': 'OpenAI GPT-3.5 Turbo - Fast and cost-effective'
            },
            # Anthropic models (secondary fallback)
            {
                'provider': anthropic,
                'name': 'claude-3-sonnet-20240229',
                'model_type': 'chat',
                'context_window': 200000,
                'input_price': 0.03,
                'output_price': 0.15,
                'is_default': True,  # Default model for Anthropic
                'description': 'Anthropic Claude 3 Sonnet - Balanced performance'
            },
            {
                'provider': anthropic,
                'name': 'claude-3-opus-20240229',
                'model_type': 'chat',
                'context_window': 200000,
                'input_price': 0.15,
                'output_price': 0.75,
                'is_default': False,
                'description': 'Anthropic Claude 3 Opus - Highest quality, most expensive'
            },
            {
                'provider': anthropic,
                'name': 'claude-3-haiku-20240307',
                'model_type': 'chat',
                'context_window': 200000,
                'input_price': 0.00025,
                'output_price': 0.00125,
                'is_default': False,
                'description': 'Anthropic Claude 3 Haiku - Fast and inexpensive'
            }
        ]
        
        created_count = 0
        updated_count = 0
        
        for model_data in models_data:
            obj, created = LLMModel.objects.get_or_create(
                provider=model_data['provider'],
                name=model_data['name'],
                defaults=model_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created model: {model_data["provider"].name} - {model_data["name"]}')
                )
            else:
                # Update existing model with new pricing and settings
                for key, value in model_data.items():
                    if key != 'provider':  # Don't change the provider relationship
                        setattr(obj, key, value)
                obj.save()
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'Updated model: {model_data["provider"].name} - {model_data["name"]}')
                )
        
        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully setup LLM providers and models. '
                f'Created: {created_count}, Updated: {updated_count}. '
                f'Gemini is now the default provider.'
            )
        )
        
        # Display cost comparison
        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.SUCCESS("COST COMPARISON (per 1K tokens)"))
        self.stdout.write("="*50)
        
        gemini_pro = LLMModel.objects.get(name='gemini-pro')
        gpt4 = LLMModel.objects.get(name='gpt-4')
        claude_sonnet = LLMModel.objects.get(name='claude-3-sonnet-20240229')
        
        self.stdout.write(f"Gemini Pro:     ${gemini_pro.input_price:.6f} input / ${gemini_pro.output_price:.6f} output")
        self.stdout.write(f"GPT-4:          ${gpt4.input_price:.3f} input / ${gpt4.output_price:.3f} output")
        self.stdout.write(f"Claude Sonnet:  ${claude_sonnet.input_price:.3f} input / ${claude_sonnet.output_price:.3f} output")
        
        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.SUCCESS("SAVINGS WITH GEMINI:"))
        self.stdout.write("="*50)
        
        gemini_input_cost = gemini_pro.input_price * 1000
        gpt4_input_cost = gpt4.input_price * 1000
        savings_percentage = ((gpt4_input_cost - gemini_input_cost) / gpt4_input_cost) * 100
        
        self.stdout.write(f"Input tokens:  {savings_percentage:.1f}% cheaper than GPT-4")
        self.stdout.write(f"Output tokens: {((gpt4.output_price - gemini_pro.output_price) / gpt4.output_price * 100):.1f}% cheaper than GPT-4")
        self.stdout.write(f"Example: 10K tokens ≈ ${gpt4_input_cost * 10:.2f} (GPT-4) vs ${gemini_input_cost * 10:.4f} (Gemini)")