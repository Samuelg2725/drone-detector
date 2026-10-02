#!/usr/bin/env python3
"""
Model Export Script

This script exports a trained model with all necessary artifacts:
- Model pickle file (classifier.pkl)
- Scaler for feature normalization
- Model metadata and configuration
- Feature names and importance
- Version tracking
- Multiple format support (pickle, joblib, ONNX)
"""

import os
import sys
import json
import pickle
import joblib
import argparse
import numpy as np
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Import project modules
from models.training.features.feature_schema import get_feature_schema, FEATURE_NAMES
from models.training.scripts.train_model import DRONE_CLASSES


# ============================================================================
# Configuration
# ============================================================================

class ExportConfig:
    """Model export configuration"""
    
    # Paths
    MODELS_DIR = Path("models")
    TRAINING_DIR = Path("models/training")
    EXPORT_DIR = Path("models/exports")
    
    # Export formats
    FORMATS = ['pickle', 'joblib', 'onnx']
    DEFAULT_FORMAT = 'pickle'
    
    # Versioning
    VERSION_FILE = "model_version.txt"
    VERSION = "2.0.0"
    
    # Metadata
    INCLUDE_METADATA = True
    INCLUDE_FEATURE_IMPORTANCE = True
    INCLUDE_SCALER = True
    INCLUDE_PERFORMANCE_METRICS = True


# ============================================================================
# Model Exporter Class
# ============================================================================

