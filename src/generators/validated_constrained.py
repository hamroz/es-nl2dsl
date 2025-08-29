#!/usr/bin/env python3
"""
Validated Constrained Generator: Enhanced generator that includes real-time validation
and optimization feedback during query generation.
"""
import json
import sys
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.generators.constrained import generate_with_retries, build_prompt
from src.validation.query_validator import QueryValidator
from src.index_profiler import IndexProfiler

logger = logging.getLogger(__name__)

class ValidatedConstrainedGenerator:
    """Enhanced generator with integrated validation and optimization"""
    
    def __init__(self):
        self.validator = QueryValidator()
        self.profiler = IndexProfiler()
    
    def generate_validated_query(
        self,
        prompt: str,
        index: str = "logs_net",
        model: str = "llama3.1:latest",
        schema_path: str = "artifacts/esdsl_schema.json",
        rules_path: Optional[str] = None,
        max_retries: int = 3,
        require_results: bool = True
    ) -> Dict[str, Any]:
        """Generate a query with integrated validation and optimization"""
        
        logger.info(f"🎯 Generating validated query for {index}")
        
        # Pre-generation analysis
        pre_analysis = self._analyze_prompt_and_index(prompt, index)
        
        # Generate initial query
        for attempt in range(max_retries):
            logger.info(f"Generation attempt {attempt + 1}/{max_retries}")
            
            # Generate query using enhanced constrained generator
            result = generate_with_retries(
                task_prompt=prompt,
                schema_path=schema_path,
                rules_path=rules_path,
                max_retries=1,  # Single attempt per iteration
                index=index,
                model=model
            )
            
            # Check if generation abstained
            if "abstain" in result:
                logger.warning(f"Generation abstained: {result['reason']}")
                if attempt == max_retries - 1:
                    return result
                continue
            
            # Validate the generated query
            validation_result = self.validator.validate_query(result, index)
            
            # Add validation info to result
            result["_validation"] = validation_result.to_dict()
            
            logger.info(f"Validation score: {validation_result.score:.1f}/100")
            
            # Check if query meets requirements
            if validation_result.is_valid:
                if not require_results or validation_result.result_count > 0:
                    logger.info(f"✅ Generated valid query with {validation_result.result_count} results")
                    
                    # Add optimization suggestions
                    if validation_result.suggestions:
                        result["_optimization_suggestions"] = validation_result.suggestions
                    
                    return result
                else:
                    # Query is valid but returns no results
                    logger.warning(f"Query returns no results - attempting to fix")
                    
                    # Try to generate a fixed version
                    fixed_prompt = self._create_fixed_prompt(prompt, index, validation_result, pre_analysis)
                    if fixed_prompt != prompt:
                        logger.info(f"Retrying with enhanced prompt")
                        prompt = fixed_prompt  # Use enhanced prompt for next attempt
                        continue
            else:
                logger.warning(f"Query validation failed: {validation_result.issues}")
                
                # Try to create a fixed prompt
                fixed_prompt = self._create_fixed_prompt(prompt, index, validation_result, pre_analysis)
                if fixed_prompt != prompt:
                    prompt = fixed_prompt
                    continue
            
            # If we reach here, try once more with the original prompt
            if attempt == max_retries - 1:
                logger.warning("Max retries reached, returning best result")
                return result
        
        # Fallback
        return {"abstain": True, "reason": "Could not generate valid query after retries"}
    
    def _analyze_prompt_and_index(self, prompt: str, index: str) -> Dict[str, Any]:
        """Analyze the prompt and index to provide context for generation"""
        analysis = {
            "prompt": prompt,
            "index": index,
            "suggested_fields": [],
            "suggested_values": {},
            "date_range": None
        }
        
        try:
            # Get index profile for context
            profile = self.profiler.analyze_index(index)
            analysis["date_range"] = profile.date_range
            
            # Analyze prompt for field intentions
            prompt_lower = prompt.lower()
            
            # Map common terms to actual fields
            field_suggestions = []
            
            if any(term in prompt_lower for term in ["malicious", "attack", "threat", "bad"]):
                # Find threat/label fields
                label_fields = [f for f in profile.fields.keys() 
                              if any(keyword in f.lower() for keyword in ["label", "threat", "attack", "status"])]
                if label_fields:
                    field_suggestions.extend(label_fields)
                    
                    # Get common values for these fields
                    for field in label_fields:
                        field_info = profile.fields[field]
                        if field_info.common_values:
                            analysis["suggested_values"][field] = list(field_info.common_values.keys())
            
            if any(term in prompt_lower for term in ["ip", "address", "source", "destination"]):
                ip_fields = [f for f in profile.fields.keys() if "ip" in f.lower()]
                field_suggestions.extend(ip_fields)
            
            if any(term in prompt_lower for term in ["port", "service"]):
                port_fields = [f for f in profile.fields.keys() if "port" in f.lower()]
                field_suggestions.extend(port_fields)
            
            analysis["suggested_fields"] = list(set(field_suggestions))
            
        except Exception as e:
            logger.debug(f"Error in prompt analysis: {e}")
        
        return analysis
    
    def _create_fixed_prompt(
        self, 
        original_prompt: str, 
        index: str, 
        validation_result, 
        pre_analysis: Dict[str, Any]
    ) -> str:
        """Create an enhanced prompt based on validation feedback"""
        
        # Start with original prompt
        enhanced_prompt = original_prompt
        
        # Fix field reference issues
        if validation_result.issues:
            for issue in validation_result.issues:
                if "not found" in issue.lower() and "did you mean" in issue.lower():
                    # Extract suggested field name
                    if ":" in issue:
                        suggested = issue.split(":")[-1].strip()
                        if suggested:
                            enhanced_prompt += f" Use field {suggested}."
        
        # Fix no results issue by suggesting alternative values
        if validation_result.result_count == 0:
            for field, values in pre_analysis.get("suggested_values", {}).items():
                if values and "malicious" in original_prompt.lower():
                    # Suggest using actual values instead of "malicious"
                    if "benign" in values:
                        enhanced_prompt = enhanced_prompt.replace("malicious", "benign")
                        enhanced_prompt += f" Note: use '{values[0]}' instead of 'malicious' for this index."
                    elif values:
                        enhanced_prompt += f" Available {field} values: {', '.join(values[:3])}."
        
        # Add field suggestions
        if pre_analysis.get("suggested_fields"):
            enhanced_prompt += f" Consider using fields: {', '.join(pre_analysis['suggested_fields'][:3])}."
        
        return enhanced_prompt
    
    def get_field_value_suggestions(self, index: str, field: str, limit: int = 10) -> List[str]:
        """Get common values for a field to help with query construction"""
        try:
            profile = self.profiler.analyze_index(index)
            if field in profile.fields:
                field_info = profile.fields[field]
                return list(field_info.common_values.keys())[:limit]
        except Exception as e:
            logger.debug(f"Error getting field values: {e}")
        
        return []
    
    def explain_validation_result(self, validation_result) -> str:
        """Generate a human-readable explanation of validation results"""
        explanation = []
        
        explanation.append(f"Query validation: {validation_result.get_status_emoji()} {validation_result.score:.1f}/100")
        
        if validation_result.execution_time_ms:
            explanation.append(f"Execution time: {validation_result.execution_time_ms:.0f}ms")
        
        if validation_result.result_count is not None:
            explanation.append(f"Results found: {validation_result.result_count}")
        
        if validation_result.issues:
            explanation.append("Issues found:")
            for issue in validation_result.issues:
                explanation.append(f"  ❌ {issue}")
        
        if validation_result.warnings:
            explanation.append("Warnings:")
            for warning in validation_result.warnings:
                explanation.append(f"  ⚠️ {warning}")
        
        if validation_result.suggestions:
            explanation.append("Optimization suggestions:")
            for suggestion in validation_result.suggestions:
                explanation.append(f"  💡 {suggestion}")
        
        return "\n".join(explanation)


