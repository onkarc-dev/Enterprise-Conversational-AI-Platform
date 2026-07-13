import pandas as pd
import numpy as np
import os
from math import radians, sin, cos, sqrt, atan2


class DynamicFlightCalculator:

    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.df = None

    # ====================================== LOAD DATA ====================================================== #

    def load_data(self):
        print("Loading CSV...")
        self.df = pd.read_csv(self.csv_path, sep=None, engine="python")
        self.df.columns = self.df.columns.str.strip()
        self.df = self.df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)


        # Create timestamp if not already created
        if 'timestamp' not in self.df.columns:
            # Try to create from index or use sequential timestamps
            if self.df.index.name:
                self.df['timestamp'] = pd.to_datetime(self.df.index, errors='coerce')
            else:
                # Create sequential timestamps starting from a base time
                base_time = pd.Timestamp.now()
                self.df['timestamp'] = base_time + pd.to_timedelta(self.df.index, unit='s')

        print("\n===== CSV COLUMNS =====")
        print(self.df.columns.tolist())
        print("=======================\n")
        
        # Check if Phase column already exists (from rule_labelled.csv)
        if 'Phase' in self.df.columns:
            print("Note: Phase column found in CSV. Will use existing phases.")
            # Convert Phase to uppercase for consistency
            self.df['Phase'] = self.df['Phase'].str.upper().str.strip()

        # Ensure timestamp column is datetime
        if 'timestamp' in self.df.columns:
            self.df['timestamp'] = pd.to_datetime(self.df['timestamp'], errors='coerce')

        # Coerce commonly used numeric columns to numeric types
        for col in ['AltMSL', 'IAS', 'VSpd', 'Pitch', 'GndSpd', 'Lat', 'Lon']:
            if col in self.df.columns:
                self.df[col] = pd.to_numeric(self.df[col], errors='coerce')




    # ============================ PHASE DETECTION ====================================================== #


    # ============================ SEGMENT ID ====================================================== #

    def create_segments(self):

        if 'Phase' not in self.df.columns:
        raise ValueError(
            f"'Phase' column not found.\nAvailable columns:\n{self.df.columns.tolist()}"
        )

        self.df['segment_id'] = (
        self.df['Phase'] != self.df['Phase'].shift()
    ).cumsum()

        print("Segment IDs Created")

    # ============================ SEGMENT HANDLING ====================================================== #

    def get_phase_segments(self, phase: str):
        # Filter by Phase column (created by detect_phases)
        if 'Phase' not in self.df.columns:
            return []
        
        phase = phase.upper() # to normalize input and match dataframe
        phase_df = self.df[self.df['Phase'] == phase].copy()

        if phase_df.empty:
            return []

        # Use existing segment_id if available, otherwise create one
        if 'segment_id' not in phase_df.columns: #checking if segment_id column exists
            phase_df['segment_id'] = (phase_df.index.to_series().diff() != 1).cumsum() #row index to series ->computes diff -> check where continuity breaks -> cumsum to assign segment ids 

        return [seg for _, seg in phase_df.groupby('segment_id')] #Groups rows by segment_id and extracts each group as a separate DataFrame.
 
    # ============================ PHASE NUMBERING ====================================================== #

    def add_phase_numbering(self):
        df = self.df.copy()
        df['Phase_Numbered'] = ""

        phase_counters = {}

        for seg_id, seg_df in df.groupby('segment_id'): #Iterates over each continuous segment
            phase = seg_df['Phase'].iloc[0] #  every row has same phase and reads from first row

            if phase not in phase_counters: #keeps count of each phase
                phase_counters[phase] = 1
            else:
                phase_counters[phase] += 1

            numbered = f"{phase}-{phase_counters[phase]}"
            df.loc[seg_df.index, 'Phase_Numbered'] = numbered #Assigns the numbered phase to all rows in that segment

        self.df = df
        print("Phase Numbering Added")
    
    # ================= DISTANCE ================= #

    def get_phase_distance(self, phase):
        df = self.df

        phase_df = df[df["Phase"] == phase][["Lat", "Lon"]].dropna() #keeps Lat n Lon after filtering of rows

        if len(phase_df) < 2:
            return 0.0

        distance = 0.0

        for i in range(len(phase_df) - 1): #Iterates over consecutive GPS points
            lat1, lon1 = phase_df.iloc[i]
            lat2, lon2 = phase_df.iloc[i + 1] #Extracts two consecutive latitude–longitude pairs
            distance += self.haversine(lat1, lon1, lat2, lon2) 

        return round(distance, 2)  # return round(distance, 2)


    def get_total_distance(self):
        df = self.df[["Lat", "Lon"]].dropna()
        distance = 0.0
        for i in range(len(df) - 1):
            lat1, lon1 = df.iloc[i]
            lat2, lon2 = df.iloc[i + 1]
            distance += self.haversine(lat1, lon1, lat2, lon2)
        return round(distance, 2)

    # ============================ USER QUERY PARSER ====================================================== #

    # ============================ OVERVIEW METHODS ====================================================== #

    def get_flight_overview(self):
        """Returns comprehensive overview of the entire flight with all phases and metrics."""
        if self.df is None:
            return {"error": "No flight data available. Please load data first."}

        info = {}

        # Flight timing
        if 'timestamp' in self.df.columns:
            flight_start = self.df['timestamp'].iloc[0]
            flight_end = self.df['timestamp'].iloc[-1]
            total_duration = flight_end - flight_start
            info['flight_start'] = str(flight_start)
            info['flight_end'] = str(flight_end)
            info['total_duration_seconds'] = total_duration.total_seconds()
            info['total_duration_formatted'] = self.format_duration(total_duration)

        # Altitude statistics
        if 'AltMSL' in self.df.columns:
            alt_data = self.df['AltMSL'].dropna()
            if not alt_data.empty:
                info['altitude'] = {
                    'min': float(alt_data.min()),
                    'max': float(alt_data.max()),
                    'avg': float(alt_data.mean()),
                    'unit': 'ft'
                }

        # IAS statistics
        if 'IAS' in self.df.columns:
            ias_data = self.df['IAS'].dropna()
            if not ias_data.empty:
                info['ias'] = {
                    'min': float(ias_data.min()),
                    'max': float(ias_data.max()),
                    'avg': float(ias_data.mean()),
                    'unit': 'knots'
                }

        # Ground speed statistics
        if 'GndSpd' in self.df.columns:
            gnd_data = self.df['GndSpd'].dropna()
            if not gnd_data.empty:
                info['gnd_speed'] = {
                    'min': float(gnd_data.min()),
                    'max': float(gnd_data.max()),
                    'avg': float(gnd_data.mean()),
                    'unit': 'knots'
                }

        # Vertical speed statistics
        if 'VSpd' in self.df.columns:
            vspd_data = self.df['VSpd'].dropna()
            if not vspd_data.empty:
                # Vertical speed in feet per minute
                info['vspd'] = {
                    'min': float(vspd_data.min()),
                    'max': float(vspd_data.max()),
                    'avg': float(vspd_data.mean()),
                    'unit': 'fpm'
                }

        # Phase breakdown by segment
        phase_list = []
        if 'segment_id' in self.df.columns:
            for seg_id, seg_data in self.df.groupby('segment_id', sort=False):
                seg_info = {'segment_id': int(seg_id)}
                phase = None
                if 'Phase' in seg_data.columns:
                    phase = seg_data['Phase'].iloc[0]
                if pd.isna(phase) or phase is None:
                    prev_phase = self.df[self.df['segment_id'] == (seg_id - 1)]['Phase'].dropna()
                    next_phase = self.df[self.df['segment_id'] == (seg_id + 1)]['Phase'].dropna()
                    if not prev_phase.empty:
                        phase = prev_phase.iloc[0]
                    elif not next_phase.empty:
                        phase = next_phase.iloc[0]
                    else:
                        phase = "UNKNOWN"
                seg_info['phase'] = phase

                if 'timestamp' in seg_data.columns and len(seg_data) > 1:
                    duration = seg_data['timestamp'].iloc[-1] - seg_data['timestamp'].iloc[0]
                    seg_info['duration_seconds'] = duration.total_seconds()
                    seg_info['duration_formatted'] = self.format_duration(duration)
                else:
                    seg_info['duration_seconds'] = len(seg_data)
                    seg_info['duration_formatted'] = f"{len(seg_data)} rows"

                if 'AltMSL' in seg_data.columns:
                    alt_clean = seg_data['AltMSL'].dropna()
                    if not alt_clean.empty:
                        seg_info['alt_min'] = float(alt_clean.min())
                        seg_info['alt_max'] = float(alt_clean.max())

                phase_list.append(seg_info)
        else:
            phase_counts = self.df['Phase'].value_counts()
            for phase, count in phase_counts.items():
                phase_list.append({'phase': phase, 'count': int(count)})

        info['phase_breakdown'] = phase_list
        return info

    def get_numbered_phase_summary(self, phase: str, segment_num: int):
        """Returns summary of a specific numbered phase segment (e.g., TAXI-1, CRUISE-2)."""
        phase = phase.upper()
        
        if 'Phase' not in self.df.columns:
            return f"Phase column not found in flight data."
        
        segments = self.get_phase_segments(phase)
        if not segments:
            return f"No segments found for {phase} phase."
        
        # Check if segment number is valid
        if segment_num < 1 or segment_num > len(segments):
            return f"Invalid segment number {segment_num}. {phase} has {len(segments)} segment(s)."
        
        # Get the specific segment
        target_seg = segments[segment_num - 1]
        
        # Build summary
        output = f"\n{phase} - Segment {segment_num} Summary\n"
        output += "="*70 + "\n\n"
        
        # Duration
        if 'timestamp' in target_seg.columns and len(target_seg) > 1:
            seg_start = target_seg['timestamp'].iloc[0]
            seg_end = target_seg['timestamp'].iloc[-1]
            duration = seg_end - seg_start
            output += f"Duration: {self.format_duration(duration)}\n"
        
        # Altitude metrics
        if 'AltMSL' in target_seg.columns:
            alt_data = target_seg['AltMSL'].dropna()
            if not alt_data.empty:
                output += f"Altitude: Start={alt_data.iloc[0]:>7.0f} ft │ End={alt_data.iloc[-1]:>7.0f} ft │ Min={alt_data.min():>7.0f} ft │ Max={alt_data.max():>7.0f} ft\n"
        
        # IAS metrics
        if 'IAS' in target_seg.columns:
            ias_data = target_seg['IAS'].dropna()
            if not ias_data.empty:
                output += f"IAS:      Start={ias_data.iloc[0]:>7.1f} kt │ End={ias_data.iloc[-1]:>7.1f} kt │ Min={ias_data.min():>7.1f} kt │ Max={ias_data.max():>7.1f} kt\n"
        
        # Vertical Speed metrics
        if 'VSpd' in target_seg.columns:
            vspd_data = target_seg['VSpd'].dropna()
            if not vspd_data.empty:
                output += f"V-Speed:  Min={vspd_data.min():>7.1f} ft/m │ Max={vspd_data.max():>7.1f} ft/m │ Avg={vspd_data.mean():>7.1f} ft/m\n"
        
        # Pitch metrics
        if 'Pitch' in target_seg.columns:
            pitch_data = target_seg['Pitch'].dropna()
            if not pitch_data.empty:
                abnormal = target_seg[(target_seg['Pitch'] > 20) | (target_seg['Pitch'] < -10)]
                abnormal_str = f"  │ ABNORMAL: {len(abnormal)} points" if not abnormal.empty else ""
                output += f"Pitch:    Min={pitch_data.min():>7.2f}° │ Max={pitch_data.max():>7.2f}° │ Avg={pitch_data.mean():>7.2f}°{abnormal_str}\n"
        
        output += "\n"
        return output

    def get_phase_overview(self, phase: str):
        """Returns structured overview of a specific phase with all metrics."""
        phase = phase.upper()
        
        if 'Phase' not in self.df.columns:
            return {"error": "Phase column not found. Please run detect_phases() first."}
        
        segments = self.get_phase_segments(phase)
        if not segments:
            available_phases = self.df['Phase'].value_counts().index.tolist()
            return {"error": f"No data found for {phase} phase. Available phases: {', '.join(available_phases)}", "available_phases": available_phases}
        
        phase_df = self.df[self.df['Phase'] == phase]

        # Basic timing info
        overview = {"phase": phase, "total_segments": len(segments)}

        # Calculate total_phase_duration by summing durations of each continuous segment
        total_phase_duration = pd.Timedelta(0)
        phase_start = None
        phase_end = None
        if segments:
            for seg in segments:
                if 'timestamp' in seg.columns and len(seg) > 1:
                    seg_start = seg['timestamp'].iloc[0]
                    seg_end = seg['timestamp'].iloc[-1]
                    total_phase_duration += (seg_end - seg_start)
                    if phase_start is None or seg_start < phase_start:
                        phase_start = seg_start
                    if phase_end is None or seg_end > phase_end:
                        phase_end = seg_end

        if phase_start is not None and phase_end is not None:
            overview['phase_start'] = str(phase_start)
            overview['phase_end'] = str(phase_end)
            overview['duration_seconds'] = total_phase_duration.total_seconds()
            overview['duration_formatted'] = self.format_duration(total_phase_duration)
        
        # Overall metrics
        metrics = {}
        
        if 'AltMSL' in phase_df.columns:
            alt_data = phase_df['AltMSL'].dropna()
            if not alt_data.empty:
                metrics['altitude'] = {
                    'min': float(alt_data.min()),
                    'max': float(alt_data.max()),
                    'avg': float(alt_data.mean()),
                    'unit': 'ft'
                }
        
        if 'IAS' in phase_df.columns:
            ias_data = phase_df['IAS'].dropna()
            if not ias_data.empty:
                metrics['ias'] = {
                    'min': float(ias_data.min()),
                    'max': float(ias_data.max()),
                    'avg': float(ias_data.mean()),
                    'unit': 'knots'
                }
        
        if 'VSpd' in phase_df.columns:
            vspd_data = phase_df['VSpd'].dropna()
            if not vspd_data.empty:
                metrics['vspd'] = {
                    'min': float(vspd_data.min()),
                    'max': float(vspd_data.max()),
                    'avg': float(vspd_data.mean()),
                    'unit': 'ft/min'
                }
        
        if 'Pitch' in phase_df.columns:
            pitch_data = phase_df['Pitch'].dropna()
            if not pitch_data.empty:
                metrics['pitch'] = {
                    'min': float(pitch_data.min()),
                    'max': float(pitch_data.max()),
                    'avg': float(pitch_data.mean()),
                    'unit': 'degrees'
                }
        
        if 'GndSpd' in phase_df.columns:
            gnd_data = phase_df['GndSpd'].dropna()
            if not gnd_data.empty:
                metrics['gnd_speed'] = {
                    'min': float(gnd_data.min()),
                    'max': float(gnd_data.max()),
                    'avg': float(gnd_data.mean()),
                    'unit': 'knots'
                }
        
        overview['metrics'] = metrics
        
        # Per-segment data
        segment_details = []
        for idx, seg in enumerate(segments, 1):
            seg_info = {"segment": idx}
            
            if 'timestamp' in seg.columns and len(seg) > 1:
                seg_start = seg['timestamp'].iloc[0]
                seg_end = seg['timestamp'].iloc[-1]
                duration = seg_end - seg_start
                seg_info['duration_seconds'] = duration.total_seconds()
                seg_info['duration_formatted'] = self.format_duration(duration)
            
            seg_metrics = {}
            if 'AltMSL' in seg.columns:
                alt_data = seg['AltMSL'].dropna()
                if not alt_data.empty:
                    seg_metrics['altitude_start'] = float(seg['AltMSL'].iloc[0])
                    seg_metrics['altitude_end'] = float(seg['AltMSL'].iloc[-1])
                    seg_metrics['altitude_min'] = float(alt_data.min())
                    seg_metrics['altitude_max'] = float(alt_data.max())
            
            if 'IAS' in seg.columns:
                ias_data = seg['IAS'].dropna()
                if not ias_data.empty:
                    seg_metrics['ias_start'] = float(seg['IAS'].iloc[0])
                    seg_metrics['ias_end'] = float(ias_data.iloc[-1])
                    seg_metrics['ias_min'] = float(ias_data.min())
                    seg_metrics['ias_max'] = float(ias_data.max())
            
            seg_info['metrics'] = seg_metrics
            segment_details.append(seg_info)
        
        overview['segment_details'] = segment_details
        return overview

    def get_segment_summary(self, segment):
        # This function returns a summary for a specific segment.
        segment_summary = ""

        # Duration
        if 'timestamp' in segment.columns and len(segment) > 1:
            seg_start = segment['timestamp'].iloc[0]
            seg_end = segment['timestamp'].iloc[-1]
            duration = seg_end - seg_start
            dur_str = self.format_duration(duration)
            segment_summary += f"  Duration: {dur_str:>12}\n"
        
        # Altitude
        if 'AltMSL' in segment.columns:
            alt_data = segment['AltMSL'].dropna()
            if not alt_data.empty:
                segment_summary += f"  Altitude: Start={segment['AltMSL'].iloc[0]:>7.0f} ft │ End={segment['AltMSL'].iloc[-1]:>7.0f} ft │ Min={alt_data.min():>7.0f} ft │ Max={alt_data.max():>7.0f} ft\n"
        
        # IAS
        if 'IAS' in segment.columns:
            ias_data = segment['IAS'].dropna()
            if not ias_data.empty:
                segment_summary += f"   IAS:      Start={segment['IAS'].iloc[0]:>7.1f} kt │ End={ias_data.iloc[-1]:>7.1f} kt │ Min={ias_data.min():>7.1f} kt │ Max={ias_data.max():>7.1f} kt\n"
        
        # Vertical Speed
        if 'VSpd' in segment.columns:
            vspd_data = segment['VSpd'].dropna()
            if not vspd_data.empty:
                segment_summary += f"  V-Speed:  Min={vspd_data.min():>7.1f} ft/m │ Max={vspd_data.max():>7.1f} ft/m │ Avg={vspd_data.mean():>7.1f} ft/m\n"
        
        # Pitch
        if 'Pitch' in segment.columns:
            pitch_data = segment['Pitch'].dropna()
            if not pitch_data.empty:
                abnormal = segment[(segment['Pitch'] > 20) | (segment['Pitch'] < -10)]
                abnormal_str = f"  ABNORMAL: {len(abnormal)} points" if not abnormal.empty else ""
                segment_summary += f"  Pitch:    Min={pitch_data.min():>7.2f}° │ Max={pitch_data.max():>7.2f}° │ Avg={pitch_data.mean():>7.2f}°{abnormal_str}\n"
        
        return segment_summary

    def get_detailed_phase_summary(self, phase: str) -> str:
        """
        Returns a detailed narrative summary of a phase with duration, altitude, speed, and subphases.
        Format: "The [phase] phase lasted [duration], during which the aircraft [climbed/descended] 
        from [alt_start] to [alt_end] feet and [accelerated/decelerated] from [ias_start] to [ias_end] knots. 
        This phase consisted of [X] subphases: [subphase list]."
        """
        phase = phase.upper()
        
        if 'Phase' not in self.df.columns:
            return ""
        
        phase_df = self.df[self.df['Phase'] == phase]
        if phase_df.empty:
            return ""
        
        # Get segments for this phase
        segments = self.get_phase_segments(phase)
        if not segments:
            return ""
        
        # === DURATION (with full formatting like "1 minute and 9 seconds") ===
        total_duration = pd.Timedelta(0)
        for seg in segments:
            if 'timestamp' in seg.columns and len(seg) > 1:
                seg_start = seg['timestamp'].iloc[0]
                seg_end = seg['timestamp'].iloc[-1]
                total_duration += (seg_end - seg_start)
        
        # Format duration in full format
        total_seconds = int(total_duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        
        duration_parts = []
        if hours > 0:
            duration_parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
        if minutes > 0:
            duration_parts.append(f"{minutes} minute{'s' if minutes > 1 else ''}")
        if secs > 0 or not duration_parts:
            duration_parts.append(f"{secs} second{'s' if secs != 1 else ''}")
        
        if len(duration_parts) == 1:
            duration_str = duration_parts[0]
        elif len(duration_parts) == 2:
            duration_str = f"{duration_parts[0]} and {duration_parts[1]}"
        else:
            duration_str = f"{duration_parts[0]}, {duration_parts[1]}, and {duration_parts[2]}"
        
        # === ALTITUDE ===
        alt_start = None
        alt_end = None
        if 'AltMSL' in phase_df.columns:
            alt_data = phase_df['AltMSL'].dropna()
            if not alt_data.empty:
                alt_start = float(alt_data.iloc[0])
                alt_end = float(alt_data.iloc[-1])
        
        # Determine altitude action (climb, descend, maintain)
        altitude_action = ""
        if alt_start is not None and alt_end is not None:
            if alt_end > alt_start:
                altitude_action = f"climbed from {int(alt_start)} to {int(alt_end)} feet"
            elif alt_end < alt_start:
                altitude_action = f"descended from {int(alt_start)} to {int(alt_end)} feet"
            else:
                altitude_action = f"maintained altitude at {int(alt_start)} feet"
        
        # === SPEED (IAS) ===
        ias_start = None
        ias_end = None
        if 'IAS' in phase_df.columns:
            ias_data = phase_df['IAS'].dropna()
            if not ias_data.empty:
                ias_start = float(ias_data.iloc[0])
                ias_end = float(ias_data.iloc[-1])
        
        # Determine speed action (accelerated, decelerated, maintained)
        speed_action = ""
        if ias_start is not None and ias_end is not None:
            if ias_end > ias_start + 1:  # Allow 1 knot margin for noise
                speed_action = f"and accelerated from {ias_start:.1f} to {ias_end:.1f} knots"
            elif ias_end < ias_start - 1:
                speed_action = f"and decelerated from {ias_start:.1f} to {ias_end:.1f} knots"
            else:
                speed_action = f"and maintained airspeed around {ias_start:.1f} knots"
        
        # === SUBPHASES ===
        subphases_list = []
        if 'Sub Phase' in phase_df.columns:
            subphases = phase_df['Sub Phase'].dropna().unique()
            subphases_list = sorted([str(sp).strip() for sp in subphases if str(sp).strip()])
        
        # Build the narrative
        summary = f"The {phase.lower()} phase lasted {duration_str}"
        
        if altitude_action or speed_action:
            summary += f", during which the aircraft {altitude_action} {speed_action}"
        
        summary += "."
        
        # Add subphases with proper capitalization
        if subphases_list:
            # Capitalize each subphase name
            capitalized_subphases = [sp.title() for sp in subphases_list]
            
            if len(capitalized_subphases) == 1:
                summary += f" This phase consisted of one subphase: {capitalized_subphases[0]}."
            else:
                subphases_str = ", ".join(capitalized_subphases[:-1])
                summary += f" This phase consisted of {len(capitalized_subphases)} subphases: {subphases_str}, and {capitalized_subphases[-1]}."
        
        return summary

    # ============================ USER QUERY PARSER ====================================================== #

    def get_subphase_overview(self):
        """Returns overview of all subphases in the flight."""
        if self.df is None or 'Sub Phase' not in self.df.columns:
            return "No subphase data available in this flight."
        subphase_df = self.df[self.df['Sub Phase'].notna()]
        if subphase_df.empty:
            return "No subphase data available in this flight."
        overview = "\n               SUBPHASE INFORMATION\n"
        overview += "═══════════════════════════════════════════════════════════════════════════════\n\n"
        overview += "  SUBPHASES DETECTED IN THIS FLIGHT:\n"
        overview += "  ─────────────────────────────────────────────────────────────────────────\n"
        subphases = sorted(subphase_df['Sub Phase'].unique())
        for subphase in subphases:
            sp_df = subphase_df[subphase_df['Sub Phase'] == subphase]
            count = len(sp_df)
            dur_str = "0s"
            if 'timestamp' in sp_df.columns and len(sp_df) > 1:
                dur = sp_df['timestamp'].iloc[-1] - sp_df['timestamp'].iloc[0]
                dur_str = f"{int(dur.total_seconds())}s" if hasattr(dur, 'total_seconds') else str(dur)
            phase = sp_df['Phase'].iloc[0] if 'Phase' in sp_df.columns else "Unknown"
            overview += f"  • {subphase:25} | Phase: {phase:10} | Duration: {dur_str:10} | Points: {count:4}\n"
            if 'AltMSL' in sp_df.columns:
                alt = sp_df['AltMSL'].dropna()
                if not alt.empty:
                    overview += f"    └─ Altitude: {alt.min():.0f} - {alt.max():.0f} ft | Avg: {alt.mean():.0f} ft\n"
            if 'IAS' in sp_df.columns:
                ias = sp_df['IAS'].dropna()
                if not ias.empty:
                    overview += f"    └─ IAS: {ias.min():.1f} - {ias.max():.1f} kt | Avg: {ias.mean():.1f} kt\n"
        overview += "\n"
        return overview

    def get_subphase_detail(self, subphase_name):
        """Returns detailed overview of a specific subphase."""
        if self.df is None or 'Sub Phase' not in self.df.columns:
            return f"No subphase data available."
        sp_df = self.df[self.df['Sub Phase'] == subphase_name]
        if sp_df.empty:
            return f"No data found for '{subphase_name}' subphase."
        count = len(sp_df)
        detail = f"\n  {subphase_name.upper()} SUBPHASE - DETAILED INFORMATION\n"
        detail += "─" * 60 + "\n"
        if 'timestamp' in sp_df.columns and len(sp_df) > 1:
            detail += f"  Duration: {self.format_duration(sp_df['timestamp'].iloc[-1] - sp_df['timestamp'].iloc[0])} | Points: {count}\n"
        if 'AltMSL' in sp_df.columns:
            alt = sp_df['AltMSL'].dropna()
            if not alt.empty:
                detail += f"  Altitude: {alt.min():.0f} - {alt.max():.0f} ft (Avg: {alt.mean():.0f} ft)\n"
        if 'IAS' in sp_df.columns:
            ias = sp_df['IAS'].dropna()
            if not ias.empty:
                detail += f"  IAS: {ias.min():.1f} - {ias.max():.1f} kt (Avg: {ias.mean():.1f} kt)\n"
        detail += "\n"
        return detail

    def get_subphase_metric(self, subphase_name, metric_type):
        """Get a specific metric for a subphase (altitude/speed/pitch)."""
        if self.df is None or 'Sub Phase' not in self.df.columns:
            return "No subphase data available in this flight."
        sp_df = self.df[self.df['Sub Phase'] == subphase_name]
        if sp_df.empty:
            return f"No data found for '{subphase_name}' subphase."

        mt = (metric_type or "avg").lower()

        # --- SPEED / IAS ---
        if mt in {"speed", "ias", "touchdown", "end", "start", "avg", "min", "max"} and 'IAS' in sp_df.columns:
            ias = sp_df['IAS'].dropna()
            if ias.empty:
                return f"No IAS data for {subphase_name}."

            # touchdown / end -> return last IAS sample
            if mt in {"touchdown", "end"}:
                val = ias.iloc[-1]
                return f"{subphase_name} IAS at touchdown: {val:.1f} kt"

            # start -> first IAS sample
            if mt == 'start':
                val = ias.iloc[0]
                return f"{subphase_name} IAS at start: {val:.1f} kt"

            # aggregate values
            if mt == 'max':
                val = ias.max(); label = 'Maximum'
            elif mt == 'min':
                val = ias.min(); label = 'Minimum'
            else:
                val = ias.mean(); label = 'Average'
            return f"{subphase_name} IAS ({label}): {val:.1f} kt (range: {ias.min():.1f} - {ias.max():.1f} kt)"

        # --- ALTITUDE ---
        if 'AltMSL' in sp_df.columns:
            alt = sp_df['AltMSL'].dropna()
            if alt.empty:
                return f"No altitude data for {subphase_name}."
            stat = mt
            if stat == "max" or stat == "maximum":
                val = alt.max(); label = "Maximum"
            elif stat == "min" or stat == "minimum":
                val = alt.min(); label = "Minimum"
            else:
                val = alt.mean(); label = "Average"
            return f"{subphase_name} altitude ({label}): {val:.0f} ft (range: {alt.min():.0f} - {alt.max():.0f} ft)"

        return f"Requested metric '{metric_type}' not available for {subphase_name}."
    def parse_query(self, query):
        q = query.lower().strip()
        
        # Extract segment number early (e.g., "taxi 1 summary" -> segment_num = 1)
        # Only treat a trailing number as an explicit numbered segment when the
        # user also asks for a 'segment', 'summary', 'overview', 'details' or
        # similar keyword. This avoids interpreting queries like 'taxi1 duration'
        # as a request for a single-segment summary — those should return
        # phase-level duration totals instead.
        segment_num = None
        import re
        seg_match = re.search(r'(?:segment\s+|taxi\s+|takeoff\s+|climb\s+|cruise\s+|descent\s+|approach\s+|landing\s+)?(\d+)', q)
        if seg_match:
            if any(k in q for k in ["segment", "summary", "overview", "details", "detail", "info"]):
                try:
                    segment_num = int(seg_match.group(1))
                except Exception:
                    segment_num = None
            else:
                segment_num = None
        
        # Direct request for structured output / phase dictionary
        phase_dict_terms = ["phase dict","phase_dict","phase dictionary","structured summary","structured output","export summary","phase summary","summary json"]
        if any(term in q for term in phase_dict_terms):
            return "phase_dict", None, None, None

        # Flight-check related queries
        check_terms = {
            'descent': ["descent initiated", "late descent", "descent initiated late" , "when did descent start" , "descent start"],
            'abrupt_transitions': ["abrupt transition", "abrupt transitions", "abrupt change", "sudden phase"],
            'climb_pitch': ["pitch during climb", "climb pitch", "pitch in climb", "pitch within sop during climb"],
            'approach_pitch': ["excessive pitch during approach", "approach pitch", "excessive pitch approach"],
            'takeoff_speed': ["speed during takeoff", "takeoff speed", "speed within limits during takeoff"],
            'descent_overspeed': ["overspeed during descent", "descent overspeed"],
            'cruise_speed_efficiency': ["speed fuel efficient", "fuel efficient speed", "cruise speed efficiency"],
            'cruise_altitude': ["cruise altitude", "was cruise altitude maintained", "cruise altitude maintained"],
            'climb_altitude_deviations': ["altitude deviations during climb", "climb altitude deviations"]
        }

        for key, phrases in check_terms.items():
            if any(p in q for p in phrases):
                return "flight_check", key, None, None

        # Generic flight checks request
        if any(x in q for x in ["flight checks", "run checks", "health check", "flight health", "check flight"]):
            return "flight_checks", None, None, None

        phase_map = {
            "taxi": "TAXI",
            "takeoff": "TAKEOFF",
            "climb": "CLIMB",
            "cruise": "CRUISE",
            "descent": "DESCENT",
            "approach": "APPROACH",
            "landing": "LANDING"
        }

        #summary or overview related queries
        overview_keywords = ["overview", "summary", "summarize", "information", "details"]
        is_overview = any(keyword in q for keyword in overview_keywords)
        
        # Check if user is asking for a numbered phase with overview (e.g., "taxi 1 summary")
        if segment_num is not None and is_overview:
            # Find which phase this numbered segment belongs to
            for phase_key, phase_value in phase_map.items():
                if phase_key in q:
                    return "phase_overview", phase_value, None, segment_num
        
        subphase_overview_terms = ["subphase", "sub phase", "sub-phase", "subphases"]
        wants_subphase_overview = is_overview and any(term in q for term in subphase_overview_terms)

        if wants_subphase_overview:
            return "subphase_info", None, None, None

        if is_overview:
            # Check if it's flight overview 
            if any(word in q for word in ["flight", "this", "entire", "whole", "complete"]):
                if "flight" in q or "this" in q:
                    return "flight_overview", None, None, None
            
            # Check for phase overview 
            for phase_key, phase_value in phase_map.items():
                if phase_key in q:
                    return "phase_overview", phase_value, None, segment_num
            
            # Default to flight overview if just overview keyword is mentioned
            return "flight_overview", None, None, None

        # ===== SUBPHASE QUERIES (e.g. "altitude of lift off", "min altitude of touchdown") ===== #
        subphase_map = {
            "lift off": "Lift Off",
            "roll for takeoff": "Roll For Takeoff",
            "landing roll": "Landing Roll",
            "flare": "Flare",
            "touch down": "Touch Down",
            "touchdown": "Touch Down",
            "low ias": "Low Ias"
        }
        metric_keywords = ["min", "max", "avg", "average", "maximum", "minimum", "highest", "lowest"]
        metric_type_words = ["altitude", "height", "pitch", "speed", "ias", "airspeed"]
        overview_kw = ["overview", "summary", "summarize", "information", "details", "info"]
        subphase_terms = ["subphase", "sub phase", "sub-phase", "lift off", "roll for takeoff", "landing roll", "flare", "touch down", "touchdown", "low ias", "takeoff roll"]

        for subphase_key, subphase_name in subphase_map.items():
            if subphase_key not in q:
                continue
            # "altitude of lift off", "pitch during flare" etc. -> subphase metric (default avg)
            if any(mt in q for mt in metric_type_words):
                # 
                # fer an explicitly parsed metric (e.g., "touchdown") if available
                metric = "avg"
                parsed = self.parse_question(q, phase_map)
                if len(parsed) == 4:
                    _, _, m, _ = parsed
                else:
                    _, _, m = parsed
                if m:
                    metric = m
                return "subphase_metric", subphase_name, metric, None
            if any(mk in q for mk in metric_keywords):
                parsed = self.parse_question(q, phase_map)
                if len(parsed) == 4:
                    intent, phase, metric, _ = parsed
                else:
                    intent, phase, metric = parsed
                if intent and metric:
                    return "subphase_metric", subphase_name, metric, None
            break

        for subphase_key, subphase_name in subphase_map.items():
            if subphase_key in q and any(kw in q for kw in overview_kw):
                return "subphase_detail", subphase_name, None, None

        # Particular subphase named without overview keyword -> return that subphase's summary only
        for subphase_key, subphase_name in subphase_map.items():
            if subphase_key in q:
                return "subphase_detail", subphase_name, None, None

        if any(term in q for term in subphase_terms):
            return "subphase_info", None, None, None

        # Allow queries asking explicitly for phases detected in this flight
        if ("phase" in q or "phases" in q) and any(k in q for k in ["what", "which", "list", "detected", "found", "present"]):
            return "phase_list", None, None, None

        # Delegate remaining parsing to helper
        result = self.parse_question(q, phase_map)
        if len(result) == 4:
            return result
        intent, phase, metric = result
        return intent, phase, metric, None

    def parse_question(self, q, phase_map):
        q = q.lower().strip()

        # ---------------- MULTI-PHASE RULES (HIGHEST PRIORITY) ---------------- #
        MULTI_RULES = [
            ({"longest", "taxi"},         "multi_duration", "TAXI", "max"),
            ({"shortest", "descent"},     "multi_duration", "DESCENT", "min"),
            ({"longest", "descent"},      "multi_duration", "DESCENT", "max"),
            ({"shortest", "taxi"},        "multi_duration", "TAXI", "min"),
            ({"flights", "long", "taxi"},"multi_duration", "TAXI", "long"),
            ({"abnormal", "climb"},       "abnormal_climb", "CLIMB", None),
        ]

        for keys, intent, phase, metric in MULTI_RULES:
            if all(k in q for k in keys):
                return intent, phase, metric
        
        # ---------------- DYNAMIC SHORTEST/LONGEST FOR ANY PHASE (NEW) ---------------- #
        # Check for 'shortest' or 'longest' keywords with any phase dynamically
        for k, v in phase_map.items():
            if k in q:
                if "shortest" in q:
                    return "multi_duration", v, "min"
                elif "longest" in q:
                    return "multi_duration", v, "max"

        # ---------------- INTENTS ---------------- #
        INTENTS = {
            "duration": {
                "how long", "duration", "time taken", "time spent",
                "elapsed time", "how much time", "length of time"
            },

            "altitude": {"altitude", "height", "level"},

            "speed": {
                "speed", "ias", "airspeed", "groundspeed", "ground speed",
                "overspeed", "touchdown", "fast", "slow", "gnd"
            },

            "pitch": {"pitch", "attitude", "nose", "angle", "rotation"},

            "distance": {"distance", "how far", "covered", "travelled", "flown"},

            "track": {"track", "path", "route", "waypoint", "coordinates", "position"},

            "routing": {"routing", "optimal", "route efficiency", "route analysis"}
        }

        intent = next(
            (i for i, kws in INTENTS.items() if any(k in q for k in kws)),
            None
        )
        speed_col = "IAS"

        # Determine speed column for ground speed vs IAS

        if any(k in q for k in ["ground", "gnd", "gs"]):
            speed_col = "GndSpd"

        # ---------------- METRICS ---------------- #
        METRICS = {
            "max": {"max", "maximum", "highest", "peak"},
            "min": {"min", "minimum", "lowest"},
            "avg": {"avg", "average", "mean", "typical", "cruise"},
            "start": {"start", "initial", "beginning", "rotation"},
            "end": {"end", "final", "landing"},
            "touchdown": {"touchdown"},
            "limit": {"overspeed", "limit", "exceed", "violate"},
            "abnormal": {"abnormal", "excessive", "unsafe", "unstable"}
        }

        metric = next(
            (m for m, kws in METRICS.items() if any(k in q for k in kws)),
            None
        )

        # Default metric for pitch
        if intent == "pitch" and metric is None:
            metric = "avg"

        # Map start/end/touchdown metrics to explicit intents if no other intent identified
        if intent is None and metric in {"start", "end", "touchdown"}:
            intent = metric

        # ---------------- PHASE ---------------- #
        phase = next(
            (v for k, v in phase_map.items() if k in q), #scans query, finds phase
            None
        )

        # ---------------- PHASE TRANSITION ---------------- #
        TRANSITION_WORDS = {
            "transition", "change", "switch", "shift",
            "begin", "start", "enter"
        }

        PARAM_WORDS = {
            "ias": {"ias", "airspeed", "speed", "ground speed", "groundspeed", "gndspd", "gs", "overspeed", "touchdown", "rotation"},
            "altitude": {"altitude", "height"},

            "time": {"time", "timestamp", "when"}
        }

        PHASE_PAIRS = {
            ("takeoff", "climb"): ("TAKEOFF", "CLIMB"),
            ("climb", "cruise"): ("CLIMB", "CRUISE"),
            ("cruise", "descent"): ("CRUISE", "DESCENT"),
            ("descent", "approach"): ("DESCENT", "APPROACH"),
            ("approach", "landing"): ("APPROACH", "LANDING")
        }

        if any(w in q for w in TRANSITION_WORDS):
            for (p1, p2), phases in PHASE_PAIRS.items():
                if p1 in q and p2 in q:
                    param = next(
                        (p for p, kws in PARAM_WORDS.items() if any(k in q for k in kws)),
                        "time"
                    )
                    return "phase_transition", phases, param

        # ---------------- POSITION ---------------- #
        POSITION_WORDS = {"where", "location", "position", "coordinates", "place"}

        if any(w in q for w in POSITION_WORDS):
            p = next((v for k, v in phase_map.items() if k in q), None)
            if p:
                return "position", p, None

        # ---------------- FALLBACK ---------------- #
        # If a standard parsing method exists on the class, call it; otherwise return detected values
        if hasattr(self, 'parse_standard_question'): #avoid attribute error crashes
            return self.parse_standard_question(q)

        return intent, phase, metric

    # ============================== UTILITY METHODS ================= ===================#

    def format_duration(self, duration):
        """Convert timedelta to formatted string (h:m:s)"""
        if not hasattr(duration, 'total_seconds'): 
            return str(duration)
        ts = duration.total_seconds()
        h = int(ts // 3600)
        m = int((ts % 3600) // 60)
        s = int(ts % 60)
        return f"{h}h {m}m {s}s" if h > 0 else (f"{m}m {s}s" if m > 0 else f"{s}s")

    def format_metric_label(self, metric):
        """Convert metric to formatted label"""
        return metric.upper() if metric else "AVERAGE"

    def haversine(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two coordinates in km."""
        R = 6371.0  # Earth radius in km

        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2  #computes the square of half the chord length between points.
        c = 2 * atan2(sqrt(a), sqrt(1 - a)) #Converts the value into an angle

        return R * c  # km
    
    def set_metadata(self, metadata: dict):
        if not hasattr(self, "phase_dict") or self.phase_dict is None:
            self.phase_dict = {
    "metadata": {},
    "phases": {},
    "subphases": {},
    "summary": {}
}


        self.phase_dict["metadata"] = metadata
    def get_metadata(self):
        return self.phase_dict.get("metadata", {})
    
    
    def get_metric_value(self, metric: str, phase: str = None, agg: str = "avg"):
        metric_map = {
            "pitch": "Pitch",
            "altitude": "AltMSL",
            "alt": "AltMSL",
            "altmsl": "AltMSL",
            "ias": "IAS",
            "gnd": "GndSpd",
            "speed": "IAS",
            "vspd": "VSpd"
        }

        unit_map = {
            "AltMSL": "ft",
            "IAS": "knots",
            "GndSpd": "knots",
            "Pitch": "degrees",
            "VSpd": "ft/min"
        }

        col = metric_map.get(metric)
        if not col:
            return {"error": f"Unsupported metric: {metric}"}

        # Get data
        if phase:
            segments = self.get_phase_segments(phase)
            if not segments:
                return {"error": f"No data for {phase} phase"}

            values = []
            for seg in segments:
                if col in seg.columns:
                    values.extend(seg[col].dropna().tolist())
        else:
            if col not in self.df.columns:
                return {"error": f"No {metric} data available"}
            values = self.df[col].dropna().tolist()

        if not values:
            return {"error": f"No {metric} data available"}

        data = np.array(values)

        # Aggregate
        if agg == "max":
            val = float(data.max())
        elif agg == "min":
            val = float(data.min())
        else:
            val = float(data.mean())

        return {
            "metric": metric,
            "phase": phase,
            "aggregation": agg,
            "value": val,
            "unit": unit_map.get(col, "")
        }
    
    def display_metadata(self):
        metadata = self.phase_dict.get("metadata", {})
        
        if not metadata:
            return "No metadata available."
        lines = []
        lines.append("┌──────────────────────────┐")
        lines.append("│      FLIGHT METADATA     │")
        lines.append("└──────────────────────────┘")

        for k, v in metadata.items():
            lines.append(f"{k.replace('_',' ').title():15}: {v}")
        return "\n".join(lines)

    def run_flight_checks(self, thresholds: dict = None):
        """Run automated flight checks and return a dictionary of results.

        thresholds: optional dict to configure limits, e.g.:
          { 'late_descent_pct': 75, 'pitch_max': 20, 'pitch_min': -10, 'speed_limit': 250, 'alt_tol_ft': 500 }
        """
        if thresholds is None:
            thresholds = {}
        late_descent_pct = thresholds.get('late_descent_pct', 75)
        pitch_max = thresholds.get('pitch_max', 20)
        pitch_min = thresholds.get('pitch_min', -10)
        speed_limit = thresholds.get('speed_limit', 250)
        alt_tol = thresholds.get('alt_tol_ft', 500)

        df = self.df
        if df is None:
            return { 'error': 'No data loaded' }

        res = {}
        start = df['timestamp'].iloc[0]
        end = df['timestamp'].iloc[-1]
        dur = (end - start).total_seconds()

        # Descent initiation
        desc = self.get_phase_segments('DESCENT')
        if desc:
            desc_start = desc[0]['timestamp'].iloc[0]
            elapsed = (desc_start - start).total_seconds()
            pct = elapsed / dur * 100 if dur > 0 else None
            seconds_before_end = (end - desc_start).total_seconds()
            res['descent'] = {
                'start': str(desc_start),
                'elapsed_sec': int(elapsed),
                'pct_of_flight': round(pct, 1),
                'sec_before_end': int(seconds_before_end),
                'late_by_rule': pct > late_descent_pct
            }
        else:
            res['descent'] = 'no descent segments'

        # Build segment summaries list for abrupt checks
        segs = []
        for sid, g in df.groupby('segment_id'):
            phase = g['Phase'].iloc[0]
            s = g['timestamp'].iloc[0] if 'timestamp' in g.columns else None
            e = g['timestamp'].iloc[-1] if 'timestamp' in g.columns else None
            end_alt = g['AltMSL'].dropna(); end_alt = end_alt.iloc[-1] if not end_alt.empty else None
            start_alt = g['AltMSL'].dropna(); start_alt = start_alt.iloc[0] if not start_alt.empty else None
            end_pitch = g['Pitch'].dropna(); end_pitch = end_pitch.iloc[-1] if not end_pitch.empty else None
            start_pitch = g['Pitch'].dropna(); start_pitch = start_pitch.iloc[0] if not start_pitch.empty else None
            end_ias = g['IAS'].dropna(); end_ias = end_ias.iloc[-1] if not end_ias.empty else None
            start_ias = g['IAS'].dropna(); start_ias = start_ias.iloc[0] if not start_ias.empty else None
            segs.append({'id': sid, 'phase': phase, 'start': s, 'end': e, 'start_alt': start_alt, 'end_alt': end_alt, 'start_pitch': start_pitch, 'end_pitch': end_pitch, 'start_ias': start_ias, 'end_ias': end_ias})

        abrupt = []
        for i in range(len(segs) - 1):
            a = segs[i]; b = segs[i + 1]
            if a['end'] is None or b['start'] is None:
                continue
            gap = (b['start'] - a['end']).total_seconds()
            alt_jump = None
            if a['end_alt'] is not None and b['start_alt'] is not None:
                alt_jump = b['start_alt'] - a['end_alt']
            ias_jump = None
            if a['end_ias'] is not None and b['start_ias'] is not None:
                ias_jump = b['start_ias'] - a['end_ias']
            pitch_jump = None
            if a['end_pitch'] is not None and b['start_pitch'] is not None:
                pitch_jump = b['start_pitch'] - a['end_pitch']
            flag = False
            reasons = []
            # Abrupt criteria
            if gap < 1:
                if alt_jump is not None and abs(alt_jump) > 500:
                    flag = True; reasons.append(f'alt_jump={alt_jump:.1f}ft')
                if ias_jump is not None and abs(ias_jump) > 30:
                    flag = True; reasons.append(f'ias_jump={ias_jump:.1f}kt')
                if pitch_jump is not None and abs(pitch_jump) > 10:
                    flag = True; reasons.append(f'pitch_jump={pitch_jump:.1f}deg')
            if flag:
                abrupt.append({'from': a['phase'], 'to': b['phase'], 'gap_s': gap, 'reasons': reasons, 'seg_from': a['id'], 'seg_to': b['id']})
        res['abrupt_transitions'] = abrupt

        # Climb pitch
        climb = self.get_phase_segments('CLIMB')
        if climb:
            pitch_arrays = [seg['Pitch'].dropna().values for seg in climb if 'Pitch' in seg.columns and not seg['Pitch'].dropna().empty]
            climb_pitch = np.concatenate(pitch_arrays) if pitch_arrays else np.array([])
            if climb_pitch.size > 0:
                maxp = float(climb_pitch.max()); minp = float(climb_pitch.min()); pct_abnormal = float(np.sum((climb_pitch > pitch_max) | (climb_pitch < pitch_min)) / climb_pitch.size * 100)
                res['climb_pitch'] = {'max': maxp, 'min': minp, 'pct_abnormal': round(pct_abnormal, 2)}
            else:
                res['climb_pitch'] = 'no pitch data'
        else:
            res['climb_pitch'] = 'no climb segments'

        # Approach pitch
        approach = self.get_phase_segments('APPROACH')
        if approach:
            pitch_arrays = [seg['Pitch'].dropna().values for seg in approach if 'Pitch' in seg.columns and not seg['Pitch'].dropna().empty]
            app_pitch = np.concatenate(pitch_arrays) if pitch_arrays else np.array([])
            if app_pitch.size > 0:
                excessive = int(np.sum((app_pitch > pitch_max) | (app_pitch < pitch_min)))
                res['approach_pitch'] = {'max': float(app_pitch.max()), 'min': float(app_pitch.min()), 'excessive_count': excessive}
            else:
                res['approach_pitch'] = 'no pitch data'
        else:
            res['approach_pitch'] = 'no approach segments'

        # Takeoff speed
        takeoff = self.get_phase_segments('TAKEOFF')
        if takeoff:
            sp_arrays = [seg['IAS'].dropna().values for seg in takeoff if 'IAS' in seg.columns and not seg['IAS'].dropna().empty]
            to_speeds = np.concatenate(sp_arrays) if sp_arrays else np.array([])
            if to_speeds.size > 0:
                overspeed_count = int(np.sum(to_speeds > speed_limit))
                res['takeoff_speed'] = {'max': float(to_speeds.max()), 'avg': float(to_speeds.mean()), 'overspeed_count': overspeed_count}
            else:
                res['takeoff_speed'] = 'no IAS data'
        else:
            res['takeoff_speed'] = 'no takeoff segments'

        # Descent overspeed
        if desc:
            sp_arrays = [seg['IAS'].dropna().values for seg in desc if 'IAS' in seg.columns and not seg['IAS'].dropna().empty]
            desc_speeds = np.concatenate(sp_arrays) if sp_arrays else np.array([])
            desc_overs = int(np.sum(desc_speeds > speed_limit)) if desc_speeds.size > 0 else 0
            res['descent_overspeed'] = {'count': desc_overs, 'max': float(desc_speeds.max()) if desc_speeds.size > 0 else None}
        else:
            res['descent_overspeed'] = 'no descent segments'

        # Cruise speed efficiency proxy
        cruise = self.get_phase_segments('CRUISE')
        if cruise:
            sp_arrays = [seg['IAS'].dropna().values for seg in cruise if 'IAS' in seg.columns and not seg['IAS'].dropna().empty]
            cruise_speeds = np.concatenate(sp_arrays) if sp_arrays else np.array([])
            if cruise_speeds.size > 0:
                mean_cr = float(cruise_speeds.mean()); std_cr = float(cruise_speeds.std()); within5 = float(np.sum(np.abs(cruise_speeds - mean_cr) <= 0.05 * mean_cr) / cruise_speeds.size * 100)
                res['cruise_speed_efficiency'] = {'mean': mean_cr, 'std': std_cr, 'pct_within_5pct': round(within5, 1)}
            else:
                res['cruise_speed_efficiency'] = 'no cruise IAS data'
        else:
            res['cruise_speed_efficiency'] = 'no cruise segments'

        # Cruise altitude consistency
        if cruise:
            alt_arrays = [seg['AltMSL'].dropna().values for seg in cruise if 'AltMSL' in seg.columns and not seg['AltMSL'].dropna().empty]
            cruise_alts = np.concatenate(alt_arrays) if alt_arrays else np.array([])
            if cruise_alts.size > 0:
                mean_alt = float(cruise_alts.mean()); std_alt = float(cruise_alts.std()); within500 = float(np.sum(np.abs(cruise_alts - mean_alt) <= alt_tol) / cruise_alts.size * 100)
                res['cruise_altitude'] = {'mean': mean_alt, 'std': std_alt, 'pct_within_500ft': round(within500, 1)}
            else:
                res['cruise_altitude'] = 'no cruise altitude data'
        else:
            res['cruise_altitude'] = 'no cruise segments'

        # Climb altitude deviations
        if climb:
            alt_arrays = [seg['AltMSL'].dropna().values for seg in climb if 'AltMSL' in seg.columns and not seg['AltMSL'].dropna().empty]
            climb_alts = np.concatenate(alt_arrays) if alt_arrays else np.array([])
            if climb_alts.size > 1:
                diffs = np.diff(climb_alts)
                large_drop_count = int(np.sum(diffs < -500))
                max_drop = float(diffs.min())
                max_rise = float(diffs.max())
                res['climb_altitude_deviations'] = {'max_rise_ft': max_rise, 'max_drop_ft': max_drop, 'large_drops_count': large_drop_count}
            else:
                res['climb_altitude_deviations'] = 'insufficient climb alt data'
        else:
            res['climb_altitude_deviations'] = 'no climb segments'

        return res

    def _format_check_answer(self, key, data):
        """Return a concise human-readable summary for a single check key."""
        if isinstance(data, str):
            return f"{key}: {data}"

        if key == 'descent':
            if isinstance(data, dict):
                late = 'Yes' if data.get('late_by_rule') else 'No'
                return f"Descent started at {data.get('start')} — Late by rule? {late} (pct_of_flight={data.get('pct_of_flight')}%)"
            return str(data)

        if key == 'abrupt_transitions':
            if not data:
                return "No abrupt phase transitions detected."
            return f"Abrupt transitions detected: {len(data)} occurrence(s). Details: {data}"

        if key == 'climb_pitch':
            if isinstance(data, dict):
                return f"Climb pitch: max={data.get('max'):.2f}°, min={data.get('min'):.2f}°, abnormal_pct={data.get('pct_abnormal')}%"
            return str(data)

        if key == 'approach_pitch':
            if isinstance(data, dict):
                return f"Approach pitch: max={data.get('max'):.2f}°, min={data.get('min'):.2f}°, excessive_count={data.get('excessive_count')}"
            return str(data)

        if key == 'takeoff_speed':
            if isinstance(data, dict):
                return f"Takeoff IAS: avg={data.get('avg'):.1f} kt, max={data.get('max'):.1f} kt, overspeed_count={data.get('overspeed_count')}"
            return str(data)

        if key == 'descent_overspeed':
            if isinstance(data, dict):
                return f"Descent overspeed: count={data.get('count')}, max={data.get('max')} kt"
            return str(data)

        if key == 'cruise_speed_efficiency':
            if isinstance(data, dict):
                return f"Cruise IAS: mean={data.get('mean'):.1f} kt, std={data.get('std'):.1f}, pct_within_5%={data.get('pct_within_5pct')}%"
            return str(data)

        if key == 'cruise_altitude':
            if isinstance(data, dict):
                return f"Cruise altitude: mean={data.get('mean'):.0f} ft, std={data.get('std'):.0f} ft, pct_within_500ft={data.get('pct_within_500ft')}%"
            return str(data)

        if key == 'climb_altitude_deviations':
            if isinstance(data, dict):
                return f"Climb altitude deviations: max_rise={data.get('max_rise_ft')} ft, max_drop={data.get('max_drop_ft')} ft, large_drops={data.get('large_drops_count')}"
            return str(data)

        return f"{key}: {data}"


    # ============================== ANSWER FUNCTION ================= ===================#

    def answer(self, user_query: str):
        result = self.parse_query(user_query)

     # Unpack safely
        intent = result[0] if len(result) > 0 else None
        phase = result[1] if len(result) > 1 else None
        metric = result[2] if len(result) > 2 else None
        segment_num = result[3] if len(result) > 3 else None
        agg = "avg"  # Default aggregation

        # Handle structured output request
        if intent == "phase_dict":
            pdict = self.build_phase_dict()
            return pdict

        # Flight checks (integrated)
        if intent == "flight_checks":
            return self.run_flight_checks()

        if intent == "flight_check":
            checks = self.run_flight_checks()
            key = phase
            if not isinstance(checks, dict):
                return checks
            if key is None:
                # Return summary of checks
                return checks
            if key not in checks:
                return f"No check data available for '{key}'"
            return self._format_check_answer(key, checks[key])

        if intent == "phase_list":
            # Return phases in order of occurrence (by segment)
            if 'segment_id' not in self.df.columns:
                self.create_segments()
            seg_phase_series = self.df.groupby('segment_id', sort=False)['Phase'].first()
            phases = [p for p in seg_phase_series.tolist() if pd.notna(p)]
            unique = []
            for p in phases:
                if p not in unique:
                    unique.append(p)
            counts = self.df['Phase'].value_counts().to_dict() if 'Phase' in self.df.columns else {}
            counts_str = ", ".join(f"{k}: {v}" for k, v in counts.items())
            return f"Phases detected in this flight (in order): {', '.join(unique)}\n\nCounts: {counts_str}"
        
        if intent == "metadata":
           return self.display_metadata()


        # Handle overview queries
        if intent == "flight_overview":
            return self.get_flight_overview()
        if intent == "list_phases":
                if 'Phase' not in self.df.columns:
                    return "Phase column not found in flight data."
                # Get unique phases and filter out NaN
                phases = self.df['Phase'].dropna().unique().tolist()
                output = "\n  PHASES DETECTED IN THIS FLIGHT\n"
                output += "  " + "─" * 40 + "\n"
                for idx, phase in enumerate(phases, 1):
                    # Count segments instead of data points
                    if 'segment_id' in self.df.columns:
                        phase_segments = self.get_phase_segments(phase)
                        segment_count = len(phase_segments)
                        output += f"  {idx}. {phase:15} ({segment_count:>6} segments)\n"
                    else:
                        count = len(self.df[self.df['Phase'] == phase])
                        output += f"  {idx}. {phase:15} ({count:>6} data points)\n"
                output += "\n"
                return output
        elif intent == "phase_overview" and phase:
            # Check if user asked for a specific numbered phase (e.g., "taxi 1 summary")
            if segment_num is not None:
                return self.get_numbered_phase_summary(phase, segment_num)
            return self.get_phase_overview(phase)
        if intent == "subphase_info":
            return self.get_subphase_overview()
        if intent == "subphase_detail" and phase:
            return self.get_subphase_detail(phase)
        if intent == "subphase_metric" and phase:
            return self.get_subphase_metric(phase, metric or "avg")
        # Handle special intents that don't use single phase segments
        if intent == "phase_transition":
            # phase expected as tuple (FROM, TO)
            if not isinstance(phase, (list, tuple)) or len(phase) != 2:
                return "Please specify both phases for a transition query."
            from_phase, to_phase = phase
            value = self.get_transition_value(from_phase, to_phase, metric)
            if value is None:
                return f"No transition found from {from_phase} to {to_phase}"
            return f"{(metric or 'value').upper()} at transition from {from_phase} to {to_phase}: {value}"

        if intent == "position":
            pos = self.get_phase_position(phase)
            if not pos:
                return f"No position data found for {phase}"
            return f"{phase} occurred at Lat {pos.get('latitude')}, Lon {pos.get('longitude')} at {pos.get('timestamp')}"


        if intent == "segment_query":
          if not segment:
               return "Please specify which segment number."

               return self.get_numbered_phase_summary(phase, segment)

         
            # ------------------ TOTAL FLIGHT DURATION ------------------
        if intent == "total_flight_duration":
                if 'timestamp' not in self.df.columns:
                    return "No timestamp data available."
                
                flight_start = self.df['timestamp'].iloc[0]
                flight_end = self.df['timestamp'].iloc[-1]
                total_duration = flight_end - flight_start
                return f"Total flight duration: {self.format_duration(total_duration)}\n"
               
        if not intent:
               return "Please ask about a valid phase and time (duration/start/end)."


        # Allow asking total flight duration without specifying a phase
        if intent == "duration" and not phase:
            if 'timestamp' not in self.df.columns:
                return "Timestamp data not available to compute flight duration."
            flight_start = self.df['timestamp'].iloc[0]
            flight_end = self.df['timestamp'].iloc[-1]
            total_duration = flight_end - flight_start
            return f"Flight Start: {flight_start}\nFlight End: {flight_end}\nTotal Duration: {self.format_duration(total_duration)}"

        if intent != "duration" and not phase:
            return "Please ask about a valid phase and time (duration/start/end)."

        segments = self.get_phase_segments(phase)
        if not segments:
            # Provide helpful debug information
            if 'Phase' in self.df.columns:
                available_phases = self.df['Phase'].value_counts().index.tolist()
                return f"No data found for {phase} phase. Available phases: {', '.join(available_phases)}"
            else:
                return f"No data found for {phase} phase. Phase column not detected. Please run detect_phases() first."

        # Handle intents that don't combine segments
        if intent == "duration":
            # If user included a segment number (e.g., 'taxi1 duration'), return a concise phase-level summary
            if segment_num is not None:
                total_duration = pd.Timedelta(0)
                for seg in segments:
                    if 'timestamp' in seg.columns and len(seg) > 1:
                        dur = seg['timestamp'].iloc[-1] - seg['timestamp'].iloc[0]
                    else:
                        dur = pd.Timedelta(seconds=len(seg))
                    total_duration += dur if hasattr(dur, 'total_seconds') else pd.Timedelta(seconds=dur)

                total_str = self.format_duration(total_duration)
                return f"The {phase.lower()} phase lasted {total_str}, covering {len(segments)} segments."

            # Default: show per-segment breakdown
            results = []
            total_duration = pd.Timedelta(0)
            for idx, seg in enumerate(segments, 1):
                if 'timestamp' in seg.columns and len(seg) > 1:
                    duration = seg['timestamp'].iloc[-1] - seg['timestamp'].iloc[0]
                else:
                    duration = len(seg)

                total_duration += duration if hasattr(duration, 'total_seconds') else pd.Timedelta(seconds=duration)

                time_str = self.format_duration(duration) if hasattr(duration, 'total_seconds') else f"{duration} data points"
                results.append(f"  Segment {idx:2d}  │  {time_str:>12}")

            # Return concise phase-level duration summary (total time + segment count)
            total_str = self.format_duration(total_duration)
            return f"The {phase.lower()} phase lasted {total_str}, covering {len(segments)} segment(s)."
        
        elif intent == "start":
            seg = segments[0]
            start_time = seg['timestamp'].iloc[0] if 'timestamp' in seg.columns else seg.index[0]
            return f"{phase} started at {start_time}"
        
        elif intent == "end":
            seg = segments[-1]
            end_time = seg['timestamp'].iloc[-1] if 'timestamp' in seg.columns else seg.index[-1]
            return f"{phase} ended at {end_time}"

        elif intent == "altitude":
            if 'AltMSL' not in segments[0].columns:
                return "Altitude data not available."
            
            results = []
            for idx, seg in enumerate(segments, 1):
                alt_data = seg['AltMSL'].dropna()
                if alt_data.empty:
                    results.append(f"  Segment {idx:2d}  │  No data")
                    continue
                
                if metric == "min":
                    # Return overall phase duration (user wants consolidated answer)
                    total_phase_duration = pd.Timedelta(0)
                    for _, d in segment_durations:
                        total_phase_duration += d
                    output = f"\nThe {phase.lower()} phase lasted approximately {self.format_duration(total_phase_duration)}, consisting of {len(segment_durations)} segments.\n"
                    return output
                elif metric == "end":
                    results.append(f"  Segment {idx:2d}  │  {seg['AltMSL'].iloc[-1]:>8.0f} ft")
            
            metric_label = self.format_metric_label(metric)
            output = "\n"
            output += f"   {phase} ALTITUDE - {metric_label} ({len(segments)} segments)\n"
            output += "  " + "─" * 40 + "\n"
            output += "\n".join(results)
            output += "\n\n"
            return output

        elif intent == "speed":
            # Determine which speed column to use based on the original query
            query_lower = user_query.lower()
            speed_col = "IAS"  # Default
            if "ground" in query_lower or "gnd" in query_lower or "gs" in query_lower:
                speed_col = "GndSpd"
            
            if speed_col not in segments[0].columns:
                return f"{speed_col} data not available."
            
            results = []
            for idx, seg in enumerate(segments, 1):
                spd_data = seg[speed_col].dropna()

                if spd_data.empty:
                    results.append(f"  Segment {idx:2d}  │  No data")
                    continue
                
                elif metric == "max":
                    # Return overall phase duration (consolidated phrasing)
                    total_phase_duration = pd.Timedelta(0)
                    for _, d in segment_durations:
                        total_phase_duration += d
                    output = f"\nThe {phase.lower()} phase lasted {self.format_duration(total_phase_duration)}, consisting of {len(segment_durations)} segments.\n"
                    return output

                elif metric == "limit":
                    SPEED_LIMIT = 250
                    overspeed = spd_data[spd_data > SPEED_LIMIT]
                    if overspeed.empty:
                        results.append(f"  Segment {idx:2d}  |  [OK] Within limits")
                    else:
                        results.append(f"  Segment {idx:2d}  │   OVERSPEED - {overspeed.max():.1f} knots")
            
            metric_label = self.format_metric_label(metric)
            output = "\n"
            output += f"    {phase} {speed_col} - {metric_label} ({len(segments)} segments)\n"
            output += "  " + "─" * 40 + "\n"
            output += "\n".join(results)
            output += "\n\n"
            return output

        elif intent == "distance":
            if 'Lat' not in segments[0].columns or 'Lon' not in segments[0].columns:
                return "Latitude/Longitude data not available for distance calculation."
            
            total_distance = 0
            for seg in segments:
                lat_data = seg['Lat'].dropna()
                lon_data = seg['Lon'].dropna()
                
                if len(lat_data) > 1 and len(lon_data) > 1:
                    for i in range(len(lat_data) - 1):
                        lat1, lon1 = lat_data.iloc[i], lon_data.iloc[i]
                        lat2, lon2 = lat_data.iloc[i + 1], lon_data.iloc[i + 1]
                        distance = self.haversine(lat1, lon1, lat2, lon2)
                        total_distance += distance
            
            output = f"\nTotal distance flown during {phase}: {total_distance:.2f} km\n\n"
            return output

        elif intent == "track":
            if 'Lat' not in segments[0].columns or 'Lon' not in segments[0].columns:
                return "Latitude/Longitude data not available for track display."
            
            output = f"\n TRACK DURING {phase}\n"
            output += "─" * 60 + "\n"
            
            total_points = 0
            for idx, seg in enumerate(segments, 1):
                lat_data = seg['Lat'].dropna()
                lon_data = seg['Lon'].dropna()
                
                output += f"\nSegment {idx}:\n"
                sample_size = max(1, len(lat_data) // 10)  # Sample every 10th point
                
                for i in range(0, len(lat_data), sample_size):
                    lat = lat_data.iloc[i]
                    lon = lon_data.iloc[i]
                    output += f"  Point {i+1}: Lat {lat:.6f}° | Lon {lon:.6f}°\n"
                    total_points += 1
                
                if len(lat_data) > 1:
                    output += f"  (Showing {total_points} sampled points from {len(lat_data)} total)\n"
            
            output += "\n" + "─" * 60 + "\n\n"
            return output

        elif intent == "routing":
            if 'Lat' not in segments[0].columns or 'Lon' not in segments[0].columns:
                return "Latitude/Longitude data not available for routing analysis."
            
            output = f"\n OPTIMAL ROUTING ANALYSIS - {phase}\n"
            output += "─" * 60 + "\n"
            
            for idx, seg in enumerate(segments, 1):
                lat_data = seg['Lat'].dropna()
                lon_data = seg['Lon'].dropna()
                
                if len(lat_data) < 2:
                    continue
                
                # Calculate actual distance traveled
                actual_distance = 0
                for i in range(len(lat_data) - 1):
                    lat1, lon1 = lat_data.iloc[i], lon_data.iloc[i]
                    lat2, lon2 = lat_data.iloc[i + 1], lon_data.iloc[i + 1]
                    actual_distance += self.haversine(lat1, lon1, lat2, lon2)
                
                # Calculate straight-line distance (optimal)
                lat_start, lon_start = lat_data.iloc[0], lon_data.iloc[0]
                lat_end, lon_end = lat_data.iloc[-1], lon_data.iloc[-1]
                optimal_distance = self.haversine(lat_start, lon_start, lat_end, lon_end)
                
                # Calculate efficiency
                efficiency = (optimal_distance / actual_distance * 100) if actual_distance > 0 else 0
                
                output += f"\nSegment {idx}:\n"
                output += f"  Actual Distance:   {actual_distance:.2f} km\n"
                output += f"  Optimal Distance:  {optimal_distance:.2f} km\n"
                output += f"  Efficiency:        {efficiency:.1f}%\n"
                output += f"  Deviation:         {actual_distance - optimal_distance:.2f} km\n"
            
            output += "\n" + "─" * 60 + "\n\n"
            return output

        elif intent == "pitch":
            if 'Pitch' not in segments[0].columns:
                return "Pitch data not available."
            
            results = []
            for idx, seg in enumerate(segments, 1):
                pitch_data = seg['Pitch'].dropna()
                if pitch_data.empty:
                    results.append(f"  Segment {idx:2d}  │  No data")
                    continue
                
                if metric == "max":
                    results.append(f"  Segment {idx:2d}  │  {pitch_data.max():>8.2f}°")
                elif metric == "min":
                    results.append(f"  Segment {idx:2d}  │  {pitch_data.min():>8.2f}°")
                elif metric == "avg":
                    results.append(f"  Segment {idx:2d}  │  {pitch_data.mean():>8.2f}°")
                elif metric == "start":
                    results.append(f"  Segment {idx:2d}  │  {seg['Pitch'].iloc[0]:>8.2f}°")
                elif metric == "end":
                    results.append(f"  Segment {idx:2d}  │  {seg['Pitch'].iloc[-1]:>8.2f}°")
                elif metric == "abnormal":
                    abnormal = seg[(seg['Pitch'] > 20) | (seg['Pitch'] < -10)]
                    if abnormal.empty:
                        results.append(f"  Segment {idx:2d}  │   Normal (-10° to 20°)")
                    else:
                        results.append(f"  Segment {idx:2d}  │   ABNORMAL - {len(abnormal)} points")
            
            metric_label = self.format_metric_label(metric)
            output = "\n"
            output += f"   {phase} PITCH - {metric_label} ({len(segments)} segments)\n"
            output += "  " + "─" * 40 + "\n"
            output += "\n".join(results)
            output += "\n\n"
            return output
        
        


        
        elif intent == "multi_duration":
            # Handle multi-phase duration queries with segment details
            if 'timestamp' not in self.df.columns:
                return "Timestamp data not available for duration calculations."
            
            phase_df = self.df[self.df['Phase'] == phase]
            if phase_df.empty:
                return f"No data found for {phase} phase."
            
            # Get segments for this phase
            segments = self.get_phase_segments(phase)
            if not segments:
                return f"No segments found for {phase} phase."
            
            # Calculate duration for each segment
            segment_durations = []
            for idx, seg in enumerate(segments, 1):
                if 'timestamp' in seg.columns and len(seg) > 1:
                    duration = seg['timestamp'].iloc[-1] - seg['timestamp'].iloc[0]
                    segment_durations.append((idx, duration))
            
            if not segment_durations:
                return f"Cannot calculate durations for {phase} phase."
            
            # Handle different metrics
            if metric == "min":
                # Find shortest segment
                min_seg_idx, min_duration = min(segment_durations, key=lambda x: x[1])
                min_seg = segments[min_seg_idx - 1]
                output = f"\nThe shortest {phase.lower()} segment lasted approximately {self.format_duration(min_duration)}.\n"
                output += f"  Segment {min_seg_idx} details:\n"
                output += self.get_segment_summary(min_seg)
                return output
            
            elif metric == "max":
                # Find longest segment
                max_seg_idx, max_duration = max(segment_durations, key=lambda x: x[1])
                max_seg = segments[max_seg_idx - 1]
                output = f"\nThe longest {phase.lower()} segment lasted approximately {self.format_duration(max_duration)}.\n"
                output += f"  Segment {max_seg_idx} details:\n"
                output += self.get_segment_summary(max_seg)
                return output
            
            elif metric == "avg":
                avg_duration = pd.Timedelta(0)
                for _, duration in segment_durations:
                    avg_duration += duration
                avg_duration = avg_duration / len(segment_durations)
                return f"Average {phase} duration is {self.format_duration(avg_duration)} across {len(segment_durations)} segments"
            
            elif metric == "long":
                # Find segments with duration > 10 minutes
                long_segments = [(idx, dur) for idx, dur in segment_durations if dur > pd.Timedelta(minutes=10)]
                if long_segments:
                    output = f"Found {len(long_segments)} {phase} segments with duration > 10 minutes:\n"
                    for seg_idx, duration in long_segments:
                        output += f"  Segment {seg_idx}: {self.format_duration(duration)}\n"
                    return output
                else:
                    return f"No {phase} segments found with duration > 10 minutes"
        
        elif intent == "multi_altitude":
            # Handle multi-phase altitude queries
            phase_df = self.df[self.df['Phase'] == phase]
            if phase_df.empty or 'AltMSL' not in phase_df.columns:
                return f"No altitude data found for {phase} phase."
            
            if 'FlightID' in self.df.columns:
                max_altitudes = phase_df.groupby('FlightID')['AltMSL'].max()
                overall_max = max_altitudes.max()
            else:
                overall_max = phase_df['AltMSL'].max()
            
            return f"Maximum altitude during {phase} across all flights is {overall_max:.0f} ft"
        
        elif intent == "abnormal_climb":
            # Handle abnormal climb detection
            climb_df = self.df[self.df['Phase'] == phase]
            if climb_df.empty:
                return f"No data found for {phase} phase."
            
            if 'VSpd' not in climb_df.columns:
                return "Vertical speed data not available."
            
            # Detect abnormal climb rates (> 3000 ft/min)
            abnormal = climb_df[climb_df['VSpd'] > 3000]
            
            if 'FlightID' in self.df.columns:
                flight_ids = abnormal['FlightID'].unique().tolist()
                if len(flight_ids) > 0:
                    return f"Abnormal climb detected in {len(flight_ids)} flight(s) with climb rate > 3000 ft/min: {', '.join(map(str, flight_ids))}"
                else:
                    return f"No abnormal climb detected. All {phase} rates are within normal limits."
            else:
                if len(abnormal) > 0:
                    return f"Abnormal climb detected: {len(abnormal)} data points with climb rate > 3000 ft/min"
                else:
                    return f"No abnormal climb detected. All {phase} rates are within normal limits."
        
        return f"Unable to process query for {phase or 'this'} phase."



        # ================= PHASE TRANSITION ================= #

    def get_transition_value(self, from_phase, to_phase, param):
        df = self.df

        trans_df = df[
            (df['Phase'] == from_phase) &
            (df['Phase'].shift(-1) == to_phase)
        ]

        if trans_df.empty:
            return None

        trans = trans_df.iloc[0]

        if param == "ias":
            return f"{trans.get('IAS', 'NA')} knots"
        elif param == "altitude":
            return f"{trans.get('AltMSL', 'NA')} ft"
        else:
            return trans.get("timestamp", "NA")

    # ================= PHASE POSITION ================= #

    def get_phase_position(self, phase):
        df = self.df
        phase_df = df[df['Phase'] == phase]

        if phase_df.empty:
            return None

        seg = phase_df.iloc[0]
        return {
            "latitude": seg.get("Lat"),
            "longitude": seg.get("Lon"),
            "timestamp": seg.get("timestamp")
        }

    def get_taxi_duration(self, segments):
        """Calculate total duration for taxi segments (segments: list of DataFrames)."""
        total = pd.Timedelta(0)
        for seg in segments:
            if 'timestamp' in seg.columns and len(seg) > 1:
                total += seg['timestamp'].iloc[-1] - seg['timestamp'].iloc[0]
        return total

    def get_taxi_overview(self, segments):
        """Return overview stats for taxi segments: duration, points, avg IAS and GndSpd."""
        total_duration = self.get_taxi_duration(segments)
        total_points = sum(len(seg) for seg in segments)
        ias_vals = []
        gnd_vals = []
        for seg in segments:
            if 'IAS' in seg.columns:
                ias_vals.extend(seg['IAS'].dropna().tolist())
            if 'GndSpd' in seg.columns:
                gnd_vals.extend(seg['GndSpd'].dropna().tolist())
        ias_avg = float(np.mean(ias_vals)) if ias_vals else 0.0
        gnd_avg = float(np.mean(gnd_vals)) if gnd_vals else 0.0
        return {"duration": total_duration, "points": total_points, "ias_avg": ias_avg, "gnd_avg": gnd_avg}

    def get_taxi_speed(self, segments):
        """Return avg IAS and GndSpd for taxi segments (list of DataFrames)."""
        res = self.get_taxi_overview(segments)
        return res["ias_avg"], res["gnd_avg"]

    def get_phase_duration(self, phase: str):
        """Return structured data about durations for the given phase across its segments."""
        
        if 'Phase' not in self.df.columns:
            return {"error": "Phase column not found. Please run detect_phases() first."}
        if not phase:
            return {"error": "Please specify a phase to compute duration for."}
        
        phase = phase.upper()
        segments = self.get_phase_segments(phase)
        if not segments:
            return {"error": f"No data found for {phase} phase."}

        segment_data = []
        total_duration = pd.Timedelta(0)
        
        for idx, seg in enumerate(segments, 1):
            if 'timestamp' in seg.columns and len(seg) > 1:
                duration = seg['timestamp'].iloc[-1] - seg['timestamp'].iloc[0]
            else:
                duration = pd.Timedelta(seconds=len(seg))
            
            total_duration += duration if hasattr(duration, 'total_seconds') else pd.Timedelta(seconds=duration)
            duration_seconds = duration.total_seconds() if hasattr(duration, 'total_seconds') else duration
            time_str = self.format_duration(duration)
            
            segment_data.append({
                "segment": idx,
                "duration_seconds": duration_seconds,
                "duration_formatted": time_str
            })

        total_str = self.format_duration(total_duration)
        total_seconds = total_duration.total_seconds() if hasattr(total_duration, 'total_seconds') else total_duration
        
        return {
            "phase": phase,
            "total_segments": len(segments),
            "segments": segment_data,
            "total_duration_seconds": total_seconds,
            "total_duration_formatted": total_str
        }

    def build_phase_dict(self, metadata: dict = None):
        """Builds and stores a structured phase_dict with metadata, phases and summary.

        Structure:
        phase_dict = {
            "metadata": {...},
            "phases": { phase_name: [segments...] },
            "summary": { "overall_phase_Summary": {...} }
        }
        """
        if not hasattr(self, "phase_dict") or self.phase_dict is None:
            self.phase_dict = {"metadata": {}, "phases": {}, "summary": {}}

        if metadata:
            self.set_metadata(metadata)

        # Ensure segments exist
        if 'segment_id' not in self.df.columns:
            self.create_segments()

        # Phase occurrence sequence (by segment order) - remove unknown phases
        seg_phase_series = self.df.groupby('segment_id')['Phase'].first()
        phase_occurrence = [p for p in seg_phase_series.tolist() if pd.notna(p)]

        # Counts
        phase_counts = self.df['Phase'].value_counts().to_dict() if 'Phase' in self.df.columns else {}

        # Per-phase details
        phases = {}
        total_time_sec = {}
        average_time_sec = {}
        total_distance_nm = {}

        for phase, count in phase_counts.items():
            segments = self.get_phase_segments(phase)
            seg_list = []
            total_sec = 0.0
            total_km = 0.0
            for seg in segments:
                seg_info = {}
                if 'timestamp' in seg.columns and len(seg) > 1:
                    start = seg['timestamp'].iloc[0]
                    end = seg['timestamp'].iloc[-1]
                    dur = (end - start).total_seconds()
                    seg_info['start'] = str(start)
                    seg_info['end'] = str(end)
                    seg_info['duration_sec'] = int(dur)
                else:
                    seg_info['start'] = None
                    seg_info['end'] = None
                    seg_info['duration_sec'] = 0
                    dur = 0

                total_sec += dur

                # Distance for segment
                if 'Lat' in seg.columns and 'Lon' in seg.columns:
                    lat = seg['Lat'].dropna()
                    lon = seg['Lon'].dropna()
                    seg_km = 0.0
                    if len(lat) > 1 and len(lon) > 1:
                        for i in range(len(lat) - 1):
                            seg_km += self.haversine(lat.iloc[i], lon.iloc[i], lat.iloc[i+1], lon.iloc[i+1])
                    seg_info['distance_nm'] = round(seg_km / 1.852, 3)
                    total_km += seg_km
                else:
                    seg_info['distance_nm'] = 0.0

                # Add other optional metrics
                if 'AltMSL' in seg.columns:
                    alt = seg['AltMSL'].dropna()
                    if not alt.empty:
                        seg_info['alt_min'] = float(alt.min())
                        seg_info['alt_max'] = float(alt.max())
                seg_list.append(seg_info)

            phases[phase] = {
                'count': int(count),
                'segments': seg_list
            }

            total_time_sec[phase.lower()] = int(total_sec)
            avg_val = (total_sec / count) if count > 0 else 0
            average_time_sec[phase.lower()] = round(avg_val, 1)
            total_distance_nm[phase.lower()] = round(total_km / 1.852, 3)

        # Build summary as requested
        overall_summary = {
            'Phase_Counts': {k.lower(): int(v) for k, v in phase_counts.items()},
            'Phase_occurance': [p for p in phase_occurrence],
            'total_time_sec': total_time_sec,
            'average_time_sec': average_time_sec,
            'total_distance_nm': total_distance_nm
        }

        self.phase_dict['phases'] = phases
        self.phase_dict['summary'] = {'overall_phase_Summary': overall_summary}

        return self.phase_dict

    # ----------------- Compatibility / legacy helper methods ----------------- #
    def build_phase_segments(self):
        """Legacy wrapper: ensure segments exist and return grouped segments."""
        if 'segment_id' not in self.df.columns:
            self.create_segments()
        return self.df.groupby('segment_id')

    def build_feature_stats(self):
        """Compute simple feature stats (lightweight, non-destructive)."""
        self.feature_stats = {}
        if 'AltMSL' in self.df.columns:
            alt = self.df['AltMSL'].dropna()
            if not alt.empty:
                self.feature_stats['alt_min'] = float(alt.min())
                self.feature_stats['alt_max'] = float(alt.max())
        return self.feature_stats

    def detect_takeoff_subphases(self):
        """Placeholder: create 'Sub Phase' column if missing and return empty list."""
        if 'Sub Phase' not in self.df.columns:
            self.df['Sub Phase'] = None
        return []

    def generate_phase_remarks(self):
        """Placeholder for older workflows — provide empty remarks dict."""
        self.phase_remarks = {}
        return self.phase_remarks

    def build_summary(self):
        """Compatibility wrapper that builds and returns the phase dictionary summary."""
        return self.build_phase_dict()

    def prepare_phases(self):
        """Convenience wrapper used by older callers: ensure segments, phase numbering and summaries are prepared.

        This method is idempotent and mirrors older API used by console_app.py and tests.
        It ensures internal structures (`segment_id`, `Phase_Numbered`, `phase_dict`, summaries)
        are created so callers can rely on them.
        """
        # Ensure segments exist
        if 'segment_id' not in getattr(self, 'df', pd.DataFrame()).columns:
            try:
                self.create_segments()
            except Exception:
                pass

        # add phase numbering if missing
        try:
            self.add_phase_numbering()
        except Exception:
            pass

        # build structures
        try:
            self.build_phase_dict()
        except Exception:
            pass
        try:
            self.build_summary()
        except Exception:
            pass

        # compute basic feature stats
        try:
            self.build_feature_stats()
        except Exception:
            pass

        return True

    def get_phase_dict(self):
        return getattr(self, 'phase_dict', None)

    def get_data_info(self) -> dict:
        """Return lightweight information about the loaded flight data for LLM prompts or UI.

        Fields:
          - columns: list of column names
          - has_altitude, has_ias, has_pitch, has_gnd
          - phases: detected phase names
        """
        info = {}
        df = getattr(self, 'df', None)
        info['columns'] = list(df.columns) if df is not None else []
        info['has_altitude'] = 'AltMSL' in info['columns']
        info['has_ias'] = 'IAS' in info['columns']
        info['has_pitch'] = 'Pitch' in info['columns']
        info['has_gnd'] = 'GndSpd' in info['columns']
        info['phases'] = []
        if df is not None and 'Phase' in df.columns:
            info['phases'] = [p for p in df['Phase'].dropna().unique().tolist()]
        return info


#---------------------MAIN BLOCK---------------------#
if __name__ == "__main__":

    FILE_PATH = "rule_labelled.csv"

    print("DEBUG: FILE_PATH repr ->", repr(FILE_PATH))
    print("DEBUG: FILE_PATH type ->", type(FILE_PATH))

    engine = DynamicFlightCalculator(FILE_PATH)

    try:
        engine.load_data()
    except Exception as e:
        print(f"Error loading file {FILE_PATH}: {e}")
        raise
	if "phase" in engine.df.columns and "Phase" not in engine.df.columns:
        	engine.df.rename(columns={"phase": "Phase"}, inplace=True)
    	engine.create_segments()
    	engine.add_phase_numbering()

    print("\nDynamic Flight Calculator Ready \n")
    print("DF head:\n", engine.df.head())

    while True:
        try:
            q = input("Ask> ")
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if q.strip().lower() in ["exit", "quit"]:
            print("Exiting...")
            break

        try:
            answer = engine.answer(q)
        except Exception as e:
            answer = f"Error processing query: {e}"

        print("\nAnswer:\n", answer, "\n")
