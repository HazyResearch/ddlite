import logging
from typing import Any, Optional

from snorkel.classification.snorkel_classifier import SnorkelClassifier
from snorkel.classification.snorkel_config import default_config
from snorkel.classification.utils import recursive_merge_dicts
from snorkel.types import Config

from .checkpointer import Checkpointer
from .log_writer import LogWriter


class LogManagerConfig(Config):
    """[summary]

    Parameters
    ----------
    TBD
    """
    counter_unit: str = "epochs"  # [points, batches, epochs]
    evaluation_freq: float = 1.0  # Evaluate performance every this many counter_units


class LogManager(object):
    """A class to manage logging during training progress.

    Parameters
    ----------
    n_batches_per_epoch
        Total number batches per epoch
    log_writer
        `LogWriter` for current run logs
    checkpointer
        `Checkpointer` for current model
    kwargs
        Config merged with `default_config["log_manager_config"]`
    """

    def __init__(
        self,
        n_batches_per_epoch: int,
        log_writer: Optional[LogWriter] = None,
        checkpointer: Optional[Checkpointer] = None,
        **kwargs: Any,
    ) -> None:
        assert isinstance(default_config["log_manager_config"], dict)
        self.config = LogManagerConfig(**kwargs)
        self.n_batches_per_epoch = n_batches_per_epoch

        self.log_writer = log_writer
        self.checkpointer = checkpointer

        # Set up counter unit
        self.counter_unit = self.config.counter_unit
        if self.counter_unit not in ["points", "batches", "epochs"]:
            raise ValueError(f"Unrecognized counter_unit: {self.counter_unit}")

        # Set up evaluation frequency
        self.evaluation_freq = self.config.evaluation_freq
        logging.info(f"Evaluating every {self.evaluation_freq} {self.counter_unit}.")

        # Set up number of X passed since last evaluation/checkpointing and total
        self.point_count = 0
        self.point_total = 0

        self.batch_count = 0
        self.batch_total = 0

        self.epoch_count = 0.0
        self.epoch_total = 0.0

        self.unit_count = 0.0
        self.unit_total = 0.0

        # Set up count that triggers the evaluation since last checkpointing
        self.trigger_count = 0

    def update(self, batch_size: int) -> None:
        """Update the count and total number."""

        # Update number of points
        self.point_count += batch_size
        self.point_total += batch_size

        # Update number of batches
        self.batch_count += 1
        self.batch_total += 1

        # Update number of epochs
        self.epoch_count = self.batch_count / self.n_batches_per_epoch
        self.epoch_total = self.batch_total / self.n_batches_per_epoch

        # Update number of units
        if self.counter_unit == "points":
            self.unit_count = self.point_count
            self.unit_total = self.point_total
        if self.counter_unit == "batches":
            self.unit_count = self.batch_count
            self.unit_total = self.batch_total
        elif self.counter_unit == "epochs":
            self.unit_count = self.epoch_count
            self.unit_total = self.epoch_total

    def trigger_evaluation(self) -> bool:
        """Check if current counts trigger evaluation."""
        satisfied = self.unit_count >= self.evaluation_freq
        if satisfied:
            self.trigger_count += 1
            self.reset()
        return satisfied

    def trigger_checkpointing(self) -> bool:
        """Check if current counts trigger  checkpointing."""
        if self.checkpointer is None:
            return False
        satisfied = self.trigger_count >= self.checkpointer.checkpoint_factor
        if satisfied:
            self.trigger_count = 0
        return satisfied

    def reset(self) -> None:
        """Reset counters."""
        self.point_count = 0
        self.batch_count = 0
        self.epoch_count = 0
        self.unit_count = 0

    def close(self, model: SnorkelClassifier) -> SnorkelClassifier:
        """Close the log writer and checkpointer if needed. Reload best model."""
        if self.log_writer is not None:
            self.log_writer.close()
        if self.checkpointer is not None:
            self.checkpointer.clear()
            model = self.checkpointer.load_best_model(model)
        return model
