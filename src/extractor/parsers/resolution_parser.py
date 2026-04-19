"""
Resolution parser for product specifications.

This module handles parsing and normalization of resolution values,
ensuring consistent WIDTHxHEIGHT format (e.g., "4608x2592").

Supported input formats:
- "1920x1080", "1920 x 1080", "1920×1080"
- "4K (3840x2160)"
- "2592P" (vertical resolution only)
- "8MP", "5MP", "2MP" (megapixel approximations)
"""

import re
from typing import Optional, Tuple


class ResolutionParser:
    """
    Parse and normalize resolution values.

    Resolution format: WIDTHxHEIGHT (in pixels)
    Example: "4608x2592"
    """

    # Common megapixel to resolution mappings
    MP_RESOLUTIONS = {
        "12MP": ("4096", "2160"),  # ~12MP 4K
        "8MP": ("3840", "2160"),   # 4K
        "6MP": ("3072", "2048"),
        "5MP": ("2592", "1944"),
        "4MP": ("2560", "1440"),
        "3MP": ("2048", "1536"),
        "2MP": ("1920", "1080"),   # 1080p
        "1MP": ("1280", "720"),    # 720p
        "0.9MP": ("1280", "720"),
        "0.4MP": ("640", "480"),   # VGA
        "0.3MP": ("640", "480"),
    }

    # Regex patterns
    RESOLUTION_PATTERN = re.compile(r'(\d{3,5})\s*[xX×]\s*(\d{3,5})')
    VERTICAL_ONLY_PATTERN = re.compile(r'(\d{3,5})[pP]')

    def parse(self, raw_value: str) -> Optional[Tuple[str, str, str]]:
        """
        Parse a resolution string into components.

        Args:
            raw_value: Raw resolution string

        Returns:
            Tuple of (width, height, normalized_string) or None if parsing fails
        """
        if not raw_value:
            return None

        # Try standard WIDTHxHEIGHT format
        match = self.RESOLUTION_PATTERN.search(raw_value)
        if match:
            width = match.group(1)
            height = match.group(2)
            normalized = f"{width}x{height}"
            return (width, height, normalized)

        # Try vertical-only format (e.g., "1080P")
        match = self.VERTICAL_ONLY_PATTERN.search(raw_value)
        if match:
            height = match.group(1)
            # Assume 16:9 aspect ratio
            width = str(int(int(height) * 16 / 9))
            normalized = f"{width}x{height}"
            return (width, height, normalized)

        # Try megapixel format (e.g., "5MP")
        mp_match = re.search(r'(\d+(?:\.\d+)?)\s*MP', raw_value, re.IGNORECASE)
        if mp_match:
            mp = mp_match.group(1) + "MP"
            if mp in self.MP_RESOLUTIONS:
                width, height = self.MP_RESOLUTIONS[mp]
                normalized = f"{width}x{height}"
                return (width, height, normalized)

        return None

    def normalize(self, raw_value: str) -> Optional[str]:
        """
        Normalize a resolution string to WIDTHxHEIGHT format.

        Args:
            raw_value: Raw resolution string

        Returns:
            Normalized resolution string (e.g., "4608x2592") or None if parsing fails
        """
        result = self.parse(raw_value)
        if result:
            return result[2]
        return None

    def validate(self, normalized: str) -> bool:
        """
        Validate that a resolution string is in correct format.

        Args:
            normalized: Resolution string to validate

        Returns:
            True if valid, False otherwise
        """
        if not normalized:
            return False

        # Check format: WIDTHxHEIGHT
        match = re.match(r'^\d{3,5}x\d{3,5}$', normalized)
        if not match:
            return False

        # Extract dimensions
        width, height = normalized.split('x')

        # Sanity check: reasonable ranges
        width_int = int(width)
        height_int = int(height)

        if width_int < 320 or width_int > 8192:
            return False
        if height_int < 240 or height_int > 4320:
            return False

        return True

    def calculate_megapixels(self, normalized: str) -> Optional[float]:
        """
        Calculate megapixels from normalized resolution.

        Args:
            normalized: Normalized resolution string (WIDTHxHEIGHT)

        Returns:
            Megapixel count (e.g., 2.1) or None if calculation fails
        """
        if not self.validate(normalized):
            return None

        width, height = normalized.split('x')
        pixels = int(width) * int(height)
        mp = pixels / 1_000_000

        # Round to 1 decimal place
        return round(mp, 1)

    def get_aspect_ratio(self, normalized: str) -> Optional[str]:
        """
        Calculate aspect ratio from normalized resolution.

        Args:
            normalized: Normalized resolution string (WIDTHxHEIGHT)

        Returns:
            Aspect ratio string (e.g., "16:9") or None if calculation fails
        """
        if not self.validate(normalized):
            return None

        width, height = normalized.split('x')
        w = int(width)
        h = int(height)

        # Calculate GCD
        import math
        divisor = math.gcd(w, h)

        if divisor == 0:
            return None

        aspect_w = w // divisor
        aspect_h = h // divisor

        return f"{aspect_w}:{aspect_h}"

    def compare_resolutions(self, res1: str, res2: str) -> int:
        """
        Compare two normalized resolutions by total pixels.

        Args:
            res1: First normalized resolution (WIDTHxHEIGHT)
            res2: Second normalized resolution (WIDTHxHEIGHT)

        Returns:
            -1 if res1 < res2, 0 if equal, 1 if res1 > res2
        """
        mp1 = self.calculate_megapixels(res1)
        mp2 = self.calculate_megapixels(res2)

        if mp1 is None or mp2 is None:
            return 0

        if mp1 < mp2:
            return -1
        elif mp1 > mp2:
            return 1
        else:
            return 0
