import os
from os.path import join as opj
import shutil
import glob
import time
import logging
import datetime
import itertools
from tempfile import TemporaryDirectory
from retry import retry

from godale import Executor

import gdal

from ost.helpers import vector as vec, raster as ras, utils as h
from ost.s1 import timeseries
from ost.to_ard import burst_to_ard
from ost import Sentinel1Scene as S1Scene

logger = logging.getLogger(__name__)


def burst_to_ard_batch(
        burst_inventory,
        download_dir,
        processing_dir,
        ard_parameters,
        data_mount='/eodata',
        max_workers=int(os.cpu_count()/2)
):
    '''Handles the batch processing of a OST complinat burst inventory file

    Args:
        burst_inventory (GeoDataFrame):
        download_dir (str):
        processing_dir (str):
        temp_dir (str):
        ard_parameters (dict):

    '''
    if max_workers > os.cpu_count()/2:
        max_workers = int(os.cpu_count()/2)
    executor_type = 'concurrent_processes'
    executor = Executor(executor=executor_type,
                        max_workers=max_workers
                        )
    for task in executor.as_completed(
            func=_execute_batch_burst_ard,
            iterable=burst_inventory.iterrows(),
            fargs=(processing_dir,
                   download_dir,
                   data_mount,
                   ard_parameters,
                   )

    ):
        task.result()


@retry(tries=3, delay=1, logger=logger)
def _execute_batch_burst_ard(
        burst,
        processing_dir,
        download_dir,
        data_mount,
        ard_parameters
):
    index, burst = burst
    resolution = ard_parameters['resolution']
    product_type = ard_parameters['product_type']
    speckle_filter = ard_parameters['speckle_filter']
    ls_mask_create = ard_parameters['ls_mask_create']
    to_db = ard_parameters['to_db']
    dem = ard_parameters['dem']

    logger.debug(
        'INFO: Entering burst {} at date {}.'.format(
            burst.BurstNr,  burst.Date
        )
    )
    master_scene = S1Scene(burst.SceneID)

    # get path to file
    master_file = master_scene.get_path(download_dir, data_mount)
    # get subswath
    subswath = burst.SwathID
    # get burst number in file
    master_burst_nr = burst.BurstNr
    # create a fileId
    master_id = '{}_{}'.format(burst.Date, burst.bid)
    # create out folder
    out_dir = '{}/{}/{}'.format(processing_dir, burst.bid, burst.Date)
    os.makedirs(out_dir, exist_ok=True)

    # check if already processed
    if os.path.isfile(opj(out_dir, '.processed')):
        logger.debug('INFO: Burst {} from {} already processed'.format(
            burst.bid, burst.Date))
        return_code = 0
        return return_code
    with TemporaryDirectory() as temp_dir:
        try:
            return_code = burst_to_ard.burst_to_ard(
                master_file=master_file,
                swath=subswath,
                master_burst_nr=burst['BurstNr'],
                master_burst_id=master_id,
                master_burst_poly=burst['geometry'],
                out_dir=out_dir,
                out_prefix=master_id,
                temp_dir=temp_dir,
                resolution=resolution,
                product_type=product_type,
                speckle_filter=speckle_filter,
                to_db=to_db,
                ls_mask_create=ls_mask_create,
                dem=dem,
            )
        except Exception as e:
            raise e
        if return_code != 0:
            raise RuntimeError(
                'Something went wrong with the GPT processing! '
                'with return code: %s' % return_code
            )
    return return_code


