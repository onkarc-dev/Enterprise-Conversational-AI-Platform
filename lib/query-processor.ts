/**
 * Query Processor - calls the FastAPI flight analytics backend.
 */

import { parseFlightCSV } from './flight-parser';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export interface QueryResult {
  success: boolean;
  answer: string;
  confidence_score: number;
  intent?: string;
  warnings: string[];
  validation_passed: boolean;
  raw?: unknown;
}

export async function processQuery(query: string): Promise<QueryResult> {
  const response = await fetch(`${API_BASE_URL}/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query: query.trim() }),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.error || `API error: ${response.statusText}`);
  }

  return {
    success: data.success !== false,
    answer: data.reply || data.response || data.answer || JSON.stringify(data.result ?? data),
    confidence_score: data.confidence_score ?? 0.9,
    intent: data.intent,
    warnings: data.warnings ?? [],
    validation_passed: data.validation_passed ?? !data.error,
    raw: data,
  };
}

export async function getFlightOverview(): Promise<unknown> {
  const response = await fetch(`${API_BASE_URL}/test`);

  if (!response.ok) {
    throw new Error(`API error: ${response.statusText}`);
  }

  return response.json();
}

export async function uploadCSV(
  file: File
): Promise<{
  success: boolean;
  filename: string;
  overview?: unknown;
  error?: string;
}> {
  try {
    const content = await file.text();
    const overview = parseFlightCSV(content);

    return {
      success: true,
      filename: file.name,
      overview: {
        ...overview,
        filename: file.name,
      },
    };
  } catch (error) {
    return {
      success: false,
      filename: file.name,
      error: error instanceof Error ? error.message : 'Failed to parse CSV file',
    };
  }
}

export async function checkBackendHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/`);
    return response.ok;
  } catch {
    return false;
  }
}
