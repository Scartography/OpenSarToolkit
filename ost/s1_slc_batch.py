import glob
import logging


from os.path import join as opj
from datetime import datetime
from shapely.wkt import loads

from ost.helpers import raster as ras
from ost.s1 import burst
from ost.helpers import helpers as h

from ost.project import Sentinel1

logger = logging.getLogger(__name__)


class Sentinel1SLCBatch(Sentinel1):
    '''A Sentinel-1 specific subclass of the Generic OST class

    This subclass creates a Sentinel-1 specific
    '''

    def __init__(self,
                 project_dir,
                 aoi,
                 start='2014-10-01',
                 end=datetime.today().strftime("%Y-%m-%d"),
                 data_mount='/eodata',
                 mirror=2,
                 download_dir=None,
                 inventory_dir=None,
                 processing_dir=None,
                 temp_dir=None,
                 product_type='SLC',
                 beam_mode='IW',
                 polarisation='*',
                 ard_type='OST'
                 ):

        super().__init__(project_dir, aoi, start, end, data_mount, mirror,
                         download_dir, inventory_dir, processing_dir, temp_dir,
                         product_type, beam_mode, polarisation
                         )

        self.ard_type = ard_type
        self.ard_parameters = {}
        self.set_ard_parameters(self.ard_type)
        self.burst_inventory = None
        self.burst_inventory_file = None

    def burst_to_ard(self, timeseries=False, timescan=False, mosaic=False,
                     overwrite=False):

        if overwrite:
            logger.debug('INFO: Deleting processing folder to start from scratch')
            h.remove_folder_content(self.processing_dir)

        if not self.ard_parameters:
            self.set_ard_parameters()

        # set resolution in degree
        self.center_lat = loads(self.aoi).centroid.y
        if float(self.center_lat) > 59 or float(self.center_lat) < -59:
            logger.debug('INFO: Scene is outside SRTM coverage. Will use 30m ASTER'
                         'DEM instead.'
                         )
            self.ard_parameters['dem'] = 'ASTER 1sec GDEM'

        # set resolution to degree
        # self.ard_parameters['resolution'] = h.resolution_in_degree(
        #    self.center_lat, self.ard_parameters['resolution'])

        nr_of_processed = len(
            glob.glob(opj(self.processing_dir, '*', '*', '.processed')))

        # check and retry function
        i = 0
        while len(self.burst_inventory) > nr_of_processed:

            burst.burst_to_ard_batch(self.burst_inventory,
                                     self.download_dir,
                                     self.processing_dir,
                                     self.temp_dir,
                                     self.ard_parameters,
                                     self.data_mount)

            nr_of_processed = len(
                glob.glob(opj(self.processing_dir, '*', '*', '.processed')))

            i += 1

            # not more than 5 trys
            if i == 5:
                break

        # do we delete the downloads here?
        if timeseries or timescan:
            burst.burst_ards_to_timeseries(self.burst_inventory,
                                           self.processing_dir,
                                           self.temp_dir,
                                           self.ard_parameters)

            # do we deleete the single ARDs here?
            if timescan:
                burst.timeseries_to_timescan(self.burst_inventory,
                                             self.processing_dir,
                                             self.temp_dir,
                                             self.ard_parameters)

        if mosaic and timeseries:
            burst.mosaic_timeseries(self.burst_inventory,
                                    self.processing_dir,
                                    self.temp_dir,
                                    self.ard_parameters
                                    )

        if mosaic and timescan:
            burst.mosaic_timescan(self.burst_inventory,
                                  self.processing_dir,
                                  self.temp_dir,
                                  self.ard_parameters)

    def create_timeseries_animation(timeseries_dir, product_list, outfile,
                                    shrink_factor=1, duration=1,
                                    add_dates=False):

        ras.create_timeseries_animation(timeseries_dir,
                                        product_list,
                                        outfile,
                                        shrink_factor=1,
                                        duration=1,
                                        add_dates=False
                                        )