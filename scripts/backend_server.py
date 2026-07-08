#!/usr/bin/env python3
"""
Flight Analytics Backend Server
Serves the Next.js frontend via REST API endpoints
Integrates all Python backend components
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import sys
import os
from pathlib import Path
import traceback

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import backend components
from lib.flight_engine import DynamicFlightCalculator
from lib.engine_executor import execute_query
from lib.llm_router import llm_parse_query, load_model, call_llm
from lib.llm_rephraser import rephrase_answer
from lib.validation_layer import get_validator, validate_and_ground_response

app = Flask(__name__)
CORS(app)

# Global state
flight_engine = None
validator = None
llm_loaded = False
uploaded_csv_path = None


def initialize_backend():
    """Initialize all backend components."""
    global flight_engine, validator, llm_loaded
    
    try:
        # Initialize flight engine with default CSV
        csv_path = "rule_labelled.csv"
        if os.path.exists(csv_path):
            flight_engine = DynamicFlightCalculator(csv_path)
            flight_engine.load_data()
            flight_engine.create_segments()
            flight_engine.add_phase_numbering()
            print(f"✓ Flight engine initialized with {csv_path}")
        
        # Initialize validator
        validator = get_validator()
        print("✓ Validation layer initialized")
        
        # Load LLM model
        try:
            load_model()
            llm_loaded = True
            print("✓ LLM model loaded")
        except Exception as e:
            print(f"⚠ LLM loading failed: {e}. Some features may be limited.")
            llm_loaded = False
        
        return True
    except Exception as e:
        print(f"✗ Backend initialization failed: {e}")
        traceback.print_exc()
        return False


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'components': {
            'engine': flight_engine is not None,
            'validator': validator is not None,
            'llm': llm_loaded
        }
    })


@app.route('/api/upload-csv', methods=['POST'])
def upload_csv():
    """Handle CSV file uploads."""
    global flight_engine, uploaded_csv_path
    
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'Only CSV files are supported'}), 400
        
        # Save uploaded file
        upload_dir = Path('uploads')
        upload_dir.mkdir(exist_ok=True)
        csv_path = upload_dir / file.filename
        file.save(str(csv_path))
        
        # Load new CSV
        flight_engine = DynamicFlightCalculator(str(csv_path))
        flight_engine.load_data()
        flight_engine.create_segments()
        flight_engine.add_phase_numbering()
        uploaded_csv_path = str(csv_path)
        
        # Get overview
        overview = flight_engine.get_flight_overview()
        
        return jsonify({
            'success': True,
            'filename': file.filename,
            'overview': overview
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/query', methods=['POST'])
def process_query():
    """Process natural language query."""
    try:
        data = request.json
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({'error': 'Query is empty'}), 400
        
        if flight_engine is None:
            return jsonify({'error': 'Flight data not loaded. Please upload a CSV file.'}), 500
        
        # Step 1: Parse query intent
        intent = llm_parse_query(query, {})
        
        if not intent or intent.get('error'):
            return jsonify({
                'success': False,
                'response': 'Could not parse query. Try asking about phases, taxi duration, or max IAS during climb.'
            })
        
        # Step 2: Execute against flight data
        result = execute_query(intent, flight_engine)
        
        if result is None or (isinstance(result, dict) and result.get('error')):
            error_msg = result.get('error', 'No data found') if isinstance(result, dict) else 'No results'
            return jsonify({
                'success': False,
                'response': error_msg
            })
        
        result['intent'] = intent.get('intent')
        
        # Step 3: Generate natural language response
        response = rephrase_answer(query, result)
        
        # Step 4: Validate response
        grounded_response, validation = validate_and_ground_response(query, intent, response)
        
        if grounded_response != response:
            response = grounded_response
        
        return jsonify({
            'success': True,
            'response': response,
            'intent': intent.get('intent'),
            'confidence': validation.get('valid', True),
            'warnings': validation.get('warnings', [])
        })
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/flight-overview', methods=['GET'])
def flight_overview():
    """Get flight data overview."""
    try:
        if flight_engine is None:
            return jsonify({'error': 'Flight data not loaded'}), 500
        
        overview = flight_engine.get_flight_overview()
        return jsonify(overview)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/phases', methods=['GET'])
def list_phases():
    """List all flight phases."""
    try:
        if flight_engine is None:
            return jsonify({'error': 'Flight data not loaded'}), 500
        
        phases = []
        for phase_name in ['TAXI', 'TAKEOFF', 'CLIMB', 'CRUISE', 'DESCENT', 'APPROACH', 'LANDING']:
            try:
                overview = flight_engine.get_phase_overview(phase_name)
                if overview and not overview.get('error'):
                    duration = overview.get('duration_formatted', 'N/A')
                    phases.append({
                        'name': phase_name,
                        'duration': duration,
                        'segments': overview.get('total_segments', 1)
                    })
            except:
                pass
        
        return jsonify({'phases': phases})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/phase/<phase_name>', methods=['GET'])
def phase_detail(phase_name):
    """Get detailed information about a flight phase."""
    try:
        if flight_engine is None:
            return jsonify({'error': 'Flight data not loaded'}), 500
        
        overview = flight_engine.get_phase_overview(phase_name.upper())
        return jsonify(overview)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("\n" + "="*80)
    print("  FLIGHT ANALYTICS BACKEND SERVER")
    print("="*80 + "\n")
    
    if initialize_backend():
        print("\n Starting Flask server...\n")
        app.run(debug=False, host='0.0.0.0', port=5000)
    else:
        print("Backend initialization failed. Exiting.")
        sys.exit(1)
