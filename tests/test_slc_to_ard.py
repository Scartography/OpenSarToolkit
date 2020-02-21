import os
import pytest
import numpy as np
import rasterio
import shutil
from shapely.geometry import box
from tempfile import TemporaryDirectory

from ost.s1_to_ard.burst_to_ard import burst_to_ard
from ost.errors import GPTRuntimeError
from ost.helpers.utils import _product_zip_to_processing_dir


def test_ost_slc_to_ard(
        ard_types,
        s1_slc_master,
        s1_slc_ost_master,
        some_bounds_slc
):
    ard_type = ard_types[0]
    out_bounds = str(box(some_bounds_slc[0],
                         some_bounds_slc[1],
                         some_bounds_slc[2],
                         some_bounds_slc[3])
                     )
    with TemporaryDirectory(dir=os.getcwd()) as processing_dir, \
            TemporaryDirectory() as temp:
        scene_id, product = s1_slc_ost_master
        # Make Creodias-like paths
        download_path = os.path.join(processing_dir, 'SAR',
                                     product.product_type,
                                     product.year,
                                     product.month,
                                     product.day
                                     )
        os.makedirs(download_path, exist_ok=True)
        _product_zip_to_processing_dir(
            processing_dir=processing_dir,
            product=product,
            product_path=s1_slc_master
        )
        product.set_ard_parameters(ard_type)
        product.ard_parameters['resolution'] = 50
        try:
            out_files = product.create_ard(
                filelist=product.get_path(processing_dir),
                out_dir=processing_dir,
                out_prefix=scene_id+'_'+ard_type,
                temp_dir=temp,
                subset=out_bounds,
            )
        except Exception as e:
            raise e
        for f in out_files:
            assert os.path.isfile(f)
        product.create_rgb(
            outfile=os.path.join(processing_dir, scene_id+'_'+ard_type+'.tif')
        )
        tif_path = product.ard_rgb
        with rasterio.open(tif_path, 'r') as out_tif:
            raster_sum = np.nansum(out_tif.read(1))
        assert raster_sum != 0


def test_ost_flat_slc_to_ard(
        ard_types,
        s1_slc_master,
        s1_slc_ost_master,
        some_bounds_slc
):
    ard_type = ard_types[1]
    out_bounds = str(box(some_bounds_slc[0],
                         some_bounds_slc[1],
                         some_bounds_slc[2],
                         some_bounds_slc[3])
                     )
    with TemporaryDirectory(dir=os.getcwd()) as processing_dir, \
            TemporaryDirectory() as temp:
        scene_id, product = s1_slc_ost_master
        # Make Creodias-like paths
        download_path = os.path.join(processing_dir, 'SAR',
                                     product.product_type,
                                     product.year,
                                     product.month,
                                     product.day
                                     )
        os.makedirs(download_path, exist_ok=True)
        _product_zip_to_processing_dir(
            processing_dir=processing_dir,
            product=product,
            product_path=s1_slc_master
        )
        product.set_ard_parameters(ard_type)
        product.ard_parameters['resolution'] = 50
        try:
            out_files = product.create_ard(
                filelist=product.get_path(processing_dir),
                out_dir=processing_dir,
                out_prefix=scene_id+'_'+ard_type,
                temp_dir=temp,
                subset=out_bounds,
            )
        except Exception as e:
            raise e
        for f in out_files:
            assert os.path.isfile(f)
        product.create_rgb(
            outfile=os.path.join(processing_dir, scene_id+'_'+ard_type+'.tif')
        )
        tif_path = product.ard_rgb
        with rasterio.open(tif_path, 'r') as out_tif:
            raster_sum = np.nansum(out_tif.read(1))
        assert raster_sum != 0


