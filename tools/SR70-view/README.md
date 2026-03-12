# SR70 View

Small browser-based viewer for SR70 railway station data.

## What it does

- extracts station and stop records from `Ciselnik.xlsx`
- builds `public/data/stations.json`
- shows the data in a searchable map and table view

## Requirements

- Node.js
- npm
- source workbook at `Ciselnik.xlsx`

## Run

```bash
npm install
npm run dev
```

This runs the data extraction step first and then starts the Vite dev server.

## Other commands

```bash
npm run build
npm run preview
```