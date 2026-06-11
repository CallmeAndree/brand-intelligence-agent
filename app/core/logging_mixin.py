import logging
from typing import Any


class LoggerMixin:
    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger(self.__class__.__module__ + "." + self.__class__.__name__)

    def log_exception(self, message: str, *args: Any, **kwargs: Any) -> None:
        self.logger.exception(message, *args, **kwargs)


def log_exception(logger: logging.Logger, message: str, *args: Any, **kwargs: Any) -> None:
    logger.exception(message, *args, **kwargs)
