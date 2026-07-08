# Flight Analytics AI - User Guide

## Overview

The Flight Analytics AI Assistant is a natural language interface for analyzing flight data with multi-layer validation and anti-hallucination safeguards. It parses flight CSV files and allows you to ask questions in natural language, receiving precise answers grounded in actual data.

## Key Features

### 1. **Natural Language Queries**
Ask questions about your flight data in plain English:
- "What was the duration of the taxi?"
- "Maximum IAS during cruise?"
- "Summary of takeoff phase"
- "Any abnormal climb?"

### 2. **Multi-Layer Validation**
Every answer is validated through:
- **Data Source Verification**: All answers trace back to actual CSV data
- **Aviation Standards Checking**: Compares metrics against documented ranges
- **Anomaly Detection**: Identifies values outside normal operational parameters
- **Confidence Scoring**: Shows reliability of each answer (0-1 scale)

### 3. **Anti-Hallucination System**
The system prevents fabricated responses by:
- Only returning values that exist in the flight data
- Refusing to extrapolate or invent data points
- Showing all data points used in calculations
- Displaying validation pass/fail status

## How to Use

### Step 1: Upload Flight Data
1. Click "Select File" or drag-and-drop a CSV file
2. CSV must contain standard aviation columns (see Expected Format below)
3. System automatically parses and validates the file

### Step 2: View Flight Summary
Once uploaded, you'll see:
- **Flight Duration**: Total time for the flight
- **Max Altitude**: Highest altitude reached
- **Max Airspeed**: Highest indicated airspeed
- **Flight Phases**: Detected phases (Ground, Taxi, Takeoff, Climb, Cruise, Descent, Approach, Landing)
- **Max G-Load**: Maximum g-forces experienced

### Step 3: Ask Questions
Use the chat interface to ask about:

#### Metric Queries
- Taxi duration
- Maximum/Average airspeed
- Maximum/Minimum altitude
- Vertical speed/Climb rate/Descent rate
- G-load analysis

#### Phase Analysis
- "Summary of [phase] phase" - e.g., "Summary of cruise phase"
- Phase duration and metrics
- Data points per phase

#### Anomaly Detection
- "Any abnormal climb?" - Detects climb phase irregularities
- Checks against aviation standards
- Identifies specific issues (overspeed, low airspeed, excessive g-load)

## Expected CSV Format

Your flight data CSV should include these columns:

### Required Columns:
- `timestamp` - Time in format HH:MM:SS
- `time_seconds` - Elapsed time in seconds
- `altitude_ft` - Altitude in feet
- `ias_knots` - Indicated airspeed in knots
- `vertical_speed_fpm` - Vertical speed in feet per minute
- `engine_thrust_percent` - Thrust percentage (0-100)
- `gear_position` - "UP" or "DOWN"

### Optional Columns:
- `mach` - Mach number
- `heading` - Heading in degrees
- `pitch_angle` - Pitch angle in degrees
- `bank_angle` - Bank angle in degrees
- `normal_acceleration_g` - G-forces
- `roll_rate` - Roll rate in degrees/sec
- `pitch_rate` - Pitch rate in degrees/sec
- `yaw_rate` - Yaw rate in degrees/sec
- `fuel_weight_lbs` - Fuel weight in pounds
- `flaps_setting` - Flaps position (0-15)

## Response Format

Each answer includes:

1. **Answer**: Direct response to your question
2. **Confidence Score**: 0.0-1.0 (how confident is the system?)
3. **Data Source**: How many data points were used
4. **Methodology**: How the answer was calculated
5. **Anomalies**: Any issues detected
6. **Validation Status**: Whether answer passed all checks

## Example Questions & Answers

### Example 1: Taxi Duration
**Question**: "What was the duration of the taxi?"
**Answer**: "The taxi duration was 3.50 minutes (210 seconds). Data points: 7."
**Confidence**: 95%
**Validation**: Passed

### Example 2: Max IAS During Cruise
**Question**: "Maximum IAS during cruise?"
**Answer**: "The maximum indicated airspeed (IAS) during cruise was 400.0 knots."
**Confidence**: 90%
**Data Source**: 45 data points from Cruise phase
**Anomalies**: None detected

### Example 3: Climb Phase Analysis
**Question**: "Summary of takeoff phase"
**Response**: 
```
Takeoff Phase Summary (12 data points):
Duration: 1.50 minutes
Altitude: 500-2100 feet (avg: 1300)
IAS: 0.0-135.0 knots (avg: 67.5)
Vertical Speed: 0-1000 fpm
```

### Example 4: Abnormal Climb Detection
**Question**: "Any abnormal climb?"
**Answer**: "The climb phase appears normal. All parameters are within expected aviation standards."
**Confidence**: 95%
**Validation**: Passed

## Aviation Standards Reference

The system validates against these standard ranges:

### Taxi Phase:
- Max IAS: 30 knots
- Altitude: 0-100 feet

### Takeoff Phase:
- IAS: 100-250 knots
- Altitude: 0-5000 feet
- Min Thrust: 75%

### Climb Phase:
- Altitude: 2000+ feet
- Vertical Speed: 500-4000 fpm
- Max IAS: 280 knots (below 10,000 ft)
- Max G-Load: 2.5g

### Cruise Phase:
- Altitude: 15,000+ feet
- IAS: 200-500 knots
- Vertical Speed: ±500 fpm

### Descent Phase:
- Vertical Speed: -4000 to -500 fpm

### Approach Phase:
- Altitude: 500-5000 feet
- IAS: 120-200 knots
- Max G-Load: 1.5g

### Landing Phase:
- Altitude: 0-500 feet
- IAS: 100-180 knots
- Max G-Load: 2.0g

## Confidence Scoring

Confidence is calculated based on:
1. **Data Availability**: More data points = higher confidence
2. **Phase Definition**: Well-defined phases (Cruise, Climb) = higher confidence
3. **Validation Passes**: More validation checks passed = higher confidence

Typically:
- 0.95+ = Excellent (direct measurement)
- 0.85-0.94 = Good (well-supported by data)
- 0.75-0.84 = Fair (adequate data)
- 0.50-0.74 = Low (limited data or estimation)

## Troubleshooting

### CSV Upload Fails
- Check that file is `.csv` format
- Verify at least these columns exist: timestamp, time_seconds, altitude_ft, ias_knots
- Ensure column headers match expected names (case-insensitive)

### Query Returns "Not Found"
- Phase may not exist in flight data
- Try different question phrasing
- Check flight summary for available phases

### Confidence Score Low
- Flight data may have gaps
- Specific phase may have few data points
- Consider the available data range

## Sample Data

A sample flight CSV is provided as `public/sample-flight.csv`. It contains a complete flight profile from taxi through landing and can be used to test all features.

## Technical Details

### Query Processing
1. **Rule Matching**: System matches query against known patterns
2. **Data Extraction**: Relevant data points are extracted from CSV
3. **Calculation**: Metrics are computed
4. **Validation**: Results checked against aviation standards
5. **Confidence Calculation**: Score generated based on data quality
6. **Response Generation**: Formatted answer with full details

### Data Storage
- No persistent database required
- Flight data parsed in-memory for fast queries
- Supports both pre-loaded and user-uploaded files
- Full traceability to source CSV rows

## Support

For issues or feature requests, check the backend logs and browser console for detailed error messages.
