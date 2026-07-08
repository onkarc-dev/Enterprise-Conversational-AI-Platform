'use client';

import { useState, useRef, useEffect } from 'react';
import { Send, AlertCircle, CheckCircle2, Zap } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { processQuery } from '@/lib/query-processor';

interface Message {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  result?: any;
  timestamp: Date;
}

interface ChatInterfaceProps {
  flightData: any;
}

export function ChatInterface({ flightData }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      type: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const result = await processQuery(input, flightData);

      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        type: 'assistant',
        content: result.answer,
        result,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error: any) {
      const errorMessage: Message = {
        id: `error-${Date.now()}`,
        type: 'assistant',
        content: `Error: ${error.message || 'Failed to process query'}`,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 rounded-xl border border-slate-700/50 bg-slate-800/30 p-6 backdrop-blur-sm">
        <h2 className="text-2xl font-bold text-white">Natural Language Query</h2>
        <p className="text-slate-300">
          Ask any question about your flight data. The system will extract relevant metrics, validate against aviation standards, and show confidence levels.
        </p>

        {/* Example Queries */}
        <div className="grid gap-2 sm:grid-cols-2 pt-4">
          {[
            'What was the duration of the taxi?',
            'Maximum IAS during cruise?',
            'Summary of takeoff phase',
            'Any abnormal climb?',
          ].map(example => (
            <button
              key={example}
              onClick={() => setInput(example)}
              className="rounded-lg border border-slate-600 bg-slate-700/30 px-4 py-2 text-left text-sm text-slate-300 transition-all hover:border-slate-500 hover:bg-slate-700/50"
            >
              {example}
            </button>
          ))}
        </div>
      </div>

      {/* Chat Messages */}
      <div className="space-y-4 max-h-96 overflow-y-auto">
        {messages.length === 0 && (
          <div className="rounded-xl border border-slate-700/50 bg-slate-800/30 p-8 text-center">
            <p className="text-slate-400">No messages yet. Ask a question about your flight data.</p>
          </div>
        )}

        {messages.map(message => (
          <div key={message.id} className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-lg rounded-lg px-4 py-3 ${
                message.type === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-800 border border-slate-700/50 text-slate-100'
              }`}
            >
              {message.result ? (
                <ResponseCard result={message.result} />
              ) : (
                <p className="text-sm">{message.content}</p>
              )}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="rounded-lg bg-slate-800 border border-slate-700/50 px-4 py-3">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 animate-bounce rounded-full bg-blue-400" />
                <div className="h-2 w-2 animate-bounce rounded-full bg-blue-400" style={{ animationDelay: '0.2s' }} />
                <div className="h-2 w-2 animate-bounce rounded-full bg-blue-400" style={{ animationDelay: '0.4s' }} />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Form */}
      <form onSubmit={handleSubmit} className="flex gap-2">
        <Input
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Ask about your flight data..."
          disabled={isLoading}
          className="bg-slate-800 border-slate-700 text-white placeholder:text-slate-500"
        />
        <Button type="submit" disabled={isLoading || !input.trim()} size="icon">
          <Send className="h-4 w-4" />
        </Button>
      </form>
    </div>
  );
}

interface ResponseCardProps {
  result: any;
}

function ResponseCard({ result }: ResponseCardProps) {
  return (
    <div className="space-y-3">
      <div className="text-sm font-semibold text-blue-100">{result.answer}</div>

      {result.confidence_score !== undefined && (
        <div className="space-y-1">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-300">Confidence Score</span>
            <span className="font-semibold text-green-400">{(result.confidence_score * 100).toFixed(0)}%</span>
          </div>
          <div className="h-2 w-full rounded-full bg-slate-700">
            <div
              className="h-full rounded-full bg-gradient-to-r from-green-500 to-blue-500 transition-all"
              style={{ width: `${result.confidence_score * 100}%` }}
            />
          </div>
        </div>
      )}

      {result.data_source && (
        <div className="text-xs text-slate-300">
          <span className="font-semibold text-slate-200">Source:</span> {result.data_source}
        </div>
      )}

      {result.anomalies && result.anomalies.length > 0 && (
        <Alert variant="destructive" className="mt-2 py-2">
          <AlertCircle className="h-3 w-3" />
          <AlertDescription className="text-xs">
            {result.anomalies.length} anomalies detected
          </AlertDescription>
        </Alert>
      )}

      {result.validation_passed && (
        <div className="flex items-center gap-1 text-xs text-green-400">
          <CheckCircle2 className="h-3 w-3" />
          <span>Validated against aviation standards</span>
        </div>
      )}
    </div>
  );
}
