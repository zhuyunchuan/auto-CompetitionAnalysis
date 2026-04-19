# Deployment Guide - Competitor Scraping System

## Prerequisites

1. **Python 3.11+** installed
2. **OpenClaw** instance (cloud or on-premise)
3. **Database** (SQLite included, PostgreSQL optional)
4. **Sufficient disk space** for Parquet snapshots and HTML cache

## Cloud Deployment Steps

### 1. Server Setup

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Python 3.11
sudo apt-get install python3.11 python3.11-venv python3-pip -y

# Install system dependencies
sudo apt-get install git curl -y
```

### 2. Project Deployment

```bash
# Clone repository
git clone https://github.com/zhuyunchuan/auto-CompetitionAnalysis.git
cd auto-CompetitionAnalysis

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install Playwright browsers (optional, for dynamic pages)
playwright install chromium --with-deps
```

### 3. Configuration

```bash
# Copy and edit configuration
cp config.yaml config.prod.yaml

# Edit production settings:
# - Adjust schedule times
# - Set proper storage paths
# - Configure rate limits
# - Set up logging paths
nano config.prod.yaml
```

### 4. Initialize Database

```bash
# Create data directories
mkdir -p data/{db,parquet,artifacts,raw_html,cache,logs}

# Initialize SQLite database
python -c "
from src.storage.db import init_database, init_storage_dirs
from src.storage.schema import Base
init_storage_dirs()
init_database()
print('Database initialized successfully')
"
```

### 5. OpenClaw Integration

#### 5.1 Register DAG

Create OpenClaw DAG file:

```python
# openclaw/dags/competitor_scraping_dag.py
import sys
sys.path.insert(0, '/path/to/auto-CompetitionAnalysis')

from src.pipeline import create_competitor_scraping_dag, register_dag

dag = create_competitor_scraping_dag()
register_dag(dag)
```

#### 5.2 Configure Schedule

```python
# OpenClaw scheduler configuration
from datetime import timedelta

from openclaw import DAG

from src.pipeline import create_competitor_scraping_dag

dag = create_competitor_scraping_dag()

# Biweekly schedule (every other Friday at 2 AM UTC)
dag.schedule = "0 2 * * 5"  # Cron expression

# Monthly schedule (1st day of month at 2 AM UTC)
# dag.schedule = "0 2 1 * *"
```

### 6. Test Run

```bash
# Manual test run with single brand
python -c "
from src.pipeline import run_manual_pipeline
from datetime import datetime

run_id = f'deploy_test_{datetime.now().strftime(\"%Y%m%d_%H%M%S\")}'
result = run_manual_pipeline(
    run_id=run_id,
    brands=['hikvision'],
    schedule_type='manual',
    config_overrides={
        'brands': {
            'hikvision': {
                'series_l1_allowlist': ['Pro']  # Test with single series
            }
        },
        'crawler': {
            'concurrent_requests': 2
        }
    }
)

print(f'Test run completed: {run_id}')
print(f'Result: {result}')
"
```

### 7. Verify Outputs

```bash
# Check Excel export
ls -lh data/artifacts/competitor_specs_*.xlsx

# Check Parquet snapshots
ls -lh data/parquet/

# Check logs
tail -f data/logs/competitor_scraping.log
```

## Monitoring

### Log Monitoring

```bash
# Follow logs in real-time
tail -f data/logs/competitor_scraping.log

# Search for errors
grep "ERROR" data/logs/competitor_scraping.log

# Search for specific run
grep "run_id=20260418_biweekly_01" data/logs/competitor_scraping.log
```

### Database Queries

```python
from src.storage.db import get_session
from src.storage.schema import RunSummary
from datetime import datetime, timedelta

# Recent runs
with get_session() as session:
    recent_runs = session.query(RunSummary).filter(
        RunSummary.started_at > datetime.utcnow() - timedelta(days=30)
    ).order_by(RunSummary.started_at.desc()).all()

    for run in recent_runs:
        print(f"{run.run_id}: {run.status} - {run.success_rate:.2%}")
```

### Quality Metrics

```bash
# Count issues by severity
python -c "
from src.storage.db import get_session
from src.storage.schema import DataQualityIssue

