"""
Stream parser for product specifications.

This module handles parsing and normalization of stream information,
particularly the main_stream_max_fps_resolution field.

Expected format: "<fps>fps (<width>x<height>)"
Example: "30fps (1920x1080)"

Structured extraction:
- fps_value: Integer FPS
- resolution_width: Integer width in pixels
- resolution_height: Integer height in pixels
"""

import re
import json
from typing import Optional, Dict, Any


class StreamParser:
    """
    Parse and normalize stream information (FPS@Resolution).

    Handles structured extraction of FPS and resolution from various formats.
    """

    # Regex patterns
    FPS_PATTERN = re.compile(r'(\d+)\s*fps', re.IGNORECASE)
    RESOLUTION_PATTERN = re.compile(r'(\d{3,5})\s*[xX×]\s*(\d{3,5})')
    PATTERN_FULL = re.compile(
        r'(\d+)\s*fps[\s@\(]*\(?(\d{3,5})\s*[xX×]\s*(\d{3,5})\)?',
        re.IGNORECASE
    )

    def parse(self, raw_value: str) -> Optional[Dict[str, Any]]:
        """
        Parse stream info into structured components.

        Args:
            raw_value: Raw stream info string

        Returns:
            Dict with keys:
            - fps_value: int or None
            - resolution_width: int or None
            - resolution_height: int or None
            - normalized: str or None
            Or None if parsing fails completely
        """
        if not raw_value:
            return None

        result = {
            'fps_value': None,
            'resolution_width': None,
            'resolution_height': None,
            'normalized': None
        }

        # Try full pattern match first (FPS + Resolution)
        match = self.PATTERN_FULL.search(raw_value)
        if match:
            result['fps_value'] = int(match.group(1))
            result['resolution_width'] = int(match.group(2))
            result['resolution_height'] = int(match.group(3))
            result['normalized'] = (
                f"{result['fps_value']}fps "
                f"({result['resolution_width']}x{result['resolution_height']})"
            )
            return result

        # Extract FPS separately
        fps_match = self.FPS_PATTERN.search(raw_value)
        if fps_match:
            result['fps_value'] = int(fps_match.group(1))

        # Extract resolution separately
        res_match = self.RESOLUTION_PATTERN.search(raw_value)
        if res_match:
            result['resolution_width'] = int(res_match.group(1))
            result['resolution_height'] = int(res_match.group(2))

        # Build normalized string based on what we found
        if result['fps_value'] and result['resolution_width']:
            result['normalized'] = (
                f"{result['fps_value']}fps "
                f"({result['resolution_width']}x{result['resolution_height']})"
            )
        elif result['fps_value']:
            result['normalized'] = f"{result['fps_value']}fps"
        elif result['resolution_width']:
            result['normalized'] = (
                f"({result['resolution_width']}x{result['resolution_height']})"
            )
        else:
            return None

        return result

    def normalize(self, raw_value: str) -> Optional[str]:
        """
        Normalize stream info to standard format.

        Args:
            raw_value: Raw stream info string

        Returns:
            Normalized string in format "<fps>fps (<width>x<height>)"
            or partial format if only FPS or resolution is found
        """
        result = self.parse(raw_value)
        if result:
            return result['normalized']
        return None

    def extract_fps(self, raw_value: str) -> Optional[int]:
        """
        Extract FPS value from stream info.

        Args:
            raw_value: Raw stream info string

        Returns:
            Integer FPS or None if not found
        """
        result = self.parse(raw_value)
        if result:
            return result['fps_value']
        return None

    def extract_resolution(self, raw_value: str) -> Optional[tuple[int, int]]:
        """
        Extract resolution from stream info.

        Args:
            raw_value: Raw stream info string

        Returns:
            Tuple of (width, height) or None if not found
        """
        result = self.parse(raw_value)
        if result and result['resolution_width']:
            return (result['resolution_width'], result['resolution_height'])
        return None

    def to_structured(self, raw_value: str) -> Optional[str]:
        """
        Convert stream info to structured JSON format.

        Args:
            raw_value: Raw stream info string

        Returns:
            JSON string with structured data or None if parsing fails
        """
        result = self.parse(raw_value)
        if result:
            # Remove None values and normalized string
            structured = {
                k: v for k, v in result.items()
                if v is not None and k != 'normalized'
            }
            return json.dumps(structured)
        return None

    def validate(self, normalized: str) -> bool:
        """
        Validate that a stream info string is in correct format.

        Args:
            normalized: Stream info string to validate

        Returns:
            True if valid, False otherwise
        """
        result = self.parse(normalized)
        return result is not None and result['normalized'] is not None

    def compare_fps(self, stream1: str, stream2: str) -> int:
        """
        Compare FPS values of two streams.

        Args:
            stream1: First stream info
            stream2: Second stream info

        Returns:
            -1 if stream1 < stream2, 0 if equal, 1 if stream1 > stream2
        """
        fps1 = self.extract_fps(stream1)
        fps2 = self.extract_fps(stream2)

        if fps1 is None or fps2 is None:
            return 0

        if fps1 < fps2:
            return -1
        elif fps1 > fps2:
            return 1
        else:
            return 0

    def compare_resolution(self, stream1: str, stream2: str) -> int:
        """
        Compare resolution values of two streams.

        Args:
            stream1: First stream info
            stream2: Second stream info

        Returns:
            -1 if stream1 < stream2, 0 if equal, 1 if stream1 > stream2
        """
        res1 = self.extract_resolution(stream1)
        res2 = self.extract_resolution(stream2)

        if res1 is None or res2 is None:
            return 0

        pixels1 = res1[0] * res1[1]
        pixels2 = res2[0] * res2[1]

        if pixels1 < pixels2:
            return -1
        elif pixels1 > pixels2:
            return 1
        else:
            return 0

    def format_with_brackets(self, fps: int, width: int, height: int) -> str:
        """
        Format stream info with FPS and resolution in brackets.

        Args:
            fps: FPS value
            width: Resolution width
            height: Resolution height

        Returns:
            Formatted string: "<fps>fps (<width>x<height>)"
        """
        return f"{fps}fps ({width}x{height})"

    def parse_multiple_streams(self, raw_text: str) -> list[Dict[str, Any]]:
        """
        Parse multiple stream specifications from text.

        Some pages list multiple streams (main, sub, third).
        This attempts to extract all of them.

        Args:
            raw_text: Text containing multiple stream specs

        Returns:
            List of parsed stream info dicts
        """
        streams = []

        # Split by common delimiters
        parts = re.split(r'[,;\n]|Stream\s*\d*', raw_text, flags=re.IGNORECASE)

        for part in parts:
            part = part.strip()
            if not part:
                continue

            result = self.parse(part)
            if result and result['normalized']:
                streams.append(result)

        return streams
