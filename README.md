# RBP Structure Downloader

A command-line tool that downloads every RNA-binding protein (RBP) structure from the [RCSB Protein Data Bank](https://www.rcsb.org/).

An entry counts as an RNA-binding protein if at least one of its polymer entities is annotated with the Gene Ontology term [GO:0003723 – RNA binding](https://www.ebi.ac.uk/QuickGO/term/GO:0003723) (molecular function). This is the same GO / UniProt-GOA annotation that defines RBPs as a class. The structure does not need to contain bound RNA to be included.

## Features

- Queries the [RCSB Search API v2](https://search.rcsb.org/) and retrieves all matching entries, not just the first page.
- Downloads structures in parallel using a configurable thread pool.
- Automatically retries transient failures (DNS errors, dropped connections, HTTP 429/500/502/503/504) with exponential backoff.
- Supports resumable downloads. Existing files are skipped when rerunning the command.
- Supports mmCIF (default) and legacy PDB formats, both gzipped and uncompressed.
- Saves the complete PDB ID list and any failed IDs to text files for reproducibility.

## Requirements

- Python 3.8+
- [requests](https://pypi.org/project/requests/)

## Installation

```bash
git clone https://github.com/<your-username>/rbp-structure-downloader.git
cd rbp-structure-downloader
pip install -r requirements.txt
```

## Usage

Download all RBP structures in gzipped mmCIF format into `./rbp_structures`:

```bash
python rbp.py
```

Fetch only the list of PDB IDs without downloading structures:

```bash
python rbp.py --ids-only
```

Download uncompressed legacy PDB files:

```bash
python rbp.py --format pdb --no-gzip
```

Specify a different output folder and number of workers:

```bash
python rbp.py --outdir ./data --workers 16
```

Use a different GO term (for example, GO:0003677 – DNA binding):

```bash
python rbp.py --go-id GO:0003677
```

## Options

| Option | Default | Description |
|---|---|---|
| `--outdir` | `./rbp_structures` | Folder where structures and ID lists are saved |
| `--go-id` | `GO:0003723` | GO molecular-function term used to select entries |
| `--format` | `cif` | `cif` (mmCIF) or `pdb` (legacy format) |
| `--no-gzip` | off | Download uncompressed files instead of `.gz` |
| `--workers` | `8` | Number of parallel download threads |
| `--ids-only` | off | Only write the ID list; skip downloading |

Note: mmCIF is recommended. Some large RBP assemblies, such as ribosomes, do not have legacy `.pdb` files and may fail with `--format pdb
