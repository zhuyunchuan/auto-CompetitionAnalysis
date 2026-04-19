"""
Range parser for distance specifications.

This module handles parsing and normalization of distance ranges,
particularly for supplement_light_range field.

Features:
- Unit conversion: ft, inches to meters
- Range handling: "10-30m", "up to 50m"
- Flexible input formats
"""

import re
from typing import Optional, Tuple, Union


class RangeParser:
    """
    Parse and normalize distance range values.

    Converts all distances to meters (m) as the canonical unit.
    Handles single values, ranges, and "up to" expressions.
    """

    # Unit conversion factors to meters
    UNIT_CONVERSIONS = {
        'm': 1.0,
        'meter': 1.0,
        'meters': 1.0,
        'mt': 1.0,
        'ft': 0.3048,
        'feet': 0.3048,
        'foot': 0.3048,
        '"': 0.0254,     # inches
        'in': 0.0254,
        'inch': 0.0254,
        'inches': 0.0254,
        'cm': 0.01,
        'mm': 0.001,
    }

    # Regex patterns
    SINGLE_VALUE_PATTERN = re.compile(
        r'(\d+(?:\.\d+)?)\s*([a-zA-Z"\'°]+)?',
        re.IGNORECASE
    )
    RANGE_PATTERN = re.compile(
        r'(\d+(?:\.\d+)?)\s*([a-zA-Z"\'°]+)?\s*[-~]\s*(\d+(?:\.\d+)?)\s*([a-zA-Z"\'°]+)?',
        re.IGNORECASE
    )
    UP_TO_PATTERN = re.compile(
        r'(?:up\s+to|maximum|max|≤\s*|<=\s*)\s*(\d+(?:\.\d+)?)\s*([a-zA-Z"\'°]+)?',
        re.IGNORECASE
    )

    def parse(self, raw_value: str) -> Optional[dict]:
        """
        Parse a distance range into structured components.

        Args:
            raw_value: Raw distance string

        Returns:
            Dict with keys:
            - min_value: float or None
            - max_value: float or None
            - unit: str (detected input unit)
            - normalized_min: str or None
            - normalized_max: str or None
            - normalized: str or None
            Or None if parsing fails
        """
        if not raw_value:
            return None

        result = {
            'min_value': None,
            'max_value': None,
            'unit': None,
            'normalized_min': None,
            'normalized_max': None,
            'normalized': None
        }

        # Try "up to" pattern first (e.g., "up to 50m")
        match = self.UP_TO_PATTERN.search(raw_value)
        if match:
            max_val = float(match.group(1))
            unit = match.group(2).lower() if match.group(2) else 'm'

            result['max_value'] = max_val
            result['unit'] = unit

            # Convert to meters
            max_meters = self._to_meters(max_val, unit)

            result['normalized_max'] = self._format_number(max_meters)
            result['normalized'] = f"up to {result['normalized_max']}m"
            return result

        # Try range pattern (e.g., "10-30m")
        match = self.RANGE_PATTERN.search(raw_value)
        if match:
            min_val = float(match.group(1))
            max_val = float(match.group(3))
            unit1 = match.group(2).lower() if match.group(2) else None
            unit2 = match.group(4).lower() if match.group(4) else None

            # Use first unit if both present, otherwise default to meters
            unit = unit1 or unit2 or 'm'

            result['min_value'] = min_val
            result['max_value'] = max_val
            result['unit'] = unit

            # Convert to meters
            min_meters = self._to_meters(min_val, unit)
            max_meters = self._to_meters(max_val, unit)

            result['normalized_min'] = self._format_number(min_meters)
            result['normalized_max'] = self._format_number(max_meters)
            result['normalized'] = f"{result['normalized_min']}-{result['normalized_max']}m"
            return result

        # Try single value pattern (e.g., "50m")
        match = self.SINGLE_VALUE_PATTERN.search(raw_value)
        if match:
            value = float(match.group(1))
            unit = match.group(2).lower() if match.group(2) else 'm'

            result['max_value'] = value
            result['unit'] = unit

            # Convert to meters
            value_meters = self._to_meters(value, unit)

            result['normalized_max'] = self._format_number(value_meters)
            result['normalized'] = f"{result['normalized_max']}m"
            return result

        return None

    def normalize(self, raw_value: str) -> Optional[str]:
        """
        Normalize a distance range to meters.

        Args:
            raw_value: Raw distance string

        Returns:
            Normalized distance string in meters (e.g., "50m", "10-30m")
            or None if parsing fails
        """
        result = self.parse(raw_value)
        if result:
            return result['normalized']
        return None

    def _to_meters(self, value: float, unit: str) -> float:
        """
        Convert a value to meters.

        Args:
            value: Numeric value
            unit: Unit string (e.g., 'ft', 'm')

        Returns:
            Value in meters

        Raises:
            ValueError: If unit is not recognized
        """
        unit = unit.lower()

        if unit not in self.UNIT_CONVERSIONS:
            raise ValueError(f"Unknown unit: {unit}")

        return value * self.UNIT_CONVERSIONS[unit]

    def _format_number(self, value: float) -> str:
        """
        Format a number cleanly (remove unnecessary decimals).

        Args:
            value: Numeric value

        Returns:
            Formatted string
        """
        if value == int(value):
            return str(int(value))
        else:
            formatted = f"{value:.2f}"
            # Remove trailing zeros after decimal point
            if '.' in formatted:
                formatted = formatted.rstrip('0').rstrip('.')
            return formatted

    def get_max_distance_in_meters(self, raw_value: str) -> Optional[float]:
        """
        Extract maximum distance in meters.

        Args:
            raw_value: Raw distance string

        Returns:
            Maximum distance in meters or None if parsing fails
        """
        result = self.parse(raw_value)
        if result and result['normalized_max']:
            return float(result['normalized_max'].replace('m', ''))
        return None

    def get_min_distance_in_meters(self, raw_value: str) -> Optional[float]:
        """
        Extract minimum distance in meters.

        Args:
            raw_value: Raw distance string

        Returns:
            Minimum distance in meters or None if parsing fails
        """
        result = self.parse(raw_value)
        if result and result['normalized_min']:
            return float(result['normalized_min'].replace('m', ''))
        return None

    def is_range(self, raw_value: str) -> bool:
        """
        Check if the value represents a range (min-max) vs single value.

        Args:
            raw_value: Raw distance string

        Returns:
            True if range, False if single value or parsing fails
        """
        result = self.parse(raw_value)
        if result:
            return result['min_value'] is not None
        return False

    def validate(self, normalized: str) -> bool:
        """
        Validate that a distance string is in correct format.

        Args:
            normalized: Distance string to validate

        Returns:
            True if valid, False otherwise
        """
        if not normalized:
            return False

        # Should end with 'm'
        if not normalized.endswith('m'):
            return False

        # Try to parse it
        result = self.parse(normalized)
        return result is not None

    def compare_distances(self, dist1: str, dist2: str) -> int:
        """
        Compare two distance ranges by their maximum values.

        Args:
            dist1: First distance string
            dist2: Second distance string

        Returns:
            -1 if dist1 < dist2, 0 if equal, 1 if dist1 > dist2
        """
        max1 = self.get_max_distance_in_meters(dist1)
        max2 = self.get_max_distance_in_meters(dist2)

        if max1 is None or max2 is None:
            return 0

        if max1 < max2:
            return -1
        elif max1 > max2:
            return 1
        else:
            return 0

    def convert_from_feet(self, value_ft: float) -> float:
        """
        Convert feet to meters.

        Args:
            value_ft: Value in feet

        Returns:
            Value in meters
        """
        return value_ft * 0.3048

    def convert_from_inches(self, value_in: float) -> float:
        """
        Convert inches to meters.

        Args:
            value_in: Value in inches

        Returns:
            Value in meters
        """
        return value_in * 0.0254

    def format_range(self, min_meters: float, max_meters: float) -> str:
        """
        Format a range in meters.

        Args:
            min_meters: Minimum value in meters
            max_meters: Maximum value in meters

        Returns:
            Formatted range string (e.g., "10-30m")
        """
        min_str = self._format_number(min_meters)
        max_str = self._format_number(max_meters)
        return f"{min_str}-{max_str}m"

    def format_single(self, value_meters: float) -> str:
        """
        Format a single distance value in meters.

        Args:
            value_meters: Value in meters

        Returns:
            Formatted string (e.g., "50m")
        """
        value_str = self._format_number(value_meters)
        return f"{value_str}m"
