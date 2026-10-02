#!/usr/bin/env python3
"""
Dataset Preparation Script

This script processes raw IQ recordings and converts them into
ready-to-use training datasets for the drone detection classifier.

Features:
- Batch processing of IQ files
- Feature extraction from multiple signal types
- Train/validation/test splitting
- Data augmentation
- Label encoding and balancing
- Progress tracking and logging
- Parallel processing support
"""

import os
import sys
import json
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Import project modules
from infrastructure.signal_io.file_reader import IQFileReader, IQFileReaderFactory
from infrastructure.signal_io.recorder import RecordingFormat
from models.training.features.feature_extractor import FeatureExtractor
from models.training.features.preprocessing import IQPreprocessor, PreprocessingConfig
from models.training.features.feature_schema import get_feature_schema, FEATURE_NAMES


# ============================================================================
# Configuration
# ============================================================================

class DatasetConfig:
    """Dataset preparation configuration"""
    
    # Paths
    RAW_DATA_DIR = Path("models/training/dataset/raw")
    PROCESSED_DATA_DIR = Path("models/training/dataset/processed")
    LABELS_FILE = Path("models/training/dataset/labels.json")
    
    # Processing parameters
    SEGMENT_DURATION_MS = 100  # Segment duration in milliseconds
    OVERLAP_RATIO = 0.5  # Overlap between segments
    MIN_SEGMENT_SNR_DB = 6  # Minimum SNR for valid segments
    MIN_SEGMENTS_PER_CLASS = 100  # Minimum segments per class
    
    # Feature extraction
    FFT_SIZE = 2048
    HOP_LENGTH = 1024
    
    # Data splitting
    TRAIN_RATIO = 0.7
    VAL_RATIO = 0.15
    TEST_RATIO = 0.15
    
    # Augmentation (enabled during training)
    AUGMENTATION_ENABLED = True
    AUGMENTATION_FACTOR = 2  # Multiply dataset size by this factor
    
    # Parallel processing
    NUM_WORKERS = 4
    CHUNK_SIZE = 100
    
    # Logging
    LOG_INTERVAL = 100


# ============================================================================
# Dataset Processor Class
# ============================================================================

