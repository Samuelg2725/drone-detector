#!/bin/bash
# install.sh - Download Leaflet and plugins

echo "Downloading Leaflet and plugins..."

# Create directories
mkdir -p images plugins/leaflet-draw/images plugins/leaflet-cluster plugins/leaflet-heatmap plugins/leaflet-control-geocoder plugins/leaflet-easybutton plugins/leaflet-fullscreen

# Download Leaflet core
curl -L -o leaflet.css "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
curl -L -o leaflet.js "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
curl -L -o leaflet-src.js "https://unpkg.com/leaflet@1.9.4/dist/leaflet-src.js"

# Download Leaflet images
curl -L -o images/layers.png "https://unpkg.com/leaflet@1.9.4/dist/images/layers.png"
curl -L -o images/layers-2x.png "https://unpkg.com/leaflet@1.9.4/dist/images/layers-2x.png"
curl -L -o images/marker-icon.png "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png"
curl -L -o images/marker-icon-2x.png "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png"
curl -L -o images/marker-shadow.png "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png"

# Download Leaflet Draw
curl -L -o plugins/leaflet-draw/leaflet.draw.css "https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.css"
curl -L -o plugins/leaflet-draw/leaflet.draw.js "https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.js"

# Download Leaflet MarkerCluster
curl -L -o plugins/leaflet-cluster/MarkerCluster.css "https://unpkg.com/leaflet.markercluster@1.5.0/dist/MarkerCluster.css"
curl -L -o plugins/leaflet-cluster/MarkerCluster.Default.css "https://unpkg.com/leaflet.markercluster@1.5.0/dist/MarkerCluster.Default.css"
curl -L -o plugins/leaflet-cluster/leaflet.markercluster.js "https://unpkg.com/leaflet.markercluster@1.5.0/dist/leaflet.markercluster.js"

# Download Leaflet Control Geocoder
curl -L -o plugins/leaflet-control-geocoder/Control.Geocoder.css "https://unpkg.com/leaflet-control-geocoder@2.4.0/dist/Control.Geocoder.css"
curl -L -o plugins/leaflet-control-geocoder/Control.Geocoder.js "https://unpkg.com/leaflet-control-geocoder@2.4.0/dist/Control.Geocoder.js"

# Download Leaflet EasyButton
curl -L -o plugins/leaflet-easybutton/easy-button.js "https://unpkg.com/leaflet-easybutton@2.4.0/src/easy-button.js"

echo "Download complete!"