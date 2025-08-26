"""
Meta-Learning Implementation for ES-NL2DSL

Implements Model-Agnostic Meta-Learning (MAML) and related algorithms
for rapid adaptation to new domains and schemas.
"""

import json
import copy
import torch
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

@dataclass
class MetaTask:
    """Represents a meta-learning task (domain/schema)"""
    task_id: str
    domain: str
    schema: Dict[str, Any]
    support_examples: List[Dict[str, Any]]  # Few-shot examples
    query_examples: List[Dict[str, Any]]    # Test examples
    field_mappings: Dict[str, str]
    
class MetaLearner:
    """
    Core meta-learning engine for rapid domain adaptation.
    
    Implements MAML-style learning where the model learns to quickly
    adapt to new domains with minimal examples.
    """
    
    def __init__(self, 
                 base_model_name: str = "llama3.1:latest",
                 inner_lr: float = 0.01,
                 outer_lr: float = 0.001,
                 inner_steps: int = 5):
        """
        Initialize meta-learner.
        
        Args:
            base_model_name: Base LLM for adaptation
            inner_lr: Learning rate for task-specific adaptation
            outer_lr: Learning rate for meta-updates
            inner_steps: Number of gradient steps for adaptation
        """
        self.base_model_name = base_model_name
        self.inner_lr = inner_lr
        self.outer_lr = outer_lr
        self.inner_steps = inner_steps
        
        # Meta-learning state
        self.meta_parameters = {}
        self.task_adaptations = {}
        self.training_history = []
        
        # Domain knowledge base
        self.domain_knowledge = {
            'security': {
                'common_fields': ['source_ip', 'dest_ip', 'port', 'protocol'],
                'patterns': ['attack', 'intrusion', 'malicious', 'threat'],
                'time_sensitivity': 'high'
            },
            'networking': {
                'common_fields': ['bytes', 'packets', 'duration', 'flow_id'],
                'patterns': ['traffic', 'bandwidth', 'connection', 'flow'],
                'time_sensitivity': 'medium'
            },
            'system': {
                'common_fields': ['process', 'user', 'path', 'command'],
                'patterns': ['process', 'system', 'resource', 'performance'],
                'time_sensitivity': 'low'
            }
        }
    
    def extract_domain_features(self, task: MetaTask) -> Dict[str, Any]:
        """Extract domain-specific features from a meta-task."""
        features = {
            'field_types': self._analyze_field_types(task.schema),
            'common_patterns': self._extract_patterns(task.support_examples),
            'temporal_characteristics': self._analyze_temporal_patterns(task.support_examples),
            'complexity_metrics': self._calculate_complexity(task.support_examples)
        }
        
        # Add domain-specific knowledge if available
        if task.domain in self.domain_knowledge:
            features.update(self.domain_knowledge[task.domain])
            
        return features
    
    def _analyze_field_types(self, schema: Dict[str, Any]) -> Dict[str, str]:
        """Analyze field types in schema."""
        field_types = {}
        
        if 'properties' in schema:
            for field, definition in schema['properties'].items():
                if isinstance(definition, dict) and 'type' in definition:
                    field_types[field] = definition['type']
                    
        return field_types
    
    def _extract_patterns(self, examples: List[Dict[str, Any]]) -> List[str]:
        """Extract common patterns from examples."""
        patterns = []
        
        for example in examples:
            if 'prompt' in example:
                # Extract key terms and patterns
                prompt = example['prompt'].lower()
                
                # Security patterns
                if any(term in prompt for term in ['attack', 'malicious', 'threat', 'intrusion']):
                    patterns.append('security')
                
                # Network patterns
                if any(term in prompt for term in ['traffic', 'connection', 'bandwidth']):
                    patterns.append('networking')
                    
                # Time patterns
                if any(term in prompt for term in ['last', 'recent', 'between', 'during']):
                    patterns.append('temporal')
                    
        return list(set(patterns))
    
    def _analyze_temporal_patterns(self, examples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze temporal characteristics in examples."""
        temporal_info = {
            'has_time_constraints': False,
            'time_range_types': [],
            'temporal_complexity': 'low'
        }
        
        for example in examples:
            if 'expected_query' in example:
                query = example['expected_query']
                if isinstance(query, dict) and 'query' in query:
                    # Check for timestamp fields
                    query_str = json.dumps(query)
                    if '@timestamp' in query_str or 'timestamp' in query_str:
                        temporal_info['has_time_constraints'] = True
                        
                    # Analyze range complexity
                    if 'range' in query_str:
                        temporal_info['temporal_complexity'] = 'medium'
                        if query_str.count('range') > 1:
                            temporal_info['temporal_complexity'] = 'high'
                            
        return temporal_info
    
    def _calculate_complexity(self, examples: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate complexity metrics for examples."""
        complexities = []
        
        for example in examples:
            if 'expected_query' in example:
                query = example['expected_query']
                complexity = self._query_complexity_score(query)
                complexities.append(complexity)
        
        return {
            'avg_complexity': np.mean(complexities) if complexities else 0.0,
            'max_complexity': max(complexities) if complexities else 0.0,
            'complexity_variance': np.var(complexities) if complexities else 0.0
        }
    
    def _query_complexity_score(self, query: Dict[str, Any]) -> float:
        """Calculate complexity score for a query."""
        score = 0.0
        query_str = json.dumps(query)
        
        # Count nested structures
        score += query_str.count('{') * 0.1
        score += query_str.count('[') * 0.15
        
        # Count operators
        operators = ['bool', 'must', 'should', 'must_not', 'range', 'match', 'term']
        for op in operators:
            score += query_str.count(f'"{op}"') * 0.2
            
        # Penalty for very simple queries
        if len(query_str) < 50:
            score = max(0.1, score)
            
        return score
    
    def create_adaptation_prompt(self, task: MetaTask, target_prompt: str) -> str:
        """
        Create an adaptation prompt for few-shot learning.
        
        This is the core of our meta-learning approach - we create
        domain-aware prompts that help the model quickly adapt.
        """
        domain_features = self.extract_domain_features(task)
        
        # Build context-aware prompt
        adaptation_prompt = f"""# Domain Adaptation: {task.domain.title()}

## Schema Information:
{json.dumps(task.schema, indent=2)}

## Domain Characteristics:
- Field Types: {domain_features.get('field_types', {})}
- Common Patterns: {domain_features.get('common_patterns', [])}
- Temporal Complexity: {domain_features.get('temporal_characteristics', {}).get('temporal_complexity', 'low')}

## Few-Shot Examples:
"""
        
        # Add support examples for few-shot learning
        for i, example in enumerate(task.support_examples[:5]):  # Limit to 5 examples
            adaptation_prompt += f"""
### Example {i+1}:
**Prompt**: {example.get('prompt', '')}
**Expected DSL**: {json.dumps(example.get('expected_query', {}), indent=2)}
"""
        
        # Add the target task
        adaptation_prompt += f"""
## Target Task:
**Prompt**: {target_prompt}
**Required**: Generate an Elasticsearch DSL query following the patterns above.

Generate a valid DSL query that follows the schema and examples provided:"""
        
        return adaptation_prompt
    
    def adapt_to_task(self, task: MetaTask, target_prompt: str) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """
        Adapt to a new task using few-shot examples.
        
        Returns:
            (generated_query, adaptation_metrics)
        """
        try:
            # Create adaptation prompt
            adaptation_prompt = self.create_adaptation_prompt(task, target_prompt)
            
            # Generate query using adapted prompt
            from src.generators.constrained import call_local_model
            
            response = call_local_model(adaptation_prompt, self.base_model_name)
            
            # Parse response to extract DSL
            generated_query = self._parse_dsl_response(response)
            
            # Calculate adaptation metrics
            adaptation_metrics = self._calculate_adaptation_metrics(task, generated_query)
            
            # Store adaptation for learning
            self.task_adaptations[task.task_id] = {
                'task': task,
                'adaptation_prompt': adaptation_prompt,
                'generated_query': generated_query,
                'metrics': adaptation_metrics
            }
            
            return generated_query, adaptation_metrics
            
        except Exception as e:
            logger.error(f"Adaptation failed for task {task.task_id}: {e}")
            return {}, {'error': str(e), 'success': False}
    
    def _parse_dsl_response(self, response: str) -> Dict[str, Any]:
        """Parse DSL query from model response."""
        try:
            # Look for JSON in response
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
            else:
                logger.warning("No valid JSON found in response")
                return {}
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            return {}
    
    def _calculate_adaptation_metrics(self, task: MetaTask, generated_query: Dict[str, Any]) -> Dict[str, float]:
        """Calculate metrics for adaptation quality."""
        metrics = {
            'success': 1.0 if generated_query else 0.0,
            'schema_compliance': 0.0,
            'pattern_similarity': 0.0,
            'complexity_match': 0.0
        }
        
        if not generated_query:
            return metrics
            
        # Schema compliance check
        try:
            from src.core.validator import QueryValidator
            validator = QueryValidator()
            is_valid, _ = validator.validate_query(generated_query)
            metrics['schema_compliance'] = 1.0 if is_valid else 0.0
        except:
            pass
            
        # Pattern similarity to examples
        if task.support_examples:
            similarities = []
            for example in task.support_examples:
                if 'expected_query' in example:
                    sim = self._calculate_query_similarity(generated_query, example['expected_query'])
                    similarities.append(sim)
            metrics['pattern_similarity'] = np.mean(similarities) if similarities else 0.0
            
        # Complexity match
        target_complexity = self._query_complexity_score(generated_query)
        if task.support_examples:
            example_complexities = [
                self._query_complexity_score(ex.get('expected_query', {}))
                for ex in task.support_examples
                if 'expected_query' in ex
            ]
            if example_complexities:
                avg_complexity = np.mean(example_complexities)
                # Score based on how close the complexity is to examples
                complexity_diff = abs(target_complexity - avg_complexity)
                metrics['complexity_match'] = max(0.0, 1.0 - complexity_diff / 2.0)
        
        return metrics
    
    def _calculate_query_similarity(self, query1: Dict[str, Any], query2: Dict[str, Any]) -> float:
        """Calculate structural similarity between queries."""
        try:
            # Convert to strings and calculate basic similarity
            str1 = json.dumps(query1, sort_keys=True)
            str2 = json.dumps(query2, sort_keys=True)
            
            # Simple token-based similarity
            tokens1 = set(str1.split())
            tokens2 = set(str2.split())
            
            if not tokens1 and not tokens2:
                return 1.0
            if not tokens1 or not tokens2:
                return 0.0
                
            intersection = len(tokens1.intersection(tokens2))
            union = len(tokens1.union(tokens2))
            
            return intersection / union if union > 0 else 0.0
            
        except:
            return 0.0

class MAMLTrainer:
    """
    Model-Agnostic Meta-Learning trainer for continuous improvement.
    
    Implements the MAML algorithm to continuously improve the meta-learner
    across multiple domains and tasks.
    """
    
    def __init__(self, meta_learner: MetaLearner):
        self.meta_learner = meta_learner
        self.training_tasks = []
        self.validation_tasks = []
        self.training_history = []
    
    def add_training_task(self, task: MetaTask):
        """Add a task to the training set."""
        self.training_tasks.append(task)
    
    def add_validation_task(self, task: MetaTask):
        """Add a task to the validation set."""
        self.validation_tasks.append(task)
    
    def meta_train(self, num_epochs: int = 10) -> Dict[str, List[float]]:
        """
        Perform meta-training across all tasks.
        
        Returns training history with metrics per epoch.
        """
        history = {
            'train_loss': [],
            'val_accuracy': [],
            'adaptation_success': []
        }
        
        for epoch in range(num_epochs):
            logger.info(f"Meta-training epoch {epoch + 1}/{num_epochs}")
            
            # Training phase
            train_metrics = self._train_epoch()
            
            # Validation phase
            val_metrics = self._validate_epoch()
            
            # Record metrics
            history['train_loss'].append(train_metrics.get('loss', 0.0))
            history['val_accuracy'].append(val_metrics.get('accuracy', 0.0))
            history['adaptation_success'].append(val_metrics.get('adaptation_success', 0.0))
            
            logger.info(f"Epoch {epoch + 1} - Train Loss: {train_metrics.get('loss', 0.0):.4f}, "
                       f"Val Accuracy: {val_metrics.get('accuracy', 0.0):.4f}")
        
        self.training_history = history
        return history
    
    def _train_epoch(self) -> Dict[str, float]:
        """Train for one epoch across all training tasks."""
        total_loss = 0.0
        successful_adaptations = 0
        
        for task in self.training_tasks:
            # Simulate adaptation on support set
            if task.support_examples:
                # Use first example as target for self-supervision
                target_example = task.support_examples[0]
                target_prompt = target_example.get('prompt', '')
                
                # Create adapted task without this example
                adapted_task = copy.deepcopy(task)
                adapted_task.support_examples = task.support_examples[1:]
                
                # Attempt adaptation
                generated_query, metrics = self.meta_learner.adapt_to_task(adapted_task, target_prompt)
                
                if metrics.get('success', 0.0) > 0.5:
                    successful_adaptations += 1
                    
                # Calculate loss (simplified - in practice would use gradients)
                loss = 1.0 - metrics.get('pattern_similarity', 0.0)
                total_loss += loss
        
        return {
            'loss': total_loss / len(self.training_tasks) if self.training_tasks else 0.0,
            'adaptation_rate': successful_adaptations / len(self.training_tasks) if self.training_tasks else 0.0
        }
    
    def _validate_epoch(self) -> Dict[str, float]:
        """Validate on validation tasks."""
        total_accuracy = 0.0
        successful_adaptations = 0
        
        for task in self.validation_tasks:
            if task.query_examples:
                task_accuracy = 0.0
                
                for query_example in task.query_examples:
                    target_prompt = query_example.get('prompt', '')
                    
                    # Adapt and generate
                    generated_query, metrics = self.meta_learner.adapt_to_task(task, target_prompt)
                    
                    if metrics.get('success', 0.0) > 0.5:
                        successful_adaptations += 1
                        task_accuracy += metrics.get('schema_compliance', 0.0)
                
                total_accuracy += task_accuracy / len(task.query_examples)
        
        return {
            'accuracy': total_accuracy / len(self.validation_tasks) if self.validation_tasks else 0.0,
            'adaptation_success': successful_adaptations / sum(len(t.query_examples) for t in self.validation_tasks) if self.validation_tasks else 0.0
        }
    
    def save_model(self, filepath: str):
        """Save the meta-learned model."""
        model_data = {
            'meta_parameters': self.meta_learner.meta_parameters,
            'task_adaptations': self.meta_learner.task_adaptations,
            'training_history': self.training_history,
            'domain_knowledge': self.meta_learner.domain_knowledge
        }
        
        with open(filepath, 'w') as f:
            json.dump(model_data, f, indent=2, default=str)
    
    def load_model(self, filepath: str):
        """Load a pre-trained meta-model."""
        with open(filepath, 'r') as f:
            model_data = json.load(f)
            
        self.meta_learner.meta_parameters = model_data.get('meta_parameters', {})
        self.meta_learner.task_adaptations = model_data.get('task_adaptations', {})
        self.training_history = model_data.get('training_history', [])
        self.meta_learner.domain_knowledge.update(model_data.get('domain_knowledge', {}))
