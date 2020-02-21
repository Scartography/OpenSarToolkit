import os
import pytest
from datetime import timedelta
from tempfile import TemporaryDirectory

from shapely.geometry import box

from ost.s1_core.s1scenes import Sentinel1Scenes as S1Scenes
from ost.s1_core.s1scene import Sentinel1Scene as S1Scene


def test_s1_scenes(s1_slc_master,
                   s1_slc_slave,
                   s1_slc_ost_master,
                   s1_slc_ost_slave
                   ):
    filelist = [s1_slc_master, s1_slc_slave]
    with TemporaryDirectory(dir=os.getcwd()) as temp:
        s1_scenes = S1Scenes(filelist,
                             processing_dir=temp,
                             ard_type=None,
                             cleanup=False
                             )
        master = s1_scenes.master
        slaves = s1_scenes.slaves
        assert isinstance(master, S1Scene)
        for slave in slaves:
            assert isinstance(slave, S1Scene)

        # Test bi-weekly products pairing
        process_scenes = s1_scenes.get_biweekly_pairs()
        start = process_scenes[0][0].timestamp
        end = process_scenes[0][1].timestamp
        dif = end-start
        control_dif = timedelta(days=11, hours=23, minutes=59, seconds=59)
        assert dif == control_dif

        product_list = [s1_slc_ost_master[1], s1_slc_ost_slave[1]]
        with TemporaryDirectory(dir=os.getcwd()) as temp:
            s1_scenes = S1Scenes(product_list,
                                 processing_dir=temp,
                                 ard_type=None,
                                 cleanup=False
                                 )
            master = s1_scenes.master
            slaves = s1_scenes.slaves
            assert isinstance(master, S1Scene)
            for slave in slaves:
                assert isinstance(slave, S1Scene)

            # Test bi-weekly products pairing
            process_scenes = s1_scenes.get_biweekly_pairs()
            start = process_scenes[0][0].timestamp
            end = process_scenes[0][1].timestamp
            dif = end-start
            control_dif = timedelta(days=11, hours=23, minutes=59, seconds=59)
            assert dif == control_dif


@pytest.mark.skipif("TRAVIS" in os.environ and os.environ["TRAVIS"] == "true",
                    reason="Skipping this test on Travis CI."
                    )
def test_create_stack(s1_grd_notnr):
    filelist = [s1_grd_notnr, s1_grd_notnr]
    with TemporaryDirectory(dir=os.getcwd()) as temp:
        s1_scenes = S1Scenes(filelist,
                             processing_dir=temp,
                             ard_type=None,
                             cleanup=False
                             )
        out_stack = s1_scenes.create_grd_stack()


@pytest.mark.skipif("TRAVIS" in os.environ and os.environ["TRAVIS"] == "true",
                    reason="Skipping this test on Travis CI."
                    )
def test_coherence_s1_scenes(s1_slc_master, s1_slc_slave, some_bounds_slc):
    filelist = [s1_slc_master, s1_slc_slave]

    with TemporaryDirectory(dir=os.getcwd()) as temp, \
            TemporaryDirectory(dir=os.getcwd()) as temp_2:
        s1_scenes = S1Scenes(filelist,
                             processing_dir=temp,
                             ard_type=None,
                             cleanup=False
                             )
        test_subset = box(some_bounds_slc[0],
                          some_bounds_slc[1],
                          some_bounds_slc[2],
                          some_bounds_slc[3]
                          ).wkt
        s1_scenes.create_coherence(
            processing_dir=temp,
            temp_dir=temp_2,
            timeliness='14days',
            subset=test_subset,
        )