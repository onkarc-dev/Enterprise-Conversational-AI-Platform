import { FlightDataRow, extractMetrics } from './flight-parser';

export interface AnomalyDetection {
  detected: boolean;
  anomalies: {
    type: string;
    value: number;
    normalRange: string;
    severity: 'info' | 'warning' | 'critical';
  }[];
}

/**
 * Aviation standard ranges for validation
 * Based on general large transport aircraft (e.g., Boeing 737, Airbus A320)
 */
const AVIATION_STANDARDS = {
  taxi: {
    ias_max: 30, // knots
    altitude_min: 0,
    altitude_max: 100,
  },
  takeoff: {
    ias_min: 100, // knots
    ias_max: 250,
    altitude_min: 0,
    altitude_max: 5000,
    thrust_min: 75, // percent
  },
  climb: {
    altitude_min: 2000,
    vertical_speed_min: 500, // fpm (should be climbing)
    vertical_speed_max: 4000,
    ias_max: 280, // below 10,000 ft
    g_load_max: 2.5, // normal operations
  },
  cruise: {
    altitude_min: 15000,
    ias_min: 200,
    ias_max: 500,
    vertical_speed_min: -500,
    vertical_speed_max: 500,
    g_load_normal: 1.0,
  },
  descent: {
    vertical_speed_min: -4000, // fpm (should be descending)
    vertical_speed_max: -500,
    ias_max: 280, // below 10,000 ft
  },
  approach: {
    altitude_min: 500,
    altitude_max: 5000,
    ias_min: 120,
    ias_max: 200,
    g_load_max: 1.5,
  },
  landing: {
    altitude_min: 0,
    altitude_max: 500,
    ias_min: 100,
    ias_max: 180,
    g_load_max: 2.0,
  },
};

/**
 * Extract specific metric values from flight data
 */
export function getMetricValue(
  data: FlightDataRow[],
  metricType: string,
  phase?: string
): { value: number | null; source_rows: FlightDataRow[]; unit: string } {
  const filtered = phase ? data.filter(d => d.phase === phase) : data;

  if (filtered.length === 0) {
    return { value: null, source_rows: [], unit: '' };
  }

  switch (metricType.toLowerCase()) {
    case 'taxi_duration':
    case 'taxi duration':
      const taxiData = data.filter(d => d.phase === 'Taxi');
      if (taxiData.length === 0) return { value: null, source_rows: [], unit: 'minutes' };
      const taxiDuration =
        (taxiData[taxiData.length - 1].time_seconds - taxiData[0].time_seconds) / 60;
      return { value: taxiDuration, source_rows: taxiData, unit: 'minutes' };

    case 'max_ias':
    case 'maximum ias':
    case 'max airspeed':
      const maxIAS = Math.max(...filtered.map(d => d.ias_knots));
      const maxIASRows = filtered.filter(d => d.ias_knots === maxIAS);
      return { value: maxIAS, source_rows: maxIASRows, unit: 'knots' };

    case 'max_altitude':
    case 'maximum altitude':
    case 'max altitude':
      const maxAlt = Math.max(...filtered.map(d => d.altitude_ft));
      const maxAltRows = filtered.filter(d => d.altitude_ft === maxAlt);
      return { value: maxAlt, source_rows: maxAltRows, unit: 'feet' };

    case 'min_altitude':
    case 'minimum altitude':
      const minAlt = Math.min(...filtered.map(d => d.altitude_ft));
      const minAltRows = filtered.filter(d => d.altitude_ft === minAlt);
      return { value: minAlt, source_rows: minAltRows, unit: 'feet' };

    case 'avg_ias':
    case 'average ias':
    case 'average airspeed':
      const avgIAS = filtered.reduce((a, b) => a + b.ias_knots, 0) / filtered.length;
      return { value: avgIAS, source_rows: filtered.slice(0, 5), unit: 'knots' };

    case 'max_vertical_speed':
    case 'maximum climb rate':
    case 'max climb rate':
      const maxVS = Math.max(...filtered.map(d => d.vertical_speed_fpm));
      const maxVSRows = filtered.filter(d => d.vertical_speed_fpm === maxVS);
      return { value: maxVS, source_rows: maxVSRows, unit: 'feet/min' };

    case 'max_descent_rate':
    case 'maximum descent rate':
      const minVS = Math.min(...filtered.map(d => d.vertical_speed_fpm));
      const minVSRows = filtered.filter(d => d.vertical_speed_fpm === minVS);
      return { value: Math.abs(minVS), source_rows: minVSRows, unit: 'feet/min' };

    case 'max_g_load':
    case 'maximum g load':
    case 'max g':
      const maxG = Math.max(...filtered.map(d => d.normal_acceleration_g));
      const maxGRows = filtered.filter(d => d.normal_acceleration_g === maxG);
      return { value: maxG, source_rows: maxGRows, unit: 'g' };

    case 'flight_duration':
    case 'total flight time':
    case 'total duration':
      const duration = filtered[filtered.length - 1].time_seconds - filtered[0].time_seconds;
      return { value: duration / 60, source_rows: [filtered[0], filtered[filtered.length - 1]], unit: 'minutes' };

    default:
      return { value: null, source_rows: [], unit: '' };
  }
}

