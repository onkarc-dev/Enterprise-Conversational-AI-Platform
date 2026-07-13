import Papa from 'papaparse';

export interface FlightDataRow {
  timestamp: string;
  time_seconds: number;
  altitude_ft: number;
  ias_knots: number;
  mach: number;
  vertical_speed_fpm: number;
  heading: number;
  pitch_angle: number;
  bank_angle: number;
  normal_acceleration_g: number;
  roll_rate: number;
  pitch_rate: number;
  yaw_rate: number;
  engine_thrust_percent: number;
  fuel_weight_lbs: number;
  gear_position: 'UP' | 'DOWN';
  flaps_setting: number;
  phase: string;
  [key: string]: any;
}

export interface FlightDataSet {
  filename: string;
  uploadedAt: string;
  totalRows: number;
  duration_seconds: number;
  startTime: string;
  endTime: string;
  data: FlightDataRow[];
  metadata: {
    aircraft_type?: string;
    flight_number?: string;
    departure?: string;
    arrival?: string;
    date?: string;
  };
}

/**
 * Parse CSV flight data into structured format
 * Handles flexible column naming and normalizes data
 */
export function parseFlightCSV(csvContent: string): FlightDataSet {
  const results = Papa.parse(csvContent, {
    header: true,
    dynamicTyping: false,
    skipEmptyLines: true,
    transformHeader: (h: string) => h.toLowerCase().trim(),
  });

  if (results.errors.length > 0) {
    throw new Error(`CSV Parse Error: ${results.errors[0].message}`);
  }

  const rawRows = results.data as Record<string, any>[];
  
  // Normalize and validate data
  const data: FlightDataRow[] = rawRows.map((row, index) => {
    const normalized: FlightDataRow = {
      timestamp: row.timestamp || row.time || `${index}`,
      time_seconds: parseFloat(row.time_seconds || row.elapsed_time || row.time || '0') || 0,
      altitude_ft: parseFloat(row.altitude_ft || row.altitude || '0') || 0,
      ias_knots: parseFloat(row.ias_knots || row.ias || row.airspeed || '0') || 0,
      mach: parseFloat(row.mach || '0') || 0,
      vertical_speed_fpm: parseFloat(row.vertical_speed_fpm || row.vs || row.vertical_speed || '0') || 0,
      heading: parseFloat(row.heading || '0') || 0,
      pitch_angle: parseFloat(row.pitch_angle || row.pitch || '0') || 0,
      bank_angle: parseFloat(row.bank_angle || row.bank || '0') || 0,
      normal_acceleration_g: parseFloat(row.normal_acceleration_g || row.g_load || row.acceleration || '1') || 1,
      roll_rate: parseFloat(row.roll_rate || '0') || 0,
      pitch_rate: parseFloat(row.pitch_rate || '0') || 0,
      yaw_rate: parseFloat(row.yaw_rate || '0') || 0,
      engine_thrust_percent: parseFloat(row.engine_thrust_percent || row.thrust || '0') || 0,
      fuel_weight_lbs: parseFloat(row.fuel_weight_lbs || row.fuel || '0') || 0,
      gear_position: (row.gear_position || row.gear || 'DOWN').toUpperCase() as 'UP' | 'DOWN',
      flaps_setting: parseFloat(row.flaps_setting || row.flaps || '0') || 0,
      phase: detectPhase(index, rawRows.length, {
        altitude_ft: parseFloat(row.altitude_ft || row.altitude || '0') || 0,
        ias_knots: parseFloat(row.ias_knots || row.ias || '0') || 0,
        engine_thrust_percent: parseFloat(row.engine_thrust_percent || row.thrust || '0') || 0,
        gear_position: (row.gear_position || row.gear || 'DOWN').toUpperCase(),
      }),
    };
    return normalized;
  });

  const totalRows = data.length;
  const duration_seconds = Math.max(
    ...data.map(d => d.time_seconds),
    0
  );

  return {
    filename: 'flight-data.csv',
    uploadedAt: new Date().toISOString(),
    totalRows,
    duration_seconds,
    startTime: data[0]?.timestamp || 'Unknown',
    endTime: data[data.length - 1]?.timestamp || 'Unknown',
    data,
    metadata: {
      date: new Date().toISOString().split('T')[0],
    },
  };
}

