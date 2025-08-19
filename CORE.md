# ES-NL2DSL: Core Concepts and Technical Design

## 🎯 Project Vision

ES-NL2DSL addresses a fundamental challenge in cybersecurity: the gap between human understanding and machine query languages. Security analysts need to investigate threats using complex Elasticsearch queries, but writing these queries requires deep technical expertise that many analysts lack. Our solution bridges this gap by enabling natural language to automatically generate secure, validated Elasticsearch DSL queries.

## 🧠 Core Problem Statement

### The Challenge
Modern Security Operations Centers (SOCs) rely heavily on Elasticsearch for log analysis and threat hunting. However:

1. **Technical Barrier**: Writing effective Elasticsearch DSL queries requires specialized knowledge
2. **Time Constraints**: Incident response demands rapid query creation under pressure
3. **Security Risks**: Manually written queries may expose sensitive data or cause performance issues
4. **Inconsistency**: Different analysts write different queries for the same investigative need

### Traditional Approaches and Their Limitations

**Rule-Based Systems**: Pattern matching approaches are rigid and cannot handle the nuanced variations in natural language. They fail when analysts use different terminology or phrasing.

**Direct LLM Translation**: Raw Large Language Model approaches without constraints often generate syntactically correct but semantically dangerous queries that could expose sensitive data or cause system overload.

**Template-Based Solutions**: Pre-built query templates are limited in scope and cannot adapt to novel investigative scenarios.

## 🔬 Our Solution: Constrained Generation

### Core Innovation
We developed a **constrained generation approach** that combines the flexibility of Large Language Models with strict security and validation controls. This ensures queries are both semantically correct and operationally safe.

### Three-Layer Architecture

#### 1. Semantic Understanding Layer (LLM-Powered)
- **Model Choice**: We support offline LLMs such as Llama 3.1, DeepSeek-R1, and other local models. Llama 3.1 is our primary model, selected for its balance of capability and local deployment
- **Few-Shot Learning**: Uses carefully curated examples to guide query generation
- **Context Awareness**: Understands cybersecurity domain terminology and investigation patterns

#### 2. Constraint Enforcement Layer
- **JSON Schema Validation**: Ensures generated queries conform to allowed DSL subset
- **Security Rule Engine**: Enforces field whitelisting, time windows, and cost limits
- **Ambiguity Detection**: Automatically identifies and rejects unclear prompts

#### 3. Execution Validation Layer
- **Semantic Comparison**: AST-based analysis to verify query intent
- **Performance Testing**: Validates query execution efficiency
- **Result Verification**: Compares outputs against expert-crafted gold standard queries

## 🛡️ Security-First Design

### Why Security is Paramount

In cybersecurity environments, query generation systems face unique risks:
- **Data Exfiltration**: Malicious prompts could attempt to extract sensitive information
- **System Disruption**: Poorly formed queries could impact Elasticsearch performance
- **Privilege Escalation**: Queries might attempt to access unauthorized data sources

### Our Security Measures

#### Ambiguity Detection
We recognize that vague prompts are security risks. Our system automatically detects and refuses to process ambiguous queries like:
- "Find events from yesterday" (temporal ambiguity)
- "Show me all users" (scope ambiguity)
- "Delete suspicious entries" (action ambiguity)

#### Field Validation
All queries are restricted to a predefined whitelist of approved fields. This prevents:
- Access to sensitive metadata fields
- Querying of administrative information
- Unintended data exposure

#### Time Window Enforcement
Every query must include explicit time boundaries (maximum 30 days) to:
- Prevent full dataset scans
- Control computational costs
- Ensure investigative relevance

#### Cost Control Mechanisms
We implement document count limits (200,000 per query) to:
- Prevent cluster overload
- Ensure reasonable response times
- Maintain system availability

## 🔒 Privacy Preservation Through Differential Privacy

### The Privacy Challenge
Security data often contains sensitive information about network topology, user behavior, and system vulnerabilities. Analysts need to investigate threats without unnecessarily exposing this sensitive data.

### Differential Privacy Implementation

#### Mathematical Foundation
We implement the Laplace mechanism with configurable privacy budgets (ε):
- **ε = 0.5**: Strong privacy protection with higher noise
- **ε = 1.0**: Moderate privacy with balanced utility
- **ε = 2.0**: Weak privacy with minimal noise impact

#### Noise Addition Strategy
- **Numerical Fields**: Laplace noise calibrated to field sensitivity
- **Timestamp Jittering**: Random time shifts within acceptable bounds
- **Count Perturbation**: Statistical noise in aggregation results

#### Privacy-Utility Analysis
We systematically evaluate how privacy protection affects query effectiveness, enabling organizations to make informed decisions about their privacy-utility tradeoffs.

## 🔄 Robustness and Adaptability

### Schema Drift Challenges
Real-world Elasticsearch schemas evolve over time as:
- New log sources are added
- Field names change due to system updates
- Data formats evolve with software versions

### Our Robustness Strategy

#### Schema Drift Testing
We deliberately create modified indices with renamed fields to test system adaptability:
- `bytes_out` → `bytes_sent`
- `label` → `classification`

This tests whether our system can maintain functionality despite schema changes.

#### Adaptive Query Generation
The LLM component can potentially adapt to schema variations by:
- Understanding field semantics beyond exact names
- Inferring equivalent fields from context
- Maintaining query intent despite structural changes

