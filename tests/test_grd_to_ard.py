import os
import numpy as np
import rasterio
from shapely.geometry import box
from tempfile import TemporaryDirectory

from ost.helpers.helpers import _zip_s1_safe_dir


def test_ost_grd_to_ard(
        ard_types,
        s1_grd_notnr_ost_product,
        s1_grd_notnr,
        some_bounds
):
    ard_type = ard_types[0]
    out_bounds = str(box(some_bounds[0], some_bounds[1], some_bounds[2], some_bounds[3]))
    with TemporaryDirectory(dir=os.getcwd()) as processing_dir, \
            TemporaryDirectory() as temp:
        scene_id, product = s1_grd_notnr_ost_product
        # Make Creodias-like paths
        download_path = os.path.join(processing_dir, 'SAR',
                                     product.product_type,
                                     product.year,
                                     product.month,
                                     product.day
                                     )
        os.makedirs(download_path, exist_ok=True)
        _zip_s1_safe_dir(os.path.dirname(s1_grd_notnr),
                         os.path.join(download_path, scene_id+'.zip.downloaded'),
                         scene_id
                         )
        _zip_s1_safe_dir(os.path.dirname(s1_grd_notnr),
                         os.path.join(download_path, scene_id+'.zip'),
                         scene_id
                         )
        product.set_ard_parameters(ard_type)
        try:
            out_files = product.create_ard(
                filelist=[product.get_path(processing_dir)],
                out_dir=processing_dir,
                out_prefix=scene_id+'_'+ard_type,
                temp_dir=temp,
                subset=out_bounds,
            )
        except Exception as e:
            raise e
        assert os.path.isfile(product.ard_dimap)
        for f in out_files:
            assert os.path.isfile(f)
        product.create_rgb(
            outfile=os.path.join(processing_dir, scene_id+'_'+ard_type+'.tif')
        )
        tif_path = product.ard_rgb
        with rasterio.open(tif_path, 'r') as out_tif:
            raster_sum = np.nansum(out_tif.read(1))
        assert raster_sum != 0


def test_ost_flat_grd_to_ard(
        ard_types,
        s1_grd_notnr_ost_product,
        s1_grd_notnr,
        some_bounds
):
    ard_type = ard_types[1]
    out_bounds = str(box(some_bounds[0], some_bounds[1], some_bounds[2], some_bounds[3]))
    with TemporaryDirectory(dir=os.getcwd()) as processing_dir, \
            TemporaryDirectory() as temp:
        scene_id, product = s1_grd_notnr_ost_product
        # Make Creodias-like paths
        download_path = os.path.join(processing_dir, 'SAR',
                                     product.product_type,
                                     product.year,
                                     product.month,
                                     product.day
                                     )
        os.makedirs(download_path, exist_ok=True)
        _zip_s1_safe_dir(os.path.dirname(s1_grd_notnr),
                         os.path.join(download_path, scene_id+'.zip.downloaded'),
                         scene_id
                         )
        _zip_s1_safe_dir(os.path.dirname(s1_grd_notnr),
                         os.path.join(download_path, scene_id+'.zip'),
                         scene_id
                         )

        product.set_ard_parameters(ard_type)
        try:
            out_files = product.create_ard(
                filelist=[product.get_path(processing_dir)],
                out_dir=processing_dir,
                out_prefix=scene_id+'_'+ard_type,
                temp_dir=temp,
                subset=out_bounds,
            )
        except Exception as e:
            raise e
        assert os.path.isfile(product.ard_dimap)
        for f in out_files:
            assert os.path.isfile(f)
        product.create_rgb(
            outfile=os.path.join(processing_dir, scene_id+'_'+ard_type+'.tif')
        )
        tif_path = product.ard_rgb
        with rasterio.open(tif_path, 'r') as out_tif:
            raster_sum = np.nansum(out_tif.read(1))
        assert raster_sum != 0