def _ard_to_ts(
        burst_inventory,
        processing_dir,
        temp_dir,
        burst,
        to_db,
        ls_mask_create,
        ls_mask_apply,
        mt_speckle_filter,
        datatype
):
    burst_dir = opj(processing_dir, burst)
    
    # get common burst extent
    list_of_scenes = glob.glob(opj(burst_dir, '20*', '*data*', '*img'))
    list_of_scenes = [x for x in list_of_scenes if 'layover'not in x]
    extent = opj(burst_dir, '{}.extent.shp'.format(burst))
    timeseries.mt_extent(list_of_scenes, extent, buffer=-0.0018)

    # remove inital extent
    for file in glob.glob(opj(burst_dir, 'tmp*')):
        os.remove(file)

    # layover/shadow mask
    if ls_mask_create is True:
        list_of_scenes = glob.glob(opj(burst_dir, '20*', '*data*', '*img'))
        list_of_layover = [x for x in list_of_scenes if 'layover'in x]
        out_ls = opj(burst_dir, '{}.ls_mask.tif'.format(burst))
        timeseries.mt_layover(list_of_layover, out_ls, extent=extent)
        logger.debug('INFO: Our common layover mask is located at {}'.format(
              out_ls))

    if ls_mask_apply:
        logger.debug(
            'INFO: Calculating symetrical difference of extent and ls_mask'
        )
        ras.polygonize_raster(out_ls, '{}.shp'.format(out_ls[:-4]))
        extent_ls_masked = opj(burst_dir, '{}.extent.masked.shp'.format(burst))
        vec.difference(extent, '{}.shp'.format(out_ls[:-4]), extent_ls_masked)
        extent = extent_ls_masked

    list_of_product_types = {'BS': 'Gamma0', 'coh': 'coh',
                             'ha_alpha': 'Alpha'}

    # we loop through each possible product
    for p, product_name in list_of_product_types.items():
        # we loop through each polarisation
        for pol in ['VV', 'VH', 'HH', 'HV']:
            # see if there is actually any imagery
            list_of_ts_bursts = sorted(glob.glob(
                opj(processing_dir, burst, '20*', '*data*', '{}*{}*img'
                    .format(product_name, pol))))
            if len(list_of_ts_bursts) > 1:
                # check for all datafiles of this product type
                list_of_ts_bursts = sorted(glob.glob(
                    opj(processing_dir, burst, '20*/', '*{}*dim'.format(
                            p))))
                list_of_ts_bursts = '\'{}\''.format(
                    ','.join(list_of_ts_bursts))
                # define out_dir for stacking routine

                out_dir = opj(processing_dir,
                              '{}/Timeseries'.format(burst))
                os.makedirs(out_dir, exist_ok=True)

                temp_stack = opj(temp_dir,
                                 '{}_{}_{}_mt'.format(burst, p, pol))

                out_stack = opj(out_dir,
                                '{}_{}_{}_mt'.format(burst, p, pol))

                stack_log = opj(out_dir,
                                '{}_{}_{}_stack.err_log'.format(
                                    burst, p, pol))

                # run stacking routines
                ts.create_stack(list_of_ts_bursts,
                                temp_stack,
                                stack_log,
                                polarisation=pol
                                )

                # run mt speckle filter
                if mt_speckle_filter is True:
                    speckle_log = opj(
                        out_dir, '{}_{}_{}_mt_speckle.err_log'.format(
                            burst, p, pol))

                    ts.mt_speckle_filter('{}.dim'.format(temp_stack),
                                         out_stack, speckle_log)
                    # remove tmp files
                    h.delete_dimap(temp_stack)
                else:
                    out_stack = temp_stack

                # convert to GeoTiffs
                if p == 'BS':
                    # get the dates of the files
                    dates = [datetime.datetime.strptime(
                        x.split('_')[-1][:-4], '%d%b%Y')
                            for x in glob.glob(
                                opj('{}.data'.format(out_stack), '*img'))]
                    # sort them
                    dates.sort()
                    # write them back to string for following loop
                    sorted_dates = [datetime.datetime.strftime(
                        ts, "%d%b%Y") for ts in dates]

                    i, outfiles = 1, []
                    for date in sorted_dates:
                        # restructure date to YYMMDD
                        in_date = datetime.datetime.strptime(date, '%d%b%Y')
                        out_date = datetime.datetime.strftime(in_date,
                                                              '%y%m%d'
                                                              )

                        infile = glob.glob(opj('{}.data'.format(out_stack),
                                               '*{}*{}*img'.format(
                                                           pol, date)))[0]

                        # create outfile
                        outfile = opj(out_dir, '{}.{}.{}.{}.tif'.format(
                            i, out_date, p, pol))

                        # mask by extent
                        ras.to_gtiff_clip_by_extend(
                            infile, outfile,
                            extent,
                            to_db=to_db,
                            out_dtype=datatype,
                            min_value=-30,
                            max_value=5,
                            no_data=0.0
                        )
                        # add ot a list for subsequent vrt creation
                        outfiles.append(outfile)

                        i += 1

                    # build vrt of timeseries
                    vrt_options = gdal.BuildVRTOptions(srcNodata=0,
                                                       separate=True)
                    gdal.BuildVRT(opj(out_dir,
                                      'Timeseries.{}.{}.vrt'.format(
                                          p, pol)),
                                  outfiles,
                                  options=vrt_options)

                if p == 'coh':
                    # get slave and master Date
                    mstDates = [datetime.datetime.strptime(
                        os.path.basename(x).split('_')[3].split('.')[0],
                        '%d%b%Y') for x in glob.glob(
                            opj('{}.data'.format(out_stack), '*img'))]

                    slvDates = [datetime.datetime.strptime(
                        os.path.basename(x).split('_')[4].split('.')[0],
                        '%d%b%Y') for x in glob.glob(
                            opj('{}.data'.format(out_stack), '*img'))]
                    # sort them
                    mstDates.sort()
                    slvDates.sort()
                    # write them back to string for following loop
                    sortedMstDates = [datetime.datetime.strftime(
                        ts, "%d%b%Y") for ts in mstDates]
                    sortedSlvDates = [datetime.datetime.strftime(
                        ts, "%d%b%Y") for ts in slvDates]

                    i, outfiles = 1, []
                    for mst, slv in zip(sortedMstDates, sortedSlvDates):

                        inMst = datetime.datetime.strptime(mst, '%d%b%Y')
                        inSlv = datetime.datetime.strptime(slv, '%d%b%Y')

                        outMst = datetime.datetime.strftime(inMst,
                                                            '%y%m%d')
                        outSlv = datetime.datetime.strftime(inSlv,
                                                            '%y%m%d')

                        infile = glob.glob(opj('{}.data'.format(out_stack),
                                               '*{}*{}_{}*img'.format(
                                                       pol, mst, slv)))[0]
                        outfile = opj(out_dir, '{}.{}.{}.{}.{}.tif'.format(
                            i, outMst, outSlv, p, pol))

                        ras.to_gtiff_clip_by_extend(
                            infile, outfile,
                            extent,
                            to_db=False,
                            out_dtype=datatype,
                            min_value=0.000001,
                            max_value=1,
                            no_data=0.0
                        )

                        # add ot a list for subsequent vrt creation
                        outfiles.append(outfile)

                        i += 1

                    # build vrt of timeseries
                    vrt_options = gdal.BuildVRTOptions(srcNodata=0,
                                                       separate=True)
                    gdal.BuildVRT(
                            opj(out_dir,
                                'Timeseries.{}.{}.vrt'.format(p, pol)),
                            outfiles,
                            options=vrt_options)

                # remove tmp files
                h.delete_dimap(out_stack)

    for pol in ['Alpha', 'Entropy', 'Anisotropy']:
        list_of_ts_bursts = sorted(glob.glob(
            opj(processing_dir, burst, '20*',
                '*{}*'.format(p), '*{}.img'.format(pol)))
        )

        if len(list_of_ts_bursts) > 1:
            list_of_ts_bursts = sorted(glob.glob(
                opj(processing_dir, burst, '20*/', '*{}*dim'.format(p))))
            list_of_ts_bursts = '\'{}\''.format(','.join(
                list_of_ts_bursts))

            # logger.debug(list_of_ts_bursts)

            out_dir = opj(processing_dir, '{}/Timeseries'.format(burst))
            os.makedirs(out_dir, exist_ok=True)

            temp_stack = opj(temp_dir, '{}_{}_mt'.format(burst, pol))
            out_stack = opj(out_dir, '{}_{}_mt'.format(burst, pol))

            stack_log = opj(out_dir,
                            '{}_{}_stack.err_log'.format(burst, pol))
            # processing routines
            ts.create_stack(list_of_ts_bursts,
                            temp_stack,
                            stack_log,
                            pattern=pol
                            )

            if mt_speckle_filter is True:
                speckle_log = opj(out_dir,
                                  '{}_{}_mt_speckle.err_log'.format(
                                         burst, pol))
                ts.mt_speckle_filter('{}.dim'.format(temp_stack),
                                     out_stack, speckle_log)
                # remove tmp files
                h.delete_dimap(temp_stack)
            else:
                out_stack = temp_stack

            # get the dates of the files
            dates = [datetime.datetime.strptime(x.split('_')[-1][:-4],
                     '%d%b%Y') for x in glob.glob(
                        opj('{}.data'.format(out_stack), '*img'))]
            # sort them
            dates.sort()
            # write them back to string for following loop
            sorted_dates = [datetime.datetime.strftime(
                ts, "%d%b%Y") for ts in dates]

            i, outfiles = 1, []
            for date in sorted_dates:
                # restructure date to YYMMDD
                in_date = datetime.datetime.strptime(date, '%d%b%Y')
                out_date = datetime.datetime.strftime(in_date, '%y%m%d')

                infile = glob.glob(opj('{}.data'.format(out_stack),
                                       '*{}*{}*img'.format(pol, date)))[0]
                # create outfile
                outfile = opj(out_dir, '{}.{}.{}.{}.tif'.format(
                        i, out_date, p, pol))
                # mask by extent
                max_value = 90 if pol is 'Alpha'else 1
                ras.to_gtiff_clip_by_extend(
                    infile,
                    outfile,
                    extent,
                    to_db=False,
                    out_dtype=datatype,
                    min_value=0.000001,
                    max_value=max_value,
                    no_data=0
                )

                # add ot a list for subsequent vrt creation
                outfiles.append(outfile)
                i += 1

            # build vrt of timeseries
            vrt_options = gdal.BuildVRTOptions(srcNodata=0, separate=True)
            gdal.BuildVRT(opj(out_dir, 'Timeseries.{}.vrt'.format(pol)),
                          outfiles,
                          options=vrt_options)

            # remove tmp files
            h.delete_dimap(out_stack)


