/**
 * Query Processor - Calls the Flask Backend API
 * Integrates with Python backend for flight analytics
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000';

export interface QueryResult {
  answer: string;
  confidence_score?: number;
  intent?: string;
  warnings?: string[];
  validation_passed?: boolean;
  success: boolean;
  error?: string;
}

/**
 * Process a natural language query via backend API
 * Calls Qwen2.5-3B-Instruct LLM with validation
 */
export async function processQuery(
  query: string,
  _flightData?: any
): Promise<QueryResult> {
  if (!query || !query.trim()) {
    throw new Error('Query cannot be empty');
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query: query.trim(),
      }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || `API error: ${response.statusText}`);
    }

    const data = await response.json();

    return {
      success: data.success !== false,
      answer: data.response || data.answer || 'No response from backend',
      confidence_score: data.confidence ?? 0.8,
      intent: data.intent,
      warnings: data.warnings ?? [],
      validation_passed: data.validation_passed ?? true,
    };
  } catch (error: any) {
    console.error('[v0] Query processing error:', error);

    // Fallback behavior if backend is unavailable
    if (error.message.includes('fetch') || error.message.includes('Failed to fetch')) {
      throw new Error(
        'Backend service unavailable. Ensure the Python server is running on port 5000.'
      );
    }

    throw error;
  }
}

/**
 * Upload a CSV file to the backend
 */
export async function uploadCSV(
  file: File
): Promise<{
  success: boolean;
  filename: string;
  overview?: any;
  error?: string;
}> {
  try {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE_URL}/api/upload-csv`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || `Upload failed: ${response.statusText}`);
    }

    const data = await response.json();
    return {
      success: data.success !== false,
      filename: data.filename,
      overview: data.overview,
    };
  } catch (error: any) {
    console.error('[v0] CSV upload error:', error);
    return {
      success: false,
      filename: '',
      error: error.message || 'Failed to upload CSV file',
    };
  }
}

/**
 * Get flight data overview
 */
export async function getFlightOverview(): Promise<any> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/flight-overview`);

    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`);
    }

    return await response.json();
  } catch (error: any) {
    console.error('[v0] Flight overview error:', error);
    return null;
  }
}

/**
 * Get list of flight phases
 */
export async function getPhases(): Promise<
  Array<{
    name: string;
    duration: string;
    segments: number;
  }>
> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/phases`);

    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`);
    }

    const data = await response.json();
    return data.phases || [];
  } catch (error: any) {
    console.error('[v0] Phases error:', error);
    return [];
  }
}

/**
 * Get details about a specific flight phase
 */
export async function getPhaseDetail(phaseName: string): Promise<any> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/phase/${phaseName}`);

    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`);
    }

    return await response.json();
  } catch (error: any) {
    console.error('[v0] Phase detail error:', error);
    return null;
  }
}

/**
 * Check backend health status
 */
export async function checkBackendHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/health`);
    return response.ok;
  } catch {
    return false;
  }
}
