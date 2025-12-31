import geopandas as gpd
import rasterio
from rasterio.mask import mask
import numpy as np
import os
import requests
import shutil
from email.utils import parsedate_to_datetime

# --- Configuration ---
GEOJSON_FILE = "boundaries.geojson"
RASTER_FILE = "population_raster.tif"
OUTPUT_FILE = "population_count.txt"
DATE_OUTPUT_FILE = "populationDate.txt"

# URL for a lightweight world boundaries file to detect the country
WORLD_MAP_URL = "https://raw.githubusercontent.com/datasets/geo-boundaries-world-110m/master/countries.geojson"

def get_country_code_from_geometry(gdf):
    """
    Spatially joins the user GeoJSON with a world map to find the country code.
    Uses a projected CRS for accurate centroid calculation.
    """
    print("🌍 Identifying country from coordinates...")
    try:
        # Load world boundaries
        world = gpd.read_file(WORLD_MAP_URL)
        
        # 1. Project to a meter-based CRS (EPSG:3857) to calculate a valid centroid
        # 2. Then project back to WGS84 (EPSG:4326) to match the world map
        centroid_gdf = gdf.to_crs(epsg=3857).centroid.to_crs(epsg=4326).to_frame('geometry')
        
        # Ensure world map is also in WGS84
        if world.crs != "EPSG:4326":
            world = world.to_crs(epsg=4326)
        
        # Spatial Join: Find which country contains the center of the user's shape
        joined = gpd.sjoin(centroid_gdf, world, predicate='within')
        
        if not joined.empty:
            # Check common ISO columns
            for col in ['ISO_A3', 'iso_a3', 'ADM0_A3']:
                if col in joined.columns:
                    code = str(joined.iloc[0][col]).upper()
                    if code != "NAN" and len(code) == 3:
                        return code
        return None
    except Exception as e:
        print(f"❌ Error during spatial detection: {e}")
        return None

def get_remote_file_date_formatted(url):
    try:
        response = requests.head(url, timeout=10)
        if 'Last-Modified' in response.headers:
            dt_object = parsedate_to_datetime(response.headers['Last-Modified'])
            return dt_object.strftime('%Y-%m-%d')
        return "Unknown"
    except: return "Unknown"

def calculate_population():
    if not os.path.exists(GEOJSON_FILE):
        print("❌ Error: boundaries.geojson not found.")
        return

    # 1. Load User GeoJSON
    user_gdf = gpd.read_file(GEOJSON_FILE)

    # 2. Process Geometry to get Country Code
    country_code = get_country_code_from_geometry(user_gdf)
    
    if not country_code or country_code == "NAN":
        print("❌ Could not determine country. Is the GeoJSON in the ocean or outside known borders?")
        return

    print(f"📍 Geometry detected in: {country_code}")

    # 3. Construct URL
    raster_url = f"https://data.worldpop.org/GIS/Population/Global_2000_2020/2020/{country_code}/{country_code.lower()}_ppp_2020_UNadj.tif"

    # 4. Get Date and Save
    date_str = get_remote_file_date_formatted(raster_url)
    with open(DATE_OUTPUT_FILE, 'w') as f:
        f.write(date_str)

    # 5. Download Raster
    if not os.path.exists(RASTER_FILE):
        print(f"📥 Downloading raster for {country_code}...")
        r = requests.get(raster_url, stream=True)
        if r.status_code != 200:
            print(f"❌ Raster not found on WorldPop for code {country_code}. Check if code is correct.")
            return
        with open(RASTER_FILE, 'wb') as f:
            shutil.copyfileobj(r.raw, f)

    # 6. Spatial Masking & Calculation
    try:
        with rasterio.open(RASTER_FILE) as src:
            if user_gdf.crs != src.crs:
                user_gdf = user_gdf.to_crs(src.crs)
            
            out_image, _ = mask(src, user_gdf.geometry, crop=True)
            data = out_image[0]
            valid_data = data[(data != src.nodata) & (data >= 0)]
            total_pop = int(np.sum(valid_data))

            print(f"✅ Calculation Complete: {total_pop:,} people.")
            with open(OUTPUT_FILE, 'w') as f:
                f.write(str(total_pop))
    finally:
        if os.path.exists(RASTER_FILE):
            os.remove(RASTER_FILE)

if __name__ == "__main__":
    calculate_population()
