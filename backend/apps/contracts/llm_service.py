import openai
from anthropic import Anthropic
import json
from django.conf import settings
from django.utils import timezone
from .models import LLMUsage, LegalReferenceLibrary


class LLMService:
    """Service for handling LLM interactions with legal grounding."""
    
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
        self.anthropic_client = Anthropic(api_key=settings.ANTHROPIC_API_KEY) if settings.ANTHROPIC_API_KEY else None
    
    def generate_clause(self, clause_type, context, contract, user):
        """Generate a legal clause using AI with legal grounding."""
        # Get relevant legal references
        legal_references = self._get_relevant_references(clause_type, contract)
        
        # Prepare prompt with legal grounding
        prompt = self._build_clause_generation_prompt(clause_type, context, legal_references)
        
        # Call LLM
        response = self._call_llm(
            prompt=prompt,
            feature='clause_gen',
            contract=contract,
            user=user,
            legal_references=legal_references
        )
        
        return {
            'clause': response['content'],
            'legal_references': [ref.id for ref in legal_references],
            'usage': response['usage']
        }
    
    def edit_contract(self, instruction, content, contract, user):
        """Edit contract content using AI."""
        # Get relevant legal references based on contract content
        legal_references = self._get_references_for_content(content)
        
        # Prepare editing prompt
        prompt = self._build_editing_prompt(instruction, content, legal_references)
        
        # Call LLM
        response = self._call_llm(
            prompt=prompt,
            feature='edit',
            contract=contract,
            user=user,
            legal_references=legal_references
        )
        
        return {
            'edited_content': response['content'],
            'explanation': response.get('explanation', ''),
            'usage': response['usage']
        }
    
    def _get_relevant_references(self, clause_type, contract):
        """Get relevant legal references for clause generation."""
        # Map clause types to legal topics
        topic_map = {
            'confidentiality': ['confidentiality', 'nda', 'trade_secrets'],
            'liability_limitation': ['liability', 'limitation', 'damages'],
            'ip_clause': ['intellectual_property', 'copyright', 'patent'],
            'governing_law': ['governing_law', 'jurisdiction', 'venue'],
            'payment_terms': ['payment', 'fees', 'compensation'],
            'force_majeure': ['force_majeure', 'act_of_god'],
            'termination': ['termination', 'default', 'remedies'],
            'warranties': ['warranties', 'representations'],
            'indemnification': ['indemnification', 'hold_harmless'],
            'dispute_resolution': ['dispute_resolution', 'arbitration', 'mediation'],
        }
        
        topics = topic_map.get(clause_type, [])
        
        # Get jurisdiction from contract or organization
        jurisdiction = self._get_jurisdiction(contract)
        
        references = LegalReferenceLibrary.objects.filter(
            is_active=True,
            topics__overlap=topics
        )
        
        if jurisdiction:
            references = references.filter(state__iexact=jurisdiction)
        
        return references[:5]  # Limit to 5 most relevant references
    
    def _get_references_for_content(self, content):
        """Extract relevant legal references from contract content."""
        # This is a simplified implementation
        # In production, you might use keyword extraction or embeddings
        common_topics = ['liability', 'confidentiality', 'indemnification', 'termination']
        
        references = LegalReferenceLibrary.objects.filter(
            is_active=True
        ).filter(
            models.Q(topics__overlap=common_topics) |
            models.Q(title__icontains=content[:100])  # Simple content matching
        )[:3]
        
        return references
    
    def _get_jurisdiction(self, contract):
        """Extract jurisdiction from contract or organization."""
        # Try to get from organization address
        if contract.organization and contract.organization.state:
            return contract.organization.state
        
        # Default fallback
        return 'California'  # Example default
    
    def _build_clause_generation_prompt(self, clause_type, context, legal_references):
        """Build prompt for clause generation with legal grounding."""
        
        references_text = ""
        for ref in legal_references:
            references_text += f"- {ref.title} ({ref.state}): {ref.excerpt}\n"
        
        prompt = f"""
        You are a legal expert drafting a {clause_type.replace('_', ' ')} clause for a contract.
        
        LEGAL REFERENCES TO GROUND YOUR RESPONSE:
        {references_text}
        
        ADDITIONAL CONTEXT:
        {context or 'No additional context provided.'}
        
        REQUIREMENTS:
        1. Generate a professionally drafted {clause_type.replace('_', ' ')} clause
        2. Ensure it is legally sound and appropriate for commercial contracts
        3. Make it clear, unambiguous, and enforceable
        4. Include appropriate legal terminology
        5. If specific jurisdiction matters, tailor it appropriately
        
        Please provide ONLY the clause text without any explanations or additional text.
        """
        
        return prompt
    
    def _build_editing_prompt(self, instruction, content, legal_references):
        """Build prompt for contract editing."""
        
        instruction_map = {
            'simplify': 'Simplify the language to make it more understandable while maintaining legal enforceability',
            'strengthen': 'Strengthen the legal provisions to provide better protection',
            'formalize': 'Make the language more formal and legally precise',
            'shorten': 'Make the text more concise while preserving all key legal points',
            'expand': 'Add more detail and specificity to the provisions',
            'rewrite_jurisdiction': 'Adapt the content for the specified jurisdiction',
            'fix_grammar': 'Fix any grammatical errors and improve readability'
        }
        
        references_text = ""
        for ref in legal_references:
            references_text += f"- {ref.title}\n"
        
        prompt = f"""
        You are a legal editor reviewing contract text.
        
        INSTRUCTION: {instruction_map.get(instruction, instruction)}
        
        LEGAL REFERENCES FOR GUIDANCE:
        {references_text}
        
        CONTRACT TEXT TO EDIT:
        {content}
        
        Please provide the edited text and a brief explanation of the changes made.
        Format your response as JSON:
        {{
            "edited_content": "the edited text here",
            "explanation": "brief explanation of changes"
        }}
        """
        
        return prompt
    
    def _call_llm(self, prompt, feature, contract, user, legal_references):
        """Make LLM API call and track usage."""
        try:
            # Use Anthropic if available, otherwise OpenAI
            if self.anthropic_client:
                response = self.anthropic_client.messages.create(
                    model="claude-3-sonnet-20240229",
                    max_tokens=4000,
                    temperature=0.3,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                content = response.content[0].text
                usage_data = {
                    'tokens_prompt': response.usage.input_tokens,
                    'tokens_completion': response.usage.output_tokens,
                    'provider_request_id': response.id
                }
                
            elif self.openai_client:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4",
                    max_tokens=4000,
                    temperature=0.3,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                content = response.choices[0].message.content
                usage_data = {
                    'tokens_prompt': response.usage.prompt_tokens,
                    'tokens_completion': response.usage.completion_tokens,
                    'provider_request_id': response.id
                }
                
            else:
                raise Exception("No LLM provider configured")
            
            # Parse JSON response if possible
            try:
                if feature == 'edit':
                    parsed = json.loads(content)
                    content = parsed.get('edited_content', content)
                    explanation = parsed.get('explanation', '')
                else:
                    explanation = ''
            except:
                explanation = ''
            
            # Track usage
            llm_usage = LLMUsage.objects.create(
                organization=user.organization,
                user=user,
                contract=contract,
                provider='anthropic' if self.anthropic_client else 'openai',
                model='claude-3-sonnet-20240229' if self.anthropic_client else 'gpt-4',
                feature=feature,
                tokens_prompt=usage_data['tokens_prompt'],
                tokens_completion=usage_data['tokens_completion'],
                provider_request_id=usage_data['provider_request_id'],
                input_context=prompt,
                generated_content=content,
                cost_estimated=self._calculate_cost(usage_data)
            )
            
            # Add legal references
            if legal_references:
                llm_usage.legal_references.set(legal_references)
            
            # Update contract LLM usage stats
            contract.llm_usage_count += 1
            contract.last_llm_usage = timezone.now()
            contract.save()
            
            return {
                'content': content,
                'explanation': explanation,
                'usage': {
                    'id': llm_usage.id,
                    'tokens_total': llm_usage.tokens_total,
                    'cost_estimated': float(llm_usage.cost_estimated)
                }
            }
            
        except Exception as e:
            # Log error but don't expose internal details
            raise Exception(f"LLM service error: {str(e)}")
    
    def _calculate_cost(self, usage_data):
        """Calculate cost based on provider and usage."""
        # Simplified cost calculation
        # In production, use actual provider pricing
        cost_per_token = 0.00002
        total_tokens = usage_data['tokens_prompt'] + usage_data['tokens_completion']
        return total_tokens * cost_per_token