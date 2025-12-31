import geopandas as gpd
import rasterio
from rasterio.mask import mask
import numpy as np
import os
import requests
from requests.exceptions import RequestException
import shutil
from email.utils import parsedate_to_datetime

# --- Configuration ---
GEOJSON_FILE = "boundaries.geojson"
RASTER_FILE = "population_raster.tif"  # Local name for the downloaded file
OUTPUT_FILE = "population_count.txt"
DATE_OUTPUT_FILE = "populationDate.txt"
# ---------------------

def get_remote_file_date_formatted(url):
    try:
        response = requests.head(url)
        if 'Last-Modified' in response.headers:
            raw_date = response.headers['Last-Modified']
            dt_object = parsedate_to_datetime(raw_date)
            return dt_object.strftime('%Y-%m-%d')
        else:
            return "Unknown"
    except Exception as e:
        print(f"Warning: Could not get date. {e}")
        return "Unknown"

def download_file(url, local_filename):
    """Downloads a file from a URL to a local path."""
    print(f"Downloading {os.path.basename(url)}...")
    try:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
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

    # 1. Load GeoJSON Boundary FIRST
    if not os.path.exists(GEOJSON_FILE):
        print(f"ERROR: GeoJSON boundary file not found at {GEOJSON_FILE}")
        return

    try:
        gpd_boundary = gpd.read_file(GEOJSON_FILE)
    except Exception as e:
        print(f"ERROR: Could not read GeoJSON file. {e}")
        return

    # --- EXTRACT COUNTRY CODE FROM GEOJSON ---
    try:
        # We take the code from the first feature (row 0)
        # NOTE: Verify your GeoJSON has a property named 'COUNTRY_CODE'. 
        # If it uses 'ISO', 'id', or 'adm0_a3', change the string below!
        country_code = gpd_boundary.iloc[0]['COUNTRY_CODE'] 
        
        print(f"📍 Detected Country Code from GeoJSON: {country_code}")
    except KeyError:
        print("❌ ERROR: Property 'COUNTRY_CODE' not found in GeoJSON. Please check your column names.")
        print(f"Available columns: {gpd_boundary.columns.tolist()}")
        return
    except IndexError:
        print("❌ ERROR: The GeoJSON appears to be empty.")
        return

    # --- CONSTRUCT DYNAMIC URL ---
    # Now we build the URL using the extracted code
    raster_url = f"https://data.worldpop.org/GIS/Population/Global_2000_2020/2020/{country_code.upper()}/{country_code.lower()}_ppp_2020_UNadj.tif"
    print(f"🔗 Target Raster URL: {raster_url}")

    # 2. Get Date from Remote URL
    date_string = get_remote_file_date_formatted(raster_url)
    print(f"📅 Remote Data Date: {date_string}")
    
    with open(DATE_OUTPUT_FILE, 'w') as f:
        f.write(date_string)

    # 3. Automatic Raster Download
    if not os.path.exists(RASTER_FILE):
        if not download_file(raster_url, RASTER_FILE):
            print("Aborting calculation due to download failure.")
            return

    # 4. Process Population Data
    geoms = gpd_boundary.geometry.tolist()

    try:
        with rasterio.open(RASTER_FILE) as src:
            # Reproject GeoJSON if necessary
            if gpd_boundary.crs != src.crs:
                print(f"Warning: GeoJSON CRS ({gpd_boundary.crs}) does not match Raster CRS ({src.crs}). Reprojecting GeoJSON.")
                gpd_boundary = gpd_boundary.to_crs(src.crs)
                geoms = gpd_boundary.geometry.tolist()

            print(f"Clipping raster '{RASTER_FILE}' using GeoJSON boundary...")
            out_image, out_transform = mask(src, geoms, crop=True)

            nodata = src.nodata
            if nodata is None:
                nodata = 0

            valid_population_values = out_image[0][out_image[0] != nodata]
            total_population = np.sum(valid_population_values)
            final_count = int(total_population)

            # Output Result
            print(f"\n✅ Calculation Complete!")
            print(f"Total Estimated Population: {final_count:,}")

            with open(OUTPUT_FILE, 'w') as f:
                f.write(str(final_count))

            print(f"Result written to {OUTPUT_FILE}")

    except rasterio.RasterioIOError as e:
        print(f"ERROR: Could not process raster file: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during processing: {e}")

    # 5. Cleanup
    if os.path.exists(RASTER_FILE):
        os.remove(RASTER_FILE)
        print(f"Cleaned up downloaded file: {RASTER_FILE}")

if __name__ == "__main__":
    calculate_population()
