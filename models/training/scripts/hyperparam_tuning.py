#!/usr/bin/env python3
"""
Hyperparameter Tuning Script

This script performs comprehensive hyperparameter optimization for the
drone detection classifier using:
- Grid Search (scikit-learn)
- Random Search (scikit-learn)
- Bayesian Optimization (Optuna)

Features:
- Multi-method hyperparameter optimization
- Cross-validation with stratification
- Parallel processing support
- Early stopping
- Results visualization
- Best model export
"""

import os
import sys
import json
import argparse
import numpy as np
import pandas as pd
import pickle
import joblib
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Scikit-learn imports
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.svm import SVC
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import (
    GridSearchCV, RandomizedSearchCV, cross_val_score,
    StratifiedKFold, train_test_split
)
from sklearn.metrics import (
    accuracy_score, f1_score, precision_score, recall_score,
    make_scorer
)

# Optuna for Bayesian optimization
try:
    import optuna
    from optuna.samplers import TPESampler
    from optuna.pruners import MedianPruner
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False
    print("[WARNING] Optuna not installed. Install with: pip install optuna")

# Progress bars
from tqdm import tqdm


# ============================================================================
# Configuration
# ============================================================================

class TuningConfig:
    """Hyperparameter tuning configuration"""
    
    # Paths
    DATA_DIR = Path("models/training/dataset/processed")
    RESULTS_DIR = Path("models/training/hyperparameter_tuning")
    MODELS_DIR = Path("models")
    
    # Data splitting
    VALIDATION_SIZE = 0.2
    RANDOM_STATE = 42
    N_FOLDS = 5
    
    # Grid search settings
    GRID_N_JOBS = -1
    GRID_VERBOSE = 1
    
    # Random search settings
    RANDOM_N_ITER = 50
    RANDOM_N_JOBS = -1
    
    # Optuna settings
    OPTUNA_N_TRIALS = 100
    OPTUNA_N_JOBS = 1
    OPTUNA_TIMEOUT = 3600  # seconds
    
    # Visualization
    FIGURE_DPI = 150
    COLOR_MAP = 'viridis'


# ============================================================================
# Hyperparameter Tuning Manager
# ============================================================================

