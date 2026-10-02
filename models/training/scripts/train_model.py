#!/usr/bin/env python3
"""
Drone Detection System - Model Training Script

This script trains a Random Forest classifier to identify drones
based on spectral features extracted from IQ samples.
"""

import numpy as np
import pandas as pd
import pickle
import json
from pathlib import Path
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import warnings
warnings.filterwarnings('ignore')

# Model configuration
MODEL_CONFIG = {
    'name': 'Drone Detection Classifier',
    'version': '2.0.0',
    'algorithm': 'RandomForest',
    'n_estimators': 100,
    'max_depth': 20,
    'min_samples_split': 5,
    'min_samples_leaf': 2,
    'max_features': 'sqrt',
    'random_state': 42,
    'n_jobs': -1
}

# Drone classes (labels)
DRONE_CLASSES = {
    0: 'noise',
    1: 'dji_mavic',
    2: 'dji_mini',
    3: 'dji_phantom',
    4: 'fpv_analog',
    5: 'fpv_digital',
    6: 'autel_evo',
    7: 'skydio',
    8: 'parrot_anafi',
    9: 'hubsan',
    10: 'yuneec',
    11: 'interference_wifi',
    12: 'interference_ble',
    13: 'interference_radar'
}

# Feature names (46 features extracted from IQ signals)
FEATURE_NAMES = [
    # Spectral features (20)
    'peak_freq', 'peak_magnitude', 'peak_width', 'peak_prominence',
    'power_spectral_density_mean', 'power_spectral_density_std',
    'power_spectral_density_skew', 'power_spectral_density_kurtosis',
    'bandwidth_3db', 'bandwidth_6db', 'bandwidth_20db',
    'roll_off_factor', 'spectral_flatness', 'spectral_centroid',
    'spectral_spread', 'spectral_rolloff',
    'noise_floor', 'signal_to_noise_ratio',
    'peak_to_average_power_ratio', 'total_harmonic_distortion',
    
    # Cyclostationary features (8)
    'cyclic_frequency_1', 'cyclic_frequency_2', 'cyclic_frequency_3',
    'cyclic_amplitude_1', 'cyclic_amplitude_2', 'cyclic_amplitude_3',
    'cyclic_coherence', 'cycle_frequency_spacing',
    
    # Statistical features (10)
    'iq_mean_real', 'iq_mean_imag', 'iq_std_real', 'iq_std_imag',
    'iq_variance', 'iq_skewness', 'iq_kurtosis',
    'amplitude_variance', 'phase_variance', 'instantaneous_frequency_std',
    
    # Modulation features (8)
    'modulation_index', 'frequency_deviation', 'symbol_rate',
    'carrier_offset', 'evm_rms', 'evm_peak',
    'phase_error_rms', 'magnitude_error_rms'
]


def generate_synthetic_data(num_samples=10000):
    """
    Generate synthetic training data for demonstration purposes.
    In production, this should load real recorded IQ data.
    """
    print(f"Generating {num_samples} synthetic samples...")
    
    X = np.random.randn(num_samples, len(FEATURE_NAMES))
    y = np.random.randint(0, len(DRONE_CLASSES), num_samples)
    
    # Add some structure to make features meaningful
    for i in range(num_samples):
        drone_type = y[i]
        
        # Different drones have different spectral characteristics
        if drone_type == 1:  # DJI Mavic
            X[i, 0] = 2.44e9  # peak_freq (2.44 GHz)
            X[i, 4] = -45  # PSD mean
            X[i, 16] = -90  # noise floor
            X[i, 17] = 45  # SNR
        elif drone_type == 4:  # FPV Analog
            X[i, 0] = 5.8e9  # peak_freq (5.8 GHz)
            X[i, 4] = -55  # PSD mean
            X[i, 8] = 8e6  # bandwidth
            X[i, 18] = 8  # PAPR
        elif drone_type == 0:  # Noise
            X[i, 4] = -80
            X[i, 16] = -85
            X[i, 17] = 5
        elif drone_type == 11:  # WiFi interference
            X[i, 0] = 2.45e9
            X[i, 8] = 20e6
            X[i, 4] = -60
    
    return X, y


def load_real_data(data_path):
    """
    Load real training data from processed numpy files.
    
    Expected file structure:
    - X_train.npy: Feature matrix (n_samples, n_features)
    - y_train.npy: Labels (n_samples,)
    - X_test.npy: Test features
    - y_test.npy: Test labels
    """
    data_path = Path(data_path)
    
    if (data_path / 'X_train.npy').exists():
        X_train = np.load(data_path / 'X_train.npy')
        y_train = np.load(data_path / 'y_train.npy')
        X_test = np.load(data_path / 'X_test.npy')
        y_test = np.load(data_path / 'y_test.npy')
        print(f"Loaded real data: {len(X_train)} training samples, {len(X_test)} test samples")
        return X_train, X_test, y_train, y_test
    else:
        print("No real data found, using synthetic data for demonstration")
        X, y = generate_synthetic_data(10000)
        return train_test_split(X, y, test_size=0.2, random_state=42)


