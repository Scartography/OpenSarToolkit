import os
import numpy as np
import rasterio
from shapely.geometry import box
from tempfile import TemporaryDirectory

from godale import Executor

from ost.helpers.utils import _product_zip_to_processing_dir


def test_slc_to_ard(
    ard_types,
    s1_slc_master,
    s1_slc_ost_master,
    some_bounds_slc
):
    max_workers = int(os.cpu_count()/4)
    executor_type = 'concurrent_processes'
    executor = Executor(executor=executor_type,
                        max_workers=max_workers
                        )
    for task in executor.as_completed(
            func=_execute_slc_test,
            iterable=ard_types,
            fargs=(s1_slc_master,
                   s1_slc_ost_master,
                   some_bounds_slc,
                   )

    ):
        task.result()


def _execute_slc_test(
        ard_type,
        s1_slc_master,
        s1_slc_ost_master,
        some_bounds_slc
):
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
