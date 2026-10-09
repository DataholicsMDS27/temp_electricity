# Ontario Energy Explorer

Purpose: explore hypothetical hourly electricity consumption per customer across Ontario FSAs.
Audience: desktop datathon demonstration and scenario exploration.
Direction: a calm map-first atlas, with a charcoal control-room variant.
Differentiator: a looping hourly interval wheel, and an optional pixel-sky Daylight theme that responds to that hour without changing the map's data palette.
Constraints: real 2021 census FSA geography, explicitly labelled synthetic predictions until a model is integrated, fixed units and legend across scenarios, no provincial totals derived from averages.

System: Public Sans for controls and prose; JetBrains Mono for interval and consumption numbers. White or charcoal opaque panels, teal or lime interface accents, 1px dividers, 12px panels, 8px controls. Consumption uses the same light-mint to dark-teal scale in every theme. Primary workspace has a 310px sidebar and a flexible map. Daylight sky occupies only the workspace background and switches map style at 06:00 and 18:00. Reduced motion disables sky animation and camera easing.

Inputs: -40 to 35 °C in 1 °C steps, weekday/weekend, 24 hourly intervals. Initial scenario: 22 °C, weekday, 14:00–15:00. Explicit prediction submit; old results remain labelled with their submitted scenario after input edits. Missing FSA predictions are grey. Search and click share a persistent selection.
