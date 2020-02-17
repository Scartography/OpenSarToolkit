import os
import imageio
import glob
import time
import logging
from os.path import join as opj

import gdal
import rasterio
import numpy as np

from ost.helpers import utils as h, raster as ras, vector as vec

logger = logging.getLogger(__name__)


def create_timeseries_animation(
        track_ts_folder,
        product_list,
        out_folder,
        shrink_factor=1,
        duration=1,
        add_dates=False
):
    if not os.path.exists(out_folder):
        os.makedirs(out_folder, exist_ok=True)
    nr_of_products = len(glob.glob(
        opj(track_ts_folder, '*{}.tif'.format(product_list[0]))))
    outfiles = []
    # for coherence it must be one less
    if 'coh.VV' in product_list or 'coh.VH' in product_list:
        nr_of_products = nr_of_products - 1
    # Iterate over the tifs from the timeseries
    for i in range(nr_of_products):
        filelist = [glob.glob(
            opj(track_ts_folder, '{}.*{}*tif'.format(i + 1, product))
        )[0]
                    for product in product_list
                    ]
        dates = os.path.basename(filelist[0]).split('.')[1]
        if add_dates:
            date = dates
        else:
            date = None

        ras.create_rgb_jpeg(
            filelist,
            opj(out_folder, '{}.{}.jpeg'.format(i+1, dates)),
            shrink_factor,
            date=date
        )
        outfiles.append(opj(out_folder, '{}.{}.jpeg'.format(i+1, dates)))
    out_gif_name = os.path.basename(track_ts_folder)+'_ts_animation.gif'
    # create gif
    with imageio.get_writer(
            opj(out_folder, out_gif_name),
            mode='I',
            duration=duration
    ) as writer:
        for file in outfiles:
            image = imageio.imread(file)
            writer.append_data(image)
            os.remove(file)
            if os.path.isfile(file + '.aux.xml'):
                os.remove(file + '.aux.xml')


def mt_extent(
        list_of_scenes,
        out_file,
        temp_dir,
        buffer=None
):
    out_dir = os.path.dirname(out_file)
    vrt_options = gdal.BuildVRTOptions(srcNodata=0, separate=True)

    # build vrt stack from all scenes
    gdal.BuildVRT(opj(out_dir, 'extent.vrt'),
                  list_of_scenes,
                  options=vrt_options)

    start = time.time()

    outline_file = opj(temp_dir, os.path.basename(out_file))
    ras.outline(opj(out_dir, 'extent.vrt'), outline_file, 0, False)

    vec.exterior(outline_file, out_file, buffer)
    h.delete_shapefile(outline_file)

    os.remove(opj(out_dir, 'extent.vrt'))
    h.timer(start)


def mt_layover(
        filelist,
        outfile,
        temp_dir,
        extent,
        update_extent=False
):
    '''
    This function is usally used in the time-series workflow of OST. A list
    of the filepaths layover/shadow masks
    :param filelist - list of files
    :param out_dir - directory where the output file will be stored
    :return path to the multi-temporal layover/shadow mask file generated
    '''

    # get some info
    burst_dir = os.path.dirname(outfile)
    burst = os.path.basename(burst_dir)
    extent = opj(burst_dir, '{}.extent.shp'.format(burst))

    # get the start time for Info on processing time
    start = time.time()
    # create path to out file
    ls_layer = opj(temp_dir, os.path.basename(outfile))

    # create a vrt-stack out of
    print(' INFO: Creating common Layover/Shadow Mask')
    vrt_options = gdal.BuildVRTOptions(srcNodata=0, separate=True)
    gdal.BuildVRT(opj(temp_dir, 'ls.vrt'), filelist, options=vrt_options)

    with rasterio.open(opj(temp_dir, 'ls.vrt')) as src:

        # get metadata
        meta = src.meta
        # update driver and reduced band count
        meta.update(driver='GTiff', count=1, dtype='uint8')

        # create outfiles
        with rasterio.open(ls_layer, 'w', **meta) as out_min:

            # loop through blocks
            for _, window in src.block_windows(1):

                # read array with all bands
                stack = src.read(range(1, src.count + 1), window=window)

                # get stats
                arr_max = np.nanmax(stack, axis=0)
                arr = arr_max / arr_max

                out_min.write(np.uint8(arr), window=window, indexes=1)

    ras.mask_by_shape(ls_layer, outfile, extent, to_db=False,
                      datatype='uint8', rescale=False, ndv=0)
    os.remove(ls_layer)
    h.timer(start)

    if update_extent:
        print(' INFO: Calculating symetrical difference of extent and ls_mask')
        # polygonize the multi-temporal ls mask
        ras.polygonize_raster(outfile, '{}.shp'.format(outfile[:-4]))

        # create file for masked extent
        extent_ls_masked = opj(burst_dir, '{}.extent.masked.shp'.format(burst))

        # calculate difference between burst exntetn and ls mask, fr masked extent
        vec.difference(extent, '{}.shp'.format(outfile[:-4]), extent_ls_masked)