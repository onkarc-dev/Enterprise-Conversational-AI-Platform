'use client';

import { useState } from 'react';
import { Upload, AlertCircle, CheckCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { uploadCSV } from '@/lib/query-processor';

interface CSVUploaderProps {
  onUpload: (data: any) => void;
}

export function CSVUploader({ onUpload }: CSVUploaderProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleFile = async (file: File) => {
    if (!file.name.endsWith('.csv')) {
      setError('Please upload a CSV file');
      return;
    }

    setIsLoading(true);
    setError(null);
    setSuccess(false);

    try {
      const result = await uploadCSV(file);
      
      if (!result.success) {
        setError(result.error || 'Failed to upload CSV');
        setIsLoading(false);
        return;
      }

      setSuccess(true);
      onUpload(result.overview);
      
      // Auto-clear success message after 3 seconds
      setTimeout(() => setSuccess(false), 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to upload CSV file');
      setIsLoading(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  return (
    <div className="w-full max-w-md">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`relative rounded-xl border-2 border-dashed p-8 text-center transition-all ${
          isDragging
            ? 'border-blue-400 bg-blue-500/10'
            : 'border-slate-600 bg-slate-800/50 hover:border-slate-500'
        }`}
      >
        {isLoading ? (
          <div className="space-y-4">
            <div className="flex justify-center">
              <div className="h-12 w-12 animate-spin rounded-full border-4 border-slate-600 border-t-blue-400" />
            </div>
            <p className="text-slate-300">Parsing flight data...</p>
          </div>
        ) : (
          <>
            <div className="mb-4 flex justify-center">
              <Upload className="h-12 w-12 text-slate-400" />
            </div>
            <h3 className="mb-2 text-xl font-semibold text-white">Upload Flight CSV</h3>
            <p className="mb-6 text-sm text-slate-400">
              Drag and drop your flight data CSV file here, or click to select
            </p>
            <label>
              <input
                type="file"
                accept=".csv"
                onChange={handleInputChange}
                className="hidden"
              />
              <Button asChild className="cursor-pointer">
                <span>Select File</span>
              </Button>
            </label>
          </>
        )}
      </div>

      {error && (
        <Alert variant="destructive" className="mt-4">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {success && (
        <Alert className="mt-4 border-green-600 bg-green-500/10">
          <CheckCircle2 className="h-4 w-4 text-green-500" />
          <AlertDescription className="text-green-400">
            Flight data uploaded successfully! You can now ask questions about your flight.
          </AlertDescription>
        </Alert>
      )}

      <div className="mt-6 space-y-2 text-sm text-slate-400">
        <p className="font-semibold text-slate-300">Expected CSV Columns:</p>
        <ul className="list-inside space-y-1 text-xs">
          <li>• timestamp, time_seconds, altitude_ft, ias_knots</li>
          <li>• vertical_speed_fpm, heading, pitch_angle, bank_angle</li>
          <li>• normal_acceleration_g, engine_thrust_percent, gear_position</li>
          <li>• flaps_setting (optional columns will auto-detect)</li>
        </ul>
      </div>
    </div>
  );
}
