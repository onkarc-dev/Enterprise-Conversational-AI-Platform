"""
Validation and grounding layer to prevent hallucinations.
Validates model outputs against actual flight data and aviation rules.
"""

import re
from typing import Dict, Tuple, Optional
import pandas as pd


class FlightDataValidator:
    """Validates and grounds flight data queries against actual data."""
    
    def __init__(self, csv_path: str = "rule_labelled.csv"):
        self.csv_path = csv_path
        self.df = None
        self.phases = set()
        self.metrics = set()
        self.load_data()
    
    def load_data(self):
        """Load and analyze flight data."""
        try:
            self.df = pd.read_csv(self.csv_path)
            self.df.columns = self.df.columns.str.strip()
            
            if 'Phase' in self.df.columns:
                # Filter out NaN and None values, keep only valid strings
                phase_values = self.df['Phase'].dropna().unique()
                self.phases = set(p for p in phase_values if isinstance(p, str) and p.strip())
                self.phases = {p.strip().upper() for p in self.phases}  # Normalize
            
            # Collect numeric columns as valid metrics
            for col in self.df.columns:
                if col.lower() in ['altmsl', 'ias', 'vspd', 'pitch', 'gndspd', 'oat', 'roll']:
                    self.metrics.add(col.lower())
                    self.metrics.add(col)
            
            print(f" Flight data loaded: {len(self.df)} rows, {len(self.phases)} phases")
        except Exception as e:
            print(f"  Could not load flight data: {e}")
    
    def is_valid_phase(self, phase: str) -> bool:
        """Check if phase exists in data."""
        if self.df is None or not phase:
            return True  # Can't validate without data or phase
        # Normalize phase and check against stored phases (already normalized)
        return phase.strip().upper() in self.phases
    
    def get_phase_bounds(self, phase: str, metric: str) -> Optional[Dict]:
        """Get realistic bounds for a metric in a phase."""
        if self.df is None:
            return None
        
        try:
            metric_col = self._find_metric_column(metric)
            if not metric_col:
                return None
            
            phase_data = self.df[self.df['Phase'].str.upper() == phase.upper()]
            if phase_data.empty:
                return None
            
            values = pd.to_numeric(phase_data[metric_col], errors='coerce').dropna()
            if len(values) == 0:
                return None
            
            return {
                'min': float(values.min()),
                'max': float(values.max()),
                'mean': float(values.mean()),
                'std': float(values.std()),
                'count': len(values)
            }
        except:
            return None
    
    def _find_metric_column(self, metric: str) -> Optional[str]:
        """Find matching column for a metric."""
        metric_lower = metric.lower()
        
        # Direct match
        for col in self.df.columns:
            if col.lower() == metric_lower:
                return col
        
        # Alias match
        aliases = {
            'altitude': 'AltMSL',
            'alt': 'AltMSL',
            'airspeed': 'IAS',
            'speed': 'IAS',
            'vspeed': 'VSpd',
            'vspd': 'VSpd',
            'pitch': 'Pitch',
        }
        
        return aliases.get(metric_lower)
    
    def validate_metric_value(self, phase: str, metric: str, value: float) -> Tuple[bool, str]:
        """
        Validate if a metric value is realistic for a phase.
        Returns (is_valid, reason).
        """
        bounds = self.get_phase_bounds(phase, metric)
        
        if bounds is None:
            return False, f"No data available for {metric} in {phase} phase"
        
        # Check if value is within reasonable range (allow +/- 2 std deviations)
        lower = bounds['min'] - 2 * bounds.get('std', 0)
        upper = bounds['max'] + 2 * bounds.get('std', 0)
        
        if value < lower or value > upper:
            return False, f"Value {value} outside realistic range [{bounds['min']:.1f}, {bounds['max']:.1f}]"
        
        return True, "Value is within realistic bounds"
    
    def validate_response(self, response: str) -> Tuple[bool, str]:
        """
        Validate LLM response for potential hallucinations.
        Returns (is_safe, issues).
        """
        # Ensure response is a string
        if not isinstance(response, str):
            response = str(response)
        
        issues = []
        
        # Check for specific numbers without data
        if re.search(r'\d{4,}', response):  # Large numbers might be made up
            issues.append("[WARNING] Contains specific values - verify they come from data")
        
        # Check for absolute claims
        absolute_phrases = [
            r"always\s",
            r"never\s",
            r"definitely\s",
            r"certainly\s",
            r"impossible\s"
        ]
        for phrase in absolute_phrases:
            if re.search(phrase, response, re.IGNORECASE):
                issues.append(f"[WARNING] Absolute claim detected: '{phrase.strip()}' - verify accuracy")
        
        # Check for speculative language
        speculative = [
            r"probably\s",
            r"likely\s",
            r"might\s",
            r"could\s",
            r"seems\s"
        ]
        for phrase in speculative:
            if re.search(phrase, response, re.IGNORECASE):
                issues.append(f"[OK] Speculative language ok: '{phrase.strip()}'")
        
        return len(issues) == 0, "; ".join(issues) if issues else "Response appears safe"


