"""
Background data loader service.

Loads fresh data from BigQuery in a background thread while app continues
serving cached data. Provides progress tracking and hot-swapping of data.
"""

import threading
import time
import logging
from typing import Callable, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class BackgroundDataLoader:
    """
    Manages background data loading with progress tracking.

    Allows app to serve cached data while fresh data loads in background.
    Provides hot-swapping when new data is ready.
    """

    def __init__(self, app_state: Any):
        """
        Initialize background loader.

        Args:
            app_state: FastAPI app.state object to update when data is ready
        """
        self.app_state = app_state
        self.loading = False
        self.progress = {
            "stage": "Idle",
            "progress": 0,
            "total": 0,
            "percent": 0,
            "started_at": None,
            "estimated_completion": None,
        }
        self.thread: Optional[threading.Thread] = None
        self.last_error: Optional[str] = None

    def start_background_load(
        self,
        load_func: Callable,
        on_complete: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
    ):
        """
        Start background data loading.

        Args:
            load_func: Function that loads data, should accept progress_callback kwarg
            on_complete: Optional callback when load succeeds
            on_error: Optional callback when load fails
        """
        if self.loading:
            logger.warning("[Background] Load already in progress, skipping")
            return False

        self.loading = True
        self.last_error = None
        self.progress = {
            "stage": "Starting background load...",
            "progress": 0,
            "total": 0,
            "percent": 0,
            "started_at": datetime.now().isoformat(),
            "estimated_completion": None,
        }

        def _load_wrapper():
            """Wrapper to handle load lifecycle."""
            try:
                logger.info("[Background] Starting data load")
                start_time = time.time()

                # Call load function with progress callback
                new_service = load_func(progress_callback=self._update_progress)

                elapsed = time.time() - start_time
                logger.info(f"[Background] Data loaded in {elapsed:.1f}s")

                # Hot-swap: atomically replace app's data service
                self.app_state.data_service = new_service
                self.progress = {
                    "stage": "Complete",
                    "progress": 1,
                    "total": 1,
                    "percent": 100,
                    "started_at": self.progress["started_at"],
                    "estimated_completion": datetime.now().isoformat(),
                }

                logger.info("[Background] Data service updated successfully")

                # NOTE: persistence is handled by the load_func (Parquet cache),
                # not here. The legacy multi-GB pickle save was removed.

                # Call success callback
                if on_complete:
                    try:
                        on_complete(new_service)
                    except Exception as e:
                        logger.error(f"[Background] Error in on_complete callback: {e}")

            except Exception as e:
                error_msg = str(e)
                logger.error(f"[Background] Load failed: {error_msg}")
                self.last_error = error_msg
                self.progress = {
                    "stage": f"Error: {error_msg}",
                    "progress": 0,
                    "total": 0,
                    "percent": 0,
                    "started_at": self.progress["started_at"],
                    "estimated_completion": None,
                }

                # Call error callback
                if on_error:
                    try:
                        on_error(e)
                    except Exception as cb_error:
                        logger.error(f"[Background] Error in on_error callback: {cb_error}")

            finally:
                self.loading = False
                logger.info("[Background] Load thread finished")

        # Start background thread
        self.thread = threading.Thread(target=_load_wrapper, daemon=True, name="background-loader")
        self.thread.start()
        logger.info("[Background] Background load thread started")
        return True

    def _update_progress(self, stage: str, progress: int, total: int):
        """
        Callback for progress updates from load function.

        Args:
            stage: Human-readable description of current stage
            progress: Current progress count
            total: Total count for completion
        """
        percent = int((progress / total * 100)) if total > 0 else 0

        # Estimate completion time based on current progress
        estimated_completion = None
        if progress > 0 and total > 0 and self.progress.get("started_at"):
            try:
                started = datetime.fromisoformat(self.progress["started_at"])
                elapsed = (datetime.now() - started).total_seconds()
                rate = progress / elapsed  # rows per second
                remaining = total - progress
                eta_seconds = remaining / rate if rate > 0 else 0
                estimated_completion = (datetime.now().timestamp() + eta_seconds)
                estimated_completion = datetime.fromtimestamp(estimated_completion).isoformat()
            except:
                pass

        self.progress = {
            "stage": stage,
            "progress": progress,
            "total": total,
            "percent": percent,
            "started_at": self.progress.get("started_at"),
            "estimated_completion": estimated_completion,
        }

        # Log every 10% progress
        if percent % 10 == 0 and percent > 0:
            logger.info(f"[Background] {stage} - {percent}%")

    def get_progress(self) -> dict:
        """
        Get current progress status.

        Returns:
            Dictionary with progress information including:
            - loading: bool - whether load is in progress
            - stage: str - current stage description
            - progress: int - current progress count
            - total: int - total count for completion
            - percent: int - percentage complete (0-100)
            - started_at: str - ISO timestamp when load started
            - estimated_completion: str - ISO timestamp of estimated completion
            - last_error: str - last error message if any
        """
        return {
            **self.progress,
            "loading": self.loading,
            "last_error": self.last_error,
        }

    def is_loading(self) -> bool:
        """Check if background load is in progress."""
        return self.loading

    def cancel(self):
        """
        Request cancellation of background load.

        Note: Cancellation is not immediate - thread will finish current operation.
        """
        if self.loading and self.thread and self.thread.is_alive():
            logger.warning("[Background] Cancellation requested (not immediate)")
            # Python doesn't support thread cancellation, just mark as cancelled
            self.progress["stage"] = "Cancellation requested..."
        else:
            logger.info("[Background] No active load to cancel")
