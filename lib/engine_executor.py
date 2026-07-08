from .flight_engine import DynamicFlightCalculator

FILE_PATH = "rule_labelled.csv"
engine = DynamicFlightCalculator(FILE_PATH)

def init_engine():
    engine.load_data()
    engine.create_segments()
    engine.add_phase_numbering()
    engine.build_summary()

def execute_query(intent_json: dict, engine) -> dict:
    intent = intent_json.get("intent")
    phase = intent_json.get("phase")
    metric = intent_json.get("metric")
    agg = intent_json.get("agg")
    segment = intent_json.get("segment")

    # Normalize phase to uppercase if present
    if phase:
        phase = phase.upper()
    
    # Debug logging
    debug = False  # Set to True for debugging
    if debug:
        print(f"[DEBUG] intent={intent}, phase={phase}, metric={metric}, agg={agg}, segment={segment}")
    
    # ----- List all phases -----
    if intent == "list_phases":
        try:
            # Get phases from the data
            phases = ["TAXI", "TAKEOFF", "CLIMB", "CRUISE", "DESCENT", "APPROACH", "LANDING"]
            # Filter to only phases that have data
            available_phases = []
            for p in phases:
                try:
                    overview = engine.get_phase_overview(p)
                    if overview and not overview.get("error"):
                        available_phases.append(p)
                except:
                    pass
            
            if available_phases:
                return {"phases": available_phases, "count": len(available_phases)}
            else:
                # Fall back to all known phases
                return {"phases": phases, "count": len(phases)}
        except Exception as e:
            return {"error": f"Error listing phases: {str(e)}"}

    # ----- Flight overview -----
    if intent == "flight_overview":
        overview = engine.get_flight_overview()
        return overview

    # ----- Phase Duration -----
    if intent == "phase_duration" and phase:
        # if a specific numbered segment requested, return numbered summary/duration
        if segment:
            try:
                seg_num = int(segment)
            except Exception:
                return {"error": f"Invalid segment number: {segment}"}
            return engine.get_numbered_phase_summary(phase, seg_num)
        
        try:
            result = engine.get_phase_duration(phase)
            if result and not result.get("error"):
                return result
            else:
                return {"error": f"No duration data found for {phase} phase."}
        except Exception as e:
            return {"error": f"Error getting duration for {phase}: {str(e)}"}

    # ----- Metric queries -----
    if intent == "metric" and phase and metric:
        # Convert metric to lowercase for engine queries
        metric_lower = metric.lower()
        
        # Special handling for start/end aggregations
        if agg in {"start", "end"}:
            try:
                segments = engine.get_phase_segments(phase)
                if not segments:
                    return {"error": f"No data found for {phase} phase."}

                col_map = {
                    'ias': 'IAS',
                    'altitude': 'AltMSL',
                    'alt': 'AltMSL',
                    'altmsl': 'AltMSL',
                    'gnd': 'GndSpd',
                    'gndspd': 'GndSpd',
                    'vspd': 'VSpd',
                    'pitch': 'Pitch'
                }
                col = col_map.get(metric_lower)

                if agg == "start":
                    seg = segments[0]
                    if col and col in seg.columns:
                        vals = seg[col].dropna()
                        if not vals.empty:
                            val = float(vals.iloc[0])
                            unit = 'knots' if metric_lower in ['ias', 'gnd', 'gndspd'] else 'ft' if metric_lower in ['altitude', 'alt', 'altmsl'] else ''
                            return {"metric": metric, "phase": phase, "position": "start", "value": val, "unit": unit}
                    return {"error": f"No {col} data available at start of {phase}."}

                else:  # end
                    seg = segments[-1]
                    if col and col in seg.columns:
                        vals = seg[col].dropna()
                        if not vals.empty:
                            val = float(vals.iloc[-1])
                            unit = 'knots' if metric_lower in ['ias', 'gnd', 'gndspd'] else 'ft' if metric_lower in ['altitude', 'alt', 'altmsl'] else ''
                            return {"metric": metric, "phase": phase, "position": "end", "value": val, "unit": unit}
                    return {"error": f"No {col} data available at end of {phase}."}
            except Exception as e:
                return {"error": f"Error getting {agg} value: {str(e)}"}

        # General aggregation handled by engine
        try:
            value = engine.get_metric_value(metric_lower, phase, agg=agg or "avg")
            if not value:
                return {"error": f"{metric} data is not available for {phase}. Try: phases, taxi, takeoff, climb, cruise, descent, approach, or landing."}
            return value
        except Exception as e:
            return {"error": f"Error retrieving {metric} for {phase}: {str(e)}"}

    # ----- Phase Overview -----
    if intent == "phase_overview" and phase:
        # support numbered phase overview (e.g., TAXI segment 1)
        if segment:
            try:
                seg_num = int(segment)
            except Exception:
                return {"error": f"Invalid segment number: {segment}"}
            return engine.get_numbered_phase_summary(phase, seg_num)
        
        try:
            data = engine.get_phase_overview(phase)
            if data and not data.get("error"):
                # Add detailed narrative summary
                detailed_summary = engine.get_detailed_phase_summary(phase)
                if detailed_summary:
                    data["detailed_summary"] = detailed_summary
                return data
            else:
                return {"error": f"No overview data for {phase} phase."}
        except Exception as e:
            return {"error": f"Error getting overview for {phase}: {str(e)}"}

    # ----- Subphase Overview -----
    if intent == "subphase_info":
        try:
            return engine.get_subphase_overview()
        except Exception as e:
            return {"error": f"Error getting subphase info: {str(e)}"}

    # ----- Subphase Detail -----
    if intent == "subphase_detail" and intent_json.get("subphase"):
        try:
            return engine.get_subphase_detail(intent_json.get("subphase"))
        except Exception as e:
            return {"error": f"Error getting subphase detail: {str(e)}"}

    # ----- Subphase Metric -----
    if intent == "subphase_metric" and intent_json.get("subphase") and metric:
        try:
            sp = intent_json.get("subphase")
            return engine.get_subphase_metric(sp, metric)
        except Exception as e:
            return {"error": f"Error getting subphase metric: {str(e)}"}

    # ----- Metric queries for a specific numbered segment -----
    if intent == "metric" and phase and metric and segment:
        try:
            seg_num = int(segment)
        except Exception:
            return {"error": f"Invalid segment number: {segment}"}

        try:
            segments = engine.get_phase_segments(phase)
            if not segments or seg_num < 1 or seg_num > len(segments):
                return {"error": f"Invalid segment number {seg_num} for phase {phase}."}

            target_seg = segments[seg_num - 1]
            metric_lower = metric.lower()
            col_map = {
                'ias': 'IAS', 'altitude': 'AltMSL', 'alt': 'AltMSL', 'altmsl': 'AltMSL', 
                'gnd': 'GndSpd', 'gndspd': 'GndSpd', 'vspd': 'VSpd', 'pitch': 'Pitch'
            }
            col = col_map.get(metric_lower)
            if not col or col not in target_seg.columns:
                return {"error": f"Metric {metric} not available for segment {seg_num} of {phase}."}

            vals = target_seg[col].dropna()
            if vals.empty:
                return {"error": f"No {metric} data for segment {seg_num} of {phase}."}

            if agg in {"start"}:
                val = float(vals.iloc[0])
                return {"metric": metric, "phase": phase, "segment": seg_num, "position": "start", "value": val}
            if agg in {"end"}:
                val = float(vals.iloc[-1])
                return {"metric": metric, "phase": phase, "segment": seg_num, "position": "end", "value": val}
            if agg == "min":
                return {"metric": metric, "phase": phase, "segment": seg_num, "aggregation": "min", "value": float(vals.min())}
            if agg == "max":
                return {"metric": metric, "phase": phase, "segment": seg_num, "aggregation": "max", "value": float(vals.max())}
            # default avg
            return {"metric": metric, "phase": phase, "segment": seg_num, "aggregation": "avg", "value": float(vals.mean())}
        except Exception as e:
            return {"error": f"Error getting segment metric: {str(e)}"}

    # ----- Segment Summary -----
    if intent == "segment_summary" and phase:
        try:
            summary = engine.get_segment_summary(phase)
            return summary
        except Exception as e:
            return {"error": f"Error getting segment summary: {str(e)}"}

    # Fallback error message - if intent doesn't match any handler
    if intent:
        return {"error": f"Cannot process '{intent}' query. Try: 'list phases', 'taxi duration', 'max IAS during climb', 'tell about approach', or 'what metrics for cruise'"}
    else:
        return {"error": "Sorry, I can't answer that with the available data. Try asking about: phases, taxi, takeoff, climb, cruise, descent, approach, or landing."}


# Initialize engine on import (best-effort)
try:
    init_engine()
except Exception as e:
    print(f"Engine initialization failed: {e}")
