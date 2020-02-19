import os
import logging
import geopandas as gpd

from shapely.geometry import box

from ost.helpers import scihub, vector as vec

logger = logging.getLogger(__name__)


def get_bursts_by_polygon(master_annotation, out_poly=None):
    master_bursts = master_annotation

    bursts_dict = {'IW1': [], 'IW2': [], 'IW3': []}
    for subswath, nr, id, b in zip(
            master_bursts['SwathID'],
            master_bursts['BurstNr'],
            master_bursts['AnxTime'],
            master_bursts['geometry']
    ):
        # Return all burst combinations if out poly is None
        if out_poly is None:
            if (nr, id) not in bursts_dict[subswath]:
                b_bounds = b.bounds
                burst_buffer = abs(b_bounds[2]-b_bounds[0])/75
                burst_bbox = box(
                    b_bounds[0], b_bounds[1], b_bounds[2], b_bounds[3]
                ).buffer(burst_buffer).envelope
                bursts_dict[subswath].append((nr, id, burst_bbox))
        elif b.intersects(out_poly):
            if (nr, id) not in bursts_dict[subswath]:
                b_bounds = b.bounds
                burst_buffer = abs(out_poly.bounds[2]-out_poly.bounds[0])/75
                burst_bbox = box(
                    b_bounds[0], b_bounds[1], b_bounds[2], b_bounds[3]
                ).buffer(burst_buffer).envelope
                bursts_dict[subswath].append((nr, id, burst_bbox))
    return bursts_dict


def get_bursts_pairs(master_annotation, slave_annotation, out_poly=None):
    master_bursts = master_annotation
    slave_bursts = slave_annotation

    bursts_dict = {'IW1': [], 'IW2': [], 'IW3': []}
    for subswath, nr, id, b in zip(
            master_bursts['SwathID'],
            master_bursts['BurstNr'],
            master_bursts['AnxTime'],
            master_bursts['geometry']
    ):
        for sl_subswath, sl_nr, sl_id, sl_b in zip(
                slave_bursts['SwathID'],
                slave_bursts['BurstNr'],
                slave_bursts['AnxTime'],
                slave_bursts['geometry']
        ):
            # Return all burst combinations if out poly is None
            if out_poly is None and b.intersects(sl_b):
                if subswath == sl_subswath and \
                        (nr, id, sl_nr, sl_id) not in bursts_dict[subswath]:
                    b_bounds = b.union(sl_b).bounds
                    burst_buffer = abs(b_bounds[2]-b_bounds[0])/75
                    burst_bbox = box(
                        b_bounds[0], b_bounds[1], b_bounds[2], b_bounds[3]
                    ).buffer(burst_buffer).envelope
                    bursts_dict[subswath].append(
                        (nr, id, sl_nr, sl_id, burst_bbox)
                    )
            elif b.intersects(sl_b) \
                    and b.intersects(out_poly) and sl_b.intersects(out_poly):
                if subswath == sl_subswath and \
                        (nr, id, sl_nr, sl_id) not in bursts_dict[subswath]:
                    b_bounds = b.union(sl_b).bounds
                    burst_buffer = abs(out_poly.bounds[2]-out_poly.bounds[0])/75
                    burst_bbox = box(
                        b_bounds[0], b_bounds[1], b_bounds[2], b_bounds[3]
                    ).buffer(burst_buffer).envelope
                    bursts_dict[subswath].append(
                        (nr, id, sl_nr, sl_id, burst_bbox)
                    )
    return bursts_dict