with get_session() as session:
    p1_count = session.query(DataQualityIssue).filter_by(severity='P1', status='open').count()
    p2_count = session.query(DataQualityIssue).filter_by(severity='P2', status='open').count()
    p3_count = session.query(DataQualityIssue).filter_by(severity='P3', status='open').count()

    print(f'P1 (Critical): {p1_count}')
    print(f'P2 (High): {p2_count}')
    print(f'P3 (Medium): {p3_count}')
"
```

## Maintenance

### Cleanup Old Data

```bash
# Remove Parquet snapshots older than 90 days
find data/parquet -type f -mtime +90 -delete

# Remove HTML snapshots older than 30 days
find data/raw_html -type f -mtime +30 -delete

# Clear cache
rm -rf data/cache/*

# Archive old logs
gzip data/logs/competitor_scraping.log.1
```

### Database Maintenance

```bash
# Vacuum SQLite database
sqlite3 data/db/competitor.db 'VACUUM;'

# Reindex
sqlite3 data/db/competitor.db 'REINDEX;'

# Check integrity
sqlite3 data/db/competitor.db 'PRAGMA integrity_check;'
```

## Troubleshooting

### Common Issues

**1. Memory Issues**
```bash
# Reduce concurrent requests in config.yaml
crawler:
  concurrent_requests: 2  # Default is 5

# Reduce batch sizes in repositories
# Edit batch_size parameters in repo_*.py files
```

**2. Timeouts**
```bash
# Increase timeout in config.yaml
crawler:
  timeout_sec: 60  # Default is 30

# Enable Playwright fallback
crawler:
  use_playwright_fallback: true
```

**3. Rate Limiting**
```bash
# Increase delays between requests
crawler:
  min_delay_ms: 1000  # Default is 300
  max_delay_ms: 2000  # Default is 1200
```

**4. Page Structure Changes**
- Update CSS selectors in adapters
- Check logs for parsing errors
- Use manual override for urgent corrections

## Backup Strategy

### Daily Backup Script

```bash
#!/bin/bash
# backup.sh - Daily backup script

DATE=$(date +%Y%m%d)
BACKUP_DIR="/backup/competitor_analysis"

# Backup SQLite database
cp data/db/competitor.db $BACKUP_DIR/competitor_$DATE.db

# Backup recent Parquet files
rsync -av data/parquet/ $BACKUP_DIR/parquet_$DATE/

# Backup configuration
cp config.yaml $BACKUP_DIR/config_$date.yaml

# Compress old backups
find $BACKUP_DIR -name "*.db" -mtime +7 -gzip
```

### Restore from Backup

```bash
# Stop pipeline
# (OpenClaw command to pause DAG)

# Restore database
cp /backup/competitor_analysis/competitor_20260418.db data/db/competitor.db

# Verify integrity
sqlite3 data/db/competitor.db 'PRAGMA integrity_check;'

# Restart pipeline
# (OpenClaw command to resume DAG)
```

## Scaling Considerations

### When to Upgrade to PostgreSQL

- More than 100K records per day
- Multiple concurrent writers
- Complex analytical queries
- Need for high availability

### Migration Steps

```bash
# 1. Install PostgreSQL
sudo apt-get install postgresql postgresql-contrib

# 2. Create database
sudo -u postgres createdb competitor_analysis

# 3. Update config.yaml
storage:
  sqlite_path: null  # Disable SQLite
  postgres_url: "postgresql://user:pass@localhost/competitor_analysis"

# 4. Run migration script
python scripts/migrate_to_postgres.py
```

## Security

### Environment Variables

```bash
# Create .env file
cat > .env <<EOF
STORAGE_SQLITE_PATH=data/db/competitor.db
CRAWLER_USER_AGENT="Your Bot Name (contact@example.com)"
LOG_LEVEL=INFO
EOF

# Load in application
python -c "from dotenv import load_dotenv; load_dotenv()"
```

### Access Control

```bash
# Restrict file permissions
chmod 600 config.yaml
chmod 700 data/db/

# Encrypt sensitive data
# Use encryption at rest for production deployments
```

## Support

For issues or questions:
- GitHub Issues: https://github.com/zhuyunchuan/auto-CompetitionAnalysis/issues
- Documentation: `docs/` directory
- Logs: `data/logs/competitor_scraping.log`