def burst_ards_to_timeseries(burst_inventory, processing_dir, temp_dir,
                             ard_parameters):

    datatype = ard_parameters['datatype']
    to_db = ard_parameters['to_db']
    
    if to_db:
        to_db_mt = False
    else:
        to_db_mt = ard_parameters['to_db_mt']
    
    ls_mask_create = ard_parameters['ls_mask_create']
    ls_mask_apply = ard_parameters['ls_mask_apply']
    mt_speckle_filter = ard_parameters['mt_speckle_filter']

    for burst in burst_inventory.bid.unique():
        _ard_to_ts(
            burst_inventory,
            processing_dir,
            temp_dir,
            burst,
            to_db_mt,
            ls_mask_create,
            ls_mask_apply,
            mt_speckle_filter,
            datatype
        )


def _timeseries_to_timescan(
        burst_inventory,
        processing_dir,
        temp_dir,
        burst_dir,
        to_db,
        metrics,
        outlier_removal
):

    product_list = ['BS.HH', 'BS.VV', 'BS.HV', 'BS.VH',
                    'coh.VV', 'coh.VH', 'Alpha', 'Entropy', 'Anisotropy'
                    ]

    for product in product_list:
        for timeseries in glob.glob(opj(burst_dir, 'Timeseries',
                                        '*{}*vrt'.format(product))):

            logger.debug('INFO: Creating timescan for {}'.format(product))
            timescan_dir = opj(burst_dir, 'Timescan')
            os.makedirs(timescan_dir, exist_ok=True)

            # we get the name of the time-series parameter
            polarisation = timeseries.split('/')[-1].split('.')[2]
            if polarisation == 'vrt':
                timescan_prefix = opj(
                    '{}'.format(timescan_dir),
                    '{}'.format(timeseries.split('/')[-1].split('.')[1]))
            else:
                timescan_prefix = opj(
                    '{}'.format(timescan_dir),
                    '{}.{}'.format(timeseries.split('/')[-1].split('.')[1],
                                   polarisation))

            start = time.time()
            if 'BS.'in timescan_prefix:    # backscatter
                timeseries.mt_metrics(timeseries, timescan_prefix, metrics,
                                      rescale_to_datatype=True,
                                      to_power=to_db,
                                      outlier_removal=outlier_removal)
            else:   # non-backscatter
                timeseries.mt_metrics(timeseries, timescan_prefix, metrics,
                                      rescale_to_datatype=False,
                                      to_power=False,
                                      outlier_removal=outlier_removal)

            h.timer(start)

    # rename and create vrt
    # logger.debug('renaming')
    i, list_of_files = 0, []
    for product in itertools.product(product_list, metrics):

        file = glob.glob(
            opj(burst_dir, 'Timescan', '*{}.{}.tif'.format(
                product[0], product[1])))

        if file:
            i += 1
            outfile = opj(burst_dir, 'Timescan', '{}.{}.{}.tif'.format(
                i, product[0], product[1]))
            shutil.move(file[0], outfile)
            list_of_files.append(outfile)

    # create vrt
    vrt_options = gdal.BuildVRTOptions(srcNodata=0, separate=True)
    gdal.BuildVRT(opj(burst_dir, 'Timescan', 'Timescan.vrt'),
                  list_of_files,
                  options=vrt_options)


