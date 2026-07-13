import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.FASTAPI_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const message = typeof body.message === 'string' ? body.message.trim() : '';

    if (!message) {
      return NextResponse.json({ error: 'message is required' }, { status: 400 });
    }

    const backendResponse = await fetch(`${API_BASE_URL}/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query: message }),
    });

    const data = await backendResponse.json();

    if (!backendResponse.ok) {
      return NextResponse.json(
        { error: data.error || 'Backend query failed', details: data },
        { status: backendResponse.status }
      );
    }

    return NextResponse.json({
      reply: data.reply || data.response || data.answer || formatResult(data.result ?? data),
      result: data.result ?? data,
      intent: data.intent,
      validation_passed: data.validation_passed ?? true,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown API route failure';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

function formatResult(value: unknown): string {
  if (typeof value === 'string') {
    return value;
  }

  if (value && typeof value === 'object' && 'error' in value) {
    return String((value as { error: unknown }).error);
  }

  return JSON.stringify(value);
}