class HyperparameterTuner:
    """
    Comprehensive hyperparameter tuning for drone detection models
    """
    
    def __init__(self, config: TuningConfig = None):
        """
        Initialize hyperparameter tuner
        
        Args:
            config: Tuning configuration
        """
        self.config = config or TuningConfig()
        self.X_train = None
        self.X_val = None
        self.y_train = None
        self.y_val = None
        self.X_test = None
        self.y_test = None
        self.best_model = None
        self.best_params = None
        self.cv_results = None
        
        # Create results directory
        self.config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        
        # Setup scoring metrics
        self.scoring = {
            'accuracy': make_scorer(accuracy_score),
            'f1_macro': make_scorer(f1_score, average='macro'),
            'precision_macro': make_scorer(precision_score, average='macro'),
            'recall_macro': make_scorer(recall_score, average='macro')
        }
        
        print("=" * 70)
        print("HYPERPARAMETER TUNING SUITE")
        print("=" * 70)
    
    def load_data(self) -> None:
        """Load and prepare dataset"""
        print("\n[1] Loading dataset...")
        
        # Load training data
        X_train_path = self.config.DATA_DIR / "X_train.npy"
        y_train_path = self.config.DATA_DIR / "y_train.npy"
        
        if not X_train_path.exists():
            raise FileNotFoundError(f"Training data not found: {X_train_path}")
        
        X = np.load(X_train_path)
        y = np.load(y_train_path)
        
        print(f"  Total samples: {len(X)}")
        print(f"  Feature dimensions: {X.shape[1]}")
        print(f"  Number of classes: {len(np.unique(y))}")
        
        # Split into train and validation
        self.X_train, self.X_val, self.y_train, self.y_val = train_test_split(
            X, y, 
            test_size=self.config.VALIDATION_SIZE,
            stratify=y,
            random_state=self.config.RANDOM_STATE
        )
        
        print(f"  Training samples: {len(self.X_train)}")
        print(f"  Validation samples: {len(self.X_val)}")
        
        # Load test data if available
        X_test_path = self.config.DATA_DIR / "X_test.npy"
        y_test_path = self.config.DATA_DIR / "y_test.npy"
        
        if X_test_path.exists():
            self.X_test = np.load(X_test_path)
            self.y_test = np.load(y_test_path)
            print(f"  Test samples: {len(self.X_test)}")
    
    # ========================================================================
    # Grid Search
    # ========================================================================
    
    def grid_search_rf(self) -> Dict[str, Any]:
        """
        Perform grid search for Random Forest classifier
        
        Returns:
            Best parameters and results
        """
        print("\n[2] Performing Grid Search - Random Forest...")
        
        # Define parameter grid
        param_grid = {
            'n_estimators': [50, 100, 200, 300],
            'max_depth': [10, 20, 30, None],
            'min_samples_split': [2, 5, 10],
            'min_samples_leaf': [1, 2, 4],
            'max_features': ['sqrt', 'log2', None],
            'bootstrap': [True, False],
            'class_weight': ['balanced', 'balanced_subsample', None]
        }
        
        # Create base model
        base_model = RandomForestClassifier(
            random_state=self.config.RANDOM_STATE,
            n_jobs=self.config.GRID_N_JOBS
        )
        
        # Setup cross-validation
        cv = StratifiedKFold(
            n_splits=self.config.N_FOLDS,
            shuffle=True,
            random_state=self.config.RANDOM_STATE
        )
        
        # Perform grid search
        grid_search = GridSearchCV(
            estimator=base_model,
            param_grid=param_grid,
            cv=cv,
            scoring='f1_macro',
            n_jobs=self.config.GRID_N_JOBS,
            verbose=self.config.GRID_VERBOSE,
            return_train_score=True
        )
        
        grid_search.fit(self.X_train, self.y_train)
        
        print(f"\n  Best parameters: {grid_search.best_params_}")
        print(f"  Best CV score: {grid_search.best_score_:.4f}")
        
        # Store results
        self.best_model = grid_search.best_estimator_
        self.best_params = grid_search.best_params_
        self.cv_results = grid_search.cv_results_
        
        return {
            'method': 'grid_search',
            'best_params': grid_search.best_params_,
            'best_score': grid_search.best_score_,
            'cv_results': grid_search.cv_results_
        }
    
    def grid_search_gbdt(self) -> Dict[str, Any]:
        """
        Perform grid search for Gradient Boosting classifier
        
        Returns:
            Best parameters and results
        """
        print("\n[3] Performing Grid Search - Gradient Boosting...")
        
        param_grid = {
            'n_estimators': [100, 200, 300],
            'learning_rate': [0.01, 0.05, 0.1, 0.2],
            'max_depth': [3, 5, 7, 10],
            'min_samples_split': [2, 5, 10],
            'min_samples_leaf': [1, 2, 4],
            'subsample': [0.8, 0.9, 1.0]
        }
        
        base_model = GradientBoostingClassifier(
            random_state=self.config.RANDOM_STATE
        )
        
        cv = StratifiedKFold(
            n_splits=self.config.N_FOLDS,
            shuffle=True,
            random_state=self.config.RANDOM_STATE
        )
        
        grid_search = GridSearchCV(
            estimator=base_model,
            param_grid=param_grid,
            cv=cv,
            scoring='f1_macro',
            n_jobs=self.config.GRID_N_JOBS,
            verbose=self.config.GRID_VERBOSE
        )
        
        grid_search.fit(self.X_train, self.y_train)
        
        print(f"\n  Best parameters: {grid_search.best_params_}")
        print(f"  Best CV score: {grid_search.best_score_:.4f}")
        
        return {
            'method': 'grid_search_gbdt',
            'best_params': grid_search.best_params_,
            'best_score': grid_search.best_score_
        }
    
    # ========================================================================
    # Random Search
    # ========================================================================
    
    def random_search_rf(self) -> Dict[str, Any]:
        """
        Perform random search for Random Forest classifier
        
        Returns:
            Best parameters and results
        """
        print("\n[4] Performing Random Search - Random Forest...")
        
        # Define parameter distributions
        param_dist = {
            'n_estimators': [int(x) for x in np.linspace(50, 500, 20)],
            'max_depth': [int(x) for x in np.linspace(5, 50, 10)] + [None],
            'min_samples_split': [2, 5, 10, 15, 20],
            'min_samples_leaf': [1, 2, 4, 6, 8],
            'max_features': ['sqrt', 'log2', None],
            'bootstrap': [True, False],
            'class_weight': ['balanced', 'balanced_subsample', None]
        }
        
        base_model = RandomForestClassifier(
            random_state=self.config.RANDOM_STATE,
            n_jobs=self.config.RANDOM_N_JOBS
        )
        
        cv = StratifiedKFold(
            n_splits=self.config.N_FOLDS,
            shuffle=True,
            random_state=self.config.RANDOM_STATE
        )
        
        random_search = RandomizedSearchCV(
            estimator=base_model,
            param_distributions=param_dist,
            n_iter=self.config.RANDOM_N_ITER,
            cv=cv,
            scoring='f1_macro',
            n_jobs=self.config.RANDOM_N_JOBS,
            random_state=self.config.RANDOM_STATE,
            verbose=self.config.GRID_VERBOSE
        )
        
        random_search.fit(self.X_train, self.y_train)
        
        print(f"\n  Best parameters: {random_search.best_params_}")
        print(f"  Best CV score: {random_search.best_score_:.4f}")
        
        return {
            'method': 'random_search',
            'best_params': random_search.best_params_,
            'best_score': random_search.best_score_
        }
    
    # ========================================================================
    # Optuna Optimization (Bayesian)
    # ========================================================================
    
    def optuna_optimize_rf(self, n_trials: int = 100) -> Dict[str, Any]:
        """
        Perform Bayesian optimization using Optuna
        
        Args:
            n_trials: Number of optimization trials
            
        Returns:
            Best parameters and results
        """
        if not OPTUNA_AVAILABLE:
            print("\n[5] Optuna not available, skipping Bayesian optimization")
            return {}
        
        print(f"\n[5] Performing Bayesian Optimization - Random Forest ({n_trials} trials)...")
        
        def objective(trial):
            """Objective function for Optuna"""
            
            # Suggest hyperparameters
            params = {
                'n_estimators': trial.suggest_int('n_estimators', 50, 500, step=10),
                'max_depth': trial.suggest_int('max_depth', 5, 50) if trial.suggest_categorical('max_depth_option', [True, False]) else None,
                'min_samples_split': trial.suggest_int('min_samples_split', 2, 20),
                'min_samples_leaf': trial.suggest_int('min_samples_leaf', 1, 10),
                'max_features': trial.suggest_categorical('max_features', ['sqrt', 'log2', None]),
                'bootstrap': trial.suggest_categorical('bootstrap', [True, False]),
                'class_weight': trial.suggest_categorical('class_weight', ['balanced', 'balanced_subsample', None])
            }
            
            # Handle max_depth None case
            if not params['max_depth']:
                params['max_depth'] = None
            
            # Create and evaluate model
            model = RandomForestClassifier(
                **params,
                random_state=self.config.RANDOM_STATE,
                n_jobs=-1
            )
            
            # Cross-validation score
            cv_scores = cross_val_score(
                model, self.X_train, self.y_train,
                cv=StratifiedKFold(3, shuffle=True, random_state=self.config.RANDOM_STATE),
                scoring='f1_macro'
            )
            
            return cv_scores.mean()
        
        # Create study
        study = optuna.create_study(
            direction='maximize',
            sampler=TPESampler(seed=self.config.RANDOM_STATE),
            pruner=MedianPruner()
        )
        
        # Optimize
        study.optimize(
            objective,
            n_trials=n_trials,
            timeout=self.config.OPTUNA_TIMEOUT,
            show_progress_bar=True
        )
        
        # Get best parameters
        best_params = study.best_params
        best_value = study.best_value
        
        print(f"\n  Best parameters: {best_params}")
        print(f"  Best score: {best_value:.4f}")
        
        # Train final model with best parameters
        # Handle max_depth None
        if not best_params.get('max_depth'):
            best_params['max_depth'] = None
        del best_params.get('max_depth_option')
        
        best_model = RandomForestClassifier(
            **best_params,
            random_state=self.config.RANDOM_STATE,
            n_jobs=-1
        )
        best_model.fit(self.X_train, self.y_train)
        
        self.best_model = best_model
        self.best_params = best_params
        
        # Save study results
        self._save_optuna_results(study)
        
        return {
            'method': 'optuna',
            'best_params': best_params,
            'best_score': best_value,
            'study': study
        }
    
    def _save_optuna_results(self, study: optuna.Study) -> None:
        """
        Save Optuna optimization results
        
        Args:
            study: Optuna study object
        """
        # Save study as pickle
        study_path = self.config.RESULTS_DIR / "optuna_study.pkl"
        with open(study_path, 'wb') as f:
            pickle.dump(study, f)
        print(f"  Study saved: {study_path}")
        
        # Save trials dataframe
        df = study.trials_dataframe()
        df_path = self.config.RESULTS_DIR / "optuna_trials.csv"
        df.to_csv(df_path, index=False)
        print(f"  Trials saved: {df_path}")
        
        # Save optimization history plot
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(df['value'], 'b-', alpha=0.5, label='Trial value')
        ax.plot(df['value'].cummax(), 'r-', linewidth=2, label='Best value')
        ax.set_xlabel('Trial')
        ax.set_ylabel('Objective Value (F1 Macro)')
        ax.set_title('Optuna Optimization History')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plot_path = self.config.RESULTS_DIR / "optuna_history.png"
        fig.savefig(plot_path, dpi=self.config.FIGURE_DPI, bbox_inches='tight')
        plt.close()
        print(f"  History plot saved: {plot_path}")
    
    # ========================================================================
    # Model Comparison
    # ========================================================================
    
    def compare_models(self, models: Dict[str, Any]) -> pd.DataFrame:
        """
        Compare different models on validation set
        
        Args:
            models: Dictionary of model name to model instance
            
        Returns:
            DataFrame with comparison results
        """
        print("\n[6] Comparing models on validation set...")
        
        results = []
        
        for name, model in models.items():
            # Predict
            y_pred = model.predict(self.X_val)
            
            # Calculate metrics
            metrics = {
                'Model': name,
                'Accuracy': accuracy_score(self.y_val, y_pred),
                'F1 Macro': f1_score(self.y_val, y_pred, average='macro'),
                'Precision Macro': precision_score(self.y_val, y_pred, average='macro'),
                'Recall Macro': recall_score(self.y_val, y_pred, average='macro')
            }
            
            results.append(metrics)
            print(f"  {name}: F1={metrics['F1 Macro']:.4f}")
        
        df = pd.DataFrame(results)
        df = df.sort_values('F1 Macro', ascending=False)
        
        return df
    
    # ========================================================================
    # Visualization
    # ========================================================================
    
    def plot_grid_search_results(self, cv_results: Dict) -> None:
        """
        Plot grid search results
        
        Args:
            cv_results: Cross-validation results from grid search
        """
        print("\n[7] Generating grid search visualizations...")
        
        # Extract parameter names
        param_names = [p for p in cv_results['params'][0].keys()]
        
        for param in param_names:
            if len(np.unique([r[param] for r in cv_results['params']])) > 1:
                fig, ax = plt.subplots(figsize=(10, 6))
                
                # Group by parameter value
                param_values = []
                mean_scores = []
                std_scores = []
                
                for value in np.unique([r[param] for r in cv_results['params']]):
                    indices = [i for i, p in enumerate(cv_results['params']) if p[param] == value]
                    mean_score = np.mean([cv_results['mean_test_score'][i] for i in indices])
                    std_score = np.std([cv_results['mean_test_score'][i] for i in indices])
                    
                    param_values.append(str(value))
                    mean_scores.append(mean_score)
                    std_scores.append(std_score)
                
                ax.errorbar(param_values, mean_scores, yerr=std_scores, 
                           fmt='o-', capsize=5, capthick=2)
                ax.set_xlabel(param)
                ax.set_ylabel('Cross-Validation Score')
                ax.set_title(f'Effect of {param} on Model Performance')
                ax.grid(True, alpha=0.3)
                
                # Rotate x labels if needed
                plt.xticks(rotation=45, ha='right')
                
                plot_path = self.config.RESULTS_DIR / f"grid_search_{param}.png"
                fig.savefig(plot_path, dpi=self.config.FIGURE_DPI, bbox_inches='tight')
                plt.close()
        
        # Plot heatmap of top 2 parameters
        if len(param_names) >= 2:
            param1 = param_names[0]
            param2 = param_names[1]
            
            # Create pivot table
            pivot_data = defaultdict(dict)
            for params, score in zip(cv_results['params'], cv_results['mean_test_score']):
                pivot_data[str(params[param1])][str(params[param2])] = score
            
            df_pivot = pd.DataFrame(pivot_data)
            
            fig, ax = plt.subplots(figsize=(12, 8))
            sns.heatmap(df_pivot, annot=True, fmt='.3f', cmap=self.config.COLOR_MAP, ax=ax)
            ax.set_xlabel(param2)
            ax.set_ylabel(param1)
            ax.set_title('Grid Search Heatmap')
            
            plot_path = self.config.RESULTS_DIR / "grid_search_heatmap.png"
            fig.savefig(plot_path, dpi=self.config.FIGURE_DPI, bbox_inches='tight')
            plt.close()
            
            print(f"  Heatmap saved: {plot_path}")
    
    def plot_learning_curve(self, model, X, y, cv=5) -> None:
        """
        Plot learning curve for the best model
        
        Args:
            model: Trained model
            X: Training features
            y: Training labels
            cv: Number of cross-validation folds
        """
        print("\n[8] Generating learning curve...")
        
        from sklearn.model_selection import learning_curve
        
        train_sizes, train_scores, test_scores = learning_curve(
            model, X, y,
            train_sizes=np.linspace(0.1, 1.0, 10),
            cv=cv,
            scoring='f1_macro',
            n_jobs=-1
        )
        
        train_mean = np.mean(train_scores, axis=1)
        train_std = np.std(train_scores, axis=1)
        test_mean = np.mean(test_scores, axis=1)
        test_std = np.std(test_scores, axis=1)
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        ax.fill_between(train_sizes, train_mean - train_std, train_mean + train_std,
                        alpha=0.1, color='blue')
        ax.fill_between(train_sizes, test_mean - test_std, test_mean + test_std,
                        alpha=0.1, color='orange')
        ax.plot(train_sizes, train_mean, 'o-', color='blue', label='Training score')
        ax.plot(train_sizes, test_mean, 'o-', color='orange', label='Cross-validation score')
        
        ax.set_xlabel('Training Examples')
        ax.set_ylabel('F1 Macro Score')
        ax.set_title('Learning Curve')
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)
        
        plot_path = self.config.RESULTS_DIR / "learning_curve.png"
        fig.savefig(plot_path, dpi=self.config.FIGURE_DPI, bbox_inches='tight')
        plt.close()
        print(f"  Learning curve saved: {plot_path}")
    
    def plot_feature_importance(self, model, feature_names: List[str]) -> None:
        """
        Plot feature importance for the best model
        
        Args:
            model: Trained model with feature_importances_
            feature_names: List of feature names
        """
        print("\n[9] Generating feature importance plot...")
        
        if not hasattr(model, 'feature_importances_'):
            print("  Model does not support feature importance")
            return
        
        importances = model.feature_importances_
        indices = np.argsort(importances)[::-1]
        
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Top 20 features
        top_n = min(20, len(feature_names))
        y_pos = np.arange(top_n)
        
        ax.barh(y_pos, importances[indices[:top_n]][::-1])
        ax.set_yticks(y_pos)
        ax.set_yticklabels([feature_names[i] for i in indices[:top_n]][::-1])
        ax.set_xlabel('Feature Importance')
        ax.set_title('Top 20 Most Important Features')
        ax.grid(True, alpha=0.3, axis='x')
        
        plt.tight_layout()
        
        plot_path = self.config.RESULTS_DIR / "feature_importance.png"
        fig.savefig(plot_path, dpi=self.config.FIGURE_DPI, bbox_inches='tight')
        plt.close()
        print(f"  Feature importance saved: {plot_path}")
    
    # ========================================================================
    # Results Saving
    # ========================================================================
    
    def save_best_model(self, model, output_path: Path = None) -> None:
        """
        Save the best model
            
        Args:
            model: Best model to save
            output_path: Output path for saved model
        """
        if output_path is None:
            output_path = self.config.MODELS_DIR / "classifier_best.pkl"
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'wb') as f:
            pickle.dump(model, f)
        
        print(f"\n[10] Best model saved: {output_path}")
    
    def save_results(self, results: Dict[str, Any]) -> None:
        """
        Save tuning results to JSON
        
        Args:
            results: Dictionary of tuning results
        """
        print("\n[11] Saving tuning results...")
        
        # Convert numpy arrays to lists for JSON serialization
        def convert_to_serializable(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                return float(obj)
            return obj
        
        # Clean results
        cleaned_results = {}
        for key, value in results.items():
            cleaned_results[key] = convert_to_serializable(value)
        
        # Add timestamp
        cleaned_results['timestamp'] = datetime.now().isoformat()
        cleaned_results['config'] = {
            'n_folds': self.config.N_FOLDS,
            'validation_size': self.config.VALIDATION_SIZE,
            'random_state': self.config.RANDOM_STATE
        }
        
        # Save to file
        output_path = self.config.RESULTS_DIR / "tuning_results.json"
        with open(output_path, 'w') as f:
            json.dump(cleaned_results, f, indent=2, default=str)
        
        print(f"  Results saved: {output_path}")
    
    # ========================================================================
    # Main Pipeline
    # ========================================================================
    
    def run_tuning(self, methods: List[str] = None) -> Dict[str, Any]:
        """
        Run hyperparameter tuning pipeline
        
        Args:
            methods: List of tuning methods to run ('grid', 'random', 'optuna')
            
        Returns:
            Dictionary of tuning results
        """
        if methods is None:
            methods = ['grid', 'random', 'optuna']
        
        # Load data
        self.load_data()
        
        results = {}
        models = {}
        
        # Grid Search
        if 'grid' in methods:
            grid_results = self.grid_search_rf()
            results['grid_search'] = grid_results
            models['Random Forest (Grid)'] = self.best_model
        
        # Random Search
        if 'random' in methods:
            random_results = self.random_search_rf()
            results['random_search'] = random_results
            models['Random Forest (Random)'] = self.best_model
        
        # Optuna Bayesian Optimization
        if 'optuna' in methods and OPTUNA_AVAILABLE:
            optuna_results = self.optuna_optimize_rf(n_trials=self.config.OPTUNA_N_TRIALS)
            results['optuna'] = optuna_results
            models['Random Forest (Optuna)'] = self.best_model
        
        # Compare models
        comparison_df = self.compare_models(models)
        results['comparison'] = comparison_df.to_dict()
        
        # Visualize results
        if 'grid_search' in results and self.cv_results:
            self.plot_grid_search_results(self.cv_results)
        
        # Use best model for further analysis
        best_model_name = comparison_df.iloc[0]['Model']
        best_model = models[best_model_name]
        
        # Plot learning curve and feature importance
        from models.training.features.feature_schema import FEATURE_NAMES
        self.plot_learning_curve(best_model, self.X_train, self.y_train)
        self.plot_feature_importance(best_model, FEATURE_NAMES)
        
        # Save results
        self.save_best_model(best_model)
        self.save_results(results)
        
        # Print summary
        print("\n" + "=" * 70)
        print("TUNING COMPLETE - SUMMARY")
        print("=" * 70)
        print(f"Best Model: {best_model_name}")
        print(f"Best Parameters: {self.best_params}")
        print(f"Validation F1: {comparison_df.iloc[0]['F1 Macro']:.4f}")
        
        return results


# ============================================================================
# Command Line Interface
# ============================================================================

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Hyperparameter tuning for drone detection model"
    )
    
    parser.add_argument(
        "--methods",
        type=str,
        nargs='+',
        default=['grid', 'random', 'optuna'],
        choices=['grid', 'random', 'optuna'],
        help="Tuning methods to run"
    )
    
    parser.add_argument(
        "--n-trials",
        type=int,
        default=100,
        help="Number of trials for Optuna (default: 100)"
    )
    
    parser.add_argument(
        "--n-folds",
        type=int,
        default=5,
        help="Number of cross-validation folds (default: 5)"
    )
    
    parser.add_argument(
        "--random-iter",
        type=int,
        default=50,
        help="Number of iterations for random search (default: 50)"
    )
    
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Disable plot generation"
    )
    
    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_args()
    
    # Create configuration
    config = TuningConfig()
    config.N_FOLDS = args.n_folds
    config.RANDOM_N_ITER = args.random_iter
    config.OPTUNA_N_TRIALS = args.n_trials
    
    # Create tuner
    tuner = HyperparameterTuner(config)
    
    # Run tuning
    results = tuner.run_tuning(methods=args.methods)
    
    print("\n[SUCCESS] Hyperparameter tuning completed!")


if __name__ == "__main__":
    main()