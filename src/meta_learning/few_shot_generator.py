"""
Few-Shot Query Generator for ES-NL2DSL

Implements few-shot learning for rapid adaptation to new domains
with minimal training examples.
"""

import json
import random
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import logging

from .meta_learner import MetaTask, MetaLearner
from .domain_adapter import DomainAdapter, SchemaAdapter

logger = logging.getLogger(__name__)

@dataclass
class FewShotExample:
    """A few-shot training example."""
    prompt: str
    expected_query: Dict[str, Any]
    domain: str
    difficulty: str  # 'easy', 'medium', 'hard'
    explanation: Optional[str] = None

class FewShotQueryGenerator:
    """
    Generates queries using few-shot learning with domain adaptation.
    
    This is the main interface for meta-learning-enhanced query generation
    that can rapidly adapt to new domains and schemas.
    """
    
    def __init__(self, 
                 base_model: str = "llama3.1:latest",
                 adaptation_examples: int = 5):
        """
        Initialize few-shot generator.
        
        Args:
            base_model: Base LLM model name
            adaptation_examples: Number of examples to use for adaptation
        """
        self.base_model = base_model
        self.adaptation_examples = adaptation_examples
        
        # Initialize components
        self.meta_learner = MetaLearner(base_model_name=base_model)
        self.domain_adapter = DomainAdapter()
        self.schema_adapter = SchemaAdapter()
        
        # Example database
        self.example_database = {}
        self.domain_examples = {}
        
        # Performance tracking
        self.generation_history = []
        self.adaptation_metrics = {}
    
    def add_examples(self, examples: List[FewShotExample], domain: str = None):
        """Add training examples to the database."""
        for example in examples:
            example_domain = domain or example.domain
            
            if example_domain not in self.domain_examples:
                self.domain_examples[example_domain] = []
            
            self.domain_examples[example_domain].append(example)
            
        logger.info(f"Added {len(examples)} examples for domain: {example_domain}")
    
    def load_examples_from_file(self, filepath: str, domain: str = None):
        """Load examples from a JSON file."""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            examples = []
            for item in data:
                example = FewShotExample(
                    prompt=item['prompt'],
                    expected_query=item['expected_query'],
                    domain=domain or item.get('domain', 'unknown'),
                    difficulty=item.get('difficulty', 'medium'),
                    explanation=item.get('explanation')
                )
                examples.append(example)
            
            self.add_examples(examples, domain)
            return len(examples)
            
        except Exception as e:
            logger.error(f"Failed to load examples from {filepath}: {e}")
            return 0
    
    def generate_with_few_shot(self, 
                              prompt: str,
                              schema: Dict[str, Any],
                              domain: str = None,
                              num_examples: int = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Generate query using few-shot learning with domain adaptation.
        
        Args:
            prompt: Natural language query prompt
            schema: Elasticsearch schema
            domain: Target domain (if known)
            num_examples: Number of examples to use (defaults to self.adaptation_examples)
        
        Returns:
            (generated_query, generation_metadata)
        """
        num_examples = num_examples or self.adaptation_examples
        
        try:
            # Step 1: Detect or validate domain
            if not domain:
                domain, confidence = self.domain_adapter.detect_domain(schema, [prompt])
                logger.info(f"Auto-detected domain: {domain} (confidence: {confidence:.3f})")
            else:
                confidence = 1.0
            
            # Step 2: Analyze schema for adaptation
            schema_analysis = self.schema_adapter.analyze_schema(schema, f"{domain}_schema")
            
            # Step 3: Select relevant few-shot examples
            selected_examples = self._select_examples(domain, prompt, num_examples)
            
            # Step 4: Create meta-task for adaptation
            meta_task = self._create_meta_task(
                domain=domain,
                schema=schema,
                examples=selected_examples,
                schema_analysis=schema_analysis
            )
            
            # Step 5: Generate query using meta-learning
            generated_query, adaptation_metrics = self.meta_learner.adapt_to_task(meta_task, prompt)
            
            # Step 6: Post-process and validate
            final_query, validation_results = self._post_process_query(
                generated_query, schema, domain
            )
            
            # Step 7: Compile metadata
            generation_metadata = {
                'domain': domain,
                'domain_confidence': confidence,
                'schema_analysis': schema_analysis,
                'selected_examples': len(selected_examples),
                'adaptation_metrics': adaptation_metrics,
                'validation_results': validation_results,
                'generation_strategy': 'few_shot_meta_learning'
            }
            
            # Track performance
            self._record_generation(prompt, final_query, generation_metadata)
            
            return final_query, generation_metadata
            
        except Exception as e:
            logger.error(f"Few-shot generation failed: {e}")
            return {}, {'error': str(e), 'success': False}
    
    def _select_examples(self, domain: str, prompt: str, num_examples: int) -> List[FewShotExample]:
        """Select the most relevant examples for few-shot learning."""
        available_examples = self.domain_examples.get(domain, [])
        
        if not available_examples:
            # Fall back to examples from similar domains
            available_examples = self._get_similar_domain_examples(domain)
        
        if not available_examples:
            logger.warning(f"No examples available for domain: {domain}")
            return []
        
        # Score examples by relevance to prompt
        scored_examples = []
        for example in available_examples:
            relevance_score = self._calculate_example_relevance(example, prompt)
            scored_examples.append((example, relevance_score))
        
        # Sort by relevance and select top examples
        scored_examples.sort(key=lambda x: x[1], reverse=True)
        selected = [example for example, score in scored_examples[:num_examples]]
        
        # Ensure diversity in difficulty
        selected = self._ensure_difficulty_diversity(selected, num_examples)
        
        logger.info(f"Selected {len(selected)} examples for domain: {domain}")
        return selected
    
    def _get_similar_domain_examples(self, target_domain: str) -> List[FewShotExample]:
        """Get examples from domains similar to the target domain."""
        # Domain similarity mapping
        domain_similarity = {
            'security': ['networking', 'system'],
            'networking': ['security', 'system'], 
            'system': ['networking', 'security']
        }
        
        similar_examples = []
        similar_domains = domain_similarity.get(target_domain, [])
        
        for similar_domain in similar_domains:
            if similar_domain in self.domain_examples:
                # Take a subset from similar domains
                examples = self.domain_examples[similar_domain][:2]  # Max 2 from each
                similar_examples.extend(examples)
        
        return similar_examples
    
    def _calculate_example_relevance(self, example: FewShotExample, target_prompt: str) -> float:
        """Calculate how relevant an example is to the target prompt."""
        relevance = 0.0
        
        # Text similarity (simple token overlap)
        example_tokens = set(example.prompt.lower().split())
        target_tokens = set(target_prompt.lower().split())
        
        if example_tokens and target_tokens:
            overlap = len(example_tokens.intersection(target_tokens))
            union = len(example_tokens.union(target_tokens))
            text_similarity = overlap / union if union > 0 else 0.0
            relevance += text_similarity * 0.6
        
        # Query complexity similarity
        target_complexity = len(target_prompt.split())
        example_complexity = len(example.prompt.split())
        
        complexity_similarity = 1.0 - abs(target_complexity - example_complexity) / max(target_complexity, example_complexity, 1)
        relevance += complexity_similarity * 0.2
        
        # Difficulty preference (prefer medium difficulty)
        difficulty_scores = {'easy': 0.7, 'medium': 1.0, 'hard': 0.8}
        relevance += difficulty_scores.get(example.difficulty, 0.5) * 0.2
        
        return relevance
    
    def _ensure_difficulty_diversity(self, examples: List[FewShotExample], target_count: int) -> List[FewShotExample]:
        """Ensure diversity in example difficulty levels."""
        if len(examples) <= target_count:
            return examples
        
        # Group by difficulty
        difficulty_groups = {'easy': [], 'medium': [], 'hard': []}
        for example in examples:
            difficulty_groups[example.difficulty].append(example)
        
        # Select balanced examples
        selected = []
        per_difficulty = target_count // 3
        remainder = target_count % 3
        
        for difficulty, group in difficulty_groups.items():
            count = per_difficulty + (1 if remainder > 0 else 0)
            selected.extend(group[:count])
            remainder = max(0, remainder - 1)
        
        # Fill remaining slots if needed
        while len(selected) < target_count:
            for group in difficulty_groups.values():
                for example in group:
                    if example not in selected:
                        selected.append(example)
                        break
                if len(selected) >= target_count:
                    break
        
        return selected[:target_count]
    
    def _create_meta_task(self, 
                         domain: str, 
                         schema: Dict[str, Any],
                         examples: List[FewShotExample],
                         schema_analysis: Dict[str, Any]) -> MetaTask:
        """Create a meta-task for the meta-learner."""
        # Convert examples to the expected format
        support_examples = []
        for example in examples:
            support_examples.append({
                'prompt': example.prompt,
                'expected_query': example.expected_query,
                'difficulty': example.difficulty,
                'explanation': example.explanation
            })
        
        # Create field mappings from schema analysis
        field_mappings = {}
        if 'field_analysis' in schema_analysis:
            field_analysis = schema_analysis['field_analysis']
            
            # Map common field types
            if field_analysis.get('temporal_fields'):
                field_mappings['timestamp'] = field_analysis['temporal_fields'][0]
            
            # Add other important mappings based on field analysis
            for field_name, field_type in field_analysis.get('field_types', {}).items():
                if any(keyword in field_name.lower() for keyword in ['id', 'user', 'ip', 'port']):
                    field_mappings[field_name.lower()] = field_name
        
        task_id = f"{domain}_{len(support_examples)}shot"
        
        return MetaTask(
            task_id=task_id,
            domain=domain,
            schema=schema,
            support_examples=support_examples,
            query_examples=[],  # No query examples for generation
            field_mappings=field_mappings
        )
    
    def _post_process_query(self, 
                           query: Dict[str, Any], 
                           schema: Dict[str, Any], 
                           domain: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Post-process the generated query for validation and optimization."""
        validation_results = {
            'is_valid': False,
            'schema_compliant': False,
            'domain_appropriate': False,
            'issues': []
        }
        
        if not query:
            validation_results['issues'].append('Empty query generated')
            return {}, validation_results
        
        # Basic structure validation
        if 'query' in query:
            validation_results['is_valid'] = True
        else:
            validation_results['issues'].append('Missing query structure')
        
        # Schema compliance check
        try:
            from src.core.validator import QueryValidator
            validator = QueryValidator()
            is_valid, error_msg = validator.validate_query(query)
            validation_results['schema_compliant'] = is_valid
            if not is_valid:
                validation_results['issues'].append(f'Schema validation: {error_msg}')
        except Exception as e:
            validation_results['issues'].append(f'Validation error: {str(e)}')
        
        # Domain appropriateness check
        domain_score = self._check_domain_appropriateness(query, domain)
        validation_results['domain_appropriate'] = domain_score > 0.5
        validation_results['domain_score'] = domain_score
        
        # Apply domain-specific optimizations if valid
        optimized_query = query
        if validation_results['schema_compliant']:
            optimized_query = self._apply_domain_optimizations(query, domain)
        
        return optimized_query, validation_results
    
    def _check_domain_appropriateness(self, query: Dict[str, Any], domain: str) -> float:
        """Check if the query is appropriate for the given domain."""
        score = 0.0
        query_str = json.dumps(query).lower()
        
        # Get domain profile
        if domain in self.domain_adapter.domain_profiles:
            profile = self.domain_adapter.domain_profiles[domain]
            
            # Check for domain-relevant fields
            field_matches = 0
            for field in profile.common_fields:
                if field.lower() in query_str:
                    field_matches += 1
            
            if profile.common_fields:
                score += (field_matches / len(profile.common_fields)) * 0.6
            
            # Check for domain patterns
            pattern_matches = 0
            for pattern in profile.temporal_patterns:
                if any(word in query_str for word in pattern.lower().split()):
                    pattern_matches += 1
            
            if profile.temporal_patterns:
                score += (pattern_matches / len(profile.temporal_patterns)) * 0.4
        
        return min(1.0, score)
    
    def _apply_domain_optimizations(self, query: Dict[str, Any], domain: str) -> Dict[str, Any]:
        """Apply domain-specific optimizations to the query."""
        optimized_query = query.copy()
        
        # Get domain profile for optimization hints
        if domain in self.domain_adapter.domain_profiles:
            profile = self.domain_adapter.domain_profiles[domain]
            
            # Security domain optimizations
            if domain == 'security':
                # Ensure time bounds for security queries
                if 'query' in optimized_query and '@timestamp' not in json.dumps(optimized_query):
                    # Add default time window for security queries
                    if 'bool' not in optimized_query['query']:
                        optimized_query['query'] = {'bool': {'must': [optimized_query['query']]}}
                    
                    time_filter = {
                        'range': {
                            '@timestamp': {
                                'gte': 'now-24h',
                                'lte': 'now'
                            }
                        }
                    }
                    
                    if 'filter' not in optimized_query['query']['bool']:
                        optimized_query['query']['bool']['filter'] = []
                    
                    optimized_query['query']['bool']['filter'].append(time_filter)
            
            # Performance optimizations for all domains
            if 'size' not in optimized_query:
                max_size = 1000 if profile.security_level == 'high' else 10000
                optimized_query['size'] = min(1000, max_size)  # Default reasonable size
        
        return optimized_query
    
    def _record_generation(self, prompt: str, query: Dict[str, Any], metadata: Dict[str, Any]):
        """Record generation for performance tracking and learning."""
        record = {
            'prompt': prompt,
            'query': query,
            'metadata': metadata,
            'timestamp': None,  # Would be set to current time
            'success': bool(query and metadata.get('validation_results', {}).get('is_valid', False))
        }
        
        self.generation_history.append(record)
        
        # Update adaptation metrics for the domain
        domain = metadata.get('domain', 'unknown')
        if domain not in self.adaptation_metrics:
            self.adaptation_metrics[domain] = {
                'total_attempts': 0,
                'successful_generations': 0,
                'avg_confidence': 0.0,
                'common_issues': []
            }
        
        metrics = self.adaptation_metrics[domain]
        metrics['total_attempts'] += 1
        
        if record['success']:
            metrics['successful_generations'] += 1
        
        # Update average confidence
        domain_confidence = metadata.get('domain_confidence', 0.0)
        metrics['avg_confidence'] = (
            (metrics['avg_confidence'] * (metrics['total_attempts'] - 1) + domain_confidence) /
            metrics['total_attempts']
        )
        
        # Track common issues
        issues = metadata.get('validation_results', {}).get('issues', [])
        for issue in issues:
            if issue not in metrics['common_issues']:
                metrics['common_issues'].append(issue)
    
    def get_adaptation_summary(self, domain: str = None) -> Dict[str, Any]:
        """Get adaptation performance summary."""
        if domain and domain in self.adaptation_metrics:
            return {
                'domain': domain,
                'metrics': self.adaptation_metrics[domain],
                'success_rate': (
                    self.adaptation_metrics[domain]['successful_generations'] /
                    max(1, self.adaptation_metrics[domain]['total_attempts'])
                )
            }
        else:
            # Overall summary
            total_attempts = sum(m['total_attempts'] for m in self.adaptation_metrics.values())
            total_successes = sum(m['successful_generations'] for m in self.adaptation_metrics.values())
            
            return {
                'overall_metrics': {
                    'total_attempts': total_attempts,
                    'total_successes': total_successes,
                    'overall_success_rate': total_successes / max(1, total_attempts),
                    'domains_covered': len(self.adaptation_metrics)
                },
                'domain_breakdown': self.adaptation_metrics
            }
    
    def save_learned_adaptations(self, filepath: str):
        """Save learned adaptations for future use."""
        save_data = {
            'adaptation_metrics': self.adaptation_metrics,
            'domain_examples': {
                domain: [
                    {
                        'prompt': ex.prompt,
                        'expected_query': ex.expected_query,
                        'domain': ex.domain,
                        'difficulty': ex.difficulty,
                        'explanation': ex.explanation
                    }
                    for ex in examples
                ]
                for domain, examples in self.domain_examples.items()
            },
            'generation_history': self.generation_history[-100:],  # Keep last 100 records
            'meta_learner_state': {
                'domain_knowledge': self.meta_learner.domain_knowledge,
                'task_adaptations': self.meta_learner.task_adaptations
            }
        }
        
        with open(filepath, 'w') as f:
            json.dump(save_data, f, indent=2, default=str)
    
    def load_learned_adaptations(self, filepath: str):
        """Load previously learned adaptations."""
        try:
            with open(filepath, 'r') as f:
                save_data = json.load(f)
            
            # Restore adaptation metrics
            self.adaptation_metrics = save_data.get('adaptation_metrics', {})
            
            # Restore examples
            for domain, examples_data in save_data.get('domain_examples', {}).items():
                examples = []
                for ex_data in examples_data:
                    example = FewShotExample(
                        prompt=ex_data['prompt'],
                        expected_query=ex_data['expected_query'],
                        domain=ex_data['domain'],
                        difficulty=ex_data['difficulty'],
                        explanation=ex_data.get('explanation')
                    )
                    examples.append(example)
                self.domain_examples[domain] = examples
            
            # Restore generation history
            self.generation_history = save_data.get('generation_history', [])
            
            # Restore meta-learner state
            meta_state = save_data.get('meta_learner_state', {})
            if 'domain_knowledge' in meta_state:
                self.meta_learner.domain_knowledge.update(meta_state['domain_knowledge'])
            if 'task_adaptations' in meta_state:
                self.meta_learner.task_adaptations = meta_state['task_adaptations']
            
            logger.info(f"Loaded adaptations from {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load adaptations from {filepath}: {e}")
            return False
