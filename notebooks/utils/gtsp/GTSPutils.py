import os
import pandas as pd
import numpy as np
import ast
from julia.api import Julia
import geopandas as gpd
import matplotlib.pyplot as plt
import json

from dotenv import load_dotenv

from utils.gpsconversion.conversionapi import convertWSG84toMN95

load_dotenv()

DATA_PATH = os.environ['DATA_PATH']

def createDistanceMatrix(api_data, use_transport, optimize):

    df = pd.DataFrame(np.zeros((len(api_data.keys()), len(api_data.keys()))))

    for i, (key, val) in enumerate(api_data.items()):

        df.loc[i, i] = 999999
        df.loc[i, np.where(df.loc[i]!=999999)[0]] = val


    df.replace({'ZERO_RESULTS': 999999}, inplace=True)

    # GM TRANSPORT CORRECTIONS
    ###########################################################################

    if use_transport:

        if optimize == 'time':
        
            # ST IMIER
            df.loc[0, 1] = 320
            df.loc[1, 0] = 300

            # LENZERHEIDE TGANTIENI-LIFT
            df.loc[2, 3] = 240
            df.loc[3, 2] = 300

            # LENZERHEIDE TGANTIENI-SPORZ
            df.loc[2, 4] = 90
            df.loc[4, 2] = 500

            # LENZERHEIDE LIFT-SPORZ
            df.loc[3, 4] = 480
            df.loc[4, 3] = 120

            # BECKENRIED-GERSAU
            df.loc[5, 6] = 1200
            df.loc[6, 5] = 1200

            # GOSCHENEN-AIROLO
            df.loc[7, 34] = 900
            df.loc[34, 7] = 4500

            # SANETSCH-GSTEIG
            df.loc[8, 37] = 900
            df.loc[37, 8] = 16200

        elif optimize == 'distance':

            pass

    return df

def createDummyNode(df, start, end, checkpoints):

    df[len(df)] = 999999
    df.loc[len(df)] = 999999

    ind_start = [x==start for x in checkpoints.keys()]
    ind_start = np.where(ind_start)[0][0]

    ind_end = [x==end for x in checkpoints.keys()]
    ind_end = np.where(ind_end)[0][0]

    # 0 for dummy-dummy
    df.loc[len(df)-1, len(df)-1] = 0

    # 0 for start-end and end-start
    df.loc[ind_start, len(df)-1] = 0
    df.loc[ind_end, len(df)-1] = 0
    df.loc[len(df)-1, ind_start] = 0
    df.loc[len(df)-1, ind_end] = 0

    df = df.astype('int')

    return df

def createClusters(checkpoints, cluster_mapping, data_version):

    such_2022 = pd.DataFrame([x for x in checkpoints.values()])
    
    # DUMMY NODE
    such_2022 = such_2022.append([(45, 6.9)])
    such_2022.reset_index(drop=True, inplace=True)

    c = pd.read_csv(os.path.join(DATA_PATH, 'DIST_MATRIX', f'clusters_{data_version}.csv'), header=None)

    such_2022['cluster'] = c

    ######### LOAD CLUSTER MAPPING HERE IF USING FCT
    
    such_2022.replace(cluster_mapping, inplace=True)
    #such_2022.reset_index(drop=True, inplace=True)
    such_2022 = such_2022.rename(columns={0: 'latitude', 1: 'longitude'})

    clusters = such_2022.groupby(by='cluster')
    clusters = [(cluster[0], [x+1 for x in list(cluster[1].index)]) for cluster in clusters]

    return such_2022, clusters

