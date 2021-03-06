import os
import sys
import glob
import logging
import geopandas as gpd

from os.path import join as opj
from datetime import datetime
from shapely.wkt import loads

from ost.helpers.bursts import burst_inventory, refine_burst_inventory
from ost.s1_core import search, refine, s1_dl, batch
from ost.s1_core.batch import _to_ard_batch
from ost.s1_core.batch_burst import burst_to_ard_batch
from ost.helpers import scihub, utils as h, vector as vec
from ost.multitemporal.utils import create_timeseries_animation
from ost.settings import SNAP_S1_RESAMPLING_METHODS, ARD_TIMESCAN_METRICS

from ost.errors import EmptyInventoryException

logger = logging.getLogger(__name__)


class Generic():
    def __init__(self,
                 project_dir,
                 aoi,
                 start='1978-06-28',
                 end=datetime.today().strftime("%Y-%m-%d"),
                 data_mount=None,
                 download_dir=None,
                 inventory_dir=None,
                 processing_dir=None
                 ):
        self.project_dir = os.path.abspath(project_dir)
        self.start = start
        self.end = end
        self.data_mount = data_mount
        self.download_dir = download_dir
        self.inventory_dir = inventory_dir
        self.processing_dir = processing_dir

        # handle the import of different aoi formats and transform
        # to a WKT string
        if aoi.split('.')[-1] != 'shp'and len(aoi) == 3:
            # get lowres data
            world = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
            country = world.name[world.iso_a3 == aoi].values[0]
            logger.debug(
                'INFO: Getting the country boundaries from Geopandas low'
                'resolution data for {}'.format(country)
            )

            self.aoi = (world['geometry']
                        [world['iso_a3'] == aoi].values[0].to_wkt())
        elif aoi.split('.')[-1] == 'shp':
            self.aoi = str(vec.shp_to_wkt(aoi))
            logger.debug(
                'INFO: Using {} shapefile as Area of Interest definition.'
            )
        else:
            try:
                loads(str(aoi))
            except:
                logger.debug('ERROR: No valid OST AOI defintion.')
                sys.exit()
            else:
                self.aoi = aoi

        if not self.download_dir:
            self.download_dir = opj(project_dir, 'download')
        if not self.inventory_dir:
            self.inventory_dir = opj(project_dir, 'inventory')
        if not self.processing_dir:
            self.processing_dir = opj(project_dir, 'processing')

        self._create_project_dir()
        self._create_download_dir(self.download_dir)
        self._create_inventory_dir(self.inventory_dir)
        self._create_processing_dir(self.processing_dir)

    def _create_project_dir(self, if_not_empty=True):
        '''Creates the high-lvel project directory

        :param instance attribute project_dir

        :return None
        '''

        if os.path.isdir(self.project_dir):
            logging.warning('Project directory already exists.'
                            'No data has been deleted at this point but'
                            'make sure you really want to use this folder.'
                            )
        else:

            os.makedirs(self.project_dir, exist_ok=True)
            logging.info('Created project directory at {}'
                         .format(self.project_dir))

    def _create_download_dir(self, download_dir=None):
        '''Creates the high-level download directory

        :param instance attribute download_dir or
               default value (i.e. /path/to/project_dir/download)

        :return None
        '''

        if download_dir is None:
            self.download_dir = opj(self.project_dir, 'download')
        else:
            self.download_dir = download_dir

        os.makedirs(self.download_dir, exist_ok=True)
        logging.info('Downloaded data will be stored in:{}'
                     .format(self.download_dir))

    def _create_processing_dir(self, processing_dir=None):
        '''Creates the high-level processing directory

        :param instance attribute processing_dir or
               default value (i.e. /path/to/project_dir/processing)

        :return None
        '''

        if processing_dir is None:
            self.processing_dir = opj(self.project_dir, 'processing')
        else:
            self.processing_dir = processing_dir

        os.makedirs(self.processing_dir, exist_ok=True)
        logging.info('Processed data will be stored in: {}'
                     .format(self.processing_dir)
                     )

    def _create_inventory_dir(self, inventory_dir=None):
        '''Creates the high-level inventory directory

        :param instance attribute inventory_dir or
               default value (i.e. /path/to/project_dir/inventory)

        :return None
        '''

        if inventory_dir is None:
            self.inventory_dir = opj(self.project_dir, 'inventory')
        else:
            self.inventory_dir = inventory_dir

        os.makedirs(self.inventory_dir, exist_ok=True)
        logging.info('Inventory files will be stored in: {}'
                     .format(self.inventory_dir))