class ModelExporter:
    """
    Export trained model with all necessary artifacts
    """
    
    def __init__(self, config: ExportConfig = None):
        """
        Initialize model exporter
        
        Args:
            config: Export configuration
        """
        self.config = config or ExportConfig()
        self.model = None
        self.scaler = None
        self.metadata = {}
        self.feature_importance = None
        
        # Create export directory
        self.config.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        
        print("=" * 70)
        print("MODEL EXPORT UTILITY")
        print("=" * 70)
    
    def load_model(self, model_path: str = None, scaler_path: str = None) -> None:
        """
        Load trained model and scaler
        
        Args:
            model_path: Path to model file
            scaler_path: Path to scaler file
        """
        print("\n[1] Loading trained model...")
        
        if model_path is None:
            model_path = self.config.MODELS_DIR / "classifier.pkl"
        
        if not Path(model_path).exists():
            raise FileNotFoundError(f"Model not found: {model_path}")
        
        # Load model based on file extension
        model_path = Path(model_path)
        
        if model_path.suffix == '.pkl':
            with open(model_path, 'rb') as f:
                self.model = pickle.load(f)
        elif model_path.suffix == '.joblib':
            self.model = joblib.load(model_path)
        else:
            with open(model_path, 'rb') as f:
                self.model = pickle.load(f)
        
        print(f"  Model loaded: {model_path}")
        print(f"  Model type: {type(self.model).__name__}")
        
        # Load scaler if available
        if self.config.INCLUDE_SCALER:
            if scaler_path is None:
                scaler_path = self.config.MODELS_DIR / "scaler.pkl"
            
            if Path(scaler_path).exists():
                with open(scaler_path, 'rb') as f:
                    self.scaler = pickle.load(f)
                print(f"  Scaler loaded: {scaler_path}")
            else:
                print("  [WARNING] Scaler not found")
    
    def load_metadata(self, metadata_path: str = None) -> None:
        """
        Load model metadata
        
        Args:
            metadata_path: Path to metadata JSON file
        """
        print("\n[2] Loading model metadata...")
        
        if metadata_path is None:
            metadata_path = self.config.MODELS_DIR / "model_metadata.json"
        
        if Path(metadata_path).exists():
            with open(metadata_path, 'r') as f:
                self.metadata = json.load(f)
            print(f"  Metadata loaded: {metadata_path}")
        else:
            print("  [WARNING] Metadata not found, creating default")
            self.metadata = self._create_default_metadata()
    
    def load_feature_importance(self, importance_path: str = None) -> None:
        """
        Load feature importance data
        
        Args:
            importance_path: Path to feature importance JSON file
        """
        print("\n[3] Loading feature importance...")
        
        if importance_path is None:
            importance_path = self.config.MODELS_DIR / "feature_importance.json"
        
        if Path(importance_path).exists():
            with open(importance_path, 'r') as f:
                importance_data = json.load(f)
                self.feature_importance = importance_data.get('feature_importance', {})
            print(f"  Feature importance loaded: {importance_path}")
        else:
            print("  [WARNING] Feature importance not found, calculating from model")
            self._calculate_feature_importance()
    
    def _create_default_metadata(self) -> Dict[str, Any]:
        """
        Create default metadata dictionary
        
        Returns:
            Default metadata
        """
        return {
            'model_name': 'Drone Detection Classifier',
            'version': self.config.VERSION,
            'algorithm': type(self.model).__name__,
            'export_date': datetime.now().isoformat(),
            'num_features': len(FEATURE_NAMES),
            'feature_names': FEATURE_NAMES,
            'num_classes': len(DRONE_CLASSES),
            'class_names': DRONE_CLASSES,
            'hyperparameters': {},
            'performance': {}
        }
    
    def _calculate_feature_importance(self) -> None:
        """
        Calculate feature importance from model if available
        """
        if hasattr(self.model, 'feature_importances_'):
            importances = self.model.feature_importances_
            self.feature_importance = {
                name: float(imp) 
                for name, imp in zip(FEATURE_NAMES, importances)
            }
            print(f"  Calculated feature importance from model")
        else:
            self.feature_importance = {name: 0.0 for name in FEATURE_NAMES}
            print("  [WARNING] Model does not support feature importance")
    
    # ========================================================================
    # Export Methods
    # ========================================================================
    
    def export_pickle(self, output_path: Path) -> None:
        """
        Export model as pickle file
        
        Args:
            output_path: Output file path
        """
        with open(output_path, 'wb') as f:
            pickle.dump(self.model, f)
        print(f"  Pickle export: {output_path}")
    
    def export_joblib(self, output_path: Path) -> None:
        """
        Export model as joblib file
        
        Args:
            output_path: Output file path
        """
        joblib.dump(self.model, output_path)
        print(f"  Joblib export: {output_path}")
    
    def export_onnx(self, output_path: Path) -> None:
        """
        Export model as ONNX format
        
        Args:
            output_path: Output file path
        """
        try:
            import skl2onnx
            from skl2onnx import convert_sklearn
            from skl2onnx.common.data_types import FloatTensorType
            
            # Define input type
            initial_type = [('float_input', FloatTensorType([None, len(FEATURE_NAMES)]))]
            
            # Convert model
            onnx_model = convert_sklearn(self.model, initial_types=initial_type)
            
            # Save ONNX model
            with open(output_path, 'wb') as f:
                f.write(onnx_model.SerializeToString())
            
            print(f"  ONNX export: {output_path}")
        except ImportError:
            print("  [WARNING] ONNX export failed: skl2onnx not installed")
        except Exception as e:
            print(f"  [WARNING] ONNX export failed: {e}")
    
    def export_scaler(self, output_path: Path) -> None:
        """
        Export scaler as pickle file
        
        Args:
            output_path: Output file path
        """
        if self.scaler is not None:
            with open(output_path, 'wb') as f:
                pickle.dump(self.scaler, f)
            print(f"  Scaler exported: {output_path}")
        else:
            print("  [WARNING] No scaler to export")
    
    def export_metadata(self, output_path: Path) -> None:
        """
        Export metadata as JSON file
        
        Args:
            output_path: Output file path
        """
        # Update metadata with latest information
        self.metadata.update({
            'export_date': datetime.now().isoformat(),
            'export_timestamp': datetime.now().timestamp(),
            'export_format': 'json',
            'file_hash': None  # Will be calculated after export
        })
        
        with open(output_path, 'w') as f:
            json.dump(self.metadata, f, indent=2)
        
        print(f"  Metadata exported: {output_path}")
    
    def export_feature_importance(self, output_path: Path) -> None:
        """
        Export feature importance as JSON file
        
        Args:
            output_path: Output file path
        """
        # Sort by importance
        sorted_importance = sorted(
            self.feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        importance_data = {
            'model_name': self.metadata.get('model_name', 'Drone Detection Classifier'),
            'version': self.config.VERSION,
            'export_date': datetime.now().isoformat(),
            'total_features': len(self.feature_importance),
            'feature_importance': self.feature_importance,
            'top_10_features': [
                {'name': name, 'importance': imp}
                for name, imp in sorted_importance[:10]
            ],
            'cumulative_importance': self._calculate_cumulative_importance(sorted_importance)
        }
        
        with open(output_path, 'w') as f:
            json.dump(importance_data, f, indent=2)
        
        print(f"  Feature importance exported: {output_path}")
    
    def _calculate_cumulative_importance(self, sorted_importance: list) -> Dict[str, float]:
        """
        Calculate cumulative importance for different feature counts
        
        Args:
            sorted_importance: List of (name, importance) tuples sorted descending
            
        Returns:
            Dictionary with cumulative importance percentages
        """
        total = sum(imp for _, imp in sorted_importance)
        cumulative = {}
        
        for n in [5, 10, 15, 20, 25, 30, 35, 40, 46]:
            if n <= len(sorted_importance):
                cum_sum = sum(imp for _, imp in sorted_importance[:n])
                cumulative[f'top_{n}'] = cum_sum / total if total > 0 else 0
        
        return cumulative
    
    def export_model_card(self, output_path: Path) -> None:
        """
        Export model card with comprehensive documentation
        
        Args:
            output_path: Output file path
        """
        model_card = f"""
# Model Card: Drone Detection Classifier

## Model Overview
- **Model Name:** {self.metadata.get('model_name', 'Drone Detection Classifier')}
- **Version:** {self.config.VERSION}
- **Algorithm:** {type(self.model).__name__}
- **Export Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Training Details
- **Number of Classes:** {len(DRONE_CLASSES)}
- **Number of Features:** {len(FEATURE_NAMES)}
- **Training Samples:** {self.metadata.get('performance', {}).get('training_samples', 'N/A')}
- **Test Samples:** {self.metadata.get('performance', {}).get('test_samples', 'N/A')}

## Performance Metrics
- **Accuracy:** {self.metadata.get('performance', {}).get('accuracy', 'N/A')}
- **F1 Score (Macro):** {self.metadata.get('performance', {}).get('f1_macro', 'N/A')}
- **Precision (Macro):** {self.metadata.get('performance', {}).get('precision_macro', 'N/A')}
- **Recall (Macro):** {self.metadata.get('performance', {}).get('recall_macro', 'N/A')}

## Class Distribution
{self._format_class_distribution()}

## Feature Importance (Top 10)
{self._format_feature_importance()}

## Usage Example
```python
import pickle
import numpy as np

# Load model
with open('classifier.pkl', 'rb') as f:
    model = pickle.load(f)

# Load scaler (if available)
with open('scaler.pkl', 'rb') as f:
    scaler = pickle.load(f)

# Extract features (46 features)
features = np.array([...]).reshape(1, -1)

# Scale features
if scaler:
    features = scaler.transform(features)

# Predict
prediction = model.predict(features)[0]
probabilities = model.predict_proba(features)[0]

# Get drone type
drone_type = DRONE_CLASSES[prediction]
confidence = np.max(probabilities)