# DSL of Dify Apps Exporter

This Python project allows you to download DSL files for all apps from the Dify platform via their API.

## Requirements

- Python 3.13 or higher
- Poetry for dependency management

## Installation

1. Clone the repository:

```bash
$ git clone https://github.com/sattosan/dify-apps-dsl-exporter.git
$ cd dify-apps-dsl-exporter
```

2. Install dependencies using Poetry:

```bash
$ poetry install
```

3. Create a .env file in the root directory with the following environment variables:

```bash
$ cp .env.example .env
```

```txt
DIFY_ORIGIN=http://localhost  # Or the Dify origin URL
EMAIL=your-email@example.com # for Dify login
PASSWORD=your-password # for Dify login
DSL_EXPORT_TAGS=YOUR_TAG
```

## UseCase

### Export DSL Files filtered by tags
```bash
$ docker run --rm \
  --env-file .env \
  -v "$(pwd)/dsl:/app/dsl" \
  sinist3r/dify-apps-dsl-exporter:0.1 export
```

### Import ALL DSL Files

```bash
$ docker run --rm \
  --env-file .env \
  -v "$(pwd)/dsl:/app/dsl" \
  sinist3r/dify-apps-dsl-exporter:0.1 import
```
