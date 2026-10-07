# temp_electricity

## Overview
Temperature Electricity (placeholder name) is an Ontario electricity consumption mapping tool. The goal is
to map the effect of temperature changes on electricity consumption at the Forward Sortation Area (FSA) level
in Ontario. The visualization will be a heatmap of every Ontario FSA, with a temperature slider so users can
see how consumption changes across FSAs.

The project includes the scripts to pull and clean the raw data, the temperature–electricity model, and the
final visualization tool.

## Motivation
The motivation behind the tool is to understand the socio-economic impacts of temperature changes on people's
livelihoods. As climate change causes rapid and severe changes to weather patterns, the need for impact and
risk assessment is increasing.

We believe our tool will fill a gap in publicly available information. While the IESO has done internal
capacity assessment and risk analysis, it has not released this information publicly. Public tools for
electricity visualization exist, such as [Electricity Maps](https://app.electricitymaps.com/map/fifteen_minutes),
but many features are behind a paywall, and the free data is limited to regional grid-level information.

Our tool is public and useful for both businesses and individuals, and it could be scaled through partnerships
with regional operators. We are currently limited to Ontario, as the IESO publicly releases electricity
consumption data at the FSA level.

## Data sources and licensing
The software and dependencies use open licenses. All data is fetched from public sources by the code in this
repository; no data files are committed.

1. **Electricity consumption:** IESO, *Hourly Consumption by Forward Sortation Area*, residential and small
   business customers, monthly files from 2018 onward.
   [reports-public.ieso.ca/public/HourlyConsumptionByFSA](https://reports-public.ieso.ca/public/HourlyConsumptionByFSA/)
2. **Temperature:** Copernicus Climate Change Service (C3S), *ERA5-Land hourly time-series data from 1950 to
   present*, hourly 2 m temperature at each FSA's grid point (~9 km), 2018 onward.
   DOI: [10.24381/ee82e357](https://doi.org/10.24381/ee82e357). Licence: CC-BY 4.0.
3. **FSA boundaries:** Statistics Canada, 2021 Census Forward Sortation Area boundary file, via the
   simplified version in [sachijay/canada_maps](https://github.com/sachijay/canada_maps).

## Setup
Requires [uv](https://docs.astral.sh/uv/).

    uv sync
    uv run jupyter lab

The temperature download needs a free [Copernicus CDS](https://cds.climate.copernicus.eu) account:
1. Accept the licence on the ERA5-Land time-series dataset page.
2. Save your API key in `~/.cdsapirc` (never in this repository):

       url: https://cds.climate.copernicus.eu/api
       key: <your-key>

## Repository
As of 2026-10-06:

    temp_electricity/
    ├── README.md
    ├── LICENSE
    ├── pyproject.toml
    ├── uv.lock
    ├── .gitignore
    ├── fsa_temperature.ipynb   # FSA boundaries + hourly temperature per FSA
    └── data/                   # created by the notebook; not committed
