#!/usr/bin/env python3
"""
Model Evaluation Script

This script evaluates the trained drone detection classifier,
providing comprehensive metrics including:
- Classification accuracy, precision, recall, F1-score
- Confusion matrix visualization
- ROC curves and AUC scores
- Per-class performance analysis
- Feature importance validation
- Error analysis and misclassification patterns
"""

import os
import sys
import json
import argparse
import numpy as np
import pandas as pd
import pickle
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report, roc_curve, auc,
    precision_recall_curve, average_precision_score,
    cohen_kappa_score, matthews_corrcoef
)
from sklearn.preprocessing import label_binarize
from collections import defaultdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Import project modules
from models.training.features.feature_schema import get_feature_schema, FEATURE_NAMES


# ============================================================================
# Configuration
# ============================================================================

class EvaluateConfig:
    """Evaluation configuration"""
    
    # Paths
    MODELS_DIR = Path("models")
    PROCESSED_DATA_DIR = Path("models/training/dataset/processed")
    RESULTS_DIR = Path("models/training/evaluation_results")
    LABELS_FILE = Path("models/training/dataset/labels.json")
    
    # Visualization
    FIGURE_DPI = 150
    COLOR_MAP = 'viridis'
    CONFUSION_MATRIX_NORM = 'true'  # 'true', 'pred', 'all', None
    
    # Reporting
    SAVE_PLOTS = True
    SAVE_JSON = True
    GENERATE_HTML_REPORT = True


# ============================================================================
# Model Evaluator Class
# ============================================================================

