# Local dataset drop zone

Place private CSV or Parquet datasets here if desired. Dataset files are ignored by Git; this README is retained.

Import any file (it does not have to live in this directory):

```bash
make validate-data FILE=/absolute/path/to/ohlcv.csv
make import-data FILE=/absolute/path/to/ohlcv.csv
```
