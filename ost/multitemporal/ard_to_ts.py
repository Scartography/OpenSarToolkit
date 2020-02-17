import os
from os.path import join as opj
import importlib
import glob
import datetime
import logging
from tempfile import TemporaryDirectory

import gdal

from ost.helpers import raster as ras, helpers as h
from ost.config.speckle_config import DEFAULT_MT_SPECKLE_DICT

logger = logging.getLogger(__name__)


def create_stack(
        filelist,
        out_stack,
        logfile,
        polarisation=None,
        pattern=None
):
    '''
    :param filelist: list of single Files (space separated)
    :param outfile: the stack that is generated
    :return:
    '''

    # get gpt file
    gpt_file = h.gpt_path()

    # get path to graph
    rootpath = importlib.util.find_spec('ost').submodule_search_locations[0]
    if pattern:
        graph = opj(rootpath, 'graphs', 'S1_TS', '1_BS_Stacking_HAalpha.xml')
        command = '{} {} -x -q {} -Pfilelist={} -PbandPattern=\'{}.*\' \
               -Poutput={}'.format(gpt_file, graph, 2 * os.cpu_count(),
                                   filelist, pattern, out_stack
                                   )
    else:
        graph = opj(rootpath, 'graphs', 'S1_TS', '1_BS_Stacking.xml')
        command = '{} {} -x -q {} -Pfilelist={} -Ppol={} \
               -Poutput={}'.format(gpt_file, graph, 2 * os.cpu_count(),
                                   filelist, polarisation, out_stack
                                   )

    return_code = h.run_command(command, logfile)

    if return_code == 0:
        logger.debug(' INFO: Succesfully created multi-temporal stack')
    else:
        logger.debug(
                     'ERROR: Stack creation exited with an error.'
                     ' See {} for Snap Error output'.format(logfile)
        )

    return return_code


def mt_speckle_filter(
        in_stack,
        out_stack,
        logfile,
        speckle_dict=None
):
    '''
    '''
    # get gpt file
    gpt_file = h.gpt_path()
    if speckle_dict is None:
        speckle_dict = DEFAULT_MT_SPECKLE_DICT

    logger.debug(' INFO: Applying multi-temporal speckle filtering.')
    # contrcut command string
    command = ('{} Multi-Temporal-Speckle-Filter -x -q {}'
               ' -PestimateENL={}'
               ' -PanSize={}'
               ' -PdampingFactor={}'
               ' -Penl={}'
               ' -Pfilter="{}"'
               ' -PfilterSizeX={}'
               ' -PfilterSizeY={}'
               ' -PnumLooksStr={}'
               ' -PsigmaStr={}'
               ' -PtargetWindowSizeStr={}'
               ' -PwindowSize={}'
               ' -t "{}" "{}"'.format(
        gpt_file, 2 * os.cpu_count(),
        speckle_dict['estimate_ENL'],
        speckle_dict['pan_size'],
        speckle_dict['damping'],
        speckle_dict['ENL'],
        speckle_dict['filter'],
        speckle_dict['filter_x_size'],
        speckle_dict['filter_y_size'],
        speckle_dict['num_of_looks'],
        speckle_dict['sigma'],
        speckle_dict['target_window_size'],
        speckle_dict['window_size'],
        out_stack,
        in_stack
    )
    )
    return_code = h.run_command(command, logfile)

    if return_code == 0:
        logger.debug(' INFO: Succesfully applied multi-temporal speckle filtering')
    else:
        raise RuntimeError('Multi-temporal speckle filtering exited with an error. \
                See {} for Snap Error output'.format(logfile)
                            )

    return return_code


