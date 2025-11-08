# Belgrade AQI Heatmaps

This project turns raw pollutant concentration values from Belgrade air-quality
stations into an interactive AQI heatmap that can be published as a static
website (e.g. on Netlify).

## Repository layout

```
.
├── aqi_heatmaps/               # Python helpers for preparing AQI data
│   └── scripts/
│       └── process_data.py     # CLI for turning CSV files into heatmap JSON
├── data/
│   ├── sample_raw_data.csv     # Example pollutant dataset from three stations
│   └── aggregated_aqi.json     # Aggregated AQI values consumed by the web app
├── web/                        # Static website ready for Netlify deployment
│   ├── app.js
│   ├── index.html
│   └── styles.css
└── netlify.toml                # Minimal Netlify configuration (static publish)
```

## 1. Prepare AQI data

1. Export the raw pollutant concentration data from WAQI as a CSV file with the
   following columns:
   - `station_id` *(string)*
   - `station_name` *(string)*
   - `latitude`, `longitude` *(decimal degrees)*
   - `timestamp` *(ISO 8601 string or `YYYY-MM-DD HH:MM:SS` in UTC)*
   - pollutant columns such as `pm25`, `pm10`, `o3`, `no2`, `so2`, `co`

2. Run the processing script to convert the CSV into the aggregated JSON that
   the web application consumes:

   ```bash
   python aqi_heatmaps/scripts/process_data.py path/to/your_raw_data.csv --output data/aggregated_aqi.json
   ```

   The script:
   - Parses the timestamps (normalising them to UTC)
   - Computes pollutant-specific AQI values using the U.S. EPA breakpoints
   - Keeps the highest AQI per station/time as the composite AQI
   - Outputs `data/aggregated_aqi.json` containing one entry per
     station/timestamp

   The `data/sample_raw_data.csv` file demonstrates the expected format and can
   be used for local testing.

## 2. Preview the heatmap locally

1. Ensure `data/aggregated_aqi.json` exists (run the processing script if
   necessary).
2. Serve the static files from the `web/` directory using any HTTP server. For
   example:

   ```bash
   # from the repository root
   python -m http.server --directory web 8000
   ```

3. Navigate to <http://localhost:8000>. You should see the map of Belgrade with
   a heatmap overlay and a control panel allowing you to select the start time
   and window length (in hours) for aggregation. The table below the map lists
   the averaged AQI per station within the selected window.

## 3. Deploy to Netlify

Netlify can publish the site straight from the `web/` folder.

1. Commit the repository to your preferred Git hosting provider.
2. Create a new site in Netlify and connect the repository.
3. When prompted for the **build command**, leave it empty (or set to `echo`).
4. Set the **publish directory** to `web` (already defined in `netlify.toml`).
5. Trigger a deploy. Netlify will host the static site at the assigned URL.

To update the site when new data arrives, re-run the processing script with the
latest CSV and commit the updated `data/aggregated_aqi.json`.

## 4. Extending the project

- **Additional pollutants**: update the `AQI_BREAKPOINTS` dictionary in
  `aqi_heatmaps/scripts/process_data.py`.
- **Alternative aggregation windows**: the web application averages data across
  all observations that fall within the selected start time and duration.
  Extend `web/app.js` if you need rolling averages or other metrics.
- **Styling**: adjust `web/styles.css` for different branding or layouts.

## License

This repository does not currently include a license. Add one if you plan to
share or open-source the project.
