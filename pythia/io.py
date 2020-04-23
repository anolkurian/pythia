import os

import fiona
import rasterio
from shapely.geometry import Point, MultiPoint
from shapely.ops import nearest_points

import pythia.functions
import pythia.util

"""rasterio reads x/y which is longitude/latitude"""


def get_site_raster_value(dataset, band, site):
    lng, lat = site
    row, col = dataset.index(lng, lat)
    data = []
    try:
        data = band[row, col]
    except IndexError:
        data = None
    return data


def peer(run, sample_size=None):
    rasters = pythia.util.get_rasters_dict(run)
    sites = []
    if isinstance(run["sites"], list):
        sites = pythia.functions.xy_from_list(run["sites"])
    else:
        sites = pythia.functions.xy_from_vector(run["sites"])
    data = []
    nodata = []
    current_nodata = 0
    layers = list(rasters.keys())
    for raster in rasters.values():
        with rasterio.open(raster) as ds:
            if "int" in ds.dtypes[0]:
                current_nodata = -999
            else:
                current_nodata = -999.
            nodata.append(current_nodata)
            masked_band = ds.read(1, masked=True)
            band = masked_band.filled(current_nodata)
            data.append([get_site_raster_value(ds, band, site) for site in sites])
    peerless = list(
        filter(
            lambda x: x is not None,
            [read_layer_by_cell(i, data, nodata, layers, sites) for i in range(len(sites))],
        )
    )
    return peerless[:sample_size]


def read_layer_by_cell(idx, data, nodata, layers, sites):
    if data is None:
        return None
    lng, lat = sites[idx]
    cell = {"lat": lat, "lng": lng, "xcrd": lng, "ycrd": lat}
    for i, c in enumerate(data):
        if c[idx] == nodata[i]:
            return None
        else:
            if layers[i] == "harvestArea" and c[idx] == 0:
                return None
            else:
                cell[layers[i]] = c[idx]
    return cell


def make_run_directory(rd):
    os.makedirs(rd, exist_ok=True)


def get_rio_profile(f):
    with rasterio.open(f) as source:
        profile = source.profile
    return profile


def get_shp_profile(f):
    pass


def extract_vector_coords(f):
    points = []
    with fiona.open(f, 'r') as source:
        for feature in source:
            if feature["geometry"]["type"] == "MultiPoint":
                points.append(feature["geometry"]["coordinates"][0])
            if feature["geometry"]["type"] == "Point":
                points.append(feature["geometry"]["coordinates"])
    return points


def find_vector_coords(f, lng, lat, a):
    coords = (lng, lat)
    with fiona.open(f, 'r') as source:
        for feature in source:
            if feature["geometry"]["type"] == "MultiPoint":
                if coords in feature["geometry"]["coordinates"]:
                    return feature["properties"][a]
            if feature["geometry"]["type"] == "Point":
                if coords == feature["geometry"]["coordinates"]:
                    return feature["properties"][a]


def find_closest_vector_coords(f, lng, lat, a):
    coords = Point(lng, lat)
    points = []
    ids = []
    with fiona.open(f, 'r') as source:
        for feature in source:
            if feature["geometry"]["type"] == "MultiPoint":
                points.extend([Point(p[0], p[1]) for p in feature["geometry"]["coordinates"]])
                ids.extend([feature["properties"][a]] * len(feature["geometry"]["coordinates"]))
            if feature["geometry"]["type"] == "Point":
                points.append(
                    Point(feature["geometry"]["coordinates"][0],
                          feature["geometry"]["coordinates"][1])
                )
                ids.append(feature["properties"][a])
    mp = MultiPoint(points)
    nearest = nearest_points(coords, mp)[1]
    return ids[points.index(nearest)]