def ard_to_ts(
        list_of_files,
        processing_dir,
        track,
        ard_params,
        pol,
        product_suffix='TC',
        no_data=0.0
):
    # get the track directory
    track_dir = opj(processing_dir, track)

    # check routine if timeseries has already been processed
    check_file = opj(track_dir,
                     'Timeseries',
                     '.{}.{}.processed'.format(product_suffix, pol)
                     )
    if os.path.isfile(check_file):
        logger.debug(
                     'INFO: Timeseries of {} for {} in {} polarisation already'
                     ' processed'.format(track, product_suffix, pol)
                     )
        return

    # get the DB scaling
    if product_suffix is not 'coh':
        to_db = ard_params['to_db_mt']

    if ard_params['apply_ls_mask']:
        extent = opj(track_dir, '{}.extent.masked.shp'.format(track))
    else:
        extent = opj(track_dir, '{}.extent.shp'.format(track))

    # min max dict for stretching in case of 16 or 8 bit datatype
    mm_dict = {'TC': {'min': -30, 'max': 5},
               'coh': {'min': 0.000001, 'max': 1},
               'Alpha': {'min': 0.000001, 'max': 90},
               'Anisotropy': {'min': 0.000001, 'max': 1},
               'Entropy': {'min': 0.000001, 'max': 1}
               }

    stretch = pol if pol in ['Alpha', 'Anisotropy', 'Entropy'] else product_suffix

    # define out_dir for stacking routine
    out_dir = opj(processing_dir, '{}'.format(track), 'Timeseries')
    os.makedirs(out_dir, exist_ok=True)

    with TemporaryDirectory() as temp_dir:
        # create namespaces
        temp_stack = opj(
            temp_dir, '{}_{}_{}'.format(track, product_suffix, pol)
        )
        out_stack = opj(
            temp_dir, '{}_{}_{}_mt'.format(track, product_suffix, pol)
        )
        stack_log = opj(
            out_dir, '{}_{}_{}_stack.err_log'.format(track, product_suffix, pol)
        )

        # run stacking routines
        # convert list of files readable for snap
        list_of_files = '\'{}\''.format(','.join(list_of_files))

        if pol in ['Alpha', 'Anisotropy', 'Entropy']:
            logger.debug(
                'INFO: Creating multi-temporal stack of images of track/track {} for'
                ' the {} band of the polarimetric H-A-Alpha'
                ' decomposition.'.format(track, pol)
            )
            create_stack(list_of_files, temp_stack, stack_log, pattern=pol)
        else:
            logger.debug(
                'INFO: Creating multi-temporal stack of images of track/track {} for'
                ' {} product_suffix in {} '
                'polarization.'.format(track, product_suffix, pol)
            )
            create_stack(list_of_files, temp_stack, stack_log, polarisation=pol)

        # run mt speckle filter
        if ard_params['mt_speckle_filter'] is True:
            speckle_log = opj(
                out_dir,
                '{}_{}_{}_mt_speckle.err_log'.format(track, product_suffix, pol)
            )
            logger.debug('INFO: Applying multi-temporal speckle filter')
            mt_speckle_filter('{}.dim'.format(temp_stack),
                              out_stack,
                              speckle_log
                              )
        else:
            out_stack = temp_stack
        if product_suffix == 'coh':
            outfiles = _get_coh_ts(
                in_stack=out_stack,
                out_dir=out_dir,
                polarization=pol,
                product_suffix=product_suffix,
                extent=extent,
                to_db=to_db,
                out_dtype=ard_params['dtype_output'],
                min=mm_dict[stretch]['min'],
                max=mm_dict[stretch]['max']
            )
        else:
            outfiles = _get_regular_ts(
                in_stack=out_stack,
                out_dir=out_dir,
                polarization=pol,
                product_suffix=product_suffix,
                extent=extent,
                to_db=to_db,
                out_dtype=ard_params['dtype_output'],
                min=mm_dict[stretch]['min'],
                max=mm_dict[stretch]['max'],
                no_data=no_data
            )
        with open(str(check_file), 'w') as file:
            file.write('passed all tests \n')
        # build vrt of timeseries
        vrt_options = gdal.BuildVRTOptions(srcNodata=0, separate=True)
        gdal.BuildVRT(opj(out_dir, 'Timeseries.{}.{}.vrt'.format(product_suffix, pol)),
                      outfiles,
                      options=vrt_options
                      )