def createGTSPfile(df, clusters):

    try:
        os.remove(os.path.join(DATA_PATH, 'GTSP_FILES', 'test_2022.gtsp'))
    except FileNotFoundError:
        pass

    dim = len(df)
    sets = len(clusters)

    # WRITE PARAMS AND WEIGHTS TO FILE
    params = f'NAME: such_test_3 \n\
    TYPE: AGTSP \n\
    COMMENT: test \n\
    DIMENSION: {dim} \n\
    GTSP_SETS: {sets} \n\
    EDGE_WEIGHT_TYPE: EXPLICIT \n\
    EDGE_WEIGHT_FORMAT: FULL_MATRIX \n\
    EDGE_WEIGHT_SECTION \n\
    {df.to_string(header=False, index=False)} \n\
    GTSP_SET_SECTION: \n'

    with open(os.path.join(DATA_PATH, 'GTSP_FILES', 'test_2022.gtsp'), 'a') as gtsp_file:
        gtsp_file.write(params)

    # WRITE SET SECTION
    outfile = open(os.path.join(DATA_PATH, 'GTSP_FILES', 'test_2022.gtsp'), 'a')

    for cluster in clusters:
        out = str(cluster[0]) + ' ' + ' '.join([str(x) for x in cluster[1]]) + ' -1' + '\n'
        outfile.write(out)

    outfile.close()

    # WRITE EOF
    with open(os.path.join(DATA_PATH, 'GTSP_FILES', 'test_2022.gtsp'), 'a') as gtsp_file:
        gtsp_file.write('EOF')

def loadOptimalTour(tour_filename):

    with open(os.path.join(DATA_PATH, 'TOUR_FILES', tour_filename)) as f:
        file = f.readlines()

    tour = ast.literal_eval(file[-1].split(": ")[-1])
    tour = [x-1 for x in tour]

    tour_cost = file[6].split(': ')[-1].strip()

    return tour, tour_cost

def reOrderTour(such_2022, tour, cluster_mapping):

    df_tour = such_2022.loc[tour].replace({v: k for k, v in cluster_mapping.items()}).iloc[::-1]

    df_1 = df_tour.loc[df_tour[df_tour.cluster == 'DUMMY'].index[0]:].iloc[1:]
    df_2 = df_tour.loc[:df_tour[df_tour.cluster == 'DUMMY'].index[0]].iloc[:-1]
    df_tour = pd.concat([df_1, df_2])

    #df_tour = df_tour.rename(columns={0: 'latitude', 1: 'longitude'})

    #such_2022 = such_2022.rename(columns={0: 'latitude', 1: 'longitude'})

    tour_coord_x, tour_coord_y = convertWSG84toMN95(df_tour)

    return tour_coord_x, tour_coord_y, df_tour