class Sentinel1(Generic):
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
                 metadata_concurency=1,
                 download_dir=None,
                 inventory_dir=None,
                 processing_dir=None,
                 product_type='*',
                 beam_mode='*',
                 polarisation='*'
                 ):

        super().__init__(project_dir, aoi, start, end, data_mount,
                         download_dir, inventory_dir, processing_dir
                         )

        self.product_type = product_type
        self.beam_mode = beam_mode
        self.polarisation = polarisation

        self.inventory = None
        self.inventory_file = None
        self.refined_inventory_dict = None
        self.coverages = None

        # Remote/Download options
        self.uname = None
        self.pword = None
        self.mirror = mirror
        self.metadata_concurency = metadata_concurency

    def search(
            self,
            outfile=None,
            append=False,
            uname=None,
            pword=None
    ):
        if self.uname is not None:
            uname = self.uname
        if self.pword is not None:
            pword = self.pword

        if outfile is None:
            outfile = opj(self.inventory_dir, 'full_inventory.shp')

        # create scihub conform aoi string
        aoi_str = scihub.create_aoi_str(self.aoi)

        # create scihub conform TOI
        toi_str = scihub.create_toi_str(self.start, self.end)

        # create scihub conform product specification
        product_specs_str = scihub.create_s1_product_specs(
                self.product_type, self.polarisation, self.beam_mode)

        # join the query
        query = scihub.create_query('Sentinel-1', aoi_str, toi_str,
                                    product_specs_str
                                    )
        if uname is None or pword is None:
            # ask for username and password
            self.uname, self.pword = scihub.ask_credentials()
        else:
            self.uname, self.pword = uname, pword

        # do the search
        self.inventory_file = opj(self.inventory_dir, outfile)
        search.scihub_catalogue(query,
                                self.inventory_file,
                                append,
                                self.uname,
                                self.pword
                                )
        
        # read inventory into the inventory attribute
        self.read_inventory()
        self.timeseries_dirs = [opj(self.processing_dir, track, 'Timeseries')
                                for track in self.inventory.relativeorbit.unique()
                                ]
        self.timescan_dirs = [opj(self.processing_dir, track, 'Timescan')
                              for track in self.inventory.relativeorbit.unique()
                              ]

    def read_inventory(self):
        '''Read the Sentinel-1 data inventory from a OST invetory shapefile

        :param

        '''

