#!/usr/bin/env python3
"""
IQ Recording Analysis Script

This script analyzes IQ recording files to extract signal characteristics,
detect drone signatures, and generate comprehensive analysis reports.
Features include:
- Spectrum analysis and visualization
- Peak detection and classification
- Modulation recognition
- SNR and signal quality estimation
- Batch processing of multiple files
- Export of analysis results
- Comparison between recordings
- Drone signature matching
- Time-frequency analysis
"""

import argparse
import json
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict
import sys
from tqdm import tqdm

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.signal_io.file_reader import IQFileReaderFactory
from domain.algorithms.fft import compute_psd, compute_spectrogram
from domain.algorithms.peak_detection import detect_peaks, find_signal_regions
from domain.algorithms.psd import estimate_snr, estimate_noise_floor
from domain.algorithms.ml_classifier import MLClassifier
from domain.algorithms.spectrum_analyzer import SpectrumAnalyzer, ModulationFeatures


# ============================================================================
# Configuration
# ============================================================================

class AnalyzeConfig:
    """Analysis configuration"""
    
    # FFT settings
    FFT_SIZE: int = 2048
    OVERLAP: float = 0.5
    WINDOW: str = 'hann'
    
    # Peak detection
    PEAK_THRESHOLD_DB: float = 6.0
    PEAK_MIN_PROMINENCE: float = 3.0
    PEAK_MIN_DISTANCE: int = 10
    
    # Signal detection
    SIGNAL_THRESHOLD_SIGMA: float = 3.0
    MIN_SIGNAL_BANDWIDTH_HZ: float = 10e3
    
    # Output
    OUTPUT_DIR: str = "data/analysis"
    FIGURE_DPI: int = 150
    SAVE_PLOTS: bool = True
    SAVE_JSON: bool = True
    
    # Processing
    MAX_FILES: int = 100
    BATCH_SIZE: int = 10


# ============================================================================
# IQ Analyzer Class
# ============================================================================

