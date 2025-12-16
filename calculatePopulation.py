
import geopandas as gpd
import rasterio
from rasterio.mask import mask
import numpy as np
import os
import requests
from requests.exceptions import RequestException
import shutil

# --- Configuration ---
GEOJSON_FILE = "sample_data/boundaries.geojson"
RASTER_FILE = "population_raster.tif"  # Local name for the downloaded file
OUTPUT_FILE = "population_count.txt"

# --- REAL RASTER URL (Example: Sierra Leone 2020) ---
# NOTE: Ensure this raster file covers the area defined by your GEOJSON_FILE!
RASTER_URL = "https://data.worldpop.org/GIS/Population/Global_2000_2020/2020/CHE/che_ppp_2020_UNadj.tif"
# ---------------------

def download_file(url, local_filename):
    """Downloads a file from a URL to a local path."""
    print(f"Downloading {os.path.basename(url)}...")
    try:
        # Use stream=True to handle large files efficiently
        with requests.get(url, stream=True) as r:
            r.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            with open(local_filename, 'wb') as f:
                shutil.copyfileobj(r.raw, f)
        print(f"Download successful. Saved to {local_filename}")
        return True
    except RequestException as e:
        print(f"ERROR: Could not download raster file from {url}. Error: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during download: {e}")
        return False


def calculate_population():
    print("Starting population calculation...")

    # Check for GeoJSON locally
    if not os.path.exists(GEOJSON_FILE):
        print(f"ERROR: GeoJSON boundary file not found at {GEOJSON_FILE}")
        return

    # 1. Automatic Raster Download
    if not os.path.exists(RASTER_FILE):
        print(f"Raster file not found locally. Attempting to download from {RASTER_URL}...")
        if not download_file(RASTER_URL, RASTER_FILE):
            print("Aborting calculation due to download failure.")
            return

    # 2. Load GeoJSON Boundary
    # Ensure the GeoJSON and Raster have compatible Coordinate Reference Systems (CRSs)
    gpd_boundary = gpd.read_file(GEOJSON_FILE)
    geoms = gpd_boundary.geometry.tolist()

    # 3. Open Population Raster
    try:
        with rasterio.open(RASTER_FILE) as src:
            # IMPORTANT CRS Check: Reproject GeoJSON if necessary
            if gpd_boundary.crs != src.crs:
                print(f"Warning: GeoJSON CRS ({gpd_boundary.crs}) does not match Raster CRS ({src.crs}). Reprojecting GeoJSON.")
                gpd_boundary = gpd_boundary.to_crs(src.crs)
                geoms = gpd_boundary.geometry.tolist() # Update geometries after reprojection

            # 4. Perform Clipping/Masking
            print(f"Clipping raster '{RASTER_FILE}' using GeoJSON boundary...")
            out_image, out_transform = mask(src, geoms, crop=True)

            # 5. Calculate the Sum
            nodata = src.nodata
            if nodata is None:
                # WorldPop generally uses 0 or -99999, but this covers cases where metadata is missing
                print("Warning: Raster has no defined NoData value. Assuming 0 for background.")
                nodata = 0

            # Filter out the NoData values (from band 0)
            valid_population_values = out_image[0][out_image[0] != nodata]

            # Calculate the total population
            total_population = np.sum(valid_population_values)
            final_count = int(total_population)

            # 6. Output Result
            print(f"\n✅ Calculation Complete!")
            print(f"Total Estimated Population: {final_count:,}")

            with open(OUTPUT_FILE, 'w') as f:
                f.write(f"Total Estimated Population: {final_count}")

            print(f"Result written to {OUTPUT_FILE}")

    except rasterio.RasterioIOError as e:
        print(f"ERROR: Could not process raster file (check file integrity and CRS): {e}")
    except Exception as e:
        print(f"An unexpected error occurred during processing: {e}")

    # 7. Cleanup (Highly Recommended)
    if os.path.exists(RASTER_FILE):
        os.remove(RASTER_FILE)
        print(f"Cleaned up downloaded file: {RASTER_FILE}")

if __name__ == "__main__":
    calculate_population()
