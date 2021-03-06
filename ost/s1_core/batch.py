import os
from os.path import join as opj
from re import findall
import glob
import gdal
import logging
import itertools
from tempfile import TemporaryDirectory

from ost import Sentinel1Scene
from ost.helpers.utils import _create_processing_dict
from ost.multitemporal.utils import mt_extent, mt_layover
from ost.multitemporal import timescan
from ost.multitemporal.ard_to_ts import ard_to_ts
from ost.multitemporal.timescan import create_tscan_vrt
from ost.mosaic import mosaic

logger = logging.getLogger(__name__)


def _to_ard_batch(
        inventory_df,
        download_dir,
        processing_dir,
        ard_parameters,
        subset=None,
        polar='VV,VH,HH,HV',
        max_workers=int(os.cpu_count()/2)
):
    # we create a processing dictionary,
    # where all frames are grouped into acquisitions
    processing_dict = _create_processing_dict(inventory_df)
    for track, allScenes in processing_dict.items():
        for list_of_scenes in processing_dict[track]:
            # get acquisition date
            acquisition_date = Sentinel1Scene(list_of_scenes[0]).start_date
            # create a subdirectory baed on acq. date
            out_dir = opj(processing_dir, track, acquisition_date)
            os.makedirs(out_dir, exist_ok=True)

            # check if already processed
            if os.path.isfile(opj(out_dir, '.processed')):
                logger.debug('Acquisition from {} of track {}'
                             'already processed'.format(acquisition_date, track)
                             )
            else:
                # get the paths to the file
                for i in list_of_scenes:
                    s1_process_scene = Sentinel1Scene(i)
                    s1_process_scene.ard_parameters = ard_parameters
                    scene_paths = ([Sentinel1Scene(i).get_path(download_dir)
                                    for i in list_of_scenes
                                    ])
                    s1_process_scene.create_ard(
                        filelist=scene_paths,
                        out_dir=out_dir,
                        out_prefix=s1_process_scene.start_date.replace('-', ''),
                        subset=subset,
                        polar=polar,
                        max_workers=max_workers
                    )


def ards_to_timeseries(
        inventory_df,
        processing_dir,
        ard_params=None,
        product_suffix='TC'
):
    for track in inventory_df.relativeorbit.unique():
        # get the burst directory
        track_dir = opj(processing_dir, track)

        # get common burst extent
        list_of_scenes = glob.glob(opj(track_dir, '20*', '*data*', '*img'))
        list_of_scenes = [x for x in list_of_scenes if 'layover' not in x]
        extent = opj(track_dir, '{}.extent.shp'.format(track))

        logger.debug(
            'INFO: Creating common extent mask for track {}'.format(track)
        )
        with TemporaryDirectory() as temp_dir:
            mt_extent(list_of_scenes, extent, temp_dir, -0.0018)

    if ard_params['create_ls_mask'] or ard_params['apply_ls_mask']:
        for track in inventory_df.relativeorbit.unique():
            # get the burst directory
            track_dir = opj(processing_dir, track)

            # get common burst extent
            list_of_scenes = glob.glob(opj(track_dir, '20*', '*data*', '*img'))
            list_of_layover = [x for x in list_of_scenes if 'layover' in x]

            # layover/shadow mask
            out_ls = opj(track_dir, '{}.ls_mask.tif'.format(track))

            logger.debug(
                'INFO: Creating common Layover/Shadow mask '
                'for track {}'.format(track)
            )
            with TemporaryDirectory() as temp_dir:
                mt_layover(
                    list_of_layover,
                    out_ls,
                    temp_dir,
                    extent,
                    ard_params['apply_ls_mask']
                )

    for track in inventory_df.relativeorbit.unique():
        # get the burst directory
        track_dir = opj(processing_dir, track)
        for pol in ['VV', 'VH', 'HH', 'HV']:
            # see if there is actually any imagery in thi polarisation
            list_of_files = sorted(glob.glob(
                opj(track_dir, '20*', '*data*', '*ma0*{}*img'.format(pol))
            ))
            if not len(list_of_files) > 1:
                continue
            # create list of dims if polarisation is present
            list_of_dims = sorted(glob.glob(
                opj(track_dir, '20*', '*'+product_suffix+'*dim')))
            ard_to_ts(
                list_of_dims,
                processing_dir,
                track,
                product_suffix=product_suffix,
                ard_params=ard_params,
                pol=pol
            )