def validate_llm_output(
    query: str,
    response: str,
    intent_dict: Dict,
    validator: FlightDataValidator
) -> Dict:
    """
    Comprehensive validation of LLM output.
    Returns validation results and recommendations.
    """
    # Ensure response is a string
    if not isinstance(response, str):
        response = str(response)
    
    result = {
        'query': query,
        'response': response,
        'valid': True,
        'warnings': [],
        'recommendations': []
    }
    
    # Extract potential values from response
    values = re.findall(r'[\d.]+', response)
    
    # Validate phase if present
    if 'phase' in intent_dict:
        phase = intent_dict.get('phase')
        if phase:  # Only validate if phase is not None and not empty
            phase_upper = phase.upper()
            if not validator.is_valid_phase(phase_upper):
                result['valid'] = False
                result['warnings'].append(f"Phase '{phase}' not found in training data")
                result['recommendations'].append("Verify phase name or use fallback rule-based parser")
    
    # Validate metric if present
    if 'metric' in intent_dict and 'phase' in intent_dict:
        metric = intent_dict.get('metric')
        phase = intent_dict.get('phase')
        if metric and phase:  # Only validate if both are present and not None
            phase_upper = phase.upper()
            bounds = validator.get_phase_bounds(phase_upper, metric)
            
            if bounds is None:
                result['warnings'].append(f"No data available for {metric} in {phase}")
                result['recommendations'].append("Return 'data not available' instead of guessing")
    
    # General response validation
    is_safe, validation_msg = validator.validate_response(response)
    if not is_safe:
        result['warnings'].append(validation_msg)
        result['recommendations'].append("Apply additional scrutiny before using this response")
    
    return result


# Global validator instance
_validator = None


def get_validator() -> FlightDataValidator:
    """Get or create global validator instance."""
    global _validator
    if _validator is None:
        _validator = FlightDataValidator()
    return _validator


def validate_and_ground_response(
    query: str,
    intent: Dict,
    llm_response: str
) -> Tuple[str, Dict]:
    """
    Take LLM response and ground it against actual data.
    Returns (grounded_response, validation_info).
    """
    validator = get_validator()
    
    # Get validation results
    validation = validate_llm_output(query, llm_response, intent, validator)
    
    # If validation failed, provide alternative
    grounded_response = llm_response
    
    if not validation['valid']:
        # Try to construct response from actual data
        if 'phase' in intent:
            phase = intent.get('phase', '').upper()
            
            if not validator.is_valid_phase(phase):
                grounded_response = f"❌ Sorry, I don't have data for the {phase} phase."
            elif 'metric' in intent:
                metric = intent.get('metric')
                bounds = validator.get_phase_bounds(phase, metric)
                
                if bounds:
                    grounded_response = (
                        f"In the {phase} phase, {metric} ranges from {bounds['min']:.1f} to "
                        f"{bounds['max']:.1f} (average: {bounds['mean']:.1f})"
                    )
                else:
                    grounded_response = f"No {metric} data available for {phase} phase."
    
    return grounded_response, validation


if __name__ == "__main__":
    # Test validator
    print("Testing Flight Data Validator...\n")
    
    validator = FlightDataValidator()
    
    # Test phase validation
    print("Phase Validation:")
    print(f"  Taxi valid: {validator.is_valid_phase('Taxi')}")
    print(f"  FakePhase valid: {validator.is_valid_phase('FakePhase')}")
    
    # Test bounds
    print("\nMetric Bounds (Taxi phase):")
    bounds = validator.get_phase_bounds('Taxi', 'AltMSL')
    if bounds:
        print(f"  AltMSL: {bounds['min']:.1f} - {bounds['max']:.1f} (mean: {bounds['mean']:.1f})")
    
    # Test response validation
    print("\nResponse Validation:")
    test_response = "During taxi, the altitude is always exactly 1718.5 feet."
    is_safe, msg = validator.validate_response(test_response)
    print(f"  Safe: {is_safe}")
    print(f"  Message: {msg}")