def timeseries_to_timescan(burst_inventory, processing_dir, temp_dir,
                           ard_parameters):
    '''Function to create a timescan out of a OST timeseries.

    '''

    if ard_parameters['to_db_mt'] or ard_parameters['to_db']:
        to_db = True
    else:
        to_db = False

    metrics = ard_parameters['metrics']
    outlier_removal = ard_parameters['outlier_removal']

    for burst in burst_inventory.bid.unique():   # ***

        burst_dir = opj(processing_dir, burst)

        logger.debug('INFO: Entering burst {}'.format(burst))
        _timeseries_to_timescan(burst_inventory, processing_dir, temp_dir,
                                burst_dir, to_db, metrics, outlier_removal)


def mosaic_timeseries(burst_inventory, processing_dir, temp_dir,
                      ard_parameters):

    product_list = ['BS.HH', 'BS.VV', 'BS.HV', 'BS.VH',
                    'coh.VV', 'coh.VH', 'ha_alpha.Alpha',
                    'ha_alpha.Entropy', 'ha_alpha.Anisotropy']

    os.makedirs(opj(processing_dir, 'Mosaic', 'Timeseries'), exist_ok=True)

    # we do this to get the minimum number of
    # timesteps per burst (should be actually the same)
    length = 99999
    for burst in burst_inventory.bid.unique():

        length_of_burst = len(burst_inventory[burst_inventory.bid == burst])

        if length_of_burst < length:
            length = length_of_burst

    # now we loop through each timestep and product
    for product in product_list:  # ****
        
        list_of_files = []
        for i in range(length):

            filelist = glob.glob(
                opj(processing_dir, '*_IW*_*', 'Timeseries', '{}.*{}.tif'
                    .format(i + 1, product)))
            
            if filelist:
                logger.debug('INFO: Creating timeseries mosaic {} for {}.'.format(
                    i + 1, product))
    
                datelist = []
                
                for file in filelist:
                    if '.coh.'in file:
                        datelist.append('{}_{}'.format(
                            os.path.basename(file).split('.')[2],
                            os.path.basename(file).split('.')[1]))
                    else:
                        datelist.append(os.path.basename(file).split('.')[1])
                
                start = sorted(datelist)[0]
                end = sorted(datelist)[-1]
                
                out_dir = opj(processing_dir, 'Mosaic', 'Timeseries')
                os.makedirs(out_dir, exist_ok=True)
                
                if start == end:
                    outfile = opj(
                        out_dir, '{}.{}.{}.tif'.format(i + 1, start, product)
                    )
                else:
                    outfile = opj(
                        out_dir,
                        '{}.{}-{}.{}.tif'.format(i + 1, start, end, product)
                    )

                list_of_files.append(outfile)
                filelist = ''.join(filelist)
                # the command
                command = ('otbcli_Mosaic -il {} -comp.feather large '
                           '-tmpdir {} -progress 1 -out {} float'.format(
                               filelist, temp_dir, outfile))
                os.system(command)

        # create vrt
        if list_of_files:
            vrt_options = gdal.BuildVRTOptions(srcNodata=0, separate=True)
            gdal.BuildVRT(opj(out_dir, '{}.Timeseries.vrt'.format(product)),
                          list_of_files,
                          options=vrt_options)


