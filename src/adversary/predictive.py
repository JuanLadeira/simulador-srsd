"""
Predictive Adversary - ML-based route prediction attack.

Implements an adversary that uses machine learning (scikit-learn)
to predict routing paths based on observed traffic patterns.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np

from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

from ..core.graph import NetworkGraph
from ..routing.baseline import FlowRecord


@dataclass
class PredictionResult:
    """Result of a route prediction."""

    flow_id: str
    source: str
    destination: str
    predicted_path: List[str]
    actual_path: List[str]
    correct: bool
    confidence: float


@dataclass
class PredictiveAdversaryMetrics:
    """Metrics for predictive adversary performance."""

    total_predictions: int = 0
    correct_predictions: int = 0
    partial_matches: int = 0  # Predicted some hops correctly

    # Per-hop accuracy
    total_hops_predicted: int = 0
    correct_hops: int = 0

    # Training info
    training_samples: int = 0
    feature_count: int = 0

    @property
    def accuracy(self) -> float:
        """Overall prediction accuracy."""
        if self.total_predictions == 0:
            return 0.0
        return self.correct_predictions / self.total_predictions

    @property
    def partial_accuracy(self) -> float:
        """Partial match rate (at least some hops correct)."""
        if self.total_predictions == 0:
            return 0.0
        return (self.correct_predictions + self.partial_matches) / self.total_predictions

    @property
    def hop_accuracy(self) -> float:
        """Per-hop prediction accuracy."""
        if self.total_hops_predicted == 0:
            return 0.0
        return self.correct_hops / self.total_hops_predicted

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "total_predictions": self.total_predictions,
            "correct_predictions": self.correct_predictions,
            "partial_matches": self.partial_matches,
            "accuracy": self.accuracy,
            "partial_accuracy": self.partial_accuracy,
            "hop_accuracy": self.hop_accuracy,
            "training_samples": self.training_samples,
            "feature_count": self.feature_count,
        }


class PredictiveAdversary:
    """
    ML-based adversary that predicts routing paths.

    Uses observed traffic patterns to train a classifier that
    predicts the path a flow will take through the network.

    Features used:
    - Source node (encoded)
    - Destination node (encoded)
    - Flow index (temporal pattern)
    - Recent path history (last N paths for same src-dst)
    """

    def __init__(
        self,
        graph: NetworkGraph,
        history_size: int = 5,
        training_ratio: float = 0.7,
        random_state: int = 42,
    ):
        """
        Initialize predictive adversary.

        Args:
            graph: Network graph
            history_size: Number of recent flows to consider as features
            training_ratio: Fraction of flows to use for training
            random_state: Random seed for reproducibility
        """
        self.graph = graph
        self.history_size = history_size
        self.training_ratio = training_ratio
        self.random_state = random_state

        # Encoders for categorical features
        self._node_encoder = LabelEncoder()
        self._path_encoder = LabelEncoder()

        # Fit node encoder with all nodes
        node_ids = [n.id for n in graph.get_nodes()]
        self._node_encoder.fit(node_ids)

        # Model
        self._model: Optional[RandomForestClassifier] = None

        # Observed flows for training
        self._observed_flows: List[FlowRecord] = []
        self._flow_history: Dict[Tuple[str, str], List[str]] = defaultdict(list)

        # Known paths (for encoding)
        self._known_paths: List[str] = []

        # Metrics
        self.metrics = PredictiveAdversaryMetrics()

        # State
        self._is_trained = False

    def observe_flow(self, flow: FlowRecord) -> None:
        """
        Observe a flow for training purposes.

        Args:
            flow: Flow record to observe
        """
        self._observed_flows.append(flow)

        # Update flow history for this source-destination pair
        key = (flow.source, flow.destination)
        path_key = "->".join(flow.path)
        self._flow_history[key].append(path_key)

        # Track unique paths
        if path_key not in self._known_paths:
            self._known_paths.append(path_key)

    def train(self) -> None:
        """
        Train the prediction model on observed flows.

        Uses a portion of observed flows for training.
        """
        if len(self._observed_flows) < 10:
            return

        # Split data
        split_idx = int(len(self._observed_flows) * self.training_ratio)
        training_flows = self._observed_flows[:split_idx]

        if len(training_flows) < 5:
            return

        # Fit path encoder with known paths
        self._path_encoder.fit(self._known_paths)

        # Build feature matrix and labels
        X, y = self._build_training_data(training_flows)

        if len(X) == 0 or len(set(y)) < 2:
            return

        # Train model
        self._model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=self.random_state,
            n_jobs=-1,
        )
        self._model.fit(X, y)

        self.metrics.training_samples = len(X)
        self.metrics.feature_count = X.shape[1] if len(X) > 0 else 0
        self._is_trained = True

    def _build_training_data(
        self, flows: List[FlowRecord]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Build feature matrix and labels from flows.

        Args:
            flows: List of flow records

        Returns:
            Tuple of (features, labels)
        """
        X = []
        y = []

        # Build history up to each flow
        history: Dict[Tuple[str, str], List[str]] = defaultdict(list)

        for i, flow in enumerate(flows):
            key = (flow.source, flow.destination)
            path_key = "->".join(flow.path)

            # Skip if path not in encoder
            if path_key not in self._known_paths:
                history[key].append(path_key)
                continue

            # Build features
            features = self._extract_features(flow, i, history[key])
            X.append(features)

            # Label is the path taken
            try:
                label = self._path_encoder.transform([path_key])[0]
                y.append(label)
            except ValueError:
                # Unknown path, skip
                continue

            # Update history
            history[key].append(path_key)
            if len(history[key]) > self.history_size:
                history[key] = history[key][-self.history_size:]

        if len(X) == 0:
            return np.array([]), np.array([])

        return np.array(X), np.array(y)

    def _extract_features(
        self,
        flow: FlowRecord,
        flow_index: int,
        history: List[str],
    ) -> List[float]:
        """
        Extract features from a flow.

        Args:
            flow: Flow record
            flow_index: Index of flow in sequence
            history: Recent path history for this src-dst pair

        Returns:
            Feature vector
        """
        features = []

        # Source and destination (encoded)
        try:
            src_encoded = self._node_encoder.transform([flow.source])[0]
            dst_encoded = self._node_encoder.transform([flow.destination])[0]
        except ValueError:
            src_encoded = -1
            dst_encoded = -1

        features.append(float(src_encoded))
        features.append(float(dst_encoded))

        # Flow index (temporal pattern)
        features.append(float(flow_index))

        # Number of possible paths (from graph)
        try:
            num_paths = len(
                list(self.graph.all_simple_paths(flow.source, flow.destination, cutoff=5))
            )
        except Exception:
            num_paths = 1
        features.append(float(min(num_paths, 10)))  # Cap at 10

        # History features (last N path encodings)
        history_features = [0.0] * self.history_size
        for i, path_key in enumerate(history[-self.history_size:]):
            try:
                if path_key in self._known_paths:
                    history_features[i] = float(
                        self._path_encoder.transform([path_key])[0]
                    )
            except ValueError:
                pass
        features.extend(history_features)

        # History diversity (number of unique paths in history)
        unique_in_history = len(set(history[-self.history_size:]))
        features.append(float(unique_in_history))

        return features

    def predict(self, flow: FlowRecord, flow_index: int = 0) -> Optional[PredictionResult]:
        """
        Predict the path for a flow.

        Args:
            flow: Flow to predict (with known actual path)
            flow_index: Index of flow in sequence

        Returns:
            Prediction result or None if model not trained
        """
        if not self._is_trained or self._model is None:
            return None

        key = (flow.source, flow.destination)
        history = self._flow_history.get(key, [])

        # Extract features
        features = self._extract_features(flow, flow_index, history)
        X = np.array([features])

        # Predict
        try:
            pred_label = self._model.predict(X)[0]
            pred_proba = self._model.predict_proba(X)[0]
            confidence = float(max(pred_proba))

            # Decode path
            pred_path_key = self._path_encoder.inverse_transform([pred_label])[0]
            predicted_path = pred_path_key.split("->")
        except Exception:
            return None

        # Compare with actual path
        actual_path_key = "->".join(flow.path)
        correct = pred_path_key == actual_path_key

        # Check partial match (first N hops)
        partial_match = False
        correct_hops = 0
        min_len = min(len(predicted_path), len(flow.path))
        for i in range(min_len):
            if predicted_path[i] == flow.path[i]:
                correct_hops += 1
        if correct_hops > 0 and not correct:
            partial_match = True

        # Update metrics
        self.metrics.total_predictions += 1
        if correct:
            self.metrics.correct_predictions += 1
        elif partial_match:
            self.metrics.partial_matches += 1
        self.metrics.total_hops_predicted += len(flow.path)
        self.metrics.correct_hops += correct_hops

        return PredictionResult(
            flow_id=flow.flow_id,
            source=flow.source,
            destination=flow.destination,
            predicted_path=predicted_path,
            actual_path=flow.path,
            correct=correct,
            confidence=confidence,
        )

    def evaluate(self, test_flows: Optional[List[FlowRecord]] = None) -> PredictiveAdversaryMetrics:
        """
        Evaluate prediction accuracy on test flows.

        Args:
            test_flows: Flows to test on (default: remaining observed flows)

        Returns:
            Metrics for the evaluation
        """
        if test_flows is None:
            # Use remaining flows after training split
            split_idx = int(len(self._observed_flows) * self.training_ratio)
            test_flows = self._observed_flows[split_idx:]

        # Reset metrics for evaluation
        self.metrics = PredictiveAdversaryMetrics(
            training_samples=self.metrics.training_samples,
            feature_count=self.metrics.feature_count,
        )

        for i, flow in enumerate(test_flows):
            self.predict(flow, flow_index=i)

        return self.metrics

    def get_feature_importance(self) -> Optional[Dict[str, float]]:
        """
        Get feature importance from the trained model.

        Returns:
            Dictionary mapping feature names to importance scores
        """
        if not self._is_trained or self._model is None:
            return None

        feature_names = [
            "source",
            "destination",
            "flow_index",
            "num_paths",
        ]
        feature_names.extend([f"history_{i}" for i in range(self.history_size)])
        feature_names.append("history_diversity")

        importances = self._model.feature_importances_

        return dict(zip(feature_names, importances))

    def reset(self) -> None:
        """Reset the adversary state."""
        self._observed_flows.clear()
        self._flow_history.clear()
        self._known_paths.clear()
        self._model = None
        self._is_trained = False
        self.metrics = PredictiveAdversaryMetrics()