def evaluateTour(start, end, use_transport, optimize, data_version, save_plot):

    reports = []
    reports_r = []
    tour_costs = []

    # LOAD CANTONAL BORDER DATA
    ###########################################################################

    df_cantons = gpd.read_file(os.path.join(DATA_PATH, 'SHP_FILES', 'swissBOUNDARIES3D_1_3_TLM_KANTONSGEBIET.shp'))
    cantons = df_cantons['NAME'].unique()

    # DEFINE CP COORDS IN MN95 FORMAT
    ###########################################################################

    cp_coord_x = [2588950.069, 2677691.166, 2680954.976, 2688009.628, 2566249.259, 2759952.968, 2600422.411]
    cp_coord_y = [1134641.528, 1202811.284, 1205098.173, 1168980.565, 1223196.312, 1176579.977, 1199574.686]

    # LOAD CHECKPOINT DATA
    ###########################################################################

    with open(os.path.join(DATA_PATH, 'CHECKPOINTS', 'mandatory_checkpoints.json'), 'r') as file:
        mandatory_checkpoints = json.load(file)
    
    mandatory_checkpoints = {k: ast.literal_eval(v) for k, v in mandatory_checkpoints.items()}

    with open(os.path.join(DATA_PATH, 'DIST_MATRIX', f'checkpoints_{data_version}.json'), 'r') as file:
        target_coords = json.load(file)
    
    target_coords= {k: tuple(v) for k, v in target_coords.items()}

    checkpoints = mandatory_checkpoints.copy()
    checkpoints.update(target_coords)

    # LOAD CLUSTER MAPPING DATA
    ###########################################################################

    with open(os.path.join(DATA_PATH, 'CHECKPOINTS', 'cluster_mapping.json'), 'r') as file:
        cluster_mapping = json.load(file)

    # LOAD GM API DATA AND CREATE DISTANCE MATRIX
    ###########################################################################

    if optimize == 'time':

        with open(os.path.join(DATA_PATH, 'DIST_MATRIX', f'api_data_time_{data_version}.json'), 'r') as file:
            api_data = json.load(file)

        df = createDistanceMatrix(api_data, use_transport=use_transport, optimize=optimize)

        with open(os.path.join(DATA_PATH, 'DIST_MATRIX', f'api_data_dist_{data_version}.json'), 'r') as file:
            api_data_distance = json.load(file)

        df_distance = createDistanceMatrix(api_data_distance, use_transport=use_transport, optimize='distance')

    elif optimize == 'distance':

        with open(os.path.join(DATA_PATH, 'DIST_MATRIX', f'api_data_dist_{data_version}.json'), 'r') as file:
            api_data = json.load(file)

        df = createDistanceMatrix(api_data, use_transport=use_transport, optimize=optimize)

        df_distance = df.copy()
    
    # CREATE DUMMY NODE
    ###########################################################################
    
    df = createDummyNode(df, start, end, checkpoints)
    
    # ADD CLUSTER
    ###########################################################################
    
    such_2022, clusters = createClusters(checkpoints, cluster_mapping, data_version)
    
    # CREATE GTSP FILE
    ###########################################################################
    
    createGTSPfile(df, clusters)
    
    # RUN JULIA SOLVER
    ###########################################################################

    #!/Applications/Julia-1.7.app/Contents/Resources/julia/bin/julia ../scripts/gtsp_solver.jl
    
    j = Julia(compiled_modules=False)
    j.include("../scripts/gtsp_solver.jl")

    # LOAD OPTIMAL TOUR
    ###########################################################################
    
    tour, tour_cost = loadOptimalTour('tour_test_2022.txt')
    
    tour_costs.append(tour_cost)

    # RE-ORDER OPTIMAL TOUR
    ###########################################################################

    tour_coord_x, tour_coord_y, df_tour = reOrderTour(such_2022, tour, cluster_mapping)

    # PLOT OPTIMAL TOUR
    ###########################################################################
    
    fig, ax = plt.subplots(figsize=(25,13))

    for canton in cantons:
        x_c, y_c = df_cantons[df_cantons['NAME']==canton]['geometry'].iloc[0].exterior.coords.xy
        x_c = list(x_c)[:-1]
        y_c = list(y_c)[:-1]
        ax.plot(x_c, y_c)

    ax.plot(cp_coord_x, cp_coord_y, 'r*', markersize=15)

    ax.plot(tour_coord_x, tour_coord_y, '-o', markersize=15)

    for i, (x, y) in enumerate(zip(tour_coord_x, tour_coord_y)):

        ax.text(x, y, i, fontsize='large')

    ax.text(2830000, 1300000, f'cost: {tour_cost}', fontsize='large')
    ax.set_title(f'start: {start} / end: {end}')

    if save_plot:
        
        plt.savefig(os.path.join(DATA_PATH, 'TOUR_VIZ', '2022', f'{start}_{end}_{tour_cost}.png'))
        
    plt.show()
    
    # CREATE REPORTS
    ###########################################################################
                    
    reports.append(getRouteReport(df_tour, df_distance, checkpoints, mandatory_checkpoints, cp_opening_times, avg_speed=26, reverse=False))
    reports_r.append(getRouteReport(df_tour, df_distance, checkpoints, mandatory_checkpoints, cp_opening_times, avg_speed=26, reverse=True))

    return reports, reports_r