def train_model(X_train, y_train, config=None):
    """
    Train the Random Forest classifier
    """
    if config is None:
        config = MODEL_CONFIG
    
    print("\n" + "="*60)
    print("Training Random Forest Classifier")
    print("="*60)
    print(f"Training samples: {len(X_train)}")
    print(f"Features: {X_train.shape[1]}")
    print(f"Classes: {len(np.unique(y_train))}")
    print(f"Parameters: {config}")
    
    # Initialize and train model
    model = RandomForestClassifier(
        n_estimators=config['n_estimators'],
        max_depth=config['max_depth'],
        min_samples_split=config['min_samples_split'],
        min_samples_leaf=config['min_samples_leaf'],
        max_features=config['max_features'],
        random_state=config['random_state'],
        n_jobs=config['n_jobs'],
        verbose=1
    )
    
    model.fit(X_train, y_train)
    
    return model


def hyperparameter_tuning(X_train, y_train):
    """
    Perform Grid Search for hyperparameter optimization
    """
    print("\n" + "="*60)
    print("Hyperparameter Tuning")
    print("="*60)
    
    param_grid = {
        'n_estimators': [50, 100, 200],
        'max_depth': [10, 20, 30, None],
        'min_samples_split': [2, 5, 10],
        'min_samples_leaf': [1, 2, 4],
        'max_features': ['sqrt', 'log2', None]
    }
    
    base_model = RandomForestClassifier(random_state=42, n_jobs=-1)
    
    grid_search = GridSearchCV(
        estimator=base_model,
        param_grid=param_grid,
        cv=5,
        scoring='accuracy',
        n_jobs=-1,
        verbose=1
    )
    
    grid_search.fit(X_train, y_train)
    
    print(f"\nBest parameters: {grid_search.best_params_}")
    print(f"Best cross-validation score: {grid_search.best_score_:.4f}")
    
    return grid_search.best_estimator_, grid_search.best_params_


def evaluate_model(model, X_test, y_test, scaler=None):
    """
    Evaluate model performance
    """
    print("\n" + "="*60)
    print("Model Evaluation")
    print("="*60)
    
    # Scale if scaler provided
    if scaler:
        X_test = scaler.transform(X_test)
    
    # Make predictions
    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)
    
    # Calculate metrics
    accuracy = accuracy_score(y_test, y_pred)
    
    print(f"\nAccuracy: {accuracy:.4f}")
    print(f"\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=list(DRONE_CLASSES.values())))
    
    # Confusion matrix
    cm = confusion_matrix(y_test, y_pred)
    print(f"\nConfusion Matrix:")
    print(cm)
    
    # Cross-validation
    cv_scores = cross_val_score(model, X_test, y_test, cv=5)
    print(f"\nCross-validation scores: {cv_scores}")
    print(f"Mean CV score: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")
    
    # Feature importance
    feature_importance = dict(zip(FEATURE_NAMES, model.feature_importances_))
    sorted_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
    
    print(f"\nTop 10 Most Important Features:")
    for i, (name, importance) in enumerate(sorted_features[:10], 1):
        print(f"  {i}. {name}: {importance:.4f}")
    
    return {
        'accuracy': accuracy,
        'cv_scores': cv_scores.tolist(),
        'feature_importance': feature_importance,
        'confusion_matrix': cm.tolist()
    }


def save_model(model, scaler, metrics, output_dir='models'):
    """
    Save trained model, scaler, and metadata
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save classifier
    classifier_path = output_dir / 'classifier.pkl'
    with open(classifier_path, 'wb') as f:
        pickle.dump(model, f)
    print(f"\nModel saved to: {classifier_path}")
    
    # Save scaler
    scaler_path = output_dir / 'scaler.pkl'
    with open(scaler_path, 'wb') as f:
        pickle.dump(scaler, f)
    print(f"Scaler saved to: {scaler_path}")
    
    # Save metadata
    metadata = {
        'model_name': MODEL_CONFIG['name'],
        'version': MODEL_CONFIG['version'],
        'algorithm': MODEL_CONFIG['algorithm'],
        'training_date': datetime.now().isoformat(),
        'num_features': len(FEATURE_NAMES),
        'feature_names': FEATURE_NAMES,
        'num_classes': len(DRONE_CLASSES),
        'class_names': DRONE_CLASSES,
        'hyperparameters': MODEL_CONFIG,
        'performance': metrics,
        'accuracy': metrics['accuracy']
    }
    
    metadata_path = output_dir / 'model_metadata.json'
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"Metadata saved to: {metadata_path}")
    
    # Save feature importance
    importance_path = output_dir / 'feature_importance.json'
    importance_data = {
        'feature_importance': metrics['feature_importance'],
        'sorted_features': sorted(metrics['feature_importance'].items(), key=lambda x: x[1], reverse=True)
    }
    with open(importance_path, 'w') as f:
        json.dump(importance_data, f, indent=2)
    print(f"Feature importance saved to: {importance_path}")


def main():
    """
    Main training pipeline
    """
    print("\n" + "="*60)
    print("Drone Detection System - Model Training")
    print("="*60)
    
    # Load data
    data_path = Path('models/training/dataset/processed')
    X_train, X_test, y_train, y_test = load_real_data(data_path)
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train model
    model = train_model(X_train_scaled, y_train)
    
    # Evaluate
    metrics = evaluate_model(model, X_test_scaled, y_test)
    
    # Save model
    save_model(model, scaler, metrics)
    
    print("\n" + "="*60)
    print("Training Complete!")
    print("="*60)


if __name__ == "__main__":
    main()