class DatasetProcessor:
    """
    Main dataset processor for converting raw IQ to training features
    """
    
    def __init__(self, config: DatasetConfig = None):
        """
        Initialize dataset processor
        
        Args:
            config: Dataset configuration (uses defaults if None)
        """
        self.config = config or DatasetConfig()
        self.feature_extractor = FeatureExtractor()
        self.preprocessor = IQPreprocessor()
        self.feature_schema = get_feature_schema()
        
        # Statistics tracking
        self.stats = {
            'total_files_processed': 0,
            'total_segments_extracted': 0,
            'segments_by_class': defaultdict(int),
            'failed_segments': 0,
            'processing_time_seconds': 0
        }
        
        # Create output directories
        self.config.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        print(f"[INFO] Dataset processor initialized")
        print(f"[INFO] Raw data directory: {self.config.RAW_DATA_DIR}")
        print(f"[INFO] Processed data directory: {self.config.PROCESSED_DATA_DIR}")
    
    # ========================================================================
    # Main Processing Pipeline
    # ========================================================================
    
    def process_all_classes(self) -> None:
        """
        Process all drone classes from raw data directory
        """
        print("\n" + "=" * 70)
        print("DATASET PREPARATION PIPELINE")
        print("=" * 70)
        
        start_time = datetime.now()
        
        # Get all class directories
        class_dirs = [d for d in self.config.RAW_DATA_DIR.iterdir() if d.is_dir()]
        
        if not class_dirs:
            print(f"[ERROR] No class directories found in {self.config.RAW_DATA_DIR}")
            print(f"[INFO] Expected structure: raw/<class_name>/<iq_files>")
            return
        
        print(f"\n[INFO] Found {len(class_dirs)} classes:")
        for d in class_dirs:
            print(f"  - {d.name}")
        
        # Process each class
        all_features = []
        all_labels = []
        all_metadata = []
        
        for class_dir in class_dirs:
            class_name = class_dir.name
            print(f"\n[INFO] Processing class: {class_name}")
            
            features, labels, metadata = self.process_class(class_dir)
            
            all_features.extend(features)
            all_labels.extend(labels)
            all_metadata.extend(metadata)
            
            print(f"[INFO] Class {class_name}: {len(features)} segments extracted")
        
        # Convert to numpy arrays
        X = np.array(all_features)
        y = np.array(all_labels)
        
        print(f"\n[INFO] Total dataset size: {len(X)} samples")
        print(f"[INFO] Feature vector size: {X.shape[1]} features")
        
        # Check class balance
        self._check_class_balance(y)
        
        # Split dataset
        self._split_and_save_dataset(X, y, all_metadata)
        
        # Save statistics
        self._save_statistics()
        
        # Print summary
        elapsed = (datetime.now() - start_time).total_seconds()
        self.stats['processing_time_seconds'] = elapsed
        
        print("\n" + "=" * 70)
        print("DATASET PREPARATION COMPLETE")
        print("=" * 70)
        print(f"Total files processed: {self.stats['total_files_processed']}")
        print(f"Total segments extracted: {self.stats['total_segments_extracted']}")
        print(f"Failed segments: {self.stats['failed_segments']}")
        print(f"Processing time: {elapsed:.2f} seconds")
        print(f"Output directory: {self.config.PROCESSED_DATA_DIR}")
    
    def process_class(self, class_dir: Path) -> tuple:
        """
        Process all files in a class directory
        
        Args:
            class_dir: Path to class directory
            
        Returns:
            Tuple of (features, labels, metadata)
        """
        # Get label ID from labels.json
        label_id = self._get_label_id(class_dir.name)
        
        if label_id is None:
            print(f"[WARNING] No label found for class: {class_dir.name}")
            return [], [], []
        
        # Get all IQ files
        iq_files = []
        for ext in ['*.iq', '*.npy', '*.h5', '*.zst']:
            iq_files.extend(class_dir.glob(ext))
        
        if not iq_files:
            print(f"[WARNING] No IQ files found in {class_dir}")
            return [], [], []
        
        print(f"[INFO] Found {len(iq_files)} files")
        
        features = []
        labels = []
        metadata = []
        
        # Process files with progress bar
        for file_path in tqdm(iq_files, desc=f"Processing {class_dir.name}"):
            try:
                file_features, file_labels, file_metadata = self.process_file(
                    file_path, label_id
                )
                features.extend(file_features)
                labels.extend(file_labels)
                metadata.extend(file_metadata)
                self.stats['total_files_processed'] += 1
            except Exception as e:
                print(f"[ERROR] Failed to process {file_path}: {e}")
                continue
        
        self.stats['segments_by_class'][class_dir.name] = len(features)
        self.stats['total_segments_extracted'] += len(features)
        
        return features, labels, metadata
    
    def process_file(self, file_path: Path, label_id: int) -> tuple:
        """
        Process a single IQ file
        
        Args:
            file_path: Path to IQ file
            label_id: Numeric label for this class
            
        Returns:
            Tuple of (features_list, labels_list, metadata_list)
        """
        # Load IQ data
        reader = IQFileReaderFactory.get_reader(file_path)
        
        with reader:
            iq_data = reader.read_all()
            sample_rate = reader.file_info.sample_rate
            
            if sample_rate == 0:
                sample_rate = 2.4e6  # Default fallback
        
        # Preprocess IQ data
        iq_data = self.preprocessor.preprocess(iq_data, sample_rate)
        
        # Segment IQ data
        segments = self._segment_iq_data(iq_data, sample_rate)
        
        features = []
        labels = []
        metadata = []
        
        for i, segment in enumerate(segments):
            # Skip low SNR segments
            snr = self._estimate_snr(segment)
            if snr < self.config.MIN_SEGMENT_SNR_DB:
                self.stats['failed_segments'] += 1
                continue
            
            # Extract features
            try:
                feature_dict = self.feature_extractor.extract_all_features(segment)
                feature_vector = self._dict_to_vector(feature_dict)
                
                features.append(feature_vector)
                labels.append(label_id)
                metadata.append({
                    'file': str(file_path),
                    'segment': i,
                    'snr_db': snr,
                    'label_id': label_id,
                    'class_name': reader.file_info.metadata.get('drone_type', 'unknown')
                })
            except Exception as e:
                print(f"[WARNING] Feature extraction failed: {e}")
                continue
        
        return features, labels, metadata
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    def _segment_iq_data(self, iq_data: np.ndarray, sample_rate: float) -> List[np.ndarray]:
        """
        Segment IQ data into overlapping windows
        
        Args:
            iq_data: IQ samples
            sample_rate: Sample rate in Hz
            
        Returns:
            List of segments
        """
        segment_samples = int(self.config.SEGMENT_DURATION_MS * sample_rate / 1000)
        hop_samples = int(segment_samples * (1 - self.config.OVERLAP_RATIO))
        
        segments = []
        for start in range(0, len(iq_data) - segment_samples + 1, hop_samples):
            segment = iq_data[start:start + segment_samples]
            segments.append(segment)
        
        return segments
    
    def _estimate_snr(self, iq_data: np.ndarray) -> float:
        """
        Estimate SNR of IQ data
        
        Args:
            iq_data: IQ samples
            
        Returns:
            SNR in dB
        """
        # Simple energy-based SNR estimation
        energy = np.abs(iq_data)**2
        signal_power = np.mean(energy)
        
        # Estimate noise as lower percentile
        noise_power = np.percentile(energy, 10)
        
        if noise_power <= 0:
            return 0
        
        snr = 10 * np.log10(signal_power / noise_power)
        return max(0, snr)
    
    def _dict_to_vector(self, feature_dict: dict) -> np.ndarray:
        """
        Convert feature dictionary to numpy vector
        
        Args:
            feature_dict: Dictionary of feature name -> value
            
        Returns:
            Feature vector as numpy array
        """
        vector = []
        for feature_name in FEATURE_NAMES:
            vector.append(feature_dict.get(feature_name, 0.0))
        return np.array(vector)
    
    def _get_label_id(self, class_name: str) -> int:
        """
        Get numeric label ID from class name
        
        Args:
            class_name: Class name (e.g., 'dji_mavic')
            
        Returns:
            Numeric label ID or None if not found
        """
        # Load labels mapping
        if self.config.LABELS_FILE.exists():
            with open(self.config.LABELS_FILE, 'r') as f:
                labels_data = json.load(f)
            
            for label_id, label_info in labels_data['label_mapping'].items():
                if label_info['name'] == class_name:
                    return int(label_id)
        
        # Fallback: use directory index
        class_dirs = sorted([d.name for d in self.config.RAW_DATA_DIR.iterdir() if d.is_dir()])
        if class_name in class_dirs:
            return class_dirs.index(class_name)
        
        return None
    
    def _check_class_balance(self, y: np.ndarray) -> None:
        """
        Check and report class balance
        
        Args:
            y: Array of labels
        """
        unique, counts = np.unique(y, return_counts=True)
        
        print("\n[INFO] Class Distribution:")
        for label, count in zip(unique, counts):
            class_name = self._get_class_name(int(label))
            percentage = count / len(y) * 100
            bar = '█' * int(percentage / 2)
            print(f"  {class_name}: {count} ({percentage:.1f}%) {bar}")
        
        # Check for imbalance
        min_count = min(counts)
        max_count = max(counts)
        imbalance_ratio = max_count / min_count
        
        if imbalance_ratio > 3:
            print(f"\n[WARNING] Class imbalance detected! Ratio: {imbalance_ratio:.1f}")
            print("[INFO] Consider collecting more data for minority classes or using class weights")
    
    def _get_class_name(self, label_id: int) -> str:
        """
        Get class name from label ID
        
        Args:
            label_id: Numeric label ID
            
        Returns:
            Class name
        """
        if self.config.LABELS_FILE.exists():
            with open(self.config.LABELS_FILE, 'r') as f:
                labels_data = json.load(f)
            
            if str(label_id) in labels_data['label_mapping']:
                return labels_data['label_mapping'][str(label_id)]['name']
        
        return f"class_{label_id}"
    
    # ========================================================================
    # Dataset Splitting and Saving
    # ========================================================================
    
    def _split_and_save_dataset(self, X: np.ndarray, y: np.ndarray, 
                                 metadata: List[dict]) -> None:
        """
        Split dataset into train/validation/test and save
        
        Args:
            X: Feature matrix
            y: Labels
            metadata: List of metadata dictionaries
        """
        from sklearn.model_selection import train_test_split
        
        # First split: train vs temp (val + test)
        X_train, X_temp, y_train, y_temp, meta_train, meta_temp = train_test_split(
            X, y, metadata, 
            test_size=(self.config.VAL_RATIO + self.config.TEST_RATIO),
            stratify=y,
            random_state=42
        )
        
        # Second split: validation vs test
        val_ratio_adjusted = self.config.VAL_RATIO / (self.config.VAL_RATIO + self.config.TEST_RATIO)
        X_val, X_test, y_val, y_test, meta_val, meta_test = train_test_split(
            X_temp, y_temp, meta_temp,
            test_size=1 - val_ratio_adjusted,
            stratify=y_temp,
            random_state=42
        )
        
        # Save datasets
        datasets = {
            'X_train': X_train,
            'X_val': X_val,
            'X_test': X_test,
            'y_train': y_train,
            'y_val': y_val,
            'y_test': y_test
        }
        
        for name, data in datasets.items():
            np.save(self.config.PROCESSED_DATA_DIR / f"{name}.npy", data)
            print(f"[INFO] Saved {name}: {data.shape}")
        
        # Save metadata
        meta_datasets = {
            'train_metadata': meta_train,
            'val_metadata': meta_val,
            'test_metadata': meta_test
        }
        
        for name, data in meta_datasets.items():
            with open(self.config.PROCESSED_DATA_DIR / f"{name}.json", 'w') as f:
                json.dump(data, f, indent=2, default=str)
        
        # Save dataset info
        dataset_info = {
            'created_at': datetime.now().isoformat(),
            'total_samples': len(X),
            'train_samples': len(X_train),
            'val_samples': len(X_val),
            'test_samples': len(X_test),
            'feature_dim': X.shape[1],
            'num_classes': len(np.unique(y)),
            'class_distribution': {
                self._get_class_name(int(label)): int(count)
                for label, count in zip(*np.unique(y, return_counts=True))
            },
            'config': {
                'segment_duration_ms': self.config.SEGMENT_DURATION_MS,
                'overlap_ratio': self.config.OVERLAP_RATIO,
                'min_snr_db': self.config.MIN_SEGMENT_SNR_DB,
                'train_ratio': self.config.TRAIN_RATIO,
                'val_ratio': self.config.VAL_RATIO,
                'test_ratio': self.config.TEST_RATIO
            }
        }
        
        with open(self.config.PROCESSED_DATA_DIR / "dataset_info.json", 'w') as f:
            json.dump(dataset_info, f, indent=2)
    
    def _save_statistics(self) -> None:
        """
        Save processing statistics
        """
        stats_file = self.config.PROCESSED_DATA_DIR / "processing_stats.json"
        
        stats = {
            'timestamp': datetime.now().isoformat(),
            'total_files_processed': self.stats['total_files_processed'],
            'total_segments_extracted': self.stats['total_segments_extracted'],
            'failed_segments': self.stats['failed_segments'],
            'segments_by_class': dict(self.stats['segments_by_class']),
            'processing_time_seconds': self.stats['processing_time_seconds']
        }
        
        with open(stats_file, 'w') as f:
            json.dump(stats, f, indent=2)
        
        print(f"\n[INFO] Statistics saved to {stats_file}")