def test_ceos_slc_to_ard(
        ard_types,
        s1_slc_master,
        s1_slc_ost_master,
        some_bounds_slc
):
    ard_type = ard_types[2]
    out_bounds = str(box(some_bounds_slc[0],
                         some_bounds_slc[1],
                         some_bounds_slc[2],
                         some_bounds_slc[3])
                     )
    with TemporaryDirectory(dir=os.getcwd()) as processing_dir, \
            TemporaryDirectory() as temp:
        scene_id, product = s1_slc_ost_master
        # Make Creodias-like paths
        download_path = os.path.join(processing_dir, 'SAR',
                                     product.product_type,
                                     product.year,
                                     product.month,
                                     product.day
                                     )
        os.makedirs(download_path, exist_ok=True)
        _product_zip_to_processing_dir(
            processing_dir=processing_dir,
            product=product,
            product_path=s1_slc_master
        )
        product.set_ard_parameters(ard_type)
        product.ard_parameters['resolution'] = 50
        try:
            out_files = product.create_ard(
                filelist=product.get_path(processing_dir),
                out_dir=processing_dir,
                out_prefix=scene_id+'_'+ard_type,
                temp_dir=temp,
                subset=out_bounds,
            )
        except Exception as e:
            raise e
        for f in out_files:
            assert os.path.isfile(f)
        product.create_rgb(
            outfile=os.path.join(processing_dir, scene_id+'_'+ard_type+'.tif')
        )
        tif_path = product.ard_rgb
        with rasterio.open(tif_path, 'r') as out_tif:
            raster_sum = np.nansum(out_tif.read(1))
        assert raster_sum != 0


def test_earth_engine_slc_to_ard(
        ard_types,
        s1_slc_master,
        s1_slc_ost_master,
        some_bounds_slc
):
    ard_type = ard_types[3]
    out_bounds = str(box(some_bounds_slc[0],
                         some_bounds_slc[1],
                         some_bounds_slc[2],
                         some_bounds_slc[3])
                     )
    with TemporaryDirectory(dir=os.getcwd()) as processing_dir, \
            TemporaryDirectory() as temp:
        scene_id, product = s1_slc_ost_master
        # Make Creodias-like paths
        download_path = os.path.join(processing_dir, 'SAR',
                                     product.product_type,
                                     product.year,
                                     product.month,
                                     product.day
                                     )
        os.makedirs(download_path, exist_ok=True)
        _product_zip_to_processing_dir(
            processing_dir=processing_dir,
            product=product,
            product_path=s1_slc_master
        )
        product.set_ard_parameters(ard_type)
        product.ard_parameters['resolution'] = 50
        try:
            out_files = product.create_ard(
                filelist=product.get_path(processing_dir),
                out_dir=processing_dir,
                out_prefix=scene_id+'_'+ard_type,
                temp_dir=temp,
                subset=out_bounds,
            )
        except Exception as e:
            raise e
        for f in out_files:
            assert os.path.isfile(f)
        product.create_rgb(
            outfile=os.path.join(processing_dir, scene_id+'_'+ard_type+'.tif')
        )
        tif_path = product.ard_rgb
        with rasterio.open(tif_path, 'r') as out_tif:
            raster_sum = np.nansum(out_tif.read(1))
        assert raster_sum != 0


def test_zhuo_slc_to_ard(
        ard_types,
        s1_slc_master,
        s1_slc_ost_master,
        some_bounds_slc
):
    ard_type = ard_types[4]
    out_bounds = str(box(some_bounds_slc[0],
                         some_bounds_slc[1],
                         some_bounds_slc[2],
                         some_bounds_slc[3])
                     )
    with TemporaryDirectory(dir=os.getcwd()) as processing_dir, \
            TemporaryDirectory() as temp:
        scene_id, product = s1_slc_ost_master
        # Make Creodias-like paths
        download_path = os.path.join(processing_dir, 'SAR',
                                     product.product_type,
                                     product.year,
                                     product.month,
                                     product.day
                                     )
        os.makedirs(download_path, exist_ok=True)
        _product_zip_to_processing_dir(
            processing_dir=processing_dir,
            product=product,
            product_path=s1_slc_master
        )
        product.set_ard_parameters(ard_type)
        product.ard_parameters['resolution'] = 50
        try:
            out_files = product.create_ard(
                filelist=product.get_path(processing_dir),
                out_dir=processing_dir,
                out_prefix=scene_id+'_'+ard_type,
                temp_dir=temp,
                subset=out_bounds,
            )
        except Exception as e:
            raise e
        for f in out_files:
            assert os.path.isfile(f)
        product.create_rgb(
            outfile=os.path.join(processing_dir, scene_id+'_'+ard_type+'.tif')
        )
        tif_path = product.ard_rgb
        with rasterio.open(tif_path, 'r') as out_tif:
            raster_sum = np.nansum(out_tif.read(1))
        assert raster_sum != 0


