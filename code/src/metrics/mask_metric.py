from torch import Tensor

import wandb
from metrics.base_metric import BaseMetric, StepData


class MaskMetric(BaseMetric):
    """Saves the first batch of images with segmentation masks"""

    def __init__(
        self,
        name: str,
        class_labels: dict,
        limit: int = 32,
        threshold: float = 0.01,
    ) -> None:
        super().__init__(name)
        self._first_batch = None
        self._limit = limit
        self.class_labels = class_labels
        self._image_label = "input"
        self._target_label = "target"
        self._threshold = threshold

    def update(self, step_data: StepData):
        if self._first_batch is None:
            x = step_data.batch[self._image_label]
            y_true = step_data.batch[self._target_label]
            y_pred = step_data.model_out["out"]

            if x.shape[0] > self._limit:
                x, y_true, y_pred = (
                    x[: self._limit],
                    y_true[: self._limit],
                    y_pred[: self._limit],
                )

            pr_masks_scr, pr_masks_val = y_pred.max(1)
            pr_masks_val[pr_masks_scr < self._threshold] = len(
                self.class_labels
            )
            # Convert from BCHW to BHWC
            self._first_batch = (
                x.detach()
                .permute(0, 2, 3, 1)
                .to(device="cpu", non_blocking=True)
                .numpy(),
                y_true.detach()
                .to(device="cpu", non_blocking=True)
                .numpy(),
                pr_masks_val.detach()
                .to(device="cpu", non_blocking=True)
                .numpy(),
            )

    def compute(self) -> Tensor:
        if self._first_batch is None:
            return {}

        images = []
        imgs, gt_masks, pr_masks = self._first_batch
        imgs = imgs.clip(0, 1)

        images = [
            wandb.Image(
                img,
                masks={
                    "predictions": {
                        "mask_data": pr_mask,
                        "class_labels": self.class_labels,
                    },
                    "ground_truth": {
                        "mask_data": gt_mask,
                        "class_labels": self.class_labels,
                    },
                },
            )
            for img, gt_mask, pr_mask in zip(imgs, gt_masks, pr_masks)
        ]

        return {self.name: images}

    def reset(self):
        self._first_batch = None