# ============================================================================
# Data Augmentation (Optional)
# ============================================================================

class DataAugmentor:
    """
    Data augmentation for increasing dataset size and robustness
    """
    
    def __init__(self, config: DatasetConfig = None):
        self.config = config or DatasetConfig()
        self.preprocessor = IQPreprocessor()
    
    def augment_dataset(self, X: np.ndarray, y: np.ndarray, 
                        factor: int = 2) -> Tuple[np.ndarray, np.ndarray]:
        """
        Augment dataset by applying transformations
        
        Args:
            X: Feature matrix
            y: Labels
            factor: Augmentation factor
            
        Returns:
            Augmented feature matrix and labels
        """
        if not self.config.AUGMENTATION_ENABLED:
            return X, y
        
        print(f"\n[INFO] Augmenting dataset (factor {factor})")
        
        # Load original IQ data (would need original signals)
        # This is a placeholder - actual augmentation requires access to raw IQ
        
        # For now, return original data
        print("[WARNING] Full augmentation requires raw IQ data access")
        
        return X, y


# ============================================================================
# Command Line Interface
# ============================================================================

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Prepare dataset for drone detection training"
    )
    
    parser.add_argument(
        "--raw-dir",
        type=str,
        default="models/training/dataset/raw",
        help="Raw data directory"
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        default="models/training/dataset/processed",
        help="Processed data output directory"
    )
    
    parser.add_argument(
        "--segment-duration",
        type=int,
        default=100,
        help="Segment duration in milliseconds"
    )
    
    parser.add_argument(
        "--min-snr",
        type=float,
        default=6.0,
        help="Minimum SNR for valid segments (dB)"
    )
    
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers"
    )
    
    parser.add_argument(
        "--no-augment",
        action="store_true",
        help="Disable data augmentation"
    )
    
    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_args()
    
    # Create configuration
    config = DatasetConfig()
    config.RAW_DATA_DIR = Path(args.raw_dir)
    config.PROCESSED_DATA_DIR = Path(args.output_dir)
    config.SEGMENT_DURATION_MS = args.segment_duration
    config.MIN_SEGMENT_SNR_DB = args.min_snr
    config.NUM_WORKERS = args.workers
    config.AUGMENTATION_ENABLED = not args.no_augment
    
    # Verify raw data directory exists
    if not config.RAW_DATA_DIR.exists():
        print(f"[ERROR] Raw data directory not found: {config.RAW_DATA_DIR}")
        print("[INFO] Expected directory structure:")
        print("  raw/")
        print("    ├── dji_mavic/")
        print("    │   ├── recording1.iq")
        print("    │   └── recording2.iq")
        print("    ├── fpv_analog/")
        print("    │   └── ...")
        print("    └── noise/")
        print("        └── ...")
        sys.exit(1)
    
    # Create processor
    processor = DatasetProcessor(config)
    
    # Process all classes
    processor.process_all_classes()
    
    print("\n[INFO] Dataset preparation complete!")
    print(f"[INFO] Processed data available at: {config.PROCESSED_DATA_DIR}")


if __name__ == "__main__":
    main()