#       define column names of inventory file (since in shp they are truncated)
        column_names = ['id', 'identifier', 'polarisationmode',
                        'orbitdirection', 'acquisitiondate', 'relativeorbit',
                        'orbitnumber', 'product_type', 'slicenumber', 'size',
                        'beginposition', 'endposition',
                        'lastrelativeorbitnumber', 'lastorbitnumber',
                        'uuid', 'platformidentifier', 'missiondatatakeid',
                        'swathidentifier', 'ingestiondate',
                        'sensoroperationalmode', 'geometry'
                        ]

        geodataframe = gpd.read_file(self.inventory_file)
        geodataframe.columns = column_names
        
        # add download_path to inventory, so we can check if data needs to be 
        # downloaded
        self.inventory = search.check_availability(
            geodataframe, self.download_dir, self.data_mount)
        return self.inventory

    def download_size(self, inventory_df=None):
        if inventory_df:
            download_size = inventory_df[
                'size'].str.replace('GB', '').astype('float32').sum()
        else:
            download_size = self.inventory[
                'size'].str.replace('GB', '').astype('float32').sum()

        logger.debug(
            'INFO: There are about {} GB need to be downloaded.'.format(
                download_size
            )
        )

    def refine(self,
               exclude_marginal=True,
               full_aoi_crossing=True,
               mosaic_refine=True,
               area_reduce=0.05
               ):
        self.refined_inventory_dict, self.coverages = refine.search_refinement(
                                       self.aoi,
                                       self.inventory,
                                       self.inventory_dir,
                                       exclude_marginal=exclude_marginal,
                                       full_aoi_crossing=full_aoi_crossing,
                                       mosaic_refine=mosaic_refine,
                                       area_reduce=area_reduce
        )

        # summing up information
        logger.debug('--------------------------------------------')
        logger.debug('Summing up the info about mosaics')
        logger.debug('--------------------------------------------')
        for key in self.refined_inventory_dict:
            logger.debug('')
            logger.debug('{} mosaics for mosaic key {}'.format(self.coverages[key], key)
                         )

    def download(
            self,
            mirror=None,
            concurrent=2,
            uname=None,
            pword=None
    ):
        if self.metadata_concurency > 1:
            concurrent = self.metadata_concurency
        # if an old inventory exists drop download_path
        if 'download_path' in self.inventory:
            self.inventory.drop('download_path', axis=1)
        if self.inventory.empty:
            raise EmptyInventoryException(
                'Run search before downloading or processing!'
            )
        # check if scenes exist
        inventory_df = search.check_availability(
            self.inventory, self.download_dir, self.data_mount
        )
        
        # extract only those scenes that need to be downloaded
        download_df = inventory_df[inventory_df.download_path.isnull()]

        # to download or not ot download - that is here the question
        if not download_df.any().any():
            self.missing_scenes = []
            logger.debug('INFO: All scenes are ready for being processed.')    
        else:
            logger.debug(
                'INFO: One or more of your scenes need to be downloaded.'
            )
            self.download_dir, self.missing_scenes = s1_dl.download_sentinel1(
                download_df,
                self.download_dir,
                mirror=mirror,
                concurrent=concurrent,
                uname=uname,
                pword=pword
            )
            for id in inventory_df.identifier:
                for missing in self.missing_scenes:
                    if id.lower() in missing.lower():
                        self.inventory = inventory_df[
                            inventory_df.identifier != id
                        ]
        return self

    def plot_inventory(self, inventory_df=None, transperancy=0.05, show=False):
        if inventory_df is None:
            vec.plot_inventory(self.aoi, self.inventory, transperancy, show)
        else:
            vec.plot_inventory(self.aoi, inventory_df, transperancy, show)