def _get_regular_ts(
        in_stack,
        out_dir,
        polarization,
        product_suffix='TC',
        extent=None,
        to_db=False,
        out_dtype='float32',
        min=0.000001,
        max=1,
        no_data=0.0
):
    # get the dates of the files
    dates = [datetime.datetime.strptime(x.split('_')[-1][:-4], '%d%b%Y')
             for x in glob.glob(opj('{}.data'.format(in_stack), '*img'))]
    # sort them
    dates.sort()
    # write them back to string for following loop
    sorted_date = [datetime.datetime.strftime(ts, "%d%b%Y")
                   for ts in dates]

    i, outfiles = 1, []
    for date in sorted_date:
        # restructure date to YYMMDD
        in_date = datetime.datetime.strptime(date, '%d%b%Y')
        out_date = datetime.datetime.strftime(in_date, '%Y%m%d')

        infile = glob.glob(opj('{}.data'.format(in_stack),
                               '*{}*{}*img'.format(polarization, date))
                           )[0]
        # create outfile
        outfile = opj(
            out_dir, '{}.{}.{}.{}.tif'.format(i, out_date, product_suffix, polarization)
        )
        logger.debug('Writing date %s to file %s', out_date, outfile)

        ras.to_gtiff_clip_by_extend(
            infile,
            outfile,
            extent,
            to_db=to_db,
            out_dtype=out_dtype,
            min_value=min,
            max_value=max,
            no_data=no_data
        )
        if outfile is None or not os.path.isfile(outfile):
            raise RuntimeError(
                'File %s was not created, something went wrong.', outfile
            )
        # add ot a list for subsequent vrt creation
        outfiles.append(outfile)
        i += 1

    return outfiles


def _get_coh_ts(
        in_stack,
        out_dir,
        polarization,
        product_suffix='coh',
        extent=None,
        to_db=False,
        out_dtype='float32',
        min=0.000001,
        max=1
):
    # get slave and master Date
    master_dates = [datetime.datetime.strptime(
        os.path.basename(x).split('_')[3].split('.')[0],
        '%d%b%Y') for x in glob.glob(
        opj('{}.data'.format(in_stack), '*img'))]

    slaves_dates = [datetime.datetime.strptime(
        os.path.basename(x).split('_')[4].split('.')[0],
        '%d%b%Y') for x in glob.glob(
        opj('{}.data'.format(in_stack), '*img'))]
    # sort them
    master_dates.sort()
    slaves_dates.sort()
    # write them back to string for following loop
    sorted_master_dates = [datetime.datetime.strftime(
        ts, "%d%b%Y") for ts in master_dates]
    sorted_slave_dates = [datetime.datetime.strftime(
        ts, "%d%b%Y") for ts in slaves_dates]

    i, outfiles = 1, []
    for mst, slv in zip(sorted_master_dates, sorted_slave_dates):
        in_master = datetime.datetime.strptime(mst, '%d%b%Y')
        in_slave = datetime.datetime.strptime(slv, '%d%b%Y')

        out_master = datetime.datetime.strftime(in_master, '%Y%m%d')
        out_slave = datetime.datetime.strftime(in_slave, '%Y%m%d')
        infile = glob.glob(opj('{}.data'.format(in_stack),
                               '*{}*{}_{}*img'.format(polarization, mst, slv)))[0]

        outfile = opj(
            out_dir,
            '{}.{}.{}.{}.{}.tif'.format(i,
                                        out_master,
                                        out_slave,
                                        product_suffix,
                                        polarization
                                        )
        )
        logger.debug('Writing to file %s', outfile)
        ras.to_gtiff_clip_by_extend(
            infile,
            outfile,
            extent,
            to_db=to_db,
            out_dtype=out_dtype,
            min_value=min,
            max_value=max,
            no_data=0.0,
            description=True
        )
        # add ot a list for suBSequent vrt creation
        outfiles.append(outfile)
        i += 1

    return outfiles
