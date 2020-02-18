import os
import logging
import pytest
from os.path import join as opj
from shapely.geometry import box
from tempfile import TemporaryDirectory
from ost.project import Sentinel1 as Sen1, Sentinel1Batch as SenBatch

from ost.settings import HERBERT_USER

logger = logging.getLogger(__name__)


def test_sentinel_generic_class(some_bounds):
    with TemporaryDirectory(dir=os.getcwd()) as temp, \
            TemporaryDirectory(dir=os.getcwd()) as dl_temp, \
            TemporaryDirectory(dir=os.getcwd()) as inv_temp:

        sen1 = Sen1(
             project_dir=temp,
             aoi=box(some_bounds[0], some_bounds[1], some_bounds[2], some_bounds[3]).wkt,
             start='2020-01-01',
             end='2020-01-04',
             data_mount='/eodata',
             download_dir=dl_temp,
             mirror=2,
             inventory_dir=inv_temp,
             processing_dir=temp,
             product_type='GRD',
             beam_mode='IW',
             polarisation='VV,VH'
             )
        sen1.search(outfile=opj(inv_temp, 'inventory.shp'),
                    append=False,
                    uname=HERBERT_USER['uname'],
                    pword=HERBERT_USER['pword']
                    )
        sen1.refine(
            exclude_marginal=True,
            full_aoi_crossing=True,
            mosaic_refine=True,
            area_reduce=0.05
        )
        assert 2 == len(sen1.inventory)
        sen1.plot_inventory(show=False)
        del sen1


def test_sentinel1_grd_batch(some_bounds):
    with TemporaryDirectory(dir=os.getcwd()) as temp, \
            TemporaryDirectory(dir=os.getcwd()) as dl_temp, \
            TemporaryDirectory(dir=os.getcwd()) as inv_temp:
        sen1 = SenBatch(
            project_dir=temp,
            aoi=box(some_bounds[0], some_bounds[1], some_bounds[2], some_bounds[3]).wkt,
            start='2020-01-01',
            end='2020-01-04',
            data_mount='/eodata',
            download_dir=dl_temp,
            mirror=2,
            inventory_dir=inv_temp,
            processing_dir=temp,
            product_type='GRD',
            beam_mode='IW',
            polarisation='VV,VH',
            ard_type='OST'
            )
        sen1.search(outfile=opj(inv_temp, 'inventory.shp'),
                    append=False,
                    uname=HERBERT_USER['uname'],
                    pword=HERBERT_USER['pword']
                    )

        sen1.download(mirror=sen1.mirror,
                      concurrent=sen1.metadata_concurency,
                      uname=HERBERT_USER['uname'],
                      pword=HERBERT_USER['asf_pword']
                      )
        sen1.to_ard(
            subset=box(
                some_bounds[0], some_bounds[1], some_bounds[2], some_bounds[3]
            ).wkt,
            overwrite=True
        )
        sen1.create_timeseries()
        sen1.create_timescan()
        sen1.create_timeseries_animations()


@pytest.mark.skip(reason="Download is tested in the batch!")
def test_sentinel_generic_download(some_bounds):
    with TemporaryDirectory() as temp, \
            TemporaryDirectory() as dl_temp, \
            TemporaryDirectory() as inv_temp:

        sen1 = Sen1(
            project_dir=temp,
            aoi=box(some_bounds[0], some_bounds[1], some_bounds[2], some_bounds[3]).wkt,
            start='2020-01-01',
            end='2020-01-04',
            data_mount='/eodata',
            download_dir=dl_temp,
            mirror=2,
            inventory_dir=inv_temp,
            processing_dir=temp,
            product_type='GRD',
            beam_mode='IW',
            polarisation='VV,VH'
        )
        sen1.search(outfile=opj(inv_temp, 'inventory.shp'),
                    append=False,
                    uname=HERBERT_USER['uname'],
                    pword=HERBERT_USER['pword']
                    )
        sen1.download(mirror=sen1.mirror,
                      concurrent=sen1.metadata_concurency,
                      uname=HERBERT_USER['uname'],
                      pword=HERBERT_USER['asf_pword']
                      )
