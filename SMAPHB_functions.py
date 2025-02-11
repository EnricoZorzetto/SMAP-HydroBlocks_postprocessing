import os
import sys
import numpy as np
import xarray as xr
import datetime
import warnings

def save_data(database_path, minlon, maxlon, minlat, maxlat, 
              start_date, end_date, time_step,
              compression_level, output_file):
    
    if time_step not in ['6h', 'daily', 'monthly', 'annual']:
         sys.exit("Error: time_step = %s not available or implemented, please use: '6h', 'daily', 'weekly', 'monthly', 'annual'" % time_step)
   
    # Read the catchments and HRU maps
    catch_map = xr.open_rasterio('%s/mapping_catchments/all_catchments.vrt' % database_path)
    catch_map = catch_map.sel(x=slice(minlon,maxlon),y=slice(maxlat,minlat))
    hru_map = xr.open_rasterio('%s/mapping_hrus/all_hrus.vrt' % database_path)
    hru_map = hru_map.sel(x=slice(minlon,maxlon),y=slice(maxlat,minlat))

    # retrieve unique catchments ID
    unique_catchments = np.unique(catch_map.values)
    unique_catchments = unique_catchments[unique_catchments != -9999]

    # retrive lat lon
    lons = catch_map.x.values
    lats = catch_map.y.values

    # Loop over catchment and retrive the data
    first_iteration = True
    for icatch in unique_catchments:

        # read SMAPHB data
        infile = '%s/SMAPHB_hru_6hr/%i.nc' % (database_path,icatch)
        ds = xr.open_dataset(infile)
        ds = ds.sel(time=slice(start_date,end_date))

        # Save temporal data and create output files
        if first_iteration:
            nt = ds.SMAPHB_SM.values.shape[0]
            times = ds.time.values
            new_data = np.ones((nt,len(lats),len(lons)))*-9999.0
            first_iteration = False

        # remap HRU data to geographic data
        mask_catchment = (catch_map.values[0] == icatch)
        for ihru in ds.hru.values:
            mask_hrus = mask_catchment & (hru_map.values[0] == ihru)
            if np.any(mask_hrus):
                position = np.where(mask_hrus)
                new_data[:,position[0],position[1]] = ds.SMAPHB_SM.values[:,ihru][:, np.newaxis]

        # close files 
        ds.close()
        del ds

    # Cleanup
    hru_map.close()
    del hru_map
    catch_map.close()
    del catch_map
    new_data[new_data == -9999.0] = np.nan
    
    # Create final output netCDF4 file
    final_map_xr = xr.DataArray(new_data, coords=[times, lats, lons], dims=["time", "lat", "lon"])
    final_map_xr.attrs["units"]="m3/m3"
    ds = final_map_xr.to_dataset(name='SMAPHB_SM')

    # Aggregate data in time according to the options: '6h', 'daily', 'monthly', 'annual'
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if time_step == '6h':
            pass
        elif time_step == 'daily':
            ds = ds.resample(time="1D").reduce(np.nanmean)
        elif time_step == 'monthly':
            ds = ds.resample(time="1MS").reduce(np.nanmean)
        elif time_step == 'annual':
            ds = ds.resample(time="1YS").reduce(np.nanmean)
    

    # Define encoding and compression
    encoding = {'SMAPHB_SM' : {'_FillValue': -9999,
                               'complevel': compression_level, # Output data compression level: 
                                                #  [0] No compression (fast)
                                                #  [9] max compression (slow)
                               'zlib': True,
                              },
                'time': {'dtype': 'i4'},
               }

    attrs = dict(title = "SMAP-HydroBlocks Surface Soil Moisture Data (m3/m3)",
                description = "SMAP-HydroBlocks (SMAP-HB) is a hyper-resolution satellite-based surface soil moisture product that combines NASA Soil Moisture Active-Passive (SMAP) L3 Enhance product, hyper-resolution land surface modeling, radiative transfer modeling, machine learning, and in-situ observations. This data is organize in geographic coordinates at 30-m 6-hourly resolution (2015-2019).",
                creator_name = "Noemi Vergopolan (noemi@princeton.edu)",
                institution = 'Princeton University',
                citation = "Vergopolan et al. (2020). Combining hyper-resolution land surface modeling with SMAP brightness temperatures to obtain 30-m soil moisture estimates. Remote Sensing of Environment, 242, 111740. https://doi.org/10.1016/j.rse.2020.111740 and Vergopolan et al. (2021). SMAP-HydroBlocks, a 30-m satellite-based soil moisture dataset for the conterminous US. Scientific Data, 8, 264. https://doi.org/10.1038/s41597-021-01050-2",
                )

    # Save output file
    os.system('rm -rf %s' % output_file)
    ds = ds.assign_attrs(attrs)
    ds.to_netcdf(output_file, encoding=encoding)
    ds.close()
    del ds
    
    return
