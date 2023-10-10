"""The class provides logging processing, logging output to different channels.

https://loguru.readthedocs.io/en/stable/api/logger.html.
"""

__author__ = "ZHEZLYAEV Aleksandr <zhezlyaev@gmail.com>"
__version__ = "1.0"

# -*- coding: utf-8 -*-

import os
import pathlib
import sys
from logging import StreamHandler
from typing import Literal, Optional


class zLog:
    """The class provides logging processing, logging output to different
    channels."""

    def __init__(self, username=None, buffer_capture=None) -> None:
        if username:
            if not isinstance(username, str):
                raise TypeError("username must be a string.")
            self.username = username
        else:
            try:
                self.username = os.environ.get("USERNAME")
            except KeyError:
                self.username = "anonymous"

        if buffer_capture:
            self.buffer_capture = buffer_capture

        self.format = "<magenta>{time:DD-MM-YYYY HH:mm:ss.SSSS}</magenta> | <level>{level: <8}</level> | <yellow>{extra[username]}</yellow> | <level>{message}</level>"

        from loguru import logger

        self.logger = logger

    def log(
        self, log_to: Optional[Literal["console", "file", "buffer", "bufferAndFile", "consoleAndFile"]] = "console"
    ):
        """The method, depending on the options, creates a log message and
        outputs them to the channel that is passed as an option."""

        if log_to not in ("console", "file", "buffer", "bufferAndFile", "consoleAndFile"):
            raise ValueError("invalid parameter passed to variable 'log_to'")

        self.logger.remove()
        self.logger = self.logger.bind(username=self.username)

        if log_to == "console":
            self.logger.add(sys.stderr, colorize=True, format=self.format)

        if log_to == "file":
            pathlib.Path("log").mkdir(parents=True, exist_ok=True)
            self.logger.add(f"log/log_{self.username}.log", retention="3 days", colorize=False, format=self.format)

        if log_to == "consoleAndFile":
            pathlib.Path("log").mkdir(parents=True, exist_ok=True)
            self.logger.add(sys.stderr, colorize=True, format=self.format)
            self.logger.add(f"log/log_{self.username}.log", retention="3 days", colorize=False, format=self.format)

        if log_to == "buffer":
            self.logger.add(StreamHandler(self.buffer_capture), colorize=False, format=self.format)

        if log_to == "bufferAndFile":
            self.logger.add(StreamHandler(self.buffer_capture), colorize=False, format=self.format)

            pathlib.Path("log").mkdir(parents=True, exist_ok=True)
            self.logger.add(f"log/log_{self.username}.log", retention="1 days", colorize=False, format=self.format)

        return self.logger
