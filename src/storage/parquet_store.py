"""
Parquet file storage for batch snapshots.

This module provides high-performance batch storage using Parquet format
with partitioning by run_id for efficient querying and historical analysis.
"""

import json
from pathlib import Path
from typing import List, Optional, Dict, Any, Iterator
from datetime import datetime

import pyarrow as pa
import pyarrow.parquet as pq
import pandas as pd

from src.core.logging import get_logger

logger = get_logger(__name__)


class ParquetStore:
    """
    Parquet-based storage for batch data snapshots.

    Provides efficient columnar storage with partitioning by run_id,
    optimized for read-heavy analytical workloads and historical comparisons.
    """

    def __init__(
        self,
        parquet_dir: str = "/data/parquet",
    ):
        """
        Initialize Parquet store.

        Args:
            parquet_dir: Directory for Parquet files
        """
        self.parquet_dir = Path(parquet_dir)
        self.parquet_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Parquet store initialized",
            extra={"parquet_dir": str(self.parquet_dir)}
        )

    def _get_run_path(self, run_id: str, table_name: str) -> Path:
        """
        Get the file path for a specific run and table.

        Args:
            run_id: Run identifier
            table_name: Name of the table (e.g., 'catalog', 'specs')

        Returns:
            Path to the Parquet file
        """
        # Partition by year/month for better organization
        # Format: parquet_dir/table_name/year=YYYY/month=MM/run_id.parquet
        try:
            # Extract date from run_id (format: YYYYMMDD_*)
            date_str = run_id.split("_")[0]
            date = datetime.strptime(date_str, "%Y%m%d")

            year_dir = self.parquet_dir / table_name / f"year={date.year:04d}"
            month_dir = year_dir / f"month={date.month:02d}"

            month_dir.mkdir(parents=True, exist_ok=True)

            return month_dir / f"{run_id}.parquet"

        except (ValueError, IndexError):
            # Fallback to flat structure if run_id format is unexpected
            table_dir = self.parquet_dir / table_name
            table_dir.mkdir(parents=True, exist_ok=True)
            return table_dir / f"{run_id}.parquet"

    def write_catalog(
        self,
        run_id: str,
        data: List[Dict[str, Any]],
    ) -> Path:
        """
        Write product catalog data to Parquet.

        Args:
            run_id: Run identifier
            data: List of catalog dictionaries

        Returns:
            Path to written Parquet file
        """
        if not data:
            logger.warning(
                "No catalog data to write",
                extra={"run_id": run_id}
            )
            return Path()

        df = pd.DataFrame(data)

        # Convert datetime columns
        datetime_cols = ["first_seen_at", "last_seen_at"]
        for col in datetime_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col])

        # Write to Parquet
        output_path = self._get_run_path(run_id, "catalog")
        df.to_parquet(
            output_path,
            engine="pyarrow",
            compression="snappy",
            index=False,
        )

        logger.info(
            f"Wrote {len(df)} catalog records to Parquet",
            extra={
                "run_id": run_id,
                "output_path": str(output_path),
                "record_count": len(df),
            }
        )

        return output_path

    def write_specs(
        self,
        run_id: str,
        data: List[Dict[str, Any]],
    ) -> Path:
        """
        Write product specification data to Parquet.

        Args:
            run_id: Run identifier
            data: List of spec dictionaries

        Returns:
            Path to written Parquet file
        """
        if not data:
            logger.warning(
                "No spec data to write",
                extra={"run_id": run_id}
            )
            return Path()

        df = pd.DataFrame(data)

        # Convert datetime columns
        datetime_cols = ["updated_at"]
        for col in datetime_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col])

        # Write to Parquet
        output_path = self._get_run_path(run_id, "specs")
        df.to_parquet(
            output_path,
            engine="pyarrow",
            compression="snappy",
            index=False,
        )

        logger.info(
            f"Wrote {len(df)} spec records to Parquet",
            extra={
                "run_id": run_id,
                "output_path": str(output_path),
                "record_count": len(df),
            }
        )

        return output_path

    def write_hierarchy(
        self,
        run_id: str,
        data: List[Dict[str, Any]],
    ) -> Path:
        """
        Write hierarchy snapshot data to Parquet.

        Args:
            run_id: Run identifier
            data: List of hierarchy dictionaries

        Returns:
            Path to written Parquet file
        """
        if not data:
            logger.warning(
                "No hierarchy data to write",
                extra={"run_id": run_id}
            )
            return Path()

        df = pd.DataFrame(data)

        # Convert datetime columns
        datetime_cols = ["discovered_at"]
        for col in datetime_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col])

        # Write to Parquet
        output_path = self._get_run_path(run_id, "hierarchy")
        df.to_parquet(
            output_path,
            engine="pyarrow",
            compression="snappy",
            index=False,
        )

        logger.info(
            f"Wrote {len(df)} hierarchy records to Parquet",
            extra={
                "run_id": run_id,
                "output_path": str(output_path),
                "record_count": len(df),
            }
        )

        return output_path

    def write_issues(
        self,
        run_id: str,
        data: List[Dict[str, Any]],
    ) -> Path:
        """
        Write quality issues data to Parquet.

        Args:
            run_id: Run identifier
            data: List of issue dictionaries

        Returns:
            Path to written Parquet file
        """
        if not data:
            logger.warning(
                "No issue data to write",
                extra={"run_id": run_id}
            )
            return Path()

        df = pd.DataFrame(data)

        # Convert datetime columns
        datetime_cols = ["created_at"]
        for col in datetime_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col])

        # Write to Parquet
        output_path = self._get_run_path(run_id, "issues")
        df.to_parquet(
            output_path,
            engine="pyarrow",
            compression="snappy",
            index=False,
        )

        logger.info(
            f"Wrote {len(df)} issue records to Parquet",
            extra={
                "run_id": run_id,
                "output_path": str(output_path),
                "record_count": len(df),
            }
        )

        return output_path

    def read_catalog(
        self,
        run_id: str,
    ) -> pd.DataFrame:
        """
        Read product catalog data from Parquet.

        Args:
            run_id: Run identifier

        Returns:
            DataFrame with catalog data
        """
        input_path = self._get_run_path(run_id, "catalog")

        if not input_path.exists():
            logger.warning(
                "Catalog Parquet file not found",
                extra={"run_id": run_id, "path": str(input_path)}
            )
            return pd.DataFrame()

        df = pd.read_parquet(input_path, engine="pyarrow")

        logger.debug(
            f"Read {len(df)} catalog records from Parquet",
            extra={"run_id": run_id}
        )

        return df

    def read_specs(
        self,
        run_id: str,
    ) -> pd.DataFrame:
        """
        Read product specification data from Parquet.

        Args:
            run_id: Run identifier

        Returns:
            DataFrame with spec data
        """
        input_path = self._get_run_path(run_id, "specs")

        if not input_path.exists():
            logger.warning(
                "Specs Parquet file not found",
                extra={"run_id": run_id, "path": str(input_path)}
            )
            return pd.DataFrame()

        df = pd.read_parquet(input_path, engine="pyarrow")

        logger.debug(
            f"Read {len(df)} spec records from Parquet",
            extra={"run_id": run_id}
        )

        return df

    def read_hierarchy(
        self,
        run_id: str,
    ) -> pd.DataFrame:
        """
        Read hierarchy snapshot data from Parquet.

        Args:
            run_id: Run identifier

        Returns:
            DataFrame with hierarchy data
        """
        input_path = self._get_run_path(run_id, "hierarchy")

        if not input_path.exists():
            logger.warning(
                "Hierarchy Parquet file not found",
                extra={"run_id": run_id, "path": str(input_path)}
            )
            return pd.DataFrame()

        df = pd.read_parquet(input_path, engine="pyarrow")

        logger.debug(
            f"Read {len(df)} hierarchy records from Parquet",
            extra={"run_id": run_id}
        )

        return df

    def read_issues(
        self,
        run_id: str,
    ) -> pd.DataFrame:
        """
        Read quality issues data from Parquet.

        Args:
            run_id: Run identifier

        Returns:
            DataFrame with issue data
        """
        input_path = self._get_run_path(run_id, "issues")

        if not input_path.exists():
            logger.warning(
                "Issues Parquet file not found",
                extra={"run_id": run_id, "path": str(input_path)}
            )
            return pd.DataFrame()

        df = pd.read_parquet(input_path, engine="pyarrow")

        logger.debug(
            f"Read {len(df)} issue records from Parquet",
            extra={"run_id": run_id}
        )

        return df

    def list_runs(
        self,
        table_name: str,
    ) -> List[str]:
        """
        List all available run IDs for a table.

        Args:
            table_name: Name of the table (catalog, specs, hierarchy, issues)

        Returns:
            List of run IDs
        """
        table_dir = self.parquet_dir / table_name

        if not table_dir.exists():
            return []

        run_ids = []

        # Walk through year/month partition structure
        for year_dir in table_dir.glob("year=*"):
            if year_dir.is_dir():
                for month_dir in year_dir.glob("month=*"):
                    if month_dir.is_dir():
                        for parquet_file in month_dir.glob("*.parquet"):
                            # Extract run_id from filename
                            run_id = parquet_file.stem
                            run_ids.append(run_id)

        # Also check for flat structure (backward compatibility)
        for parquet_file in table_dir.glob("*.parquet"):
            run_id = parquet_file.stem
            if run_id not in run_ids:
                run_ids.append(run_id)

        return sorted(run_ids, reverse=True)

    def read_multiple_runs(
        self,
        table_name: str,
        run_ids: List[str],
    ) -> pd.DataFrame:
        """
        Read and concatenate data from multiple runs.

        Args:
            table_name: Name of the table
            run_ids: List of run IDs to read

        Returns:
            Concatenated DataFrame
        """
        dataframes = []

        for run_id in run_ids:
            if table_name == "catalog":
                df = self.read_catalog(run_id)
            elif table_name == "specs":
                df = self.read_specs(run_id)
            elif table_name == "hierarchy":
                df = self.read_hierarchy(run_id)
            elif table_name == "issues":
                df = self.read_issues(run_id)
            else:
                logger.warning(
                    f"Unknown table name: {table_name}",
                    extra={"table_name": table_name}
                )
                continue

            if not df.empty:
                dataframes.append(df)

        if not dataframes:
            return pd.DataFrame()

        combined_df = pd.concat(dataframes, ignore_index=True)

        logger.info(
            f"Combined {len(combined_df)} records from {len(run_ids)} runs",
            extra={"table_name": table_name, "run_count": len(run_ids)}
        )

        return combined_df

    def delete_run(
        self,
        run_id: str,
    ) -> List[Path]:
        """
        Delete all Parquet files for a specific run.

        Args:
            run_id: Run identifier

        Returns:
            List of deleted file paths
        """
        deleted_paths = []

        tables = ["catalog", "specs", "hierarchy", "issues"]

        for table_name in tables:
            file_path = self._get_run_path(run_id, table_name)

            if file_path.exists():
                file_path.unlink()
                deleted_paths.append(file_path)
                logger.info(
                    f"Deleted Parquet file for run",
                    extra={
                        "run_id": run_id,
                        "table_name": table_name,
                        "path": str(file_path),
                    }
                )

        return deleted_paths

    def get_storage_stats(
        self,
    ) -> Dict[str, Any]:
        """
        Get storage statistics.

        Returns:
            Dictionary with storage statistics
        """
        stats = {
            "tables": {},
            "total_size_bytes": 0,
        }

        tables = ["catalog", "specs", "hierarchy", "issues"]

        for table_name in tables:
            table_dir = self.parquet_dir / table_name

            if not table_dir.exists():
                stats["tables"][table_name] = {
                    "run_count": 0,
                    "size_bytes": 0,
                }
                continue

            # Count files and calculate size
            parquet_files = list(table_dir.rglob("*.parquet"))
            total_size = sum(f.stat().st_size for f in parquet_files)

            stats["tables"][table_name] = {
                "run_count": len(parquet_files),
                "size_bytes": total_size,
            }

            stats["total_size_bytes"] += total_size

        return stats


# Global Parquet store instance
_parquet_store: Optional[ParquetStore] = None


def get_parquet_store(
    parquet_dir: Optional[str] = None,
) -> ParquetStore:
    """
    Get global Parquet store instance.

    Args:
        parquet_dir: Optional directory path (uses default if not specified)

    Returns:
        ParquetStore instance
    """
    global _parquet_store

    if _parquet_store is None:
        if parquet_dir is None:
            import os
            parquet_dir = os.getenv(
                "PARQUET_DIR",
                "/data/parquet"
            )

        _parquet_store = ParquetStore(parquet_dir=parquet_dir)

    return _parquet_store
