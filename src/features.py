"""
Feature engineering + preprocessing pipeline for Step 1.

Responsibilities:
  - select the safe (non-leaky) feature columns
  - build X (features) and y (target)
  - build a sklearn ColumnTransformer:
        numeric    -> SimpleImputer(median) + StandardScaler
        categorical-> SimpleImputer(most_frequent) + OneHotEncoder
"""

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

import config


def build_xy(df):
    """Return (X, y) using only the configured, non-leaky feature columns."""
    # Guard: make sure none of the leakage columns leaked into the feature list.
    leaky = set(config.LEAKAGE_COLS) & set(config.ALL_FEATURES)
    if leaky:
        raise ValueError(f"Leakage columns present in feature list: {sorted(leaky)}")

    X = df[config.ALL_FEATURES].copy()

    # MCC_Code is a category code, not a magnitude -> force to string.
    if "MCC_Code" in X.columns:
        X["MCC_Code"] = X["MCC_Code"].astype("string")

    y = df[config.TARGET].astype(int)
    return X, y


def build_preprocessor():
    """Build the ColumnTransformer that handles numeric + categorical columns."""
    numeric_pipe = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])

    categorical_pipe = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_pipe, config.NUMERIC_FEATURES),
            ("cat", categorical_pipe, config.CATEGORICAL_FEATURES),
        ],
        remainder="drop",
    )
    return preprocessor


def get_feature_metadata():
    """Return a dict describing the feature set (used for outputs/feature_list.json)."""
    return {
        "target": config.TARGET,
        "n_numeric": len(config.NUMERIC_FEATURES),
        "n_categorical": len(config.CATEGORICAL_FEATURES),
        "numeric_features": config.NUMERIC_FEATURES,
        "categorical_features": config.CATEGORICAL_FEATURES,
        "excluded_leakage_columns": config.LEAKAGE_COLS,
        "comparison_only_column": config.COMPARISON_COL,
    }
