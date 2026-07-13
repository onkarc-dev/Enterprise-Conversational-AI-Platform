'use client';

import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Clock, Gauge, TrendingUp, AlertTriangle } from 'lucide-react';
import { getFlightPhases, extractMetrics } from '@/lib/flight-parser';

interface FlightSummaryProps {
  flightData: any;
}

export function FlightSummary({ flightData }: FlightSummaryProps) {
  const phases = getFlightPhases(flightData.data);
  const overallMetrics = extractMetrics(flightData.data);
  const maxAltitude = overallMetrics?.altitude?.max;
  const maxIas = overallMetrics?.ias?.max;
  const avgIas = overallMetrics?.ias?.avg;

  return (
    <>
      <Card className="border-slate-700/50 bg-slate-800/50 backdrop-blur-sm">
        <div className="flex items-start justify-between p-6">
          <div>
            <p className="text-sm font-medium text-slate-400">Flight Duration</p>
            <p className="mt-2 text-3xl font-bold text-white">
              {(flightData.duration_seconds / 60).toFixed(1)}m
            </p>
            <p className="mt-1 text-xs text-slate-500">{flightData.totalRows} data points</p>
          </div>
          <Clock className="h-8 w-8 text-blue-400" />
        </div>
      </Card>

      <Card className="border-slate-700/50 bg-slate-800/50 backdrop-blur-sm">
        <div className="flex items-start justify-between p-6">
          <div>
            <p className="text-sm font-medium text-slate-400">Max Altitude</p>
            <p className="mt-2 text-3xl font-bold text-white">
              {maxAltitude !== undefined ? maxAltitude.toFixed(0) : '-'} ft
            </p>
            <p className="mt-1 text-xs text-slate-500">
              {maxAltitude !== undefined ? `FL${(maxAltitude / 100).toFixed(0)}` : 'FL-'}
            </p>
          </div>
          <TrendingUp className="h-8 w-8 text-emerald-400" />
        </div>
      </Card>

      <Card className="border-slate-700/50 bg-slate-800/50 backdrop-blur-sm">
        <div className="flex items-start justify-between p-6">
          <div>
            <p className="text-sm font-medium text-slate-400">Max Airspeed</p>
            <p className="mt-2 text-3xl font-bold text-white">
              {maxIas !== undefined ? maxIas.toFixed(1) : '-'} kts
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Avg: {avgIas !== undefined ? avgIas.toFixed(1) : '-'} kts
            </p>
          </div>
          <Gauge className="h-8 w-8 text-violet-400" />
        </div>
      </Card>

      <Card className="border-slate-700/50 bg-slate-800/50 backdrop-blur-sm md:col-span-2 lg:col-span-3">
        <div className="p-6">
          <p className="text-sm font-medium text-slate-400 mb-4">Flight Phases</p>
          <div className="flex flex-wrap gap-2">
            {phases.length > 0 ? (
              phases.map(phase => (
                <Badge key={phase} variant="secondary" className="bg-slate-700/50 text-slate-200">
                  {phase}
                </Badge>
              ))
            ) : (
              <span className="text-sm text-slate-400">No phases detected</span>
            )}
          </div>
        </div>
      </Card>

      {overallMetrics?.g_load && (
        <Card className="border-slate-700/50 bg-slate-800/50 backdrop-blur-sm">
          <div className="flex items-start justify-between p-6">
            <div>
              <p className="text-sm font-medium text-slate-400">Max G-Load</p>
              <p className="mt-2 text-3xl font-bold text-white">
                {overallMetrics.g_load.max.toFixed(2)}g
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Avg: {overallMetrics.g_load.avg.toFixed(2)}g
              </p>
            </div>
            {overallMetrics.g_load.max > 2.5 ? (
              <AlertTriangle className="h-8 w-8 text-orange-400" />
            ) : (
              <AlertTriangle className="h-8 w-8 text-slate-600" />
            )}
          </div>
        </Card>
      )}
    </>
  );
}