def burst_inventory(inventory_df,
                    outfile,
                    download_dir=os.getenv('HOME'),
                    data_mount='/eodata',
                    uname=None, pword=None
                    ):
    '''Creates a Burst GeoDataFrame from an OST inventory file

    Args:

    Returns:


    '''
    # create column names for empty data frame
    from ost.s1.s1scene import Sentinel1Scene as S1Scene
    column_names = ['SceneID', 'Track', 'Direction', 'Date', 'SwathID',
                    'AnxTime', 'BurstNr', 'geometry']

    # crs for empty dataframe
    crs = {'init': 'epsg:4326', 'no_defs': True}
    # create empty dataframe
    gdf_full = gpd.GeoDataFrame(columns=column_names, crs=crs)
    # uname, pword = scihub.askScihubCreds()

    for scene_id in inventory_df.identifier:
        # read into S1Scene class
        scene = S1Scene(scene_id)

        logger.debug('INFO: Getting burst info from {}.'.format(scene.scene_id))

        # get orbit direction
        orbit_direction = inventory_df[
            inventory_df.identifier == scene_id].orbitdirection.values[0]

        filepath = scene.get_path(download_dir, data_mount)
        if not filepath:
            logger.debug('INFO: Retrieving burst info from scihub'
                         '(need to download xml files)')
            if not uname and not pword:
                uname, pword = scihub.ask_credentials()

            opener = scihub.connect(uname=uname, pword=pword)
            if scene.scihub_online_status(opener) is False:
                logger.debug('INFO: Product needs to be online'
                             'to create a burst database.')
                logger.debug('INFO: Download the product first and '
                             'do the burst list from the local data.')
            else:
                single_gdf = scene._scihub_annotation_get(uname, pword)
        elif filepath[-4:] == '.zip':
            single_gdf = scene._zip_annotation_get(download_dir, data_mount)
        elif filepath[-5:] == '.SAFE':
            single_gdf = scene._safe_annotation_get(download_dir, data_mount)

        # add orbit direction
        single_gdf['Direction'] = orbit_direction
        # append
        gdf_full = gdf_full.append(single_gdf)

    gdf_full = gdf_full.reset_index(drop=True)
    for i in gdf_full['AnxTime'].unique():

        # get similar burst times
        idx = gdf_full.index[(gdf_full.AnxTime >= i - 1) &
                             (gdf_full.AnxTime <= i + 1) &
                             (gdf_full.AnxTime != i)].unique().values

        # reset all to first value
        for j in idx:
            gdf_full.at[j, 'AnxTime'] = i

    # create the acrual burst id
    gdf_full['bid'] = gdf_full.Direction.str[0] + \
                      gdf_full.Track.astype(str) + '_'+ \
                      gdf_full.SwathID.astype(str) + '_'+ \
                      gdf_full.AnxTime.astype(str)

    # save file to out
    gdf_full['Date'] = gdf_full['Date'].astype(str)
    gdf_full['BurstNr'] = gdf_full['BurstNr'].astype(str)
    gdf_full['AnxTime'] = gdf_full['AnxTime'].astype(str)
    gdf_full['Track'] = gdf_full['Track'].astype(str)
    gdf_full.to_file(outfile)

    return gdf_full


def refine_burst_inventory(aoi, burst_gdf, outfile):
    '''Creates a Burst GeoDataFrame from an OST inventory file

    Args:

    Returns:


    '''

    # turn aoi into a geodataframe
    aoi_gdf = vec.wkt_to_gdf(aoi)

    # get columns of input dataframe for later return function
    cols = burst_gdf.columns

    # 1) get only intersecting footlogger.debugs
    # (double, since we do this before)
    burst_gdf = gpd.sjoin(burst_gdf, aoi_gdf, how='inner', op='intersects')

    # if aoi  gdf has an id field we need to rename the changed id_left field
    if 'id_left'in burst_gdf.columns.tolist():
        # rename id_left to id
        burst_gdf.columns = (['id'if x == 'id_left'else x
                              for x in burst_gdf.columns.tolist()])

    # save file to out
    burst_gdf['Date'] = burst_gdf['Date'].astype(str)
    burst_gdf['BurstNr'] = burst_gdf['BurstNr'].astype(str)
    burst_gdf['AnxTime'] = burst_gdf['AnxTime'].astype(str)
    burst_gdf['Track'] = burst_gdf['Track'].astype(str)
    burst_gdf.to_file(outfile)
    return burst_gdf[cols]