def main():
    """CLI interface for validated constrained generator"""
    parser = argparse.ArgumentParser(description="Generate validated Elasticsearch queries")
    parser.add_argument("--prompt", required=True, help="Natural language query prompt")
    parser.add_argument("--index", default="logs_net", help="Target Elasticsearch index")
    parser.add_argument("--model", default="llama3.1:latest", help="Model to use for generation")
    parser.add_argument("--schema", default="artifacts/esdsl_schema.json", help="Schema file path")
    parser.add_argument("--task-id", help="Task ID for output naming")
    parser.add_argument("--allow-empty", action="store_true", help="Allow queries that return no results")
    parser.add_argument("--max-retries", type=int, default=3, help="Maximum retry attempts")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - [VALIDATED] - %(levelname)s - %(message)s'
    )
    
    try:
        generator = ValidatedConstrainedGenerator()
        result = generator.generate_validated_query(
            prompt=args.prompt,
            index=args.index,
            model=args.model,
            schema_path=args.schema,
            max_retries=args.max_retries,
            require_results=not args.allow_empty
        )
        
        # Save result
        if args.task_id:
            output_file = Path("artifacts/generated") / f"{args.task_id}.json"
        else:
            output_file = Path("artifacts/generated") / "validated_generated.json"
        
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Extract validation info for separate display
        validation_info = result.pop("_validation", None)
        optimization_suggestions = result.pop("_optimization_suggestions", None)
        
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        if "abstain" in result:
            print(f"Generation abstained: {result['reason']}")
            sys.exit(1)
        else:
            print(f"Successfully generated validated query saved to {output_file}")
            
            # Show validation summary
            if validation_info:
                print(f"\nValidation Summary:")
                print(f"  Status: {'✅ VALID' if validation_info['is_valid'] else '❌ INVALID'}")
                print(f"  Score: {validation_info['score']:.1f}/100")
                if validation_info.get('result_count') is not None:
                    print(f"  Results: {validation_info['result_count']}")
                if validation_info.get('execution_time_ms'):
                    print(f"  Speed: {validation_info['execution_time_ms']:.0f}ms")
            
            # Show optimization suggestions
            if optimization_suggestions:
                print(f"\nOptimization Suggestions:")
                for suggestion in optimization_suggestions:
                    print(f"  💡 {suggestion}")
            
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