class IQAnalyzer:
    """
    Comprehensive IQ recording analyzer
    
    Features:
    - Spectrum analysis
    - Peak detection
    - SNR estimation
    - Modulation classification
    - Drone signature matching
    - Report generation
    """
    
    def __init__(self, config: AnalyzeConfig = None):
        """
        Initialize analyzer
        
        Args:
            config: Analysis configuration
        """
        self.config = config or AnalyzeConfig()
        self.results = {}
        self.classifier = MLClassifier()
        self.spectrum_analyzer = SpectrumAnalyzer()
        
        # Create output directory
        self.output_dir = Path(self.config.OUTPUT_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        print("=" * 60)
        print("IQ Recording Analyzer")
        print("=" * 60)
    
    # ========================================================================
    # File Analysis
    # ========================================================================
    
    async def analyze_file(self, file_path: Path, save_results: bool = True) -> Dict[str, Any]:
        """
        Analyze a single IQ file
        
        Args:
            file_path: Path to IQ file
            save_results: Whether to save results
            
        Returns:
            Analysis results dictionary
        """
        print(f"\n📊 Analyzing: {file_path.name}")
        
        # Load IQ data
        iq_data, metadata = await self._load_iq_file(file_path)
        
        if iq_data is None:
            return {'error': 'Failed to load file'}
        
        sample_rate = metadata.get('sample_rate', 10e6)
        
        # Perform analysis
        results = {
            'file_info': {
                'name': file_path.name,
                'size_bytes': file_path.stat().st_size,
                'sample_rate_hz': sample_rate,
                'num_samples': len(iq_data),
                'duration_seconds': len(iq_data) / sample_rate
            },
            'statistics': self._compute_statistics(iq_data),
            'spectrum': await self._analyze_spectrum(iq_data, sample_rate),
            'peaks': await self._analyze_peaks(iq_data, sample_rate),
            'signal': await self._analyze_signal(iq_data, sample_rate),
            'modulation': await self._classify_modulation(iq_data, sample_rate),
            'drone_matches': await self._match_drone_signatures(iq_data, sample_rate),
            'timestamp': datetime.now().isoformat()
        }
        
        # Store results
        self.results[file_path.stem] = results
        
        # Save results
        if save_results:
            await self._save_results(file_path.stem, results)
            await self._generate_plots(file_path.stem, iq_data, sample_rate, results)
        
        # Print summary
        self._print_summary(results)
        
        return results
    
    async def analyze_directory(self, directory: Path, pattern: str = "*.iq") -> List[Dict]:
        """
        Analyze all IQ files in directory
        
        Args:
            directory: Directory path
            pattern: File pattern
            
        Returns:
            List of analysis results
        """
        print(f"\n📁 Analyzing directory: {directory}")
        
        files = list(directory.glob(pattern))
        files = files[:self.config.MAX_FILES]
        
        print(f"Found {len(files)} files to analyze")
        
        results = []
        for file_path in tqdm(files, desc="Analyzing files"):
            result = await self.analyze_file(file_path, save_results=True)
            results.append(result)
        
        # Generate summary report
        await self._generate_summary_report(results, directory)
        
        return results
    
    # ========================================================================
    # Core Analysis Methods
    # ========================================================================
    
    def _compute_statistics(self, iq_data: np.ndarray) -> Dict[str, Any]:
        """Compute basic signal statistics"""
        
        real = np.real(iq_data)
        imag = np.imag(iq_data)
        
        stats = {
            'mean_real': float(np.mean(real)),
            'mean_imag': float(np.mean(imag)),
            'std_real': float(np.std(real)),
            'std_imag': float(np.std(imag)),
            'max_abs': float(np.max(np.abs(iq_data))),
            'min_abs': float(np.min(np.abs(iq_data))),
            'mean_power_dbm': 10 * np.log10(np.mean(np.abs(iq_data)**2) + 1e-12),
            'peak_power_dbm': 10 * np.log10(np.max(np.abs(iq_data)**2) + 1e-12),
            'crest_factor': float(np.max(np.abs(iq_data)) / (np.sqrt(np.mean(np.abs(iq_data)**2)) + 1e-12)),
            'skewness': float(np.mean((real - np.mean(real))**3) / (np.std(real)**3 + 1e-12)),
            'kurtosis': float(np.mean((real - np.mean(real))**4) / (np.std(real)**4 + 1e-12))
        }
        
        return stats
    
    async def _analyze_spectrum(self, iq_data: np.ndarray, sample_rate: float) -> Dict[str, Any]:
        """Analyze power spectrum"""
        
        # Compute PSD
        frequencies, psd = compute_psd(iq_data, sample_rate, self.config.FFT_SIZE, self.config.OVERLAP)
        psd_db = 10 * np.log10(psd + 1e-12)
        
        # Estimate noise floor
        noise_floor = estimate_noise_floor(psd_db)
        
        # Estimate SNR
        snr = estimate_snr(psd_db, noise_floor)
        
        # Find peak
        peak_idx = np.argmax(psd_db)
        peak_freq = frequencies[peak_idx]
        peak_power = psd_db[peak_idx]
        
        # Calculate occupied bandwidth (99% power)
        cum_power = np.cumsum(psd)
        total_power = cum_power[-1]
        lower_idx = np.argmax(cum_power >= 0.005 * total_power)
        upper_idx = np.argmax(cum_power >= 0.995 * total_power)
        occupied_bw = frequencies[upper_idx] - frequencies[lower_idx]
        
        # Calculate spectral flatness
        geometric_mean = np.exp(np.mean(np.log(psd + 1e-12)))
        arithmetic_mean = np.mean(psd)
        spectral_flatness = geometric_mean / arithmetic_mean if arithmetic_mean > 0 else 0
        
        return {
            'noise_floor_dbm': float(noise_floor),
            'snr_db': float(snr),
            'peak_frequency_hz': float(peak_freq),
            'peak_power_dbm': float(peak_power),
            'occupied_bandwidth_hz': float(occupied_bw),
            'spectral_flatness': float(spectral_flatness),
            'frequency_range_hz': [float(frequencies[0]), float(frequencies[-1])]
        }
    
    async def _analyze_peaks(self, iq_data: np.ndarray, sample_rate: float) -> Dict[str, Any]:
        """Detect and analyze spectral peaks"""
        
        # Compute PSD
        frequencies, psd = compute_psd(iq_data, sample_rate, self.config.FFT_SIZE, self.config.OVERLAP)
        psd_db = 10 * np.log10(psd + 1e-12)
        
        # Detect peaks
        peaks = detect_peaks(
            psd_db,
            threshold=self.config.PEAK_THRESHOLD_DB,
            prominence=self.config.PEAK_MIN_PROMINENCE,
            distance=self.config.PEAK_MIN_DISTANCE
        )
        
        peak_list = []
        for peak in peaks:
            peak_list.append({
                'frequency_hz': float(frequencies[peak]),
                'frequency_mhz': float(frequencies[peak] / 1e6),
                'power_dbm': float(psd_db[peak]),
                'index': int(peak)
            })
        
        # Find signal regions
        signal_mask = psd_db > (np.percentile(psd_db, 10) + self.config.PEAK_THRESHOLD_DB)
        signal_regions = find_signal_regions(frequencies, signal_mask)
        
        return {
            'num_peaks': len(peaks),
            'peaks': peak_list,
            'signal_regions': [
                {'start_hz': start, 'end_hz': end, 'bandwidth_hz': end - start}
                for start, end in signal_regions
            ],
            'strongest_peak': peak_list[0] if peak_list else None
        }
    
    async def _analyze_signal(self, iq_data: np.ndarray, sample_rate: float) -> Dict[str, Any]:
        """Analyze time-domain signal characteristics"""
        
        # Compute envelope
        envelope = np.abs(iq_data)
        
        # Analyze envelope statistics
        envelope_mean = np.mean(envelope)
        envelope_std = np.std(envelope)
        envelope_max = np.max(envelope)
        
        # Detect bursts
        threshold = envelope_mean + 2 * envelope_std
        above_threshold = envelope > threshold
        
        bursts = []
        in_burst = False
        start_idx = 0
        
        for i, is_above in enumerate(above_threshold):
            if is_above and not in_burst:
                in_burst = True
                start_idx = i
            elif not is_above and in_burst:
                in_burst = False
                bursts.append({
                    'start_sample': start_idx,
                    'end_sample': i,
                    'duration_seconds': (i - start_idx) / sample_rate,
                    'peak_power': float(np.max(envelope[start_idx:i]))
                })
        
        # Calculate duty cycle
        total_samples = len(iq_data)
        burst_samples = sum(b['end_sample'] - b['start_sample'] for b in bursts)
        duty_cycle = burst_samples / total_samples if total_samples > 0 else 0
        
        return {
            'envelope_mean': float(envelope_mean),
            'envelope_std': float(envelope_std),
            'envelope_peak': float(envelope_max),
            'peak_to_average_ratio': float(envelope_max / (envelope_mean + 1e-12)),
            'burst_count': len(bursts),
            'duty_cycle': float(duty_cycle),
            'bursts': bursts[:10]  # Limit to first 10 bursts
        }
    
    async def _classify_modulation(self, iq_data: np.ndarray, sample_rate: float) -> Dict[str, Any]:
        """Classify modulation type"""
        
        modulation = self.spectrum_analyzer.estimate_modulation(iq_data)
        
        return {
            'type': modulation.modulation_type.value,
            'confidence': modulation.confidence,
            'symbol_rate': modulation.symbol_rate,
            'carrier_offset_hz': modulation.carrier_offset,
            'evm_percent': modulation.evm * 100,
            'phase_noise_dbc': modulation.phase_noise
        }
    
    async def _match_drone_signatures(self, iq_data: np.ndarray, sample_rate: float) -> List[Dict]:
        """Match against known drone signatures"""
        
        # Extract features for classification
        features = await self._extract_features(iq_data, sample_rate)
        
        # Get predictions
        try:
            predictions = self.classifier.predict_proba(features.reshape(1, -1))[0]
            
            # Get top matches
            top_indices = np.argsort(predictions)[-5:][::-1]
            class_names = self.classifier.classes_
            
            matches = []
            for idx in top_indices:
                if predictions[idx] > 0.3:  # Only include matches above threshold
                    matches.append({
                        'drone_type': class_names[idx],
                        'confidence': float(predictions[idx])
                    })
            
            return matches
            
        except Exception as e:
            return [{'error': str(e)}]
    
    async def _extract_features(self, iq_data: np.ndarray, sample_rate: float) -> np.ndarray:
        """Extract features for classification"""
        
        # This would call the feature extractor
        # Placeholder - return zeros
        return np.zeros(46)
    
    # ========================================================================
    # Visualization
    # ========================================================================
    
    async def _generate_plots(self, file_stem: str, iq_data: np.ndarray, 
                               sample_rate: float, results: Dict):
        """Generate analysis plots"""
        
        if not self.config.SAVE_PLOTS:
            return
        
        plot_dir = self.output_dir / file_stem
        plot_dir.mkdir(parents=True, exist_ok=True)
        
        # Spectrum plot
        await self._plot_spectrum(iq_data, sample_rate, results, plot_dir / "spectrum.png")
        
        # Spectrogram
        await self._plot_spectrogram(iq_data, sample_rate, plot_dir / "spectrogram.png")
        
        # Constellation diagram
        await self._plot_constellation(iq_data, plot_dir / "constellation.png")
        
        # Time domain
        await self._plot_time_domain(iq_data, sample_rate, plot_dir / "time_domain.png")
        
        print(f"  Plots saved to: {plot_dir}")
    
    async def _plot_spectrum(self, iq_data: np.ndarray, sample_rate: float,
                              results: Dict, output_path: Path):
        """Plot power spectrum"""
        
        frequencies, psd = compute_psd(iq_data, sample_rate, self.config.FFT_SIZE, self.config.OVERLAP)
        psd_db = 10 * np.log10(psd + 1e-12)
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        ax.plot(frequencies / 1e6, psd_db, 'b-', linewidth=1, alpha=0.7)
        
        # Mark peaks
        peaks = results.get('peaks', {}).get('peaks', [])
        for peak in peaks:
            ax.axvline(x=peak['frequency_mhz'], color='r', linestyle='--', alpha=0.5, linewidth=1)
            ax.plot(peak['frequency_mhz'], peak['power_dbm'], 'ro', markersize=8)
        
        # Mark noise floor
        noise_floor = results.get('spectrum', {}).get('noise_floor_dbm', -100)
        ax.axhline(y=noise_floor, color='g', linestyle='--', alpha=0.5, label=f'Noise Floor: {noise_floor:.1f} dBm')
        
        ax.set_xlabel('Frequency (MHz)')
        ax.set_ylabel('Power (dBm)')
        ax.set_title(f'Spectrum Analysis - {results["file_info"]["name"]}')
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=self.config.FIGURE_DPI, bbox_inches='tight')
        plt.close()
    
    async def _plot_spectrogram(self, iq_data: np.ndarray, sample_rate: float, output_path: Path):
        """Plot spectrogram"""
        
        f, t, Sxx = compute_spectrogram(iq_data, sample_rate, nperseg=512, noverlap=256)
        Sxx_db = 10 * np.log10(Sxx + 1e-12)
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        im = ax.pcolormesh(t, f / 1e6, Sxx_db, shading='gouraud', cmap='viridis')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Frequency (MHz)')
        ax.set_title('Spectrogram')
        plt.colorbar(im, ax=ax, label='Power (dB)')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=self.config.FIGURE_DPI, bbox_inches='tight')
        plt.close()
    
    async def _plot_constellation(self, iq_data: np.ndarray, output_path: Path):
        """Plot constellation diagram"""
        
        # Take a subset for visibility
        samples = iq_data[:min(5000, len(iq_data))]
        
        fig, ax = plt.subplots(figsize=(8, 8))
        
        ax.scatter(np.real(samples), np.imag(samples), s=1, alpha=0.5, c='b')
        ax.set_xlabel('In-phase')
        ax.set_ylabel('Quadrature')
        ax.set_title('Constellation Diagram')
        ax.grid(True, alpha=0.3)
        ax.axis('equal')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=self.config.FIGURE_DPI, bbox_inches='tight')
        plt.close()
    
    async def _plot_time_domain(self, iq_data: np.ndarray, sample_rate: float, output_path: Path):
        """Plot time domain signal"""
        
        # Take a subset for visibility (first 1000 samples)
        samples = iq_data[:min(1000, len(iq_data))]
        t = np.arange(len(samples)) / sample_rate * 1000  # milliseconds
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
        
        # Real part
        ax1.plot(t, np.real(samples), 'b-', linewidth=0.5)
        ax1.set_ylabel('In-phase')
        ax1.set_title('Time Domain Signal')
        ax1.grid(True, alpha=0.3)
        
        # Imaginary part
        ax2.plot(t, np.imag(samples), 'r-', linewidth=0.5)
        ax2.set_xlabel('Time (ms)')
        ax2.set_ylabel('Quadrature')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=self.config.FIGURE_DPI, bbox_inches='tight')
        plt.close()
    
    # ========================================================================
    # Results Management
    # ========================================================================
    
    async def _save_results(self, file_stem: str, results: Dict):
        """Save analysis results to JSON"""
        
        if not self.config.SAVE_JSON:
            return
        
        json_path = self.output_dir / f"{file_stem}_analysis.json"
        
        with open(json_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"  Results saved to: {json_path}")
    
    async def _generate_summary_report(self, results: List[Dict], directory: Path):
        """Generate summary report for batch analysis"""
        
        summary = {
            'analysis_date': datetime.now().isoformat(),
            'directory': str(directory),
            'files_analyzed': len(results),
            'summary_statistics': self._aggregate_results(results),
            'drone_detections': self._aggregate_drone_detections(results),
            'file_results': results
        }
        
        # Save summary
        summary_path = self.output_dir / f"summary_{directory.name}.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        # Generate HTML report
        await self._generate_html_report(summary, directory)
        
        print(f"\n📊 Summary report saved to: {summary_path}")
    
    def _aggregate_results(self, results: List[Dict]) -> Dict:
        """Aggregate statistics across files"""
        
        total_duration = 0
        total_samples = 0
        snr_values = []
        peak_powers = []
        
        for result in results:
            if 'error' in result:
                continue
            
            info = result.get('file_info', {})
            total_duration += info.get('duration_seconds', 0)
            total_samples += info.get('num_samples', 0)
            
            spectrum = result.get('spectrum', {})
            if 'snr_db' in spectrum:
                snr_values.append(spectrum['snr_db'])
            if 'peak_power_dbm' in spectrum:
                peak_powers.append(spectrum['peak_power_dbm'])
        
        return {
            'total_files': len(results),
            'successful_analyses': len([r for r in results if 'error' not in r]),
            'total_duration_seconds': total_duration,
            'total_samples': total_samples,
            'avg_snr_db': np.mean(snr_values) if snr_values else 0,
            'avg_peak_power_dbm': np.mean(peak_powers) if peak_powers else 0,
            'min_snr_db': np.min(snr_values) if snr_values else 0,
            'max_snr_db': np.max(snr_values) if snr_values else 0
        }
    
    def _aggregate_drone_detections(self, results: List[Dict]) -> Dict:
        """Aggregate drone detection statistics"""
        
        drone_counts = defaultdict(int)
        total_detections = 0
        
        for result in results:
            matches = result.get('drone_matches', [])
            for match in matches:
                drone_type = match.get('drone_type', 'unknown')
                drone_counts[drone_type] += 1
                total_detections += 1
        
        return {
            'total_detections': total_detections,
            'by_drone_type': dict(drone_counts),
            'detection_rate': total_detections / len(results) if results else 0
        }
    
    async def _generate_html_report(self, summary: Dict, directory: Path):
        """Generate HTML summary report"""
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>IQ Analysis Report - {directory.name}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1, h2 {{ color: #333; }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        .summary-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }}
        .summary-card .value {{
            font-size: 28px;
            font-weight: bold;
        }}
        .summary-card .label {{
            font-size: 12px;
            opacity: 0.9;
            margin-top: 5px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #4facfe;
            color: white;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #888;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>IQ Recording Analysis Report</h1>
        <p><strong>Directory:</strong> {directory}</p>
        <p><strong>Analysis Date:</strong> {summary['analysis_date']}</p>
        <p><strong>Files Analyzed:</strong> {summary['files_analyzed']}</p>
        
        <h2>Summary Statistics</h2>
        <div class="summary-grid">
            <div class="summary-card">
                <div class="value">{summary['summary_statistics']['total_duration_seconds']:.1f}</div>
                <div class="label">Total Duration (s)</div>
            </div>
            <div class="summary-card">
                <div class="value">{summary['summary_statistics']['total_samples']:,}</div>
                <div class="label">Total Samples</div>
            </div>
            <div class="summary-card">
                <div class="value">{summary['summary_statistics']['avg_snr_db']:.1f}</div>
                <div class="label">Avg SNR (dB)</div>
            </div>
            <div class="summary-card">
                <div class="value">{summary['summary_statistics']['avg_peak_power_dbm']:.1f}</div>
                <div class="label">Avg Peak Power (dBm)</div>
            </div>
        </div>
        
        <h2>Drone Detections</h2>
        <div class="summary-grid">
            <div class="summary-card">
                <div class="value">{summary['drone_detections']['total_detections']}</div>
                <div class="label">Total Detections</div>
            </div>
            <div class="summary-card">
                <div class="value">{summary['drone_detections']['detection_rate']:.1%}</div>
                <div class="label">Detection Rate</div>
            </div>
        </div>
        
        <h3>Detections by Drone Type</h3>
        <table>
            <thead>
                <tr><th>Drone Type</th><th>Count</th></tr>
            </thead>
            <tbody>
        """
        
        for drone_type, count in summary['drone_detections']['by_drone_type'].items():
            html_content += f"<tr><td>{drone_type}</td><td>{count}</td></tr>"
        
        html_content += f"""
            </tbody>
        </table>
        
        <h2>Individual File Results</h2>
        <table>
            <thead>
                <tr><th>File</th><th>Duration (s)</th><th>SNR (dB)</th><th>Peak Power (dBm)</th><th>Drone Match</th></tr>
            </thead>
            <tbody>
        """
        
        for result in summary['file_results']:
            if 'error' in result:
                continue
            info = result.get('file_info', {})
            spectrum = result.get('spectrum', {})
            matches = result.get('drone_matches', [])
            top_match = matches[0]['drone_type'] if matches else 'None'
            
            html_content += f"""
                <tr>
                    <td>{info.get('name', 'Unknown')}</td>
                    <td>{info.get('duration_seconds', 0):.2f}</td>
                    <td>{spectrum.get('snr_db', 0):.1f}</td>
                    <td>{spectrum.get('peak_power_dbm', 0):.1f}</td>
                    <td>{top_match}</td>
                </tr>
            """
        
        html_content += f"""
            </tbody>
        </table>
        
        <div class="footer">
            <p>Generated by Drone Detection System IQ Analyzer</p>
        </div>
    </div>
</body>
</html>
        """
        
        html_path = self.output_dir / f"report_{directory.name}.html"
        with open(html_path, 'w') as f:
            f.write(html_content)
        
        print(f"  HTML report saved to: {html_path}")
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    async def _load_iq_file(self, file_path: Path) -> Tuple[Optional[np.ndarray], Dict]:
        """Load IQ file and metadata"""
        
        try:
            reader = IQFileReaderFactory.get_reader(file_path)
            
            async with reader:
                iq_data = await reader.read_all()
                metadata = reader.file_info.to_dict() if hasattr(reader.file_info, 'to_dict') else {}
                metadata['sample_rate'] = getattr(reader.file_info, 'sample_rate', 10e6)
            
            return iq_data, metadata
            
        except Exception as e:
            print(f"  Error loading {file_path}: {e}")
            return None, {}
    
    def _print_summary(self, results: Dict):
        """Print analysis summary"""
        
        if 'error' in results:
            print(f"  ❌ Analysis failed: {results['error']}")
            return
        
        info = results.get('file_info', {})
        spectrum = results.get('spectrum', {})
        peaks = results.get('peaks', {})
        matches = results.get('drone_matches', [])
        
        print(f"  Duration: {info.get('duration_seconds', 0):.2f}s")
        print(f"  SNR: {spectrum.get('snr_db', 0):.1f} dB")
        print(f"  Peak Power: {spectrum.get('peak_power_dbm', 0):.1f} dBm")
        print(f"  Peaks Detected: {peaks.get('num_peaks', 0)}")
        
        if matches:
            top_match = matches[0]
            print(f"  🎯 Drone Match: {top_match.get('drone_type', 'Unknown')} "
                  f"(confidence: {top_match.get('confidence', 0):.1%})")
        else:
            print(f"  🤔 No drone matches found")
    
    async def compare_recordings(self, file_paths: List[Path]) -> Dict:
        """
        Compare multiple recordings
        
        Args:
            file_paths: List of file paths to compare
            
        Returns:
            Comparison results
        """
        print(f"\n📊 Comparing {len(file_paths)} recordings")
        
        results = []
        for file_path in file_paths:
            result = await self.analyze_file(file_path, save_results=False)
            results.append(result)
        
        # Extract key metrics for comparison
        comparison = {
            'files': [],
            'summary': {
                'best_snr': {'file': None, 'value': -np.inf},
                'best_peak_power': {'file': None, 'value': -np.inf},
                'most_peaks': {'file': None, 'value': 0}
            }
        }
        
        for result in results:
            if 'error' in result:
                continue
            
            file_name = result['file_info']['name']
            snr = result['spectrum'].get('snr_db', 0)
            peak_power = result['spectrum'].get('peak_power_dbm', -np.inf)
            num_peaks = result['peaks'].get('num_peaks', 0)
            
            comparison['files'].append({
                'name': file_name,
                'snr_db': snr,
                'peak_power_dbm': peak_power,
                'num_peaks': num_peaks,
                'drone_matches': result.get('drone_matches', [])
            })
            
            if snr > comparison['summary']['best_snr']['value']:
                comparison['summary']['best_snr'] = {'file': file_name, 'value': snr}
            
            if peak_power > comparison['summary']['best_peak_power']['value']:
                comparison['summary']['best_peak_power'] = {'file': file_name, 'value': peak_power}
            
            if num_peaks > comparison['summary']['most_peaks']['value']:
                comparison['summary']['most_peaks'] = {'file': file_name, 'value': num_peaks}
        
        # Save comparison
        comp_path = self.output_dir / "comparison.json"
        with open(comp_path, 'w') as f:
            json.dump(comparison, f, indent=2, default=str)
        
        print(f"\n✅ Comparison saved to: {comp_path}")
        
        return comparison


# ============================================================================
# Main Function
# ============================================================================

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Analyze IQ recording files"
    )
    
    parser.add_argument(
        "input",
        type=str,
        help="Input file or directory path"
    )
    
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default="data/analysis",
        help="Output directory for results"
    )
    
    parser.add_argument(
        "--pattern", "-p",
        type=str,
        default="*.iq",
        help="File pattern for directory processing"
    )
    
    parser.add_argument(
        "--compare", "-c",
        nargs="+",
        help="Compare multiple files (provide file paths)"
    )
    
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Disable plot generation"
    )
    
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Disable JSON output"
    )
    
    args = parser.parse_args()
    
    # Configure analyzer
    config = AnalyzeConfig()
    config.OUTPUT_DIR = args.output_dir
    config.SAVE_PLOTS = not args.no_plots
    config.SAVE_JSON = not args.no_json
    
    analyzer = IQAnalyzer(config)
    
    input_path = Path(args.input)
    
    if args.compare:
        # Compare mode
        file_paths = [Path(f) for f in args.compare]
        await analyzer.compare_recordings(file_paths)
    
    elif input_path.is_file():
        # Single file mode
        await analyzer.analyze_file(input_path)
    
    elif input_path.is_dir():
        # Directory mode
        await analyzer.analyze_directory(input_path, args.pattern)
    
    else:
        print(f"Invalid input: {input_path}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())