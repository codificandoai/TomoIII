import unittest
import os
import pandas as pd
import numpy as np
import joblib

from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from challenge.model import DelayModel

class TestModel(unittest.TestCase):

    FEATURES_COLS = [
        "OPERA_Latin American Wings", 
        "MES_7",
        "MES_10",
        "OPERA_Grupo LATAM",
        "MES_12",
        "TIPOVUELO_I",
        "MES_4",
        "MES_11",
        "OPERA_Sky Airline",
        "OPERA_Copa Air"
    ]

    TARGET_COL = [
        "delay"
    ]


    def setUp(self) -> None:
        super().setUp()
        self.model = DelayModel()
        self.data = pd.read_csv(filepath_or_buffer="../data/data.csv")
        

    def test_model_preprocess_for_training(
        self
    ):
        features, target = self.model.preprocess(
            data=self.data,
            target_column="delay"
        )

        assert isinstance(features, pd.DataFrame)
        assert features.shape[1] == len(self.FEATURES_COLS)
        assert set(features.columns) == set(self.FEATURES_COLS)

        assert isinstance(target, pd.DataFrame)
        assert target.shape[1] == len(self.TARGET_COL)
        assert set(target.columns) == set(self.TARGET_COL)


    def test_model_preprocess_for_serving(
        self
    ):
        features = self.model.preprocess(
            data=self.data
        )

        assert isinstance(features, pd.DataFrame)
        assert features.shape[1] == len(self.FEATURES_COLS)
        assert set(features.columns) == set(self.FEATURES_COLS)


    def test_model_fit(
        self
    ):
        features, target = self.model.preprocess(
            data=self.data,
            target_column="delay"
        )

        _, features_validation, _, target_validation = train_test_split(features, target, test_size = 0.33, random_state = 42)

        self.model.fit(
            features=features,
            target=target
        )

        predicted_target = self.model._model.predict(
            features_validation
        )

        report = classification_report(target_validation, predicted_target, output_dict=True)
        
        assert report["0"]["recall"] < 0.60
        assert report["0"]["f1-score"] < 0.70
        assert report["1"]["recall"] > 0.60
        assert report["1"]["f1-score"] > 0.30


    def test_model_predict(
        self
    ):
        features = self.model.preprocess(
            data=self.data
        )

        predicted_targets = self.model.predict(
            features=features
        )

        assert isinstance(predicted_targets, list)
        assert len(predicted_targets) == features.shape[0]
        assert all(isinstance(predicted_target, int) for predicted_target in predicted_targets)

    def test_preprocess_api_input(self):
        """Test preprocess_api with list of dicts (API JSON input)."""
        flights = [
            {"OPERA": "Grupo LATAM", "TIPOVUELO": "I", "MES": 12},
            {"OPERA": "Latin American Wings", "TIPOVUELO": "N", "MES": 7},
            {"OPERA": "Sky Airline", "TIPOVUELO": "I", "MES": 4},
        ]
        features = self.model.preprocess_api(flights)
        assert isinstance(features, pd.DataFrame)
        assert features.shape == (3, len(self.FEATURES_COLS))
        assert set(features.columns) == set(self.FEATURES_COLS)

    def test_feature_alignment(self):
        """Test that unknown OPERA/MES values produce all-zero rows aligned to TOP_10_FEATURES."""
        api_data = pd.DataFrame([
            {"OPERA": "Unknown Airline", "TIPOVUELO": "N", "MES": 2},
        ])
        features = self.model.preprocess(api_data)
        assert features.shape == (1, len(self.FEATURES_COLS))
        assert (features.iloc[0] == 0).all()

    def test_predict_single_flight(self):
        """Test predict on a single flight returns a list with one int."""
        api_data = pd.DataFrame([
            {"OPERA": "Grupo LATAM", "TIPOVUELO": "N", "MES": 3},
        ])
        features = self.model.preprocess(api_data)
        predictions = self.model.predict(features)
        assert isinstance(predictions, list)
        assert len(predictions) == 1
        assert predictions[0] in (0, 1)

    def test_predict_output_values_are_binary(self):
        """Test that all predictions are 0 or 1."""
        features = self.model.preprocess(self.data)
        predictions = self.model.predict(features)
        assert all(p in (0, 1) for p in predictions)

    def test_get_min_diff(self):
        """Test the static _get_min_diff method."""
        row = pd.Series({
            "Fecha-O": "2017-01-01 23:45:00",
            "Fecha-I": "2017-01-01 23:30:00",
        })
        result = DelayModel._get_min_diff(row)
        assert result == 15.0

    def test_preprocess_target_delay_values(self):
        """Test that target column contains only 0 and 1."""
        features, target = self.model.preprocess(self.data, target_column="delay")
        unique_vals = set(target["delay"].unique())
        assert unique_vals.issubset({0, 1})

    def test_model_persistence(self):
        """Test that fit saves dict with model + feature_columns, and _load restores both."""
        features, target = self.model.preprocess(self.data, target_column="delay")
        self.model.fit(features, target)
        assert os.path.exists(DelayModel._MODEL_PATH)

        saved = joblib.load(DelayModel._MODEL_PATH)
        assert isinstance(saved, dict)
        assert "model" in saved
        assert "feature_columns" in saved

        new_model = DelayModel()
        assert new_model._model is None
        assert new_model._feature_columns is None
        new_model._load()
        assert new_model._model is not None
        assert new_model._feature_columns == self.FEATURES_COLS

        feats = new_model.preprocess_api([{"OPERA": "Copa Air", "TIPOVUELO": "I", "MES": 10}])
        preds = new_model.predict(feats)
        assert isinstance(preds, list)
        assert len(preds) == 1

    def test_load_backward_compat(self):
        """Test _load handles old format (raw model, not dict)."""
        features, target = self.model.preprocess(self.data, target_column="delay")
        self.model.fit(features, target)
        joblib.dump(self.model._model, DelayModel._MODEL_PATH)

        new_model = DelayModel()
        new_model._load()
        assert new_model._model is not None
        assert new_model._feature_columns is None

    def test_feature_columns_property_default(self):
        """Test feature_columns returns TOP_10_FEATURES when no custom columns set."""
        assert self.model.feature_columns == DelayModel.TOP_10_FEATURES

    def test_feature_columns_property_custom(self):
        """Test feature_columns returns custom columns after fit."""
        features, target = self.model.preprocess(self.data, target_column="delay")
        self.model.fit(features, target)
        assert self.model.feature_columns == self.FEATURES_COLS

    def test_train_from_csv(self):
        """Test train_from_csv loads data, preprocesses, fits, and saves."""
        csv_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "data.csv"
        )
        self.model.train_from_csv(csv_path)
        assert self.model._model is not None
        assert self.model._feature_columns is not None
        assert os.path.exists(DelayModel._MODEL_PATH)

    def test_threshold_in_minutes(self):
        """Test THRESHOLD_IN_MINUTES is used for delay calculation."""
        assert DelayModel.THRESHOLD_IN_MINUTES == 15

    def test_get_period_day(self):
        """Test _get_period_day classifies morning, afternoon, and night correctly."""
        assert DelayModel._get_period_day("2017-01-01 08:00:00") == "mañana"
        assert DelayModel._get_period_day("2017-01-01 05:00:00") == "mañana"
        assert DelayModel._get_period_day("2017-01-01 11:59:00") == "mañana"
        assert DelayModel._get_period_day("2017-01-01 12:00:00") == "tarde"
        assert DelayModel._get_period_day("2017-01-01 15:30:00") == "tarde"
        assert DelayModel._get_period_day("2017-01-01 18:59:00") == "tarde"
        assert DelayModel._get_period_day("2017-01-01 19:00:00") == "noche"
        assert DelayModel._get_period_day("2017-01-01 23:59:00") == "noche"
        assert DelayModel._get_period_day("2017-01-01 00:00:00") == "noche"
        assert DelayModel._get_period_day("2017-01-01 04:59:00") == "noche"

    def test_is_high_season(self):
        """Test _is_high_season identifies high season date ranges."""
        assert DelayModel._is_high_season("2017-12-20 10:00:00") == 1
        assert DelayModel._is_high_season("2017-01-15 10:00:00") == 1
        assert DelayModel._is_high_season("2017-02-28 10:00:00") == 1
        assert DelayModel._is_high_season("2017-07-20 10:00:00") == 1
        assert DelayModel._is_high_season("2017-09-15 10:00:00") == 1
        assert DelayModel._is_high_season("2017-06-01 10:00:00") == 0
        assert DelayModel._is_high_season("2017-04-15 10:00:00") == 0
        assert DelayModel._is_high_season("2017-11-01 10:00:00") == 0

    def test_preprocess_generates_derived_columns(self):
        """Test that preprocess generates period_day and high_season from Fecha-I."""
        sample = self.data.head(10)
        features, target = self.model.preprocess(sample, target_column="delay")
        assert isinstance(features, pd.DataFrame)
        assert isinstance(target, pd.DataFrame)
        assert target.shape == (10, 1)

    def test_predictions_match_ground_truth(self):
        """Validate predictions against actual delay labels on training data."""
        features, target = self.model.preprocess(self.data, target_column="delay")
        x_train, x_test, y_train, y_test = train_test_split(
            features, target, test_size=0.33, random_state=42
        )
        self.model.fit(x_train, y_train)
        preds = self.model.predict(x_test)

        report = classification_report(y_test, preds, output_dict=True)
        assert report["1"]["recall"] > 0.60
        assert report["1"]["f1-score"] > 0.30
        assert report["0"]["f1-score"] > 0.50
        assert set(preds).issubset({0, 1})
        assert len(set(preds)) == 2

    def test_retrain_with_new_data(self):
        """Test model can be retrained with new/updated data."""
        csv_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "data.csv"
        )
        self.model.train_from_csv(csv_path)
        feats1 = self.model.preprocess_api([
            {"OPERA": "Grupo LATAM", "TIPOVUELO": "N", "MES": 7}
        ])
        pred1 = self.model.predict(feats1)

        self.model.train_from_csv(csv_path)
        feats2 = self.model.preprocess_api([
            {"OPERA": "Grupo LATAM", "TIPOVUELO": "N", "MES": 7}
        ])
        pred2 = self.model.predict(feats2)

        assert pred1 == pred2
        assert self.model._model is not None
        assert self.model._feature_columns is not None

    def test_varied_api_predictions(self):
        """Test API-style input produces varied (not all same) predictions."""
        csv_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "data.csv"
        )
        self.model.train_from_csv(csv_path)
        flights = [
            {"OPERA": "Aerolineas Argentinas", "TIPOVUELO": "N", "MES": 3},
            {"OPERA": "Grupo LATAM", "TIPOVUELO": "N", "MES": 7},
            {"OPERA": "Latin American Wings", "TIPOVUELO": "N", "MES": 7},
            {"OPERA": "Sky Airline", "TIPOVUELO": "I", "MES": 12},
            {"OPERA": "Copa Air", "TIPOVUELO": "I", "MES": 10},
            {"OPERA": "Unknown Airline", "TIPOVUELO": "N", "MES": 2},
        ]
        feats = self.model.preprocess_api(flights)
        preds = self.model.predict(feats)
        assert len(preds) == 6
        assert all(p in (0, 1) for p in preds)