def test_ceos_grd_to_ard(
        ard_types,
        s1_grd_notnr_ost_product,
        s1_grd_notnr,
        some_bounds
):
    ard_type = ard_types[2]
    out_bounds = str(box(some_bounds[0], some_bounds[1], some_bounds[2], some_bounds[3]))
    with TemporaryDirectory(dir=os.getcwd()) as processing_dir, \
            TemporaryDirectory() as temp:
        scene_id, product = s1_grd_notnr_ost_product
        # Make Creodias-like paths
        download_path = os.path.join(processing_dir, 'SAR',
                                     product.product_type,
                                     product.year,
                                     product.month,
                                     product.day
                                     )
        os.makedirs(download_path, exist_ok=True)
        _zip_s1_safe_dir(os.path.dirname(s1_grd_notnr),
                        os.path.join(download_path, scene_id+'.zip.downloaded'),
                        scene_id
                        )
        _zip_s1_safe_dir(os.path.dirname(s1_grd_notnr),
                        os.path.join(download_path, scene_id+'.zip'),
                        scene_id
                        )

        product.set_ard_parameters(ard_type)
        try:
            out_files = product.create_ard(
                filelist=[product.get_path(processing_dir)],
                out_dir=processing_dir,
                out_prefix=scene_id+'_'+ard_type,
                temp_dir=temp,
                subset=out_bounds,
            )
        except Exception as e:
            raise e
        assert os.path.isfile(product.ard_dimap)
        for f in out_files:
            assert os.path.isfile(f)
        product.create_rgb(
            outfile=os.path.join(processing_dir, scene_id+'_'+ard_type+'.tif')
        )
        tif_path = product.ard_rgb
        with rasterio.open(tif_path, 'r') as out_tif:
            raster_sum = np.nansum(out_tif.read(1))
        assert raster_sum != 0


def test_earth_engine_grd_to_ard(
        ard_types,
        s1_grd_notnr_ost_product,
        s1_grd_notnr,
        some_bounds
):
    ard_type = ard_types[3]
    out_bounds = str(box(some_bounds[0], some_bounds[1], some_bounds[2], some_bounds[3]))
    with TemporaryDirectory(dir=os.getcwd()) as processing_dir, \
            TemporaryDirectory() as temp:
        scene_id, product = s1_grd_notnr_ost_product
        # Make Creodias-like paths
        download_path = os.path.join(processing_dir, 'SAR',
                                     product.product_type,
                                     product.year,
                                     product.month,
                                     product.day
                                     )
        os.makedirs(download_path, exist_ok=True)
        _zip_s1_safe_dir(os.path.dirname(s1_grd_notnr),
                        os.path.join(download_path, scene_id+'.zip.downloaded'),
                        scene_id
                        )
        _zip_s1_safe_dir(os.path.dirname(s1_grd_notnr),
                        os.path.join(download_path, scene_id+'.zip'),
                        scene_id
                        )

        product.set_ard_parameters(ard_type)
        try:
            out_files = product.create_ard(
                filelist=[product.get_path(processing_dir)],
                out_dir=processing_dir,
                out_prefix=scene_id+'_'+ard_type,
                temp_dir=temp,
                subset=out_bounds,
            )
        except Exception as e:
            raise e
        assert os.path.isfile(product.ard_dimap)
        for f in out_files:
            assert os.path.isfile(f)
        product.create_rgb(
            outfile=os.path.join(processing_dir, scene_id+'_'+ard_type+'.tif')
        )
        tif_path = product.ard_rgb
        with rasterio.open(tif_path, 'r') as out_tif:
            raster_sum = np.nansum(out_tif.read(1))
        assert raster_sum != 0


def test_zhuo_grd_to_ard(
        ard_types,
        s1_grd_notnr_ost_product,
        s1_grd_notnr,
        some_bounds
):
    ard_type = ard_types[4]
    out_bounds = str(box(some_bounds[0], some_bounds[1], some_bounds[2], some_bounds[3]))
    with TemporaryDirectory(dir=os.getcwd()) as processing_dir, \
            TemporaryDirectory() as temp:
        scene_id, product = s1_grd_notnr_ost_product
        # Make Creodias-like paths
        download_path = os.path.join(processing_dir, 'SAR',
                                     product.product_type,
                                     product.year,
                                     product.month,
                                     product.day
                                     )
        os.makedirs(download_path, exist_ok=True)
        _zip_s1_safe_dir(os.path.dirname(s1_grd_notnr),
                        os.path.join(download_path, scene_id+'.zip.downloaded'),
                        scene_id
                        )
        _zip_s1_safe_dir(os.path.dirname(s1_grd_notnr),
                        os.path.join(download_path, scene_id+'.zip'),
                        scene_id
                        )

        product.set_ard_parameters(ard_type)
        try:
            out_files = product.create_ard(
                filelist=[product.get_path(processing_dir)],
                out_dir=processing_dir,
                out_prefix=scene_id+'_'+ard_type,
                temp_dir=temp,
                subset=out_bounds,
            )
        except Exception as e:
            raise e
        assert os.path.isfile(product.ard_dimap)
        for f in out_files:
            assert os.path.isfile(f)
        product.create_rgb(
            outfile=os.path.join(processing_dir, scene_id+'_'+ard_type+'.tif')
        )
        tif_path = product.ard_rgb
        with rasterio.open(tif_path, 'r') as out_tif:
            raster_sum = np.nansum(out_tif.read(1))
        assert raster_sum != 0