class ModelEvaluator:
    """
    Comprehensive model evaluation with visualization and reporting
    """
    
    def __init__(self, config: EvaluateConfig = None):
        """
        Initialize model evaluator
        
        Args:
            config: Evaluation configuration
        """
        self.config = config or EvaluateConfig()
        self.model = None
        self.scaler = None
        self.X_test = None
        self.y_test = None
        self.y_pred = None
        self.y_pred_proba = None
        self.class_names = []
        self.class_labels = []
        
        # Create results directory
        self.config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        
        # Load label mapping
        self.load_label_mapping()
        
        print("=" * 70)
        print("MODEL EVALUATION SUITE")
        print("=" * 70)
    
    def load_label_mapping(self):
        """Load label mapping from JSON file"""
        if self.config.LABELS_FILE.exists():
            with open(self.config.LABELS_FILE, 'r') as f:
                labels_data = json.load(f)
            
            self.class_names = []
            self.class_labels = []
            
            for label_id, label_info in labels_data['label_mapping'].items():
                if int(label_id) != 0:  # Skip 'noise' class for main metrics
                    self.class_names.append(label_info['display_name'])
                    self.class_labels.append(int(label_id))
            
            # Sort by label ID
            sorted_pairs = sorted(zip(self.class_labels, self.class_names))
            self.class_labels, self.class_names = zip(*sorted_pairs) if sorted_pairs else ([], [])
            self.class_labels = list(self.class_labels)
            self.class_names = list(self.class_names)
        else:
            print("[WARNING] Labels file not found, using default class names")
    
    def load_data(self) -> None:
        """Load test dataset"""
        print("\n[1] Loading test dataset...")
        
        # Load test features and labels
        X_test_path = self.config.PROCESSED_DATA_DIR / "X_test.npy"
        y_test_path = self.config.PROCESSED_DATA_DIR / "y_test.npy"
        
        if not X_test_path.exists() or not y_test_path.exists():
            raise FileNotFoundError(f"Test data not found in {self.config.PROCESSED_DATA_DIR}")
        
        self.X_test = np.load(X_test_path)
        self.y_test = np.load(y_test_path)
        
        print(f"  Test samples: {len(self.X_test)}")
        print(f"  Feature dimensions: {self.X_test.shape[1]}")
        print(f"  Number of classes: {len(np.unique(self.y_test))}")
    
    def load_model(self, model_path: str = None) -> None:
        """
        Load trained model and scaler
        
        Args:
            model_path: Path to model pickle file (uses default if None)
        """
        print("\n[2] Loading trained model...")
        
        if model_path is None:
            model_path = self.config.MODELS_DIR / "classifier.pkl"
        
        if not Path(model_path).exists():
            raise FileNotFoundError(f"Model not found: {model_path}")
        
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)
        
        # Load scaler if exists
        scaler_path = self.config.MODELS_DIR / "scaler.pkl"
        if scaler_path.exists():
            with open(scaler_path, 'rb') as f:
                self.scaler = pickle.load(f)
            
            # Scale test data
            self.X_test = self.scaler.transform(self.X_test)
        
        print(f"  Model loaded: {model_path}")
        print(f"  Model type: {type(self.model).__name__}")
    
    def predict(self) -> None:
        """Run predictions on test data"""
        print("\n[3] Running predictions...")
        
        self.y_pred = self.model.predict(self.X_test)
        
        # Get prediction probabilities if available
        if hasattr(self.model, 'predict_proba'):
            self.y_pred_proba = self.model.predict_proba(self.X_test)
        else:
            self.y_pred_proba = None
        
        print(f"  Predictions complete")
        print(f"  Unique predictions: {np.unique(self.y_pred)}")
    
    # ========================================================================
    # Metrics Calculation
    # ========================================================================
    
    def calculate_metrics(self) -> dict:
        """
        Calculate comprehensive performance metrics
        
        Returns:
            Dictionary of metrics
        """
        print("\n[4] Calculating metrics...")
        
        metrics = {}
        
        # Overall metrics
        metrics['accuracy'] = accuracy_score(self.y_test, self.y_pred)
        metrics['precision_macro'] = precision_score(self.y_test, self.y_pred, average='macro')
        metrics['recall_macro'] = recall_score(self.y_test, self.y_pred, average='macro')
        metrics['f1_macro'] = f1_score(self.y_test, self.y_pred, average='macro')
        
        metrics['precision_weighted'] = precision_score(self.y_test, self.y_pred, average='weighted')
        metrics['recall_weighted'] = recall_score(self.y_test, self.y_pred, average='weighted')
        metrics['f1_weighted'] = f1_score(self.y_test, self.y_pred, average='weighted')
        
        metrics['precision_micro'] = precision_score(self.y_test, self.y_pred, average='micro')
        metrics['recall_micro'] = recall_score(self.y_test, self.y_pred, average='micro')
        metrics['f1_micro'] = f1_score(self.y_test, self.y_pred, average='micro')
        
        # Additional metrics
        metrics['kappa'] = cohen_kappa_score(self.y_test, self.y_pred)
        metrics['mcc'] = matthews_corrcoef(self.y_test, self.y_pred)
        
        print(f"  Accuracy: {metrics['accuracy']:.4f}")
        print(f"  Macro F1: {metrics['f1_macro']:.4f}")
        print(f"  Weighted F1: {metrics['f1_weighted']:.4f}")
        print(f"  Cohen's Kappa: {metrics['kappa']:.4f}")
        print(f"  Matthews CC: {metrics['mcc']:.4f}")
        
        return metrics
    
    def per_class_metrics(self) -> pd.DataFrame:
        """
        Calculate per-class performance metrics
        
        Returns:
            DataFrame with per-class metrics
        """
        print("\n[5] Calculating per-class metrics...")
        
        # Get classification report
        report = classification_report(
            self.y_test, self.y_pred, 
            target_names=self.class_names,
            output_dict=True,
            zero_division=0
        )
        
        # Convert to DataFrame
        df = pd.DataFrame(report).transpose()
        
        # Add support (number of samples per class)
        support = []
        for class_name in self.class_names:
            class_label = self.class_labels[self.class_names.index(class_name)]
            support.append(np.sum(self.y_test == class_label))
        
        df['support'] = support + [np.sum(self.y_test), np.sum(self.y_test)]
        
        return df
    
    def confusion_matrix_data(self) -> np.ndarray:
        """
        Compute confusion matrix
        
        Returns:
            Confusion matrix as numpy array
        """
        return confusion_matrix(self.y_test, self.y_pred, labels=self.class_labels)
    
    # ========================================================================
    # Visualization
    # ========================================================================
    
    def plot_confusion_matrix(self, save: bool = True) -> plt.Figure:
        """
        Plot and save confusion matrix
        
        Args:
            save: Whether to save the figure
            
        Returns:
            Matplotlib figure
        """
        print("\n[6] Generating confusion matrix...")
        
        cm = self.confusion_matrix_data()
        
        # Normalize if requested
        if self.config.CONFUSION_MATRIX_NORM:
            cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
            fmt = '.2f'
            title = 'Normalized Confusion Matrix'
        else:
            fmt = 'd'
            title = 'Confusion Matrix'
        
        fig, ax = plt.subplots(figsize=(14, 12))
        
        sns.heatmap(
            cm, 
            annot=True, 
            fmt=fmt,
            cmap=self.config.COLOR_MAP,
            xticklabels=self.class_names,
            yticklabels=self.class_names,
            ax=ax,
            cbar_kws={'label': 'Proportion' if self.config.CONFUSION_MATRIX_NORM else 'Count'}
        )
        
        ax.set_xlabel('Predicted Label', fontsize=12)
        ax.set_ylabel('True Label', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        
        plt.xticks(rotation=45, ha='right')
        plt.yticks(rotation=0)
        plt.tight_layout()
        
        if save:
            fig.savefig(
                self.config.RESULTS_DIR / 'confusion_matrix.png',
                dpi=self.config.FIGURE_DPI,
                bbox_inches='tight'
            )
            print(f"  Saved: {self.config.RESULTS_DIR / 'confusion_matrix.png'}")
        
        return fig
    
    def plot_roc_curves(self, save: bool = True) -> plt.Figure:
        """
        Plot ROC curves for each class
        
        Args:
            save: Whether to save the figure
            
        Returns:
            Matplotlib figure
        """
        print("\n[7] Generating ROC curves...")
        
        if self.y_pred_proba is None:
            print("  [SKIP] Prediction probabilities not available")
            return None
        
        # Binarize labels for multi-class ROC
        y_test_bin = label_binarize(self.y_test, classes=self.class_labels)
        n_classes = len(self.class_labels)
        
        fig, ax = plt.subplots(figsize=(12, 10))
        
        # Compute ROC curve and ROC area for each class
        colors = plt.cm.viridis(np.linspace(0, 1, n_classes))
        
        for i, (label, name, color) in enumerate(zip(self.class_labels, self.class_names, colors)):
            fpr, tpr, _ = roc_curve(y_test_bin[:, i], self.y_pred_proba[:, i])
            roc_auc = auc(fpr, tpr)
            
            ax.plot(fpr, tpr, color=color, lw=2,
                    label=f'{name} (AUC = {roc_auc:.3f})')
        
        ax.plot([0, 1], [0, 1], 'k--', lw=2, label='Random Chance')
        ax.set_xlim([0.0, 1.0])
        ax.set_ylim([0.0, 1.05])
        ax.set_xlabel('False Positive Rate', fontsize=12)
        ax.set_ylabel('True Positive Rate', fontsize=12)
        ax.set_title('ROC Curves by Drone Type', fontsize=14, fontweight='bold')
        ax.legend(loc="lower right", fontsize=10)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save:
            fig.savefig(
                self.config.RESULTS_DIR / 'roc_curves.png',
                dpi=self.config.FIGURE_DPI,
                bbox_inches='tight'
            )
            print(f"  Saved: {self.config.RESULTS_DIR / 'roc_curves.png'}")
        
        return fig
    
    def plot_precision_recall_curves(self, save: bool = True) -> plt.Figure:
        """
        Plot Precision-Recall curves for each class
        
        Args:
            save: Whether to save the figure
            
        Returns:
            Matplotlib figure
        """
        print("\n[8] Generating Precision-Recall curves...")
        
        if self.y_pred_proba is None:
            print("  [SKIP] Prediction probabilities not available")
            return None
        
        y_test_bin = label_binarize(self.y_test, classes=self.class_labels)
        n_classes = len(self.class_labels)
        
        fig, ax = plt.subplots(figsize=(12, 10))
        
        colors = plt.cm.viridis(np.linspace(0, 1, n_classes))
        
        for i, (label, name, color) in enumerate(zip(self.class_labels, self.class_names, colors)):
            precision, recall, _ = precision_recall_curve(y_test_bin[:, i], self.y_pred_proba[:, i])
            ap_score = average_precision_score(y_test_bin[:, i], self.y_pred_proba[:, i])
            
            ax.plot(recall, precision, color=color, lw=2,
                    label=f'{name} (AP = {ap_score:.3f})')
        
        ax.set_xlim([0.0, 1.0])
        ax.set_ylim([0.0, 1.05])
        ax.set_xlabel('Recall', fontsize=12)
        ax.set_ylabel('Precision', fontsize=12)
        ax.set_title('Precision-Recall Curves by Drone Type', fontsize=14, fontweight='bold')
        ax.legend(loc="lower left", fontsize=10)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save:
            fig.savefig(
                self.config.RESULTS_DIR / 'precision_recall_curves.png',
                dpi=self.config.FIGURE_DPI,
                bbox_inches='tight'
            )
            print(f"  Saved: {self.config.RESULTS_DIR / 'precision_recall_curves.png'}")
        
        return fig
    
    def plot_performance_bar_chart(self, metrics: dict, save: bool = True) -> plt.Figure:
        """
        Plot performance bar chart
        
        Args:
            metrics: Dictionary of metrics
            save: Whether to save the figure
            
        Returns:
            Matplotlib figure
        """
        print("\n[9] Generating performance bar chart...")
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        metric_names = ['Accuracy', 'Precision (Macro)', 'Recall (Macro)', 'F1 (Macro)']
        metric_values = [
            metrics['accuracy'],
            metrics['precision_macro'],
            metrics['recall_macro'],
            metrics['f1_macro']
        ]
        colors = ['#4caf50', '#2196f3', '#ff9800', '#f44336']
        
        bars = ax.bar(metric_names, metric_values, color=colors, edgecolor='black', linewidth=1.5)
        
        # Add value labels on bars
        for bar, value in zip(bars, metric_values):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                    f'{value:.3f}', ha='center', va='bottom', fontweight='bold')
        
        ax.set_ylim([0, 1.1])
        ax.set_ylabel('Score', fontsize=12)
        ax.set_title('Model Performance Metrics', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        
        if save:
            fig.savefig(
                self.config.RESULTS_DIR / 'performance_bar_chart.png',
                dpi=self.config.FIGURE_DPI,
                bbox_inches='tight'
            )
            print(f"  Saved: {self.config.RESULTS_DIR / 'performance_bar_chart.png'}")
        
        return fig
    
    def plot_per_class_f1(self, per_class_df: pd.DataFrame, save: bool = True) -> plt.Figure:
        """
        Plot per-class F1 scores
        
        Args:
            per_class_df: DataFrame with per-class metrics
            save: Whether to save the figure
            
        Returns:
            Matplotlib figure
        """
        print("\n[10] Generating per-class F1 chart...")
        
        # Extract F1 scores for each class
        f1_scores = []
        classes_with_data = []
        
        for class_name in self.class_names:
            if class_name in per_class_df.index:
                f1_scores.append(per_class_df.loc[class_name, 'f1-score'])
                classes_with_data.append(class_name)
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        colors = plt.cm.RdYlGn(np.array(f1_scores))
        
        bars = ax.barh(classes_with_data, f1_scores, color=colors, edgecolor='black', linewidth=1)
        
        # Add value labels
        for bar, score in zip(bars, f1_scores):
            ax.text(bar.get_width() + 0.01, bar.get_y() + bar.get_height()/2,
                    f'{score:.3f}', ha='left', va='center', fontsize=10)
        
        ax.set_xlim([0, 1.05])
        ax.set_xlabel('F1 Score', fontsize=12)
        ax.set_title('Per-Class F1 Scores', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='x')
        
        plt.tight_layout()
        
        if save:
            fig.savefig(
                self.config.RESULTS_DIR / 'per_class_f1.png',
                dpi=self.config.FIGURE_DPI,
                bbox_inches='tight'
            )
            print(f"  Saved: {self.config.RESULTS_DIR / 'per_class_f1.png'}")
        
        return fig
    
    def plot_misclassification_analysis(self, save: bool = True) -> plt.Figure:
        """
        Analyze and visualize misclassifications
        
        Args:
            save: Whether to save the figure
            
        Returns:
            Matplotlib figure
        """
        print("\n[11] Analyzing misclassifications...")
        
        # Find misclassified samples
        misclassified = self.y_test != self.y_pred
        misclassified_indices = np.where(misclassified)[0]
        
        if len(misclassified_indices) == 0:
            print("  No misclassifications found!")
            return None
        
        # Group misclassifications by true label and predicted label
        misclass_matrix = defaultdict(lambda: defaultdict(int))
        
        for idx in misclassified_indices:
            true_label = self.y_test[idx]
            pred_label = self.y_pred[idx]
            
            true_name = self.class_names[self.class_labels.index(true_label)] if true_label in self.class_labels else f"Class_{true_label}"
            pred_name = self.class_names[self.class_labels.index(pred_label)] if pred_label in self.class_labels else f"Class_{pred_label}"
            
            misclass_matrix[true_name][pred_name] += 1
        
        # Create heatmap of misclassifications
        true_classes = list(misclass_matrix.keys())
        pred_classes = set()
        for t in misclass_matrix.values():
            pred_classes.update(t.keys())
        pred_classes = sorted(pred_classes)
        
        # Build matrix
        misclass_array = np.zeros((len(true_classes), len(pred_classes)))
        for i, true_cls in enumerate(true_classes):
            for j, pred_cls in enumerate(pred_classes):
                misclass_array[i, j] = misclass_matrix[true_cls].get(pred_cls, 0)
        
        fig, ax = plt.subplots(figsize=(12, 10))
        
        sns.heatmap(
            misclass_array,
            annot=True,
            fmt='d',
            cmap='Reds',
            xticklabels=pred_classes,
            yticklabels=true_classes,
            ax=ax,
            cbar_kws={'label': 'Number of Misclassifications'}
        )
        
        ax.set_xlabel('Predicted as', fontsize=12)
        ax.set_ylabel('True Class', fontsize=12)
        ax.set_title('Misclassification Analysis', fontsize=14, fontweight='bold')
        
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        if save:
            fig.savefig(
                self.config.RESULTS_DIR / 'misclassification_analysis.png',
                dpi=self.config.FIGURE_DPI,
                bbox_inches='tight'
            )
            print(f"  Saved: {self.config.RESULTS_DIR / 'misclassification_analysis.png'}")
        
        print(f"  Total misclassifications: {len(misclassified_indices)} ({len(misclassified_indices)/len(self.y_test)*100:.2f}%)")
        
        return fig
    
    # ========================================================================
    # Reporting
    # ========================================================================
    
    def save_results_json(self, metrics: dict, per_class_df: pd.DataFrame) -> None:
        """
        Save evaluation results as JSON
        
        Args:
            metrics: Dictionary of metrics
            per_class_df: DataFrame with per-class metrics
        """
        print("\n[12] Saving results as JSON...")
        
        # Prepare results dictionary
        results = {
            'evaluation_timestamp': datetime.now().isoformat(),
            'model_info': {
                'type': type(self.model).__name__,
                'num_classes': len(self.class_labels),
                'feature_dim': self.X_test.shape[1],
                'test_samples': len(self.y_test)
            },
            'overall_metrics': metrics,
            'per_class_metrics': {},
            'confusion_matrix': self.confusion_matrix_data().tolist()
        }
        
        # Add per-class metrics
        for class_name in self.class_names:
            if class_name in per_class_df.index:
                results['per_class_metrics'][class_name] = {
                    'precision': float(per_class_df.loc[class_name, 'precision']),
                    'recall': float(per_class_df.loc[class_name, 'recall']),
                    'f1_score': float(per_class_df.loc[class_name, 'f1-score']),
                    'support': int(per_class_df.loc[class_name, 'support'])
                }
        
        # Save to file
        output_path = self.config.RESULTS_DIR / 'evaluation_results.json'
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"  Saved: {output_path}")
    
    def generate_html_report(self, metrics: dict, per_class_df: pd.DataFrame) -> None:
        """
        Generate HTML report
        
        Args:
            metrics: Dictionary of metrics
            per_class_df: DataFrame with per-class metrics
        """
        print("\n[13] Generating HTML report...")
        
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Drone Detection Model Evaluation Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            padding: 30px;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #4facfe;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .metric-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
        }}
        .metric-card .value {{
            font-size: 36px;
            font-weight: bold;
        }}
        .metric-card .label {{
            font-size: 14px;
            opacity: 0.9;
            margin-top: 5px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
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
        .image-container {{
            text-align: center;
            margin: 30px 0;
        }}
        .image-container img {{
            max-width: 100%;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #888;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Drone Detection Model Evaluation Report</h1>
        <p><strong>Evaluation Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><strong>Model Type:</strong> {type(self.model).__name__}</p>
        <p><strong>Test Samples:</strong> {len(self.y_test)}</p>
        <p><strong>Number of Classes:</strong> {len(self.class_labels)}</p>
        
        <h2>Overall Performance Metrics</h2>
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="value">{metrics['accuracy']:.3f}</div>
                <div class="label">Accuracy</div>
            </div>
            <div class="metric-card">
                <div class="value">{metrics['precision_macro']:.3f}</div>
                <div class="label">Precision (Macro)</div>
            </div>
            <div class="metric-card">
                <div class="value">{metrics['recall_macro']:.3f}</div>
                <div class="label">Recall (Macro)</div>
            </div>
            <div class="metric-card">
                <div class="value">{metrics['f1_macro']:.3f}</div>
                <div class="label">F1 Score (Macro)</div>
            </div>
            <div class="metric-card">
                <div class="value">{metrics['kappa']:.3f}</div>
                <div class="label">Cohen's Kappa</div>
            </div>
            <div class="metric-card">
                <div class="value">{metrics['mcc']:.3f}</div>
                <div class="label">Matthews CC</div>
            </div>
        </div>
        
        <h2>Per-Class Performance</h2>
        <table>
            <thead>
                <tr>
                    <th>Drone Type</th>
                    <th>Precision</th>
                    <th>Recall</th>
                    <th>F1 Score</th>
                    <th>Support</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for class_name in self.class_names:
            if class_name in per_class_df.index:
                row = per_class_df.loc[class_name]
                html_content += f"""
                <tr>
                    <td>{class_name}</td>
                    <td>{row['precision']:.3f}</td>
                    <td>{row['recall']:.3f}</td>
                    <td>{row['f1-score']:.3f}</td>
                    <td>{int(row['support'])}</td>
                </tr>
                """
        
        html_content += """
            </tbody>
        </table>
        
        <h2>Visualizations</h2>
        
        <div class="image-container">
            <h3>Confusion Matrix</h3>
            <img src="confusion_matrix.png" alt="Confusion Matrix">
        </div>
        
        <div class="image-container">
            <h3>ROC Curves</h3>
            <img src="roc_curves.png" alt="ROC Curves">
        </div>
        
        <div class="image-container">
            <h3>Precision-Recall Curves</h3>
            <img src="precision_recall_curves.png" alt="Precision-Recall Curves">
        </div>
        
        <div class="image-container">
            <h3>Performance Metrics</h3>
            <img src="performance_bar_chart.png" alt="Performance Bar Chart">
        </div>
        
        <div class="image-container">
            <h3>Per-Class F1 Scores</h3>
            <img src="per_class_f1.png" alt="Per-Class F1 Scores">
        </div>
        
        <div class="footer">
            <p>Generated by Drone Detection System Model Evaluation Suite</p>
        </div>
    </div>
</body>
</html>
        """
        
        output_path = self.config.RESULTS_DIR / 'evaluation_report.html'
        with open(output_path, 'w') as f:
            f.write(html_content)
        
        print(f"  Saved: {output_path}")
    
    # ========================================================================
    # Main Evaluation Pipeline
    # ========================================================================
    
    def run_evaluation(self, model_path: str = None) -> dict:
        """
        Run complete model evaluation pipeline
        
        Args:
            model_path: Path to model file
            
        Returns:
            Dictionary of evaluation results
        """
        # Load data and model
        self.load_data()
        self.load_model(model_path)
        self.predict()
        
        # Calculate metrics
        metrics = self.calculate_metrics()
        per_class_df = self.per_class_metrics()
        
        # Generate visualizations
        self.plot_confusion_matrix(save=self.config.SAVE_PLOTS)
        self.plot_roc_curves(save=self.config.SAVE_PLOTS)
        self.plot_precision_recall_curves(save=self.config.SAVE_PLOTS)
        self.plot_performance_bar_chart(metrics, save=self.config.SAVE_PLOTS)
        self.plot_per_class_f1(per_class_df, save=self.config.SAVE_PLOTS)
        self.plot_misclassification_analysis(save=self.config.SAVE_PLOTS)
        
        # Save results
        if self.config.SAVE_JSON:
            self.save_results_json(metrics, per_class_df)
        
        if self.config.GENERATE_HTML_REPORT:
            self.generate_html_report(metrics, per_class_df)
        
        # Print summary
        print("\n" + "=" * 70)
        print("EVALUATION SUMMARY")
        print("=" * 70)
        print(f"Accuracy:  {metrics['accuracy']:.4f}")
        print(f"F1 Score (Macro): {metrics['f1_macro']:.4f}")
        print(f"F1 Score (Weighted): {metrics['f1_weighted']:.4f}")
        print(f"Cohen's Kappa: {metrics['kappa']:.4f}")
        print(f"Matthews CC: {metrics['mcc']:.4f}")
        print("=" * 70)
        print(f"Results saved to: {self.config.RESULTS_DIR}")
        
        return metrics


# ============================================================================
# Command Line Interface
# ============================================================================

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Evaluate trained drone detection model"
    )
    
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Path to model pickle file"
    )
    
    parser.add_argument(
        "--data-dir",
        type=str,
        default="models/training/dataset/processed",
        help="Processed data directory"
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        default="models/training/evaluation_results",
        help="Output directory for results"
    )
    
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Disable plot generation"
    )
    
    parser.add_argument(
        "--no-html",
        action="store_true",
        help="Disable HTML report generation"
    )
    
    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_args()
    
    # Create configuration
    config = EvaluateConfig()
    config.PROCESSED_DATA_DIR = Path(args.data_dir)
    config.RESULTS_DIR = Path(args.output_dir)
    config.SAVE_PLOTS = not args.no_plots
    config.GENERATE_HTML_REPORT = not args.no_html
    
    # Create evaluator and run
    evaluator = ModelEvaluator(config)
    evaluator.run_evaluation(model_path=args.model)


if __name__ == "__main__":
    main()