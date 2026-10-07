# temp_electricity
## Overview
Temperature Electricity (Placeholder name) is an Ontario electricity consumption mapping tool. The goal is 
to create a visualization tool that will map the effect of temperature changes on electricity consumption 
at an FSA level in the province of Ontario. This visualization is to be done as a heatmap containing every 
Ontario FSA, where the user is able to adjust the temperature using a slider to see how consumption changes 
across the FSAs. 

The project will include the pulling and cleaning scripts needed to pull and process the raw data, the scripts
used for our temperature-electricity model, and the final visualization tool. 

## Motivation
The motivation behind the tool is to understand the socio-economic impacts of temperature changes on people's 
livelihoods. As climate change causes rapid and severe changes to weather patterns, the need for impact and 
risk assessment is increasing. 

We believe our tool will fill a gap in publicly available information. While the IESO has done internal 
capacity assessment and risk analysis, it has not released this information publicly. There exist public tools
for electricity capacity visualization, such as [Electricitymaps.com](https://app.electricitymaps.com/map/fifteen_minutes), but many features are locked behind a paywall, with the accessible data being limited to regional level grid information. 

Our tool is useful for both businesses and individuals, it is public, and it could potentially be scaled through partnership with regional operators to access their information. We are currently limited to Ontario, 
as the IESO publicly releases electricity consumption information at the level we require. 

## Data and licensing
The software, dependencies, and bundled assets use open licenses. The public data is fetched from the public 
government and open source services 

We will be using data from three separate sources:
1. Hourly Ontario FSA electricity consumption data from the IESO, found [here](https://reports-public.ieso.ca/public/HourlyConsumptionByFSA/?C=M;O=A)
2. Hourly temperature data from [here](https://open-meteo.com/en/docs/historical-weather-api)
NOTE: The API is limiting us at the moment but we have a possible alternative
3. Statistics Canada FSA Geolocation data, found [here](https://github.com/sachijay/canada_maps)

## Repository
As of 2026-10-06, the repository is organized as follows:
temp_electricity/
│
├── README.md
├── pyproject.toml
├── uv.lock
├── .gitignore
│
├── src/
│
├── tests/
│
├── data/
│
└── notebooks/