/**
 * Get phase summary with all metrics
 */
export function getPhaseSummary(data: FlightDataRow[], phase: string) {
  const phaseData = data.filter(d => d.phase === phase);

  if (phaseData.length === 0) {
    return null;
  }

  const metrics = extractMetrics(data, phase);
  const anomalies = detectAnomalies(phaseData, phase);

  return {
    phase,
    duration_seconds: metrics?.time_range.duration || 0,
    data_points: phaseData.length,
    metrics,
    anomalies,
    sample_data: {
      start: phaseData[0],
      mid: phaseData[Math.floor(phaseData.length / 2)],
      end: phaseData[phaseData.length - 1],
    },
  };
}

/**
 * Detect anomalies compared to aviation standards
 */
export function detectAnomalies(data: FlightDataRow[], phase: string): AnomalyDetection {
  const standards = AVIATION_STANDARDS[phase.toLowerCase() as keyof typeof AVIATION_STANDARDS];

  if (!standards) {
    return { detected: false, anomalies: [] };
  }

  const anomalies: AnomalyDetection['anomalies'] = [];

  for (const row of data) {
    // Check IAS limits
    if ('ias_max' in standards && row.ias_knots > standards.ias_max) {
      anomalies.push({
        type: 'Excessive airspeed',
        value: row.ias_knots,
        normalRange: `0-${standards.ias_max} knots`,
        severity: 'warning',
      });
    }

    if ('ias_min' in standards && row.ias_knots < standards.ias_min) {
      anomalies.push({
        type: 'Low airspeed',
        value: row.ias_knots,
        normalRange: `${standards.ias_min}+ knots`,
        severity: 'warning',
      });
    }

    // Check altitude limits
    if ('altitude_max' in standards && row.altitude_ft > standards.altitude_max) {
      anomalies.push({
        type: 'Excessive altitude',
        value: row.altitude_ft,
        normalRange: `0-${standards.altitude_max} feet`,
        severity: 'info',
      });
    }

    // Check vertical speed
    if ('vertical_speed_max' in standards && row.vertical_speed_fpm > standards.vertical_speed_max) {
      anomalies.push({
        type: 'Excessive climb rate',
        value: row.vertical_speed_fpm,
        normalRange: `${standards.vertical_speed_min || -4000}-${standards.vertical_speed_max} fpm`,
        severity: 'info',
      });
    }

    // Check g-load
    if ('g_load_max' in standards && row.normal_acceleration_g > standards.g_load_max) {
      anomalies.push({
        type: 'Excessive g-load',
        value: row.normal_acceleration_g,
        normalRange: `1.0-${standards.g_load_max} g`,
        severity: 'critical',
      });
    }
  }

  return {
    detected: anomalies.length > 0,
    anomalies: [...new Map(anomalies.map(a => [a.type, a])).values()].slice(0, 5), // Deduplicate and limit
  };
}

/**
 * Check for abnormal climb patterns
 */
export function detectAbnormalClimb(data: FlightDataRow[]): {
  abnormal: boolean;
  issues: string[];
  details: Record<string, any>;
} {
  const climbData = data.filter(d => d.phase === 'Climb');

  if (climbData.length === 0) {
    return { abnormal: false, issues: [], details: {} };
  }

  const issues: string[] = [];
  const details: Record<string, any> = {};

  // Check vertical speed consistency
  const verticalSpeeds = climbData.map(d => d.vertical_speed_fpm);
  const avgVS = verticalSpeeds.reduce((a, b) => a + b, 0) / verticalSpeeds.length;
  const vsVariance =
    verticalSpeeds.reduce((a, b) => a + Math.pow(b - avgVS, 2), 0) / verticalSpeeds.length;
  const vsStdDev = Math.sqrt(vsVariance);

  details.climb_rate_avg = Math.round(avgVS);
  details.climb_rate_variance = Math.round(vsStdDev);

  if (avgVS < 500) {
    issues.push('Low average climb rate (< 500 fpm)');
  }

  if (avgVS > 4000) {
    issues.push('Excessive climb rate (> 4000 fpm)');
  }

  // Check for stall risk (airspeed too low)
  const lowAirspeed = climbData.filter(d => d.ias_knots < 120);
  if (lowAirspeed.length > climbData.length * 0.1) {
    issues.push(`Low airspeed detected in ${lowAirspeed.length} data points`);
    details.low_airspeed_points = lowAirspeed.length;
  }

  // Check for overspeed risk
  const overspeed = climbData.filter(d => d.ias_knots > 280);
  if (overspeed.length > climbData.length * 0.1) {
    issues.push(`Overspeed condition detected in ${overspeed.length} data points`);
    details.overspeed_points = overspeed.length;
  }

  // Check for high g-loads
  const highG = climbData.filter(d => d.normal_acceleration_g > 2.0);
  if (highG.length > 0) {
    issues.push(`High g-loads detected (${highG.length} points exceeding 2.0g)`);
    details.high_g_points = highG.length;
    details.max_g = Math.max(...climbData.map(d => d.normal_acceleration_g));
  }

  return {
    abnormal: issues.length > 0,
    issues,
    details,
  };
}