@pytest.mark.skipif("TRAVIS" in os.environ and os.environ["TRAVIS"] == "true",
                    reason="Skipping this test on Travis CI."
                    )
def test_burst_to_ard(
        s1_slc_master,
        s1_slc_ost_master,
        s1_slc_slave,
        s1_slc_ost_slave,
        some_bounds_slc
):
    out_bounds = box(some_bounds_slc[0],
                     some_bounds_slc[1],
                     some_bounds_slc[2],
                     some_bounds_slc[3]
                     )
    with TemporaryDirectory(dir=os.getcwd()) as processing_dir, \
            TemporaryDirectory() as temp:

        # Make Creodias paths
        scene_id, product = s1_slc_ost_master
        slave_id, slave = s1_slc_ost_slave

        download_path = os.path.join(processing_dir, 'SAR',
                                     product.product_type,
                                     product.year,
                                     product.month,
                                     product.day
                                     )
        slave_dl_path = os.path.join(processing_dir, 'SAR',
                                     slave.product_type,
                                     slave.year,
                                     slave.month,
                                     slave.day
                                     )
        os.makedirs(download_path, exist_ok=True)
        os.makedirs(slave_dl_path, exist_ok=True)

        if not os.path.exists(
                os.path.join(download_path, os.path.basename(s1_slc_master))
        ):
            shutil.copy(s1_slc_master, download_path)
            with open(
                    os.path.join(
                        download_path, os.path.basename(s1_slc_master)
                    )+'.downloaded', 'w'
            ) as zip_dl:
                zip_dl.write('1')
        if not os.path.exists(
                os.path.join(slave_dl_path, os.path.basename(s1_slc_slave))
        ):
            shutil.copy(s1_slc_slave, slave_dl_path)
            with open(
                    os.path.join(
                        slave_dl_path, os.path.basename(s1_slc_slave)
                    )+'.downloaded', 'w'
            ) as zip_dl:
                zip_dl.write('1')

        bursts = product._zip_annotation_get(download_dir=processing_dir)
        slave_bursts = slave._zip_annotation_get(download_dir=processing_dir)

        # Get relevant bursts for AOI (bounds_wkt)
        bursts_dict = {'IW1': [], 'IW2': [], 'IW3': []}
        for subswath, nr, id, b in zip(
                bursts['SwathID'],
                bursts['BurstNr'],
                bursts['AnxTime'],
                bursts['geometry']
        ):
            for sl_subswath, sl_nr, sl_id, sl_b in zip(
                    slave_bursts['SwathID'],
                    slave_bursts['BurstNr'],
                    slave_bursts['AnxTime'],
                    slave_bursts['geometry']
            ):
                if b.intersects(sl_b) \
                        and b.intersects(out_bounds) \
                        and sl_b.intersects(out_bounds):
                    if subswath == sl_subswath and \
                            (nr, id, sl_nr, sl_id) not in bursts_dict[subswath]:
                        b_bounds = b.union(sl_b).bounds
                        burst_buffer = abs(some_bounds_slc[2]-some_bounds_slc[0])/75
                        burst_bbox = box(
                            b_bounds[0], b_bounds[1], b_bounds[2], b_bounds[3]
                        ).buffer(burst_buffer).envelope
                        bursts_dict[subswath].append(
                            (nr, id, sl_nr, sl_id, burst_bbox)
                        )

        for swath, b in bursts_dict.items():
            if b != []:
                for burst in b:
                    # Master burst number, master burst ID,
                    # slave burst nr, slave_burst ID,
                    # bouding box of both bursts
                    m_nr, m_burst_id, sl_burst_nr, sl_burst_id, b_bbox = burst
                    out_prefix = product.start_date+'_'+slave.start_date
                    return_code = burst_to_ard(
                        master_file=s1_slc_master,
                        swath=swath,
                        master_burst_nr=m_nr,
                        master_burst_id=str(m_burst_id),
                        master_burst_poly=b_bbox,
                        out_dir=processing_dir,
                        out_prefix=out_prefix,
                        temp_dir=temp,
                        polarimetry=False,
                        pol_speckle_filter=False,
                        resolution=50,
                        product_type='GTCgamma',
                        speckle_filter=False,
                        to_db=False,
                        ls_mask_create=False,
                        dem='SRTM 1sec HGT',
                    )
                    if return_code != 0:
                        raise GPTRuntimeError
                    assert return_code == 0
