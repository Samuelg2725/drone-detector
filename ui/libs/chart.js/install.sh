#!/bin/bash
# install.sh - Download Chart.js and plugins

echo "Downloading Chart.js and plugins..."

# Create directories
mkdir -p plugins helpers

# Download Chart.js core
curl -L -o chart.js "https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.js"
curl -L -o chart.min.js "https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js"
curl -L -o chart.umd.js "https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.umd.js"

# Download plugins
curl -L -o plugins/chartjs-plugin-datalabels.js "https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.0.0/dist/chartjs-plugin-datalabels.js"
curl -L -o plugins/chartjs-plugin-datalabels.min.js "https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.0.0/dist/chartjs-plugin-datalabels.min.js"
curl -L -o plugins/chartjs-plugin-annotation.js "https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@2.0.1/dist/chartjs-plugin-annotation.js"
curl -L -o plugins/chartjs-plugin-annotation.min.js "https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@2.0.1/dist/chartjs-plugin-annotation.min.js"
curl -L -o plugins/chartjs-plugin-zoom.js "https://cdn.jsdelivr.net/npm/chartjs-plugin-zoom@1.2.0/dist/chartjs-plugin-zoom.js"
curl -L -o plugins/chartjs-plugin-zoom.min.js "https://cdn.jsdelivr.net/npm/chartjs-plugin-zoom@1.2.0/dist/chartjs-plugin-zoom.min.js"

echo "Download complete!"