/**
 * Auto-detect flight phase based on parameters
 * Phases: Ground, Taxi, Takeoff, Climb, Cruise, Descent, Approach, Landing, Ground
 */
function detectPhase(
  index: number,
  totalRows: number,
  params: {
    altitude_ft: number;
    ias_knots: number;
    engine_thrust_percent: number;
    gear_position: string;
  }
): string {
  const { altitude_ft, ias_knots, engine_thrust_percent, gear_position } = params;

  // Ground phase
  if (altitude_ft < 500) {
    if (ias_knots < 10 && engine_thrust_percent < 20) return 'Ground';
    if (ias_knots > 5 && ias_knots < 50) return 'Taxi';
  }

  // Takeoff
  if (altitude_ft >= 500 && altitude_ft < 2000 && ias_knots > 50) {
    return 'Takeoff';
  }

  // Climb
  if (altitude_ft >= 2000 && altitude_ft < 25000 && engine_thrust_percent > 80) {
    return 'Climb';
  }

  // Cruise
  if (altitude_ft >= 20000 && engine_thrust_percent < 80) {
    return 'Cruise';
  }

  // Descent
  if (altitude_ft < 25000 && altitude_ft > 2000 && engine_thrust_percent < 50 && index > totalRows * 0.5) {
    return 'Descent';
  }

  // Approach & Landing
  if (altitude_ft < 2000 && altitude_ft >= 500 && index > totalRows * 0.6) {
    return 'Approach';
  }

  if (altitude_ft < 500 && ias_knots < 100 && index > totalRows * 0.7) {
    return 'Landing';
  }

  return 'Unknown';
}

/**
 * Extract specific metrics from flight data
 */
export function extractMetrics(data: FlightDataRow[], phase?: string) {
  const filtered = phase ? data.filter(d => d.phase === phase) : data;

  if (filtered.length === 0) {
    return null;
  }

  return {
    count: filtered.length,
    time_range: {
      start: filtered[0].time_seconds,
      end: filtered[filtered.length - 1].time_seconds,
      duration: filtered[filtered.length - 1].time_seconds - filtered[0].time_seconds,
    },
    altitude: {
      min: Math.min(...filtered.map(d => d.altitude_ft)),
      max: Math.max(...filtered.map(d => d.altitude_ft)),
      avg: filtered.reduce((a, b) => a + b.altitude_ft, 0) / filtered.length,
    },
    ias: {
      min: Math.min(...filtered.map(d => d.ias_knots)),
      max: Math.max(...filtered.map(d => d.ias_knots)),
      avg: filtered.reduce((a, b) => a + b.ias_knots, 0) / filtered.length,
    },
    vertical_speed: {
      min: Math.min(...filtered.map(d => d.vertical_speed_fpm)),
      max: Math.max(...filtered.map(d => d.vertical_speed_fpm)),
      avg: filtered.reduce((a, b) => a + b.vertical_speed_fpm, 0) / filtered.length,
    },
    g_load: {
      min: Math.min(...filtered.map(d => d.normal_acceleration_g)),
      max: Math.max(...filtered.map(d => d.normal_acceleration_g)),
      avg: filtered.reduce((a, b) => a + b.normal_acceleration_g, 0) / filtered.length,
    },
    thrust: {
      min: Math.min(...filtered.map(d => d.engine_thrust_percent)),
      max: Math.max(...filtered.map(d => d.engine_thrust_percent)),
      avg: filtered.reduce((a, b) => a + b.engine_thrust_percent, 0) / filtered.length,
    },
  };
}

/**
 * Get all unique phases in the flight
 */
export function getFlightPhases(data: FlightDataRow[]): string[] {
  return [...new Set(data.map(d => d.phase))].filter(p => p !== 'Unknown');
}
