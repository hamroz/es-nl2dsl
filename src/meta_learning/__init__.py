"""
Meta-Learning Module for ES-NL2DSL

This module implements meta-learning algorithms for rapid domain adaptation
in natural language to Elasticsearch DSL query generation.

Key Features:
- Few-shot learning for new schemas and domains
- Model-Agnostic Meta-Learning (MAML) implementation
- Rapid adaptation with minimal examples (<10)
- Cross-domain transfer learning

Components:
- meta_learner.py: Core MAML implementation
- domain_adapter.py: Domain-specific adaptation logic
- few_shot_generator.py: Few-shot query generation
- evaluation.py: Meta-learning evaluation metrics
"""

from .meta_learner import MetaLearner, MAMLTrainer
from .domain_adapter import DomainAdapter, SchemaAdapter
from .few_shot_generator import FewShotQueryGenerator
from .evaluation import MetaLearningEvaluator

__all__ = [
    'MetaLearner',
    'MAMLTrainer', 
    'DomainAdapter',
    'SchemaAdapter',
    'FewShotQueryGenerator',
    'MetaLearningEvaluator'
]
