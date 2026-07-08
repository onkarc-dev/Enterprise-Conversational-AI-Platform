'use client';

import { ReactNode } from 'react';

interface FlightAnalyticsContainerProps {
  flightData: any;
  children: ReactNode;
}

export function FlightAnalyticsContainer({
  flightData,
  children,
}: FlightAnalyticsContainerProps) {
  return (
    <div className="space-y-8">
      {/* Summary Section */}
      <div>
        <h2 className="mb-6 text-2xl font-bold text-white">Flight Overview</h2>
        {children}
      </div>
    </div>
  );
}
