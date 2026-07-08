'use client';

import { useState, useRef, useEffect } from 'react';
import { FlightAnalyticsContainer } from '@/components/flight-analytics-container';
import { CSVUploader } from '@/components/csv-uploader';
import { ChatInterface } from '@/components/chat-interface';
import { FlightSummary } from '@/components/flight-summary';
import { Button } from '@/components/ui/button';
import { ChevronDown } from 'lucide-react';

export default function Home() {
  const [flightData, setFlightData] = useState<any>(null);
  const [isAnalytics, setIsAnalytics] = useState(false);
  const chatRef = useRef<HTMLDivElement>(null);

  const handleCSVUpload = (data: any) => {
    setFlightData(data);
    setIsAnalytics(true);
    setTimeout(() => {
      chatRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, 300);
  };

  const handleNewUpload = () => {
    setFlightData(null);
    setIsAnalytics(false);
  };

  if (!flightData) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        {/* Header */}
        <header className="border-b border-slate-700/50 bg-slate-900/50 backdrop-blur-sm">
          <div className="mx-auto max-w-7xl px-6 py-8">
            <div className="flex flex-col gap-2">
              <h1 className="text-4xl font-bold text-white">Flight Analytics AI</h1>
              <p className="text-slate-400">
                Natural Language Flight Data Analysis with Anti-Hallucination Validation
              </p>
            </div>
          </div>
        </header>

        {/* Hero Section */}
        <div className="mx-auto max-w-7xl px-6 py-20">
          <div className="grid gap-12 lg:grid-cols-2 lg:gap-16">
            {/* Left side - Features */}
            <div className="flex flex-col justify-center gap-8">
              <div>
                <h2 className="mb-4 text-3xl font-bold text-white">
                  Ask Questions About Your Flight Data
                </h2>
                <p className="text-lg text-slate-300">
                  Upload your flight CSV and get precise answers with full transparency. Our multi-layer validation ensures every response is grounded in actual data.
                </p>
              </div>

              <div className="space-y-4">
                <div className="rounded-lg border border-slate-700/50 bg-slate-800/30 p-4">
                  <h3 className="mb-2 font-semibold text-emerald-400">Natural Questions</h3>
                  <p className="text-sm text-slate-300">
                    "What was the duration of the taxi?" "Maximum IAS during cruise?" "Any abnormal climb?"
                  </p>
                </div>

                <div className="rounded-lg border border-slate-700/50 bg-slate-800/30 p-4">
                  <h3 className="mb-2 font-semibold text-blue-400">Confidence Scoring</h3>
                  <p className="text-sm text-slate-300">
                    Every answer includes confidence level based on data availability and validation passes.
                  </p>
                </div>

                <div className="rounded-lg border border-slate-700/50 bg-slate-800/30 p-4">
                  <h3 className="mb-2 font-semibold text-violet-400">Full Traceability</h3>
                  <p className="text-sm text-slate-300">
                    See exactly which data points were used, methodology, and anomalies detected.
                  </p>
                </div>

                <div className="rounded-lg border border-slate-700/50 bg-slate-800/30 p-4">
                  <h3 className="mb-2 font-semibold text-orange-400">Aviation Standards</h3>
                  <p className="text-sm text-slate-300">
                    Automatic anomaly detection against aviation manual ranges and procedures.
                  </p>
                </div>
              </div>
            </div>

            {/* Right side - Upload */}
            <div className="flex items-center">
              <CSVUploader onUpload={handleCSVUpload} />
            </div>
          </div>
        </div>

        {/* Scroll indicator */}
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 animate-bounce text-slate-400">
          <ChevronDown size={24} />
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Header with Navigation */}
      <header className="border-b border-slate-700/50 bg-slate-900/50 backdrop-blur-sm sticky top-0 z-40">
        <div className="mx-auto max-w-7xl px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-white">Flight Analytics</h1>
              <p className="text-sm text-slate-400">{flightData?.filename}</p>
            </div>
            <Button variant="outline" onClick={handleNewUpload} size="sm">
              Upload New Flight
            </Button>
          </div>
        </div>
      </header>

      {/* Analytics Container */}
      <div className="mx-auto max-w-7xl px-6 py-8">
        <FlightAnalyticsContainer flightData={flightData}>
          {/* Flight Summary Cards */}
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            <FlightSummary flightData={flightData} />
          </div>

          {/* Chat Interface */}
          <div ref={chatRef} className="mt-12 scroll-mt-24">
            <ChatInterface flightData={flightData} />
          </div>
        </FlightAnalyticsContainer>
      </div>
    </main>
  );
}
