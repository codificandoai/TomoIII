import pandas as pd
import numpy as np
import os
import joblib
import xgboost as xgb

from datetime import datetime
from typing import Tuple, Union, List


class DelayModel:

    TOP_10_FEATURES = [
        "OPERA_Latin American Wings",
        "MES_7",
        "MES_10",
        "OPERA_Grupo LATAM",
        "MES_12",
        "TIPOVUELO_I",
        "MES_4",
        "MES_11",
        "OPERA_Sky Airline",
        "OPERA_Copa Air",
    ]

    THRESHOLD_IN_MINUTES = 15

    _MODEL_PATH = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "model.pkl"
    )

    def __init__(
        self
    ):
        self._model = None # Model should be saved in this attribute.
        self._feature_columns = None

    @property
    def feature_columns(self) -> List[str]:
        """Dynamic feature columns: uses saved columns if available, otherwise TOP_10_FEATURES."""
        if self._feature_columns is not None:
            return self._feature_columns
        return self.TOP_10_FEATURES

    def train_from_csv(self, csv_path: str) -> None:
        """Train model automatically from a CSV file."""
        data = pd.read_csv(csv_path, low_memory=False)
        features, target = self.preprocess(data, target_column="delay")
        self.fit(features, target)

    def preprocess_api(self, flights: List[dict]) -> pd.DataFrame:
        """Preprocess API JSON input into model features."""
        df = pd.DataFrame(flights)
        return self.preprocess(df)

    def preprocess(
        self,
        data: pd.DataFrame,
        target_column: str = None
    ) -> Union[Tuple[pd.DataFrame, pd.DataFrame], pd.DataFrame]:
        """
        Prepare raw data for training or predict.

        Args:
            data (pd.DataFrame): raw data.
            target_column (str, optional): if set, the target is returned.

        Returns:
            Tuple[pd.DataFrame, pd.DataFrame]: features and target.
            or
            pd.DataFrame: features.
        """
        data = data.copy()

        # Generate derived columns when raw data is available
        if "Fecha-I" in data.columns:
            data["period_day"] = data["Fecha-I"].apply(self._get_period_day)
            data["high_season"] = data["Fecha-I"].apply(self._is_high_season)

        if "Fecha-O" in data.columns and "Fecha-I" in data.columns:
            data["min_diff"] = data.apply(self._get_min_diff, axis=1)

        # One-hot encode categorical columns
        dummies_list = [
            pd.get_dummies(data["OPERA"], prefix="OPERA"),
            pd.get_dummies(data["TIPOVUELO"], prefix="TIPOVUELO"),
            pd.get_dummies(data["MES"], prefix="MES"),
        ]
        if "period_day" in data.columns:
            dummies_list.append(pd.get_dummies(data["period_day"], prefix="period_day"))
        if "high_season" in data.columns:
            dummies_list.append(data[["high_season"]])

        features = pd.concat(dummies_list, axis=1)
        features = features.reindex(columns=self.feature_columns, fill_value=0)

        if target_column:
            if "min_diff" not in data.columns:
                data["min_diff"] = data.apply(self._get_min_diff, axis=1)
            data[target_column] = np.where(data["min_diff"] > self.THRESHOLD_IN_MINUTES, 1, 0)
            target = data[[target_column]]
            return features, target

        return features

    def fit(
        self,
        features: pd.DataFrame,
        target: pd.DataFrame
    ) -> None:
        """
        Fit model with preprocessed data.

        Args:
            features (pd.DataFrame): preprocessed data.
            target (pd.DataFrame): target.
        """
        self._feature_columns = features.columns.tolist()

        target_values = target.iloc[:, 0]
        n_y0 = int((target_values == 0).sum())
        n_y1 = int((target_values == 1).sum())
        scale = n_y0 / n_y1

        self._model = xgb.XGBClassifier(
            random_state=1,
            learning_rate=0.01,
            scale_pos_weight=scale,
            n_estimators=500,
            max_depth=3,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric="logloss",
        )
        self._model.fit(features, target_values)

        self._save()

    def predict(
        self,
        features: pd.DataFrame
    ) -> List[int]:
        """
        Predict delays for new flights.

        Args:
            features (pd.DataFrame): preprocessed data.
        
        Returns:
            (List[int]): predicted targets.
        """
        if self._model is None:
            self._load()

        predictions = self._model.predict(features)
        return [int(p) for p in predictions]

    def _save(self) -> None:
        """Save model and configuration to disk."""
        joblib.dump(
            {"model": self._model, "feature_columns": self._feature_columns},
            self._MODEL_PATH,
        )

    def _load(self) -> None:
        """Load model and configuration from disk."""
        saved = joblib.load(self._MODEL_PATH)
        if isinstance(saved, dict):
            self._model = saved["model"]
            self._feature_columns = saved.get("feature_columns")
        else:
            self._model = saved

    @staticmethod
    def _get_min_diff(row: pd.Series) -> float:
        """Difference in minutes between Fecha-O and Fecha-I."""
        fecha_o = datetime.strptime(row["Fecha-O"], "%Y-%m-%d %H:%M:%S")
        fecha_i = datetime.strptime(row["Fecha-I"], "%Y-%m-%d %H:%M:%S")
        return ((fecha_o - fecha_i).total_seconds()) / 60

    @staticmethod
    def _get_period_day(date_str: str) -> str:
        """Classify time of day: morning (5:00-11:59), afternoon (12:00-18:59), night (19:00-4:59)."""
        date_time = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").time()
        morning_min = datetime.strptime("05:00", "%H:%M").time()
        morning_max = datetime.strptime("11:59", "%H:%M").time()
        afternoon_min = datetime.strptime("12:00", "%H:%M").time()
        afternoon_max = datetime.strptime("18:59", "%H:%M").time()
        evening_min = datetime.strptime("19:00", "%H:%M").time()
        evening_max = datetime.strptime("23:59", "%H:%M").time()
        night_min = datetime.strptime("00:00", "%H:%M").time()
        night_max = datetime.strptime("04:59", "%H:%M").time()

        if morning_min <= date_time <= morning_max:
            return "mañana"
        elif afternoon_min <= date_time <= afternoon_max:
            return "tarde"
        elif (evening_min <= date_time <= evening_max) or (night_min <= date_time <= night_max):
            return "noche"
        return "noche"

    @staticmethod
    def _is_high_season(date_str: str) -> int:
        """1 if date is in high season (Dec 15-Mar 3, Jul 15-31, Sep 11-30), 0 otherwise."""
        year = int(date_str.split("-")[0])
        fecha = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        ranges = [
            (datetime(year, 12, 15), datetime(year, 12, 31)),
            (datetime(year, 1, 1), datetime(year, 3, 3)),
            (datetime(year, 7, 15), datetime(year, 7, 31)),
            (datetime(year, 9, 11), datetime(year, 9, 30)),
        ]
        for range_min, range_max in ranges:
            if range_min <= fecha <= range_max:
                return 1
        return 0