def timeseries_to_timescan(
        inventory_df,
        processing_dir,
        ard_params=None
):
    to_db = False
    # get the db scaling right
    if ard_params['to_db']:
        to_db = True

    dtype_conversion = True if ard_params['dtype_output'] != 'float32' else False
    for track in inventory_df.relativeorbit.unique():
        logger.debug('INFO: Entering track {}.'.format(track))
        # get track directory
        track_dir = opj(processing_dir, track)
        # define and create Timescan directory
        timescan_dir = opj(track_dir, 'Timescan')
        os.makedirs(timescan_dir, exist_ok=True)
        # loop thorugh each polarization
        for polar in ['VV', 'VH', 'HH', 'HV']:
            if os.path.isfile(opj(timescan_dir, '.{}.processed'.format(polar))):
                logger.debug(
                    'INFO: Timescans for track {} already'
                    ' processed.'.format(track))
                continue
            # Get timeseries vrt
            timeseries_vrt = glob.glob(
                opj(track_dir, 'Timeseries', '*.TC.{}.vrt'.format(polar))
            )
            if len(timeseries_vrt) > 1:
                raise RuntimeError(
                    'More vrt file per polarization in the timeseries '
                    'of track: %s',
                    track
                )
            elif len(timeseries_vrt) == 0:
                logger.debug(
                    'The %s polarisation is not availible in track %s',
                    polar, track
                )
                continue
            timeseries_vrt = timeseries_vrt[0]
            if not os.path.isfile(timeseries_vrt):
                raise RuntimeError('VRT file for timeseries in track '
                                   '%s missing!', track)
            logger.debug(
                'INFO: Processing Timescans of {} '
                'for track {}.'.format(polar, track)
            )
            # create a datelist for harmonics
            scenelist = glob.glob(
                opj(track_dir, 'Timeseries', '*TC.{}.tif'.format(polar))
            )

            # create a datelist for harmonics calculation
            datelist = []
            for file in sorted(scenelist):
                datelist.append(findall(r"\D(\d{8})\D", os.path.basename(file)))
            # define timescan prefix
            timescan_prefix = opj(timescan_dir, 'TC.{}'.format(polar))
            # run timescan
            timescan.mt_metrics(
                timeseries_vrt,
                timescan_prefix,
                ard_params['metrics'],
                rescale_to_datatype=dtype_conversion,
                to_power=to_db,
                outlier_removal=ard_params['remove_outliers'],
                datelist=datelist
            )


def mosaic_timeseries(
        inventory_df,
        processing_dir,
        temp_dir,
        cut_to_aoi=False,
        exec_file=None
):

    logger.debug(' -----------------------------------')
    logger.debug('INFO: Mosaicking Time-series layers')
    logger.debug(' -----------------------------------')

    # create output folder
    ts_dir = opj(processing_dir, 'Mosaic', 'Timeseries')
    os.makedirs(ts_dir, exist_ok=True)

    # loop through polarisations
    for p in ['VV', 'VH', 'HH', 'HV']:
        tracks = inventory_df.relativeorbit.unique()
        nr_of_ts = len(glob.glob(opj(
            processing_dir, tracks[0], 'Timeseries', '*.{}.tif'.format(p))))

        if not nr_of_ts >= 1:
            continue

        outfiles = []
        for i in range(1, nr_of_ts + 1):

            filelist = glob.glob(opj(
                processing_dir, '*', 'Timeseries',
                '{}.*.{}.tif'.format(i, p)))
            filelist = [file for file in filelist if 'Mosaic' not in file]

            # create
            datelist = []
            for file in filelist:
                datelist.append(os.path.basename(file).split('.')[1])

            filelist = ' '.join(filelist)
            start, end = sorted(datelist)[0], sorted(datelist)[-1]

            if start == end:
                outfile = opj(ts_dir, '{}.{}.BS.{}.tif'.format(i, start, p))
            else:
                outfile = opj(ts_dir, '{}.{}-{}.BS.{}.tif'.format(i, start, end, p))

            check_file = opj(
                os.path.dirname(outfile),
                '.{}.processed'.format(os.path.basename(outfile)[:-4])
            )
            outfiles.append(outfile)

            if os.path.isfile(check_file):
                logger.debug(
                    'INFO: Mosaic layer {} already'
                    ' processed.'.format(os.path.basename(outfile))
                )
                continue

            logger.debug('INFO: Mosaicking layer {}.'.format(os.path.basename(outfile)))
            mosaic.mosaic(
                filelist,
                outfile,
                cut_to_aoi
            )

        if exec_file:
            logger.debug(' gdalbuildvrt ....command, outfiles')
            continue

        # create vrt
        vrt_options = gdal.BuildVRTOptions(srcNodata=0, separate=True)
        gdal.BuildVRT(opj(ts_dir, 'Timeseries.{}.vrt'.format(p)),
                      outfiles,
                      options=vrt_options
                      )


def mosaic_timescan(
        processing_dir,
        ard_params,
        cut_to_aoi=False,
):
    metrics = ard_params['metrics']
    if 'harmonics' in metrics:
        metrics.remove('harmonics')
        metrics.extend(['amplitude', 'phase', 'residuals'])

    if 'percentiles' in metrics:
        metrics.remove('percentiles')
        metrics.extend(['p95', 'p5'])

    # create out directory of not existent
    tscan_dir = opj(processing_dir, 'Mosaic', 'Timescan')
    os.makedirs(tscan_dir, exist_ok=True)
    outfiles = []

    # loop through all pontial proucts
    for polar, metric in itertools.product(['VV', 'HH', 'VH', 'HV'], metrics):
        # create a list of files based on polarisation and metric
        filelist = glob.glob(opj(processing_dir, '*', 'Timescan',
                                 '*TC.{}.{}.tif'.format(polar, metric)
                                 )
                             )

        # break loop if there are no files
        if not len(filelist) >= 2:
            continue

        # get number
        filelist = ' '.join(filelist)
        outfile = opj(tscan_dir, 'BS.{}.{}.tif'.format(polar, metric))
        check_file = opj(
            os.path.dirname(outfile),
            '.{}.processed'.format(os.path.basename(outfile)[:-4])
        )
        if os.path.isfile(check_file):
            logger.debug('INFO: Mosaic layer {} already '
                         ' processed.'.format(os.path.basename(outfile))
                         )
            continue

        logger.debug('INFO: Mosaicking layer {}.'.format(os.path.basename(outfile)))
        mosaic.mosaic(filelist, outfile, cut_to_aoi)
        outfiles.append(outfile)

    create_tscan_vrt(tscan_dir, ard_params)