class Sentinel1Batch(Sentinel1):
    def __init__(self,
                 project_dir,
                 aoi,
                 start='2014-10-01',
                 end=datetime.today().strftime("%Y-%m-%d"),
                 data_mount='/eodata',
                 mirror=2,
                 metadata_concurency=1,
                 download_dir=None,
                 inventory_dir=None,
                 processing_dir=None,
                 product_type='SLC',
                 beam_mode='IW',
                 polarisation='*',
                 track='*',
                 ard_type='OST',
                 max_workers=os.cpu_count()
                 ):

        super().__init__(project_dir, aoi, start, end, data_mount, mirror,
                         metadata_concurency, download_dir, inventory_dir,
                         processing_dir, product_type, beam_mode, polarisation
                         )
        self.max_workers = max_workers

        self.ard_type = ard_type
        self.ard_parameters = {}
        self.set_ard_parameters(ard_type)

        self.animations_dir = opj(self.processing_dir, 'Animations')

    # processing related functions
    def to_ard(self, subset=None, overwrite=False):
        logger.debug(
            'INFO: Starting %s ARD processing for %s',
            self.ard_parameters['type'], self.product_type
        )

        if overwrite:
            logger.debug(
                'INFO: Deleting processing folder to start from scratch'
            )
            h.remove_folder_content(self.processing_dir)

        if not self.ard_parameters:
            self.set_ard_parameters()
        if self.inventory.empty:
            raise EmptyInventoryException(
                'Run search before downloading and processing!'
            )
        # set resolution in degree
        self.center_lat = loads(self.aoi).centroid.y
        if float(self.center_lat) > 59 or float(self.center_lat) < -59:
            logger.debug('INFO: Scene is outside SRTM coverage. '
                         'Will use 30m ASTER DEM instead.'
                         )
            self.ard_parameters['dem'] = 'ASTER 1sec GDEM'

        if subset:
            if subset.split('.')[-1] == '.shp':
                subset = str(vec.shp_to_wkt(subset, buffer=0.1, envelope=True))
            elif subset.startswith('POLYGON (('):
                subset = loads(subset).buffer(0.1).to_wkt()
            elif subset.geom_type == 'MultiPolygon' \
                    or subset.geom_type == 'Polygon':
                subset = subset.wkt
            else:
                logger.debug('ERROR: No valid subset given.'
                             'Should be either path to a shapefile '
                             'or a WKT Polygon.'
                             )
                sys.exit()
        if self.product_type == 'GRD':
            _to_ard_batch(
                self.inventory,
                self.download_dir,
                self.processing_dir,
                self.ard_parameters,
                subset
            )
        elif self.product_type == 'SLC' and not self.burst_inventory.empty:
            burst_to_ard_batch(
                burst_inventory=self.burst_inventory,
                download_dir=self.download_dir,
                processing_dir=self.processing_dir,
                ard_parameters=self.ard_parameters,
                data_mount=self.data_mount,
                max_workers=self.max_workers
            )
        logger.debug(
                'INFO:%s ARD processing for %s DONE!',
                self.ard_parameters['type'], self.product_type
            )

    def create_timeseries(self):
        nr_of_processed = len(
            glob.glob(opj(self.processing_dir, '*', 'Timeseries', '.processed'))
        )
        # nr_of_tracks = inventory_df.relativeorbit.unique().values
        # check and retry function
        i = 0
        while len(self.inventory.relativeorbit.unique()) > nr_of_processed:
            batch.ards_to_timeseries(self.inventory,
                                     self.processing_dir,
                                     self.ard_parameters
                                     )
            nr_of_processed = len(
                glob.glob(opj(self.processing_dir, '*',
                              'Timeseries', '.processed'))
            )
            i += 1
            # not more than 5 trys
            if i == 5:
                break

    def create_timescan(self):
        nr_of_processed = len(
            glob.glob(opj(
                self.processing_dir, '*', 'Timescan', '.processed')
            )
        )
        i = 0
        while len(self.inventory.relativeorbit.unique()) > nr_of_processed:
            batch.timeseries_to_timescan(
                self.inventory,
                self.processing_dir,
                self.ard_parameters
            )
            nr_of_processed = len(glob.glob(opj(
                self.processing_dir, '*', 'Timescan', '.processed')))
            i += 1

            # not more than 5 trys
            if i == 5:
                break

    def create_mosaic(self, subset):
        if subset is None:
            batch.mosaic_timeseries(
                self.inventory,
                self.processing_dir,
            )
        else:
            batch.mosaic_timeseries(
                self.inventory,
                self.processing_dir,
            )

    def create_burst_inventory(self,
                               key=None,
                               refine=True,
                               uname=None,
                               pword=None
                               ):
        if self.product_type != 'SLC':
            raise TypeError('Product needs to be SLC!')
        if self.uname is not None:
            uname = self.uname
        if self.pword is not None:
            pword = self.pword

        if key:
            outfile = opj(self.inventory_dir,
                          'bursts.{}.shp').format(key)
            self.burst_inventory = burst_inventory(
                self.refined_inventory_dict[key],
                outfile,
                download_dir=self.download_dir,
                data_mount=self.data_mount,
                uname=uname, pword=pword)
        else:
            outfile = opj(self.inventory_dir,
                          'bursts.full.shp'
                          )

            self.burst_inventory = burst_inventory(
                self.inventory,
                outfile,
                download_dir=self.download_dir,
                data_mount=self.data_mount,
                uname=uname,
                pword=pword
            )

        if refine:
            # logger.debug('{}.refined.shp'.format(outfile[:-4]))
            self.burst_inventory = refine_burst_inventory(
                self.aoi, self.burst_inventory,
                '{}.refined.shp'.format(outfile[:-4])
            )
        return self

    def create_timeseries_animations(self,
                                     shrink_factor=5,
                                     duration=1,
                                     add_dates=False
                                     ):
        for ts_dir in self.timeseries_dirs:
            create_timeseries_animation(
                track_ts_folder=ts_dir,
                product_list=['TC.VV', 'TC.VH'],
                out_folder=self.animations_dir,
                shrink_factor=shrink_factor,
                duration=duration,
                add_dates=add_dates
            )

    def read_burst_inventory(self, key):
        '''Read the Sentinel-1 data inventory from a OST inventory shapefile

        :param

        '''
        if self.product_type != 'SLC':
            raise TypeError('Product needs to be SLC!')

        if key:
            file = opj(self.inventory_dir, 'burst_inventory.{}.shp').format(
                key)
        else:
            file = opj(self.inventory_dir, 'burst_inventory.shp')

        # define column names of file (since in shp they are truncated)
        # create column names for empty data frame
        column_names = [
            'SceneID',
            'Track',
            'Direction',
            'Date',
            'SwathID',
            'AnxTime',
            'BurstNr',
            'geometry'
        ]

        geodataframe = gpd.read_file(file)
        geodataframe.columns = column_names
        geodataframe['Date'] = geodataframe['Date'].astype(int)
        geodataframe['BurstNr'] = geodataframe['BurstNr'].astype(int)
        geodataframe['AnxTime'] = geodataframe['AnxTime'].astype(int)
        geodataframe['Track'] = geodataframe['Track'].astype(int)
        self.burst_inventory = geodataframe
        return geodataframe

    def set_ard_parameters(self, ard_type='OST'):
        if ard_type == 'OST':
            self.ard_parameters['type'] = ard_type
            self.ard_parameters['resolution'] = 20
            self.ard_parameters['border_noise'] = True
            self.ard_parameters['product_type'] = 'GTCgamma'
            self.ard_parameters['speckle_filter'] = False
            self.ard_parameters['ls_mask_create'] = False
            self.ard_parameters['to_db'] = False
            self.ard_parameters['polarisation'] = 'VV,VH,HH,HV'
            self.ard_parameters['dem'] = 'SRTM 1Sec HGT'
            self.ard_parameters['resampling'] = SNAP_S1_RESAMPLING_METHODS[2]
            # time-series specific
            self.ard_parameters['mt_speckle_filter'] = True
            self.ard_parameters['to_db_mt'] = True
            self.ard_parameters['dtype_output'] = 'float32'
            self.ard_parameters['apply_ls_mask'] = False
            self.ard_parameters['create_ls_mask'] = False
            # timescan specific
            self.ard_parameters['metrics'] = ARD_TIMESCAN_METRICS
            self.ard_parameters['remove_outliers'] = True
        elif ard_type == 'OST_flat':
            self.ard_parameters['type'] = ard_type
            self.ard_parameters['resolution'] = 20
            self.ard_parameters['border_noise'] = True
            self.ard_parameters['product_type'] = 'RTC'
            self.ard_parameters['speckle_filter'] = False
            self.ard_parameters['ls_mask_create'] = True
            self.ard_parameters['to_db'] = False
            self.ard_parameters['polarisation'] = 'VV,VH,HH,HV'
            self.ard_parameters['dem'] = 'SRTM 1Sec HGT'
            self.ard_parameters['resampling'] = SNAP_S1_RESAMPLING_METHODS[2]
            # time-series specific
            self.ard_parameters['mt_speckle_filter'] = True
            self.ard_parameters['to_db_mt'] = True
            self.ard_parameters['dtype_output'] = 'float32'
            self.ard_parameters['apply_ls_mask'] = False
            self.ard_parameters['create_ls_mask'] = False
            # timescan specific
            self.ard_parameters['metrics'] = ARD_TIMESCAN_METRICS
            self.ard_parameters['remove_outliers'] = True
        elif ard_type == 'CEOS':
            self.ard_parameters['type'] = ard_type
            self.ard_parameters['resolution'] = 10
            self.ard_parameters['border_noise'] = True
            self.ard_parameters['product_type'] = 'RTC'
            self.ard_parameters['speckle_filter'] = False
            self.ard_parameters['ls_mask_create'] = False
            self.ard_parameters['to_db'] = False
            self.ard_parameters['polarisation'] = 'VV,VH,HH,HV'
            self.ard_parameters['dem'] = 'SRTM 1Sec HGT'
            self.ard_parameters['resampling'] = SNAP_S1_RESAMPLING_METHODS[3]
            # time-series specific
            self.ard_parameters['mt_speckle_filter'] = False
            self.ard_parameters['to_db_mt'] = False
            self.ard_parameters['dtype_output'] = 'float32'
            self.ard_parameters['apply_ls_mask'] = False
            self.ard_parameters['create_ls_mask'] = False
            # timescan specific
            self.ard_parameters['metrics'] = ARD_TIMESCAN_METRICS
            self.ard_parameters['remove_outliers'] = False
        elif ard_type == 'EarthEngine':
            self.ard_parameters['type'] = ard_type
            self.ard_parameters['resolution'] = 10
            self.ard_parameters['border_noise'] = True
            self.ard_parameters['product_type'] = 'GTCsigma'
            self.ard_parameters['speckle_filter'] = False
            self.ard_parameters['ls_mask_create'] = False
            self.ard_parameters['to_db'] = True
            self.ard_parameters['polarisation'] = 'VV,VH,HH,HV'
            self.ard_parameters['dem'] = 'SRTM 1Sec HGT'
            self.ard_parameters['resampling'] = SNAP_S1_RESAMPLING_METHODS[3]
            # time-series specific
            self.ard_parameters['mt_speckle_filter'] = False
            self.ard_parameters['to_db_mt'] = False
            self.ard_parameters['dtype_output'] = 'float32'
            self.ard_parameters['apply_ls_mask'] = False
            # timescan specific
            self.ard_parameters['metrics'] = ARD_TIMESCAN_METRICS
            self.ard_parameters['remove_outliers'] = False
        elif ard_type == 'Zhuo':
            self.ard_parameters['type'] = ard_type
            self.ard_parameters['resolution'] = 25
            self.ard_parameters['border_noise'] = False
            self.ard_parameters['product_type'] = 'RTC'
            self.ard_parameters['speckle_filter'] = True
            self.ard_parameters['ls_mask_create'] = True
            self.ard_parameters['to_db'] = True
            self.ard_parameters['dem'] = 'SRTM 1Sec HGT'
            self.ard_parameters['resampling'] = SNAP_S1_RESAMPLING_METHODS[2]
            # time-series specific
            self.ard_parameters['mt_speckle_filter'] = False
            self.ard_parameters['to_db_mt'] = False
            self.ard_parameters['dtype_output'] = 'float32'
            self.ard_parameters['apply_ls_mask'] = False
            self.ard_parameters['create_ls_mask'] = False
            # timescan specific
            self.ard_parameters['metrics'] = ARD_TIMESCAN_METRICS
            self.ard_parameters['remove_outliers'] = False
