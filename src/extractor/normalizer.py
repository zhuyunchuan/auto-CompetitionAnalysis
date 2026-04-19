"""
Field value normalizer for competitor product specifications.

This module provides normalization functions for converting raw extracted
values into standardized formats according to field_dictionary_v1.md rules.

Key normalization operations:
- Resolution: WIDTHxHEIGHT format (e.g., "4608x2592")
- Distance: Convert to meters (m)
- Aperture: f/number format (e.g., "f/1.8")
- FPS@Resolution: Structured format with fps, width, height
- Text: Cleanup and alias mapping
"""

import re
import json
from typing import Optional, Dict, List, Any, Union

from .field_registry import FieldRegistry


class Normalizer:
    """
    Normalize raw field values to canonical formats.

    This class provides the core normalization logic for all field types,
    ensuring consistent data format across different brands and sources.
    """

    def __init__(self):
        """Initialize the normalizer with field registry."""
        self.field_registry = FieldRegistry()
        self._init_unit_mappings()
        self._init_alias_mappings()

    def _init_unit_mappings(self):
        """Initialize unit conversion mappings."""
        self.distance_units = {
            'm': 1.0,
            'meter': 1.0,
            'meters': 1.0,
            'mt': 1.0,
            'ft': 0.3048,
            'feet': 0.3048,
            'foot': 0.3048,
            '"': 0.0254,  # inches
            'in': 0.0254,
            'inch': 0.0254,
        }

        self.resolution_patterns = [
            (r'(\d{3,5})\s*[xX×]\s*(\d{3,5})', r'\1x\2'),  # Standard: 1920x1080
            (r'(\d{3,5})\*[xX×]\s*(\d{3,5})', r'\1x\2'),  # Variations
        ]

    def _init_alias_mappings(self):
        """Initialize common value aliases for standardization."""
        self.image_sensor_aliases = {
            '1/2.8" Progressive Scan CMOS': '1/2.8" CMOS',
            '1/2.8" CMOS': '1/2.8" CMOS',
            '1/3" Progressive Scan CMOS': '1/3" CMOS',
            '1/1.8" Progressive Scan CMOS': '1/1.8" CMOS',
            '1/1.8" CMOS': '1/1.8" CMOS',
            'CMOS': 'CMOS',
            'CCD': 'CCD',
        }

        self.light_type_aliases = {
            'smart supplement light': 'Smart',
            'ir': 'IR',
            'infrared': 'IR',
            'white light': 'White Light',
            'led': 'LED',
            'laser': 'Laser',
        }

        self.protection_aliases = {
            'ip67': 'IP67',
            'ip66': 'IP66',
            'ik10': 'IK10',
            'ik08': 'IK08',
        }

    def normalize(
        self,
        field_code: str,
        raw_value: str,
        value_type: str = "text"
    ) -> tuple[Optional[str], Optional[str], List[str]]:
        """
        Normalize a field value to its canonical format.

        Args:
            field_code: The field code (from field_dictionary_v1.md)
            raw_value: The raw extracted value
            value_type: The value type (text, number_or_text, integer, list_text)

        Returns:
            Tuple of (normalized_value, unit, issues)
            - normalized_value: The normalized value (or None if normalization fails)
            - unit: The detected/canonical unit (or None)
            - issues: List of warning/error messages
        """
        issues = []

        if not raw_value or raw_value.strip() == '':
            return None, None, ['Empty value']

        # Route to appropriate normalizer based on field code
        if field_code == "max_resolution":
            return self._normalize_resolution(raw_value)

        elif field_code == "main_stream_max_fps_resolution":
            return self._normalize_stream_info(raw_value)

        elif field_code == "supplement_light_range":
            return self._normalize_distance(raw_value)

        elif field_code == "aperture":
            return self._normalize_aperture(raw_value)

        elif field_code == "stream_count":
            return self._normalize_integer(raw_value)

        elif field_code in ["interface_items", "deep_learning_function_categories"]:
            return self._normalize_list(raw_value)

        elif field_code == "image_sensor":
            return self._normalize_by_alias(raw_value, self.image_sensor_aliases)

        elif field_code == "supplement_light_type":
            return self._normalize_by_alias(raw_value, self.light_type_aliases)

        elif field_code in ["approval_protection", "approval_anti_corrosion_protection"]:
            return self._normalize_by_alias(raw_value, self.protection_aliases)

        # Default: basic text cleanup
        return self._normalize_text(raw_value)

    def _normalize_resolution(self, raw_value: str) -> tuple[Optional[str], Optional[str], List[str]]:
        """
        Normalize resolution to WIDTHxHEIGHT format.

        Examples:
        - "1920 x 1080" -> "1920x1080"
        - "4K (3840x2160)" -> "3840x1080"
        - "2592×1944" -> "2592x1944"

        Args:
            raw_value: Raw resolution string

        Returns:
            Tuple of (normalized_resolution, unit, issues)
        """
        # Extract resolution using regex
        match = re.search(r'(\d{3,5})\s*[xX×]\s*(\d{3,5})', raw_value)

        if match:
            width = match.group(1)
            height = match.group(2)
            normalized = f"{width}x{height}"
            return normalized, "px", []

        # Try alternative patterns
        # Sometimes resolution is written as "4608P" or similar
        match = re.search(r'(\d{3,5})[pPiI]', raw_value)
        if match:
            # Vertical resolution only, approximate as 16:9
            height = match.group(1)
            width = str(int(int(height) * 16 / 9))
            normalized = f"{width}x{height}"
            return normalized, "px", ["Derived from vertical resolution only"]

        return None, None, ["Could not parse resolution format"]

    def _normalize_distance(self, raw_value: str) -> tuple[Optional[str], Optional[str], List[str]]:
        """
        Normalize distance to meters.

        Supports input units: m, meters, ft, feet, inches
        Output is always in meters.

        Examples:
        - "50m" -> "50"
        - "100 ft" -> "30.48"
        - "30 meters" -> "30"

        Args:
            raw_value: Raw distance string

        Returns:
            Tuple of (normalized_distance, unit, issues)
        """
        # Extract numeric value and unit
        match = re.search(r'(\d+(?:\.\d+)?)\s*([a-zA-Z"\'°]+)?', raw_value)

        if not match:
            return None, None, ["Could not parse distance format"]

        value = float(match.group(1))
        unit = match.group(2).lower() if match.group(2) else ''

        # Default to meters if no unit specified
        if not unit:
            return str(value), "m", ["No unit specified, assumed meters"]

        # Convert to meters
        if unit in self.distance_units:
            conversion_factor = self.distance_units[unit]
            value_meters = value * conversion_factor

            # Round to 2 decimal places for cleanliness
            if value_meters == int(value_meters):
                normalized = str(int(value_meters))
            else:
                normalized = f"{value_meters:.2f}".rstrip('0').rstrip('.')

            return normalized, "m", []
        else:
            # Unknown unit, return original value and flag issue
            return raw_value, unit, [f"Unknown unit: {unit}"]

    def _normalize_aperture(self, raw_value: str) -> tuple[Optional[str], Optional[str], List[str]]:
        """
        Normalize aperture to f/number format.

        Examples:
        - "F1.8" -> "f/1.8"
        - "f/2.0" -> "f/2.0"
        - "1.8" -> "f/1.8"

        Args:
            raw_value: Raw aperture string

        Returns:
            Tuple of (normalized_aperture, unit, issues)
        """
        # Extract numeric value
        match = re.search(r'([\d.]+)', raw_value)

        if match:
            value = match.group(1)
            normalized = f"f/{value}"
            return normalized, "f", []

        return None, None, ["Could not parse aperture format"]

    def _normalize_stream_info(self, raw_value: str) -> tuple[Optional[str], Optional[str], List[str]]:
        """
        Normalize stream information (FPS@Resolution) to structured format.

        Expected format: "<fps>fps (<width>x<height>)"
        Example: "30fps (1920x1080)"

        Args:
            raw_value: Raw stream info string

        Returns:
            Tuple of (normalized_stream_info, unit, issues)
        """
        # Extract FPS
        fps_match = re.search(r'(\d+)\s*fps', raw_value, re.IGNORECASE)

        # Extract resolution
        res_match = re.search(r'(\d{3,5})\s*[xX×]\s*(\d{3,5})', raw_value)

        if fps_match and res_match:
            fps = fps_match.group(1)
            width = res_match.group(1)
            height = res_match.group(2)

            normalized = f"{fps}fps ({width}x{height})"
            return normalized, "fps+px", []
        elif fps_match:
            fps = fps_match.group(1)
            return f"{fps}fps", "fps+px", ["Resolution not found"]
        elif res_match:
            width = res_match.group(1)
            height = res_match.group(2)
            return f"({width}x{height})", "fps+px", ["FPS not found"]
        else:
            return None, None, ["Could not parse stream info format"]

    def _normalize_integer(self, raw_value: str) -> tuple[Optional[str], Optional[str], List[str]]:
        """
        Normalize an integer value.

        Args:
            raw_value: Raw integer string

        Returns:
            Tuple of (normalized_int, unit, issues)
        """
        # Extract first integer found
        match = re.search(r'(\d+)', raw_value)

        if match:
            return match.group(1), "count", []

        return None, None, ["Could not parse integer value"]

    def _normalize_list(self, raw_value: str) -> tuple[Optional[str], None, List[str]]:
        """
        Normalize a list field value.

        Parses comma, semicolon, or newline separated values and
        outputs as JSON array.

        Args:
            raw_value: Raw list string

        Returns:
            Tuple of (normalized_list_json, None, issues)
        """
        # Try to parse as JSON first
        try:
            parsed = json.loads(raw_value)
            if isinstance(parsed, list):
                # Validate all items are strings
                if all(isinstance(item, str) for item in parsed):
                    return json.dumps(parsed, ensure_ascii=False), None, []
                else:
                    # Convert non-string items to strings
                    parsed = [str(item) for item in parsed]
                    return json.dumps(parsed, ensure_ascii=False), None, ["Converted non-string items to strings"]
        except (json.JSONDecodeError, TypeError):
            pass

        # Split by common separators
        items = re.split(r'[,;，、\n]', raw_value)
        items = [item.strip() for item in items if item.strip()]

        if not items:
            return None, None, ["No list items found"]

        # Remove duplicates while preserving order
        seen = set()
        unique_items = []
        for item in items:
            if item.lower() not in seen:
                seen.add(item.lower())
                unique_items.append(item)

        normalized = json.dumps(unique_items, ensure_ascii=False)
        return normalized, None, []

    def _normalize_by_alias(
        self,
        raw_value: str,
        alias_map: Dict[str, str]
    ) -> tuple[Optional[str], None, List[str]]:
        """
        Normalize a value using alias mapping.

        Args:
            raw_value: Raw value string
            alias_map: Dictionary mapping aliases to canonical values

        Returns:
            Tuple of (normalized_value, None, issues)
        """
        # Clean up the raw value
        cleaned = raw_value.strip()

        # Try exact match (case-insensitive)
        for alias, canonical in alias_map.items():
            if cleaned.lower() == alias.lower():
                return canonical, None, []

        # Try partial match
        for alias, canonical in alias_map.items():
            if alias.lower() in cleaned.lower() or cleaned.lower() in alias.lower():
                return canonical, None, ["Partial alias match"]

        # No match found, return original
        return cleaned, None, ["No alias match found"]

    def _normalize_text(self, raw_value: str) -> tuple[str, None, List[str]]:
        """
        Basic text normalization (whitespace cleanup).

        Args:
            raw_value: Raw text string

        Returns:
            Tuple of (normalized_text, None, issues)
        """
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', raw_value).strip()

        # Remove common artifacts
        normalized = normalized.strip('.,;:，、；：')

        return normalized, None, []

    def batch_normalize(
        self,
        field_values: Dict[str, str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Normalize multiple field values at once.

        Args:
            field_values: Dict mapping field_code to raw_value

        Returns:
            Dict mapping field_code to {
                'normalized_value': str or None,
                'unit': str or None,
                'issues': List[str]
            }
        """
        results = {}

        for field_code, raw_value in field_values.items():
            normalized_value, unit, issues = self.normalize(
                field_code,
                raw_value
            )

            results[field_code] = {
                'normalized_value': normalized_value,
                'unit': unit,
                'issues': issues
            }

        return results