## 📊 Comprehensive Evaluation Framework

### Multi-Dimensional Assessment

#### Accuracy Metrics
- **Jaccard Similarity**: Measures overlap between generated and expert query results
- **F1 Score**: Harmonic mean of precision and recall for balanced assessment
- **Precision/Recall**: Detailed analysis of result quality

#### Security Metrics
- **Adversarial Resistance**: Tests against 20+ red-team prompts designed to bypass security
- **Block Rate**: Percentage of malicious prompts successfully rejected (target ≥95%)
- **Validation Compliance**: Adherence to security rules and constraints

#### Performance Metrics
- **Generation Latency**: Time from prompt to validated query
- **Success Rate**: Percentage of legitimate prompts successfully processed
- **Retry Analysis**: Understanding failure modes and recovery patterns

#### Privacy Metrics
- **Utility Degradation**: Quantifying accuracy loss due to privacy protection
- **Noise Impact Assessment**: Understanding how differential privacy affects specific query types

### Baseline Comparisons

#### Rules-Based Baseline
Simple pattern matching for comparison, representing traditional automation approaches.

#### Zero-Shot LLM Baseline
Raw LLM without constraints, demonstrating the need for our security measures.

#### Expert Human Queries
Gold standard queries crafted by cybersecurity experts for ground truth comparison.

## 🧪 Test Scenario Design

### Realistic Cybersecurity Use Cases

Our 12 test scenarios represent authentic SOC investigation patterns:

#### Basic Threat Detection
- Malicious event identification
- Time-bounded investigations
- Label-based filtering

#### Network Analysis
- Traffic volume analysis
- Port-based investigations
- Protocol-specific queries

#### Advanced Investigations
- Multi-condition filtering
- Source/destination analysis
- Combined threat indicators

### Scenario Complexity Progression
From simple single-condition queries to complex multi-factor investigations, ensuring comprehensive system testing.

## 🏗️ Technical Architecture Decisions

### Why Elasticsearch?
- **Industry Standard**: Widely adopted in cybersecurity
- **Powerful Query Language**: Rich DSL for complex investigations
- **Scalability**: Handles large-scale security data
- **Real-time Capabilities**: Supports live threat hunting

### Why Offline LLMs (Llama 3.1 as Primary)?
- **Local Deployment**: No external API dependencies for security-sensitive environments
- **Model Flexibility**: Support for various offline models (Llama 3.1, DeepSeek-R1, GPT-OSS, etc.)
- **Sufficient Capability**: Strong enough for domain-specific query generation
- **Resource Efficiency**: Balanced performance without excessive hardware requirements
- **Open Source**: Transparent and auditable models

### Why JSON Schema Validation?
- **Precise Control**: Exact specification of allowed query structures
- **Security Enforcement**: Prevents unauthorized query patterns
- **Maintainability**: Clear documentation of permitted operations
- **Extensibility**: Easy to modify as requirements evolve

### Why Docker Containerization?
- **Environment Consistency**: Identical behavior across different systems
- **Security Isolation**: Contained execution environment
- **Easy Deployment**: Simplified setup and scaling
- **Dependency Management**: Controlled software stack

## 🎯 Target Applications

### Research Applications
- **Query Translation Research**: Advancing natural language to formal query translation
- **Security Automation**: Exploring AI-assisted cybersecurity operations
- **Privacy Technology**: Developing practical differential privacy applications
- **Robustness Studies**: Understanding system adaptation to schema changes

### Production Applications
- **SOC Query Assistant**: Helping analysts write complex investigation queries
- **Incident Response**: Rapid query generation during security incidents
- **Compliance Auditing**: Generating queries for regulatory compliance checks
- **Training and Education**: Teaching Elasticsearch through natural language examples

## 🌐 Broader Impact

### Democratizing Threat Hunting
By removing technical barriers, we enable more security professionals to perform effective threat hunting, regardless of their Elasticsearch expertise.

### Accelerating Incident Response
Faster query generation means quicker threat identification and response, potentially preventing or minimizing security breaches.

### Standardizing Investigations
Consistent query generation promotes standardized investigation procedures across different analysts and organizations.

### Privacy-Aware Security
Our differential privacy implementation demonstrates how security analysis can be performed while protecting sensitive information.

## 🚀 Future Directions

### Advanced Query Optimization
Automatic query performance optimization based on data distribution and cluster characteristics.

### Multi-Modal Input
Supporting diagram-based and visual query specification alongside natural language.

### Federated Query Generation
Extending to multiple data sources beyond Elasticsearch, including databases and cloud platforms.

### Adaptive Learning
System improvement based on analyst feedback and query effectiveness over time.

### Advanced Privacy Techniques
Exploring homomorphic encryption and secure multi-party computation for enhanced privacy.

## 🧠 Design Philosophy

### Security by Design
Every component prioritizes security over convenience, ensuring production-ready deployment in sensitive environments.

### Transparency and Explainability
All system decisions are traceable and auditable, crucial for security operations where understanding system behavior is essential.

### Practical Utility
Solutions must work in real-world SOC environments with realistic constraints and requirements.

### Continuous Validation
Ongoing testing and evaluation ensure system reliability and effectiveness as threats and technologies evolve.

---

This framework represents a significant advancement in bridging the gap between human security expertise and machine-executable queries, enabling more effective and accessible cybersecurity operations while maintaining the highest standards of security and privacy protection.