def mosaic_timescan(burst_inventory,
                    processing_dir,
                    temp_dir,
                    ard_parameters
                    ):

    product_list = ['BS.HH', 'BS.VV', 'BS.HV', 'BS.VH',
                    'coh.VV', 'coh.VH', 'Alpha', 'Entropy', 'Anisotropy']
    metrics = ard_parameters['metrics']

    os.makedirs(opj(processing_dir, 'Mosaic', 'Timescan'), exist_ok=True)
    i, list_of_files = 0, []
    for product in itertools.product(product_list, metrics):   # ****

        filelist = ''.join(glob.glob(
            opj(processing_dir, '*', 'Timescan', '*{}.{}.tif'.format(
                product[0], product[1]))))

        if filelist:
            i += 1
            outfile = opj(processing_dir, 'Mosaic', 'Timescan',
                          '{}.{}.{}.tif'.format(i, product[0], product[1]))
            command = ('otbcli_Mosaic -il {} -comp.feather large -tmpdir {}'
                       '-progress 1 -out {} float'.format(
                               filelist, temp_dir, outfile))
            os.system(command)
            list_of_files.append(outfile)

    # create vrt
    vrt_options = gdal.BuildVRTOptions(srcNodata=0, separate=True)
    gdal.BuildVRT(opj(processing_dir, 'Mosaic', 'Timescan', 'Timescan.vrt'),
                  list_of_files,
                  options=